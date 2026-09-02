import argparse
from copy import deepcopy
import html
import json
import time
import logging
import os
import tempfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from astro.chart import calculate_chart
from astro.panchanga import calculate_panchanga
from astro.south_chart import generate_north_indian_svg, generate_south_indian_svg
from astro.text_builder import (
    build_telegram_compact_panchanga_text,
    build_telegram_panchanga_text,
    format_day_segment_line,
)
from astro.text_catalog import normalize_catalog_text


DEFAULT_CITY = "Москва"
DEFAULT_LATITUDE = 55.7558
DEFAULT_LONGITUDE = 37.6173
DEFAULT_TIMEZONE = 3.0
DEFAULT_CALC_HOUR = 6
DEFAULT_CALC_MINUTE = 0
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_SAFE_MESSAGE_LIMIT = min(3800, TELEGRAM_MESSAGE_LIMIT - 100)
TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_MAX_ATTEMPTS = 5
TELEGRAM_TIMEOUT = (10, 45)
TELEGRAM_CHUNK_PAUSE_SECONDS = 1.2
FULL_PANCHANGA_URL = "http://127.0.0.1:8000/full/html"
PUBLIC_PANCHANGA_URL = "https://vedascope.ru/panchanga"
VK_API_BASE = "https://api.vk.com/method"
VK_DEFAULT_API_VERSION = "5.199"

LOGGER = logging.getLogger("daily_post")


def load_env_file(path=".env"):
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_today_moscow():
    return datetime.now(MOSCOW_TZ).date()


def _segment_boundary(segment, key, timezone):
    value = segment.get(key)
    if not value:
        return None
    try:
        boundary = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if boundary.tzinfo is None:
        boundary = boundary.replace(tzinfo=timezone)
    return boundary


def filter_segments_for_publication(segments, publish_at):
    """Return segments relevant at/after publish_at without changing astronomy."""
    filtered = []
    for segment in segments or []:
        ends_at = _segment_boundary(segment, "ends_at", publish_at.tzinfo)
        if ends_at is not None and ends_at <= publish_at:
            continue
        item = deepcopy(segment)
        item["publication_window"] = True
        item["is_current_at_publish_time"] = not filtered
        filtered.append(item)
    return filtered


def prepare_daily_publication_data(panchanga, hour, minute):
    """Build one filtered data set shared by Telegram and VK renderers."""
    prepared = deepcopy(panchanga)
    timezone_name = ((prepared.get("location") or {}).get("timezone_name") or "Europe/Moscow")
    try:
        timezone = ZoneInfo(timezone_name)
    except (KeyError, ValueError):
        timezone = MOSCOW_TZ
    target_date = datetime.strptime(prepared["date"], "%Y-%m-%d")
    publish_at = target_date.replace(hour=hour, minute=minute, tzinfo=timezone)
    day_dynamics = prepared.setdefault("day_dynamics", {})
    day_dynamics["publish_time"] = publish_at.strftime("%H:%M")
    day_dynamics["publication_window_start"] = publish_at.isoformat(timespec="minutes")

    filtered_by_kind = {}
    for kind in ("tithi", "nakshatra"):
        key = f"{kind}_segments"
        filtered = filter_segments_for_publication(day_dynamics.get(key), publish_at)
        day_dynamics[key] = filtered
        day_dynamics[f"dominant_{kind}"] = filtered[0] if filtered else None
        filtered_by_kind[kind] = filtered

    transitions = []
    for transition in day_dynamics.get("transitions") or []:
        transition_at = _segment_boundary(transition, "at", timezone)
        if transition_at is None or transition_at > publish_at:
            transitions.append(transition)
    day_dynamics["transitions"] = transitions

    prepared.setdefault("tithi", {})["day_periods"] = filtered_by_kind["tithi"]
    prepared.setdefault("nakshatra", {})["day_periods"] = filtered_by_kind["nakshatra"]
    prepared["lunar_day_periods"] = {
        "tithi": filtered_by_kind["tithi"],
        "nakshatra": filtered_by_kind["nakshatra"],
    }
    return prepared


def build_chart_data(target_date, hour, minute):
    chart_data = calculate_chart(
        target_date.year,
        target_date.month,
        target_date.day,
        hour,
        minute,
        DEFAULT_TIMEZONE,
        DEFAULT_LATITUDE,
        DEFAULT_LONGITUDE,
    )
    chart_data["city"] = DEFAULT_CITY
    chart_data["latitude"] = DEFAULT_LATITUDE
    chart_data["longitude"] = DEFAULT_LONGITUDE
    return chart_data


def render_chart_png(svg, output_path):
    try:
        import cairosvg
    except ImportError as exc:
        raise RuntimeError(
            "PNG generation requires cairosvg. Install dependencies from requirements.txt."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            "PNG generation requires the native Cairo library. "
            "On Debian/Ubuntu install it with: sudo apt install libcairo2"
        ) from exc

    try:
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(output_path))
    except OSError as exc:
        raise RuntimeError(
            "PNG generation requires the native Cairo library. "
            "On Debian/Ubuntu install it with: sudo apt install libcairo2"
        ) from exc


def generate_chart_images(target_date, hour, minute, output_dir):
    chart_data = build_chart_data(target_date, hour, minute)
    images = {
        "south": output_dir / "panchanga_south.png",
        "north": output_dir / "panchanga_north.png",
    }

    render_chart_png(generate_south_indian_svg(chart_data), images["south"])
    render_chart_png(generate_north_indian_svg(chart_data), images["north"])

    for style, path in images.items():
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"{style} chart PNG was not created: {path}")

    return images


def escape_html(value):
    return html.escape(str(value), quote=True)


def format_lunar_periods(periods):
    if not periods:
        return escape_html("нет данных")

    return "\n".join(
        escape_html(format_day_segment_line(period.get("kind") or "tithi", period, periods))
        for period in periods
    )


def dynamic_segment_name(segment):
    return escape_html(
        segment.get("display")
        or segment.get("name")
        or segment.get("key")
        or segment.get("index")
        or "нет данных"
    )


def current_dynamic_segment(segments):
    return next((segment for segment in segments or [] if segment.get("is_current_at_publish_time")), None)


def format_publish_state(day_dynamics):
    if not day_dynamics:
        return ""

    time_label = escape_html(day_dynamics.get("publish_time", "06:00"))
    tithi = current_dynamic_segment(day_dynamics.get("tithi_segments"))
    nakshatra = current_dynamic_segment(day_dynamics.get("nakshatra_segments"))
    lines = [f"🕕 <b>На момент публикации ({time_label} MSK)</b>"]
    if tithi:
        lines.append(f"Титхи: <b>{dynamic_segment_name(tithi)}</b>")
    if nakshatra:
        lines.append(f"Накшатра: <b>{dynamic_segment_name(nakshatra)}</b>")
    return "\n".join(lines) if len(lines) > 1 else ""


def format_dynamic_transition_line(title, segments):
    if not segments:
        return ""
    kind = segments[0].get("kind") or ("nakshatra" if title == "Накшатра" else "tithi")
    parts = [escape_html(format_day_segment_line(kind, segment, segments)) for segment in segments]
    return f"{title}: " + "; ".join(parts)


def format_day_changes(day_dynamics):
    if not day_dynamics or not day_dynamics.get("transitions"):
        return ""

    lines = ["🔄 <b>Изменения в течение дня</b>"]
    tithi_line = format_dynamic_transition_line("Титхи", day_dynamics.get("tithi_segments"))
    nakshatra_line = format_dynamic_transition_line("Накшатра", day_dynamics.get("nakshatra_segments"))
    if tithi_line:
        lines.append(tithi_line)
    if nakshatra_line:
        lines.append(nakshatra_line)
    return "\n".join(lines)


def format_dynamic_recommendation(day_dynamics):
    summary = build_final_recommendation(day_dynamics)
    if not summary:
        return ""
    return f"<b>Итоговая рекомендация дня</b>\n{escape_html(summary)}"


def dominant_dynamic_data(day_dynamics, key, fallback):
    segment = (day_dynamics or {}).get(key) or {}
    return segment.get("data") or fallback


def dominant_dynamic_label(day_dynamics, key):
    segment = (day_dynamics or {}).get(key) or {}
    return dynamic_segment_name(segment) if segment else ""


def format_items(items):
    if not items:
        return escape_html("нет данных")

    return "\n".join(f"• {escape_html(normalize_catalog_text(item))}" for item in items)


def get_period(periods, name):
    if not periods:
        return "нет данных"

    period = periods.get(name)
    if not period:
        return "нет данных"

    return f"{period['start']} - {period['end']}"


def build_section(title, body):
    return f"{title}\n{body}".strip()


def append_section(sections, title, body):
    if body:
        sections.append(build_section(title, body))


def build_daily_text(panchanga):
    return build_telegram_panchanga_text(panchanga)

def build_compact_daily_text(panchanga):
    return build_telegram_compact_panchanga_text(panchanga)

def split_html_messages(text, limit=TELEGRAM_SAFE_MESSAGE_LIMIT):
    if len(text) <= limit:
        return [text]

    sections = text.split("\n\n")
    messages = []
    current = ""

    for section in sections:
        candidate = section if not current else f"{current}\n\n{section}"
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            messages.append(current)
            current = section
        else:
            if "<blockquote>" in section or "<a " in section or "</" in section:
                LOGGER.warning("Cannot safely split HTML section over Telegram limit")
                return None

            while len(section) > limit:
                split_at = section.rfind("\n", 0, limit)
                if split_at <= 0:
                    split_at = section.rfind(" ", 0, limit)
                if split_at <= 0:
                    LOGGER.warning("Cannot safely split plain section over Telegram limit")
                    return None
                messages.append(section[:split_at].strip())
                section = section[split_at:].strip()
            current = section

    if current:
        messages.append(current)

    return messages


def split_plain_messages(text, limit=TELEGRAM_SAFE_MESSAGE_LIMIT):
    text = collapse_blank_lines(text)
    if len(text) <= limit:
        return [text] if text else []

    messages = []
    current = ""
    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            messages.append(current)
            current = ""

        while len(paragraph) > limit:
            split_at = paragraph.rfind("\n", 0, limit)
            if split_at <= 0:
                split_at = paragraph.rfind(" ", 0, limit)
            if split_at <= 0:
                split_at = limit
            messages.append(paragraph[:split_at].strip())
            paragraph = paragraph[split_at:].strip()

        current = paragraph

    if current:
        messages.append(current)

    return messages


class TelegramApiError(RuntimeError):
    def __init__(self, method, status_code=None, description="", retry_after=None):
        self.method = method
        self.status_code = status_code
        self.description = description or ""
        self.retry_after = retry_after
        message = f"Telegram {method} failed"
        if status_code is not None:
            message += f": HTTP {status_code}"
        if self.description:
            message += f": {self.description}"
        super().__init__(message)


def telegram_retry_delay(attempt, retry_after=None):
    if retry_after:
        return max(float(retry_after), 1.0) + 1.0
    return min(60.0, 2 ** (attempt - 1) * 3.0)


def parse_telegram_response(response, method):
    try:
        payload = response.json()
    except ValueError as exc:
        description = response.text[:500]
        LOGGER.warning(
            "Telegram %s non-JSON response HTTP %s: %s",
            method,
            response.status_code,
            description,
        )
        raise TelegramApiError(method, response.status_code, description) from exc

    description = payload.get("description", "")
    parameters = payload.get("parameters") or {}
    retry_after = parameters.get("retry_after")

    if not response.ok or not payload.get("ok"):
        raise TelegramApiError(method, response.status_code, description, retry_after)

    LOGGER.info("Telegram %s ok HTTP %s", method, response.status_code)
    return payload


def should_retry_telegram_error(error):
    if error.retry_after:
        return True
    if error.status_code is None:
        return True
    return error.status_code == 429 or error.status_code >= 500


def sanitize_telegram_error(value, bot_token):
    text = str(value)
    if bot_token:
        text = text.replace(bot_token, "<redacted>")
    return text


def telegram_api_request(bot_token, method, data=None, files=None, timeout=TELEGRAM_TIMEOUT):
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/{method}"
    last_error = None

    for attempt in range(1, TELEGRAM_MAX_ATTEMPTS + 1):
        try:
            response = requests.post(url, data=data, files=files, timeout=timeout)
            payload = parse_telegram_response(response, method)
            if attempt > 1:
                LOGGER.info("Telegram %s succeeded on attempt %s/%s", method, attempt, TELEGRAM_MAX_ATTEMPTS)
            return payload
        except TelegramApiError as exc:
            last_error = exc
            LOGGER.warning(
                "Telegram %s attempt %s/%s failed: HTTP %s description=%s",
                method,
                attempt,
                TELEGRAM_MAX_ATTEMPTS,
                exc.status_code,
                exc.description or "no description",
            )
            if attempt >= TELEGRAM_MAX_ATTEMPTS or not should_retry_telegram_error(exc):
                raise
            delay = telegram_retry_delay(attempt, exc.retry_after)
        except requests.RequestException as exc:
            safe_error = sanitize_telegram_error(exc, bot_token)
            last_error = safe_error
            LOGGER.warning(
                "Telegram %s attempt %s/%s failed: %s",
                method,
                attempt,
                TELEGRAM_MAX_ATTEMPTS,
                safe_error,
            )
            if attempt >= TELEGRAM_MAX_ATTEMPTS:
                raise RuntimeError(
                    f"Telegram {method} failed after {TELEGRAM_MAX_ATTEMPTS} attempts: {safe_error}"
                ) from None
            delay = telegram_retry_delay(attempt)

        LOGGER.info("Telegram %s retrying in %.1f seconds", method, delay)
        time.sleep(delay)

    raise RuntimeError(f"Telegram {method} failed after {TELEGRAM_MAX_ATTEMPTS} attempts: {last_error}")


def send_media_group(bot_token, channel_id, images):
    media = [
        {
            "type": "photo",
            "media": "attach://south",
            "caption": "📅 Карта дня",
        },
        {
            "type": "photo",
            "media": "attach://north",
        },
    ]

    LOGGER.info("sendMediaGroup starting image_count=2")
    files = {
        "south": ("panchanga_south.png", images["south"].read_bytes(), "image/png"),
        "north": ("panchanga_north.png", images["north"].read_bytes(), "image/png"),
    }
    try:
        payload = telegram_api_request(
            bot_token,
            "sendMediaGroup",
            data={
                "chat_id": channel_id,
                "media": json.dumps(media, ensure_ascii=False),
            },
            files=files,
            timeout=TELEGRAM_TIMEOUT,
        )
    except Exception:
        LOGGER.exception("sendMediaGroup fail")
        raise

    LOGGER.info("sendMediaGroup ok image_count=2")
    return payload


def send_message(bot_token, channel_id, text, parse_mode="HTML"):
    data = {
        "chat_id": channel_id,
        "text": text,
        "disable_web_page_preview": "true",
    }
    if parse_mode:
        data["parse_mode"] = parse_mode

    return telegram_api_request(bot_token, "sendMessage", data=data, timeout=TELEGRAM_TIMEOUT)


def is_html_parse_error(error):
    description = error.description.lower()
    return error.status_code == 400 and (
        "parse" in description
        or "entity" in description
        or "tag" in description
        or "can't find end" in description
    )


def send_daily_text(bot_token, channel_id, text, compact_text):
    messages = split_html_messages(text)
    if messages is None:
        LOGGER.warning("Sending compact daily text because full HTML text could not be split safely")
        messages = split_html_messages(compact_text)
        if messages is None:
            LOGGER.warning("Compact HTML text could not be split safely; falling back to plain text")
            messages = split_plain_messages(telegram_html_to_plain_text(text))

    LOGGER.info("Daily text chunks: %s", len(messages))

    for index, message in enumerate(messages, start=1):
        try:
            send_message(bot_token, channel_id, message, parse_mode="HTML")
            LOGGER.info("sendMessage ok chunk %s/%s length=%s mode=HTML", index, len(messages), len(message))
        except TelegramApiError as exc:
            if not is_html_parse_error(exc):
                LOGGER.error(
                    "sendMessage fail chunk %s/%s length=%s mode=HTML: %s",
                    index,
                    len(messages),
                    len(message),
                    exc,
                )
                raise

            LOGGER.warning(
                "sendMessage chunk %s/%s failed because Telegram rejected HTML; retrying as plain text",
                index,
                len(messages),
            )
            plain_chunks = split_plain_messages(telegram_html_to_plain_text(message))
            for plain_index, plain_message in enumerate(plain_chunks, start=1):
                send_message(bot_token, channel_id, plain_message, parse_mode=None)
                LOGGER.info(
                    "sendMessage ok chunk %s/%s plain_part=%s/%s length=%s mode=plain",
                    index,
                    len(messages),
                    plain_index,
                    len(plain_chunks),
                    len(plain_message),
                )

        if index < len(messages):
            time.sleep(TELEGRAM_CHUNK_PAUSE_SECONDS)



class TelegramHtmlToTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.href_stack = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"style", "script"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "a":
            attrs_map = dict(attrs)
            self.href_stack.append(attrs_map.get("href", ""))
        elif tag == "br":
            self.parts.append("\n")
        elif tag in {"p", "div", "section", "blockquote"}:
            self.parts.append("\n\n")
        elif tag == "li":
            self.parts.append("\n• ")

    def handle_endtag(self, tag):
        if tag in {"style", "script"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "a" and self.href_stack:
            href = self.href_stack.pop()
            if href:
                self.parts.append(f" ({href})")
        elif tag in {"p", "div", "section", "blockquote", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        self.parts.append(data)

    def get_text(self):
        lines = [line.rstrip() for line in "".join(self.parts).splitlines()]
        return "\n".join(lines).strip()


def collapse_blank_lines(text):
    lines = [line.rstrip() for line in html.unescape(text).splitlines()]
    collapsed = []
    blank_seen = False

    for line in lines:
        if line.strip():
            collapsed.append(line)
            blank_seen = False
        elif not blank_seen:
            collapsed.append("")
            blank_seen = True

    return "\n".join(collapsed).strip()


def telegram_html_to_plain_text(text):
    parser = TelegramHtmlToTextParser()
    parser.feed(text)
    parser.close()
    return collapse_blank_lines(parser.get_text())


def telegram_html_to_vk_text(text):
    return telegram_html_to_plain_text(text)


def env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_vk_group_id(group_id):
    if not group_id:
        return None
    try:
        return abs(int(str(group_id).strip()))
    except ValueError as exc:
        raise RuntimeError(f"VK_GROUP_ID must be an integer, got {group_id!r}") from exc


def get_vk_config(force_enabled=False):
    return {
        "enabled": force_enabled or env_flag("VK_POST_ENABLED"),
        "access_token": os.getenv("VK_ACCESS_TOKEN", ""),
        "api_version": os.getenv("VK_API_VERSION", VK_DEFAULT_API_VERSION),
        "group_id": normalize_vk_group_id(os.getenv("VK_GROUP_ID")),
        "group_screen_name": (os.getenv("VK_GROUP_SCREEN_NAME") or "").strip().lstrip("@"),
    }


def vk_api_request(method, config, params=None, files=None, timeout=30):
    if not config.get("access_token"):
        raise RuntimeError("VK_ACCESS_TOKEN must be set to publish VK post")

    payload = dict(params or {})
    payload["access_token"] = config["access_token"]
    payload["v"] = config.get("api_version") or VK_DEFAULT_API_VERSION
    url = f"{VK_API_BASE}/{method}"

    try:
        response = requests.post(url, data=payload, files=files, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"VK {method} request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"VK {method} returned non-JSON response") from exc

    if data.get("error"):
        error = data["error"]
        code = error.get("error_code")
        message = error.get("error_msg", "unknown error")
        raise RuntimeError(f"VK {method} error {code}: {message}")

    return data.get("response")


def resolve_vk_group_id(config):
    group_id = config.get("group_id")
    if group_id:
        return group_id

    screen_name = config.get("group_screen_name")
    if not screen_name:
        raise RuntimeError("VK_GROUP_ID or VK_GROUP_SCREEN_NAME must be set to publish VK post")

    resolved = vk_api_request(
        "utils.resolveScreenName",
        config,
        {"screen_name": screen_name},
    )
    if not resolved or resolved.get("type") != "group" or not resolved.get("object_id"):
        raise RuntimeError(f"VK screen name {screen_name!r} did not resolve to a group")
    return normalize_vk_group_id(resolved["object_id"])


def upload_vk_wall_photo(config, group_id, image_path):
    upload_server = vk_api_request(
        "photos.getWallUploadServer",
        config,
        {"group_id": group_id},
    )
    upload_url = upload_server.get("upload_url")
    if not upload_url:
        raise RuntimeError("VK photos.getWallUploadServer did not return upload_url")

    with open(image_path, "rb") as image_file:
        try:
            upload_response = requests.post(
                upload_url,
                files={"photo": image_file},
                timeout=60,
            )
            upload_response.raise_for_status()
            upload_data = upload_response.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"VK photo upload failed for {image_path}: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"VK photo upload returned non-JSON response for {image_path}") from exc

    saved = vk_api_request(
        "photos.saveWallPhoto",
        config,
        {
            "group_id": group_id,
            "photo": upload_data.get("photo"),
            "server": upload_data.get("server"),
            "hash": upload_data.get("hash"),
        },
    )
    if not saved:
        raise RuntimeError(f"VK photos.saveWallPhoto returned empty response for {image_path}")

    photo = saved[0]
    owner_id = photo.get("owner_id")
    photo_id = photo.get("id")
    if owner_id is None or photo_id is None:
        raise RuntimeError(f"VK saved photo response missing owner_id/id for {image_path}")
    return f"photo{owner_id}_{photo_id}"


def publish_vk_post(config, text, images):
    group_id = resolve_vk_group_id(config)
    vk_text = telegram_html_to_vk_text(text)
    image_paths = [images["south"], images["north"]]
    try:
        attachments = [upload_vk_wall_photo(config, group_id, image_path) for image_path in image_paths]
    except RuntimeError as exc:
        # VK community tokens may publish to their own wall, but VK rejects
        # photos.getWallUploadServer for this authorization type (error 27).
        # Keep the daily publication working as a text-only post until a user
        # token with photo permissions is configured.
        error_text = str(exc)
        if "error 27" not in error_text or "Group authorization failed" not in error_text:
            raise
        LOGGER.warning(
            "VK community token cannot upload wall photos; publishing text-only post"
        )
        attachments = []

    params = {
        "owner_id": -group_id,
        "from_group": 1,
        "message": vk_text,
    }
    if attachments:
        params["attachments"] = ",".join(attachments)

    response = vk_api_request("wall.post", config, params)
    LOGGER.info("VK wall.post response: %s", response)
    return response


def log_vk_dry_run(config, text, images):
    vk_text = telegram_html_to_vk_text(text)
    group_id = config.get("group_id") or "resolve from VK_GROUP_SCREEN_NAME on send"
    LOGGER.info(
        "VK dry run: enabled=%s group_screen_name=%s group_id=%s text_length=%s image_count=%s api_calls=skipped",
        config.get("enabled"),
        config.get("group_screen_name") or "",
        group_id,
        len(vk_text),
        len(images or {}),
    )


def maybe_publish_vk(config, text, images, raise_on_failure=False):
    if not config.get("enabled"):
        LOGGER.info("VK posting disabled")
        return None

    try:
        result = publish_vk_post(config, text, images)
        LOGGER.info("VK post published")
        return result
    except Exception:
        LOGGER.exception("VK publication failed")
        if raise_on_failure:
            raise
        return None

def parse_args():
    parser = argparse.ArgumentParser(description="Publish daily Panchanga.")
    parser.add_argument("--dry-run", action="store_true", help="Generate content without sending it.")
    parser.add_argument("--date", help="Date in YYYY-MM-DD format. Defaults to today in Moscow.")
    parser.add_argument("--hour", type=int, default=int(os.getenv("PANCHANGA_HOUR", DEFAULT_CALC_HOUR)))
    parser.add_argument("--minute", type=int, default=int(os.getenv("PANCHANGA_MINUTE", DEFAULT_CALC_MINUTE)))
    parser.add_argument("--send-vk", action="store_true", help="Send VK post even if VK_POST_ENABLED is not set.")
    parser.add_argument("--vk-only", action="store_true", help="Send only VK post and skip Telegram publication.")
    return parser.parse_args()

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env_file()
    args = parse_args()
    dry_run = args.dry_run or env_flag("DRY_RUN")

    bot_token = os.getenv("BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID")
    vk_config = get_vk_config(force_enabled=args.send_vk or args.vk_only)
    target_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else get_today_moscow()
    )

    LOGGER.info(
        "Preparing daily Panchanga post for %s %02d:%02d MSK",
        target_date,
        args.hour,
        args.minute,
    )

    panchanga = calculate_panchanga(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
        latitude=DEFAULT_LATITUDE,
        longitude=DEFAULT_LONGITUDE,
        timezone=DEFAULT_TIMEZONE,
        hour=args.hour,
        minute=args.minute,
        timezone_name="Europe/Moscow",
    )
    publication_data = prepare_daily_publication_data(panchanga, args.hour, args.minute)
    text = build_daily_text(publication_data)
    compact_text = build_compact_daily_text(publication_data)
    LOGGER.info(
        "Generated daily text length: %s compact_text_length=%s",
        len(text),
        len(compact_text),
    )

    with tempfile.TemporaryDirectory(prefix="vedascope_daily_") as temp_dir:
        output_dir = Path(temp_dir)
        try:
            images = generate_chart_images(target_date, args.hour, args.minute, output_dir)
        except Exception:
            LOGGER.exception("Chart image generation failed")
            raise

        LOGGER.info("Generated south chart: %s (%s bytes)", images["south"], images["south"].stat().st_size)
        LOGGER.info("Generated north chart: %s (%s bytes)", images["north"], images["north"].stat().st_size)

        if dry_run:
            LOGGER.info("Dry run enabled; Telegram and VK sending skipped")
            LOGGER.info("Dry-run Telegram text:\n%s", text)
            LOGGER.info("Dry-run VK text:\n%s", telegram_html_to_vk_text(text))
            chunks = split_html_messages(text)
            if chunks is None:
                LOGGER.warning("Dry run: full text cannot be split safely; compact text would be used")
                chunks = split_html_messages(compact_text)
            if chunks is None:
                LOGGER.warning("Dry run: compact HTML text cannot be split safely; plain text would be used")
                chunks = split_plain_messages(telegram_html_to_plain_text(text))
            LOGGER.info("Daily text message count: %s", len(chunks or []))
            log_vk_dry_run(vk_config, text, images)
            return

        if args.vk_only:
            maybe_publish_vk(vk_config, text, images, raise_on_failure=True)
            return

        if not bot_token or not channel_id:
            raise RuntimeError("BOT_TOKEN and CHANNEL_ID must be set in environment or .env")

        telegram_error = None
        try:
            send_media_group(bot_token, channel_id, images)
            LOGGER.info("Chart album sent to %s", channel_id)
            send_daily_text(bot_token, channel_id, text, compact_text)
            LOGGER.info("Daily Panchanga text sent to %s", channel_id)
        except Exception as exc:
            telegram_error = exc
            LOGGER.exception("Telegram publication failed")

        maybe_publish_vk(vk_config, text, images, raise_on_failure=True)

        if telegram_error:
            raise RuntimeError("Telegram publication failed; VK publication was attempted") from telegram_error


if __name__ == "__main__":
    main()
