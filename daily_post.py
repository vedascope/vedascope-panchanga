import argparse
import html
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from astro.chart import calculate_chart
from astro.panchanga import calculate_panchanga
from astro.south_chart import generate_north_indian_svg, generate_south_indian_svg


DEFAULT_CITY = "Москва"
DEFAULT_LATITUDE = 55.7558
DEFAULT_LONGITUDE = 37.6173
DEFAULT_TIMEZONE = 3.0
DEFAULT_CALC_HOUR = 6
DEFAULT_CALC_MINUTE = 0
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_SAFE_MESSAGE_LIMIT = min(3800, TELEGRAM_MESSAGE_LIMIT - 100)
FULL_PANCHANGA_URL = "https://panchanga.vedascope.ru/full/html"

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

    lines = []
    for period in periods:
        name = period.get("display") or period.get("name")
        safe_name = escape_html(name)
        start = escape_html(period["starts_at"])
        end = escape_html(period["ends_at"])
        if len(periods) == 1:
            lines.append(f"{safe_name} до {end}")
        elif period.get("ends_at_time"):
            lines.append(f"{safe_name} до {end}")
        else:
            lines.append(f"{safe_name} с {start}")
    return "\n".join(lines)


def format_items(items):
    if not items:
        return escape_html("нет данных")

    return "\n".join(f"• {escape_html(item)}" for item in items)


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
    date_text = datetime.strptime(panchanga["date"], "%Y-%m-%d").strftime("%d.%m.%Y")
    vara = panchanga["vara"]
    tithi = panchanga["tithi"]
    nakshatra = panchanga["nakshatra"]
    vedic_yoga = panchanga.get("vedic_yoga", {})
    karana = panchanga.get("karana", {})
    muhurta = panchanga.get("muhurta") or {}
    moon = panchanga.get("moon", {})
    moon_yogas = panchanga.get("yogas") or []

    vara_data = vara.get("data") or {}
    tithi_data = tithi.get("data") or {}
    nakshatra_data = nakshatra.get("data") or {}
    moon_data = moon.get("data") or {}

    sections = [
        f"🌞 <b>Панчанга на {escape_html(date_text)}</b>",
    ]

    append_section(
        sections,
        "🌙 <b>Титхи</b>",
        "\n".join(
            [
                format_lunar_periods(tithi.get("day_periods")),
                "",
                f"<b>{escape_html(tithi_data.get('display', ''))}</b>",
                escape_html(tithi_data.get("summary", "")),
                escape_html(tithi_data.get("description", "")),
            ]
        ).strip(),
    )

    nakshatra_types = ", ".join(nakshatra_data.get("types", []))
    append_section(
        sections,
        "⭐ <b>Накшатра</b>",
        "\n".join(
            [
                format_lunar_periods(nakshatra.get("day_periods")),
                "",
                f"<b>{escape_html(nakshatra_data.get('ru', ''))}</b>"
                + (f" ({escape_html(nakshatra_types)})" if nakshatra_types else ""),
                escape_html(nakshatra_data.get("summary", "")),
                escape_html(nakshatra_data.get("description", "")),
            ]
        ).strip(),
    )

    append_section(
        sections,
        "🧘 <b>Йога</b>",
        escape_html(vedic_yoga.get("ru", "нет данных")),
    )
    append_section(
        sections,
        "🔱 <b>Карана</b>",
        escape_html(karana.get("ru", "нет данных")),
    )

    sun_moon_lines = []
    if muhurta.get("sunrise"):
        sun_moon_lines.append(f"🌅 <b>Восход Солнца:</b> {escape_html(muhurta['sunrise'])}")
    if muhurta.get("sunset"):
        sun_moon_lines.append(f"🌇 <b>Закат Солнца:</b> {escape_html(muhurta['sunset'])}")
    if muhurta.get("moonrise"):
        sun_moon_lines.append(f"🌙 <b>Восход Луны:</b> {escape_html(muhurta['moonrise'])}")
    if muhurta.get("moonset"):
        sun_moon_lines.append(f"🌘 <b>Закат Луны:</b> {escape_html(muhurta['moonset'])}")
    if sun_moon_lines:
        sections.append("\n".join(sun_moon_lines))

    sections.append(
        "\n".join(
            [
                "❗ <b>Важные периоды дня</b>",
                "",
                "<blockquote>",
                f"Раху-кала: {escape_html(get_period(muhurta, 'rahu_kalam'))}",
                f"Ямаганда: {escape_html(get_period(muhurta, 'yamaganda'))}",
                f"Гулика: {escape_html(get_period(muhurta, 'gulika'))}",
                f"Абхиджит-мухурта: {escape_html(get_period(muhurta, 'abhijit_muhurta'))}",
                "</blockquote>",
            ]
        )
    )

    recommendation_parts = []
    if vara_data.get("description"):
        recommendation_parts.append(
            f"<b>{escape_html(vara_data.get('ru', 'Вара'))}</b>\n"
            f"{escape_html(vara_data['description'])}"
        )
    if moon_data.get("summary") or moon_data.get("description"):
        recommendation_parts.append(
            "\n".join(
                [
                    f"<b>Луна в {escape_html(moon_data.get('ru', ''))}</b>",
                    escape_html(moon_data.get("summary", "")),
                    escape_html(moon_data.get("description", "")),
                ]
            ).strip()
        )
    if tithi_data.get("rikta"):
        recommendation_parts.append(
            "\n".join(
                [
                    "<b>Рикта-титхи — пустые руки</b>",
                    escape_html(
                        "Эти лунные сутки лучше использовать для завершения, очищения "
                        "и отказа от лишнего. Важные долгосрочные начинания и крупные "
                        "покупки лучше перенести."
                    ),
                ]
            )
        )
    gandanta = nakshatra.get("gandanta") or {}
    if gandanta.get("active") and gandanta.get("description"):
        recommendation_parts.append(
            f"<b>Ганданта Луны</b>\n{escape_html(gandanta['description'])}"
        )
    if tithi_data.get("favorable"):
        recommendation_parts.append(
            f"<b>Благоприятно по титхи</b>\n{format_items(tithi_data.get('favorable'))}"
        )
    if tithi_data.get("unfavorable"):
        recommendation_parts.append(
            f"<b>Не рекомендуется по титхи</b>\n{format_items(tithi_data.get('unfavorable'))}"
        )
    if nakshatra_data.get("favorable"):
        recommendation_parts.append(
            f"<b>Благоприятно по накшатре</b>\n{format_items(nakshatra_data.get('favorable'))}"
        )
    if nakshatra_data.get("unfavorable"):
        recommendation_parts.append(
            f"<b>Не рекомендуется по накшатре</b>\n{format_items(nakshatra_data.get('unfavorable'))}"
        )
    if moon_yogas:
        yoga_lines = []
        for yoga in moon_yogas:
            yoga_lines.append(
                f"<b>{escape_html(yoga.get('title', 'Йога'))}</b>\n"
                f"{escape_html(yoga.get('description', ''))}"
            )
        recommendation_parts.append("\n\n".join(yoga_lines))

    if recommendation_parts:
        append_section(
            sections,
            "✨ <b>Рекомендации дня</b>",
            "\n\n".join(recommendation_parts),
        )

    sections.append(
        f'🔗 <a href="{escape_html(FULL_PANCHANGA_URL)}">Открыть Панчангу в браузере</a>'
    )

    return "\n\n".join(section for section in sections if section).strip()


def build_compact_daily_text(panchanga):
    date_text = datetime.strptime(panchanga["date"], "%Y-%m-%d").strftime("%d.%m.%Y")
    tithi = panchanga["tithi"]
    nakshatra = panchanga["nakshatra"]
    vedic_yoga = panchanga.get("vedic_yoga", {})
    karana = panchanga.get("karana", {})
    muhurta = panchanga.get("muhurta") or {}

    return "\n\n".join(
        [
            f"🌞 <b>Панчанга на {escape_html(date_text)}</b>",
            f"🌙 <b>Титхи</b>\n{format_lunar_periods(tithi.get('day_periods'))}",
            f"⭐ <b>Накшатра</b>\n{format_lunar_periods(nakshatra.get('day_periods'))}",
            f"🧘 <b>Йога:</b> {escape_html(vedic_yoga.get('ru', 'нет данных'))}",
            f"🔱 <b>Карана:</b> {escape_html(karana.get('ru', 'нет данных'))}",
            "\n".join(
                [
                    "❗ <b>Важные периоды дня</b>",
                    "",
                    "<blockquote>",
                    f"Раху-кала: {escape_html(get_period(muhurta, 'rahu_kalam'))}",
                    f"Ямаганда: {escape_html(get_period(muhurta, 'yamaganda'))}",
                    f"Гулика: {escape_html(get_period(muhurta, 'gulika'))}",
                    f"Абхиджит-мухурта: {escape_html(get_period(muhurta, 'abhijit_muhurta'))}",
                    "</blockquote>",
                ]
            ),
            f'🔗 <a href="{escape_html(FULL_PANCHANGA_URL)}">Открыть Панчангу в браузере</a>',
        ]
    )


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


def check_telegram_response(response, method):
    try:
        payload = response.json()
    except ValueError as exc:
        LOGGER.error("Telegram %s non-JSON response: %s", method, response.text)
        raise RuntimeError(
            f"Telegram {method} returned non-JSON response: {response.text}"
        ) from exc

    if not response.ok:
        LOGGER.error("Telegram %s HTTP error response: %s", method, response.text)
        raise RuntimeError(
            f"Telegram {method} failed: HTTP {response.status_code}: {response.text}"
        )

    if not payload.get("ok"):
        LOGGER.error("Telegram %s ok=false response: %s", method, response.text)
        raise RuntimeError(f"Telegram {method} failed: {response.text}")

    LOGGER.info("Telegram %s response: %s", method, response.text)
    return payload


def send_media_group(bot_token, channel_id, images):
    url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"
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

    with open(images["south"], "rb") as south, open(images["north"], "rb") as north:
        try:
            response = requests.post(
                url,
                data={
                    "chat_id": channel_id,
                    "media": json.dumps(media, ensure_ascii=False),
                },
                files={
                    "south": south,
                    "north": north,
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Telegram sendMediaGroup failed: {exc}") from exc

    return check_telegram_response(response, "sendMediaGroup")


def send_message(bot_token, channel_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = requests.post(
            url,
            data={
                "chat_id": channel_id,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Telegram sendMessage failed: {exc}") from exc

    return check_telegram_response(response, "sendMessage")


def send_daily_text(bot_token, channel_id, text, compact_text):
    messages = split_html_messages(text)
    if messages is None:
        LOGGER.warning("Sending compact daily text because full HTML text could not be split safely")
        messages = split_html_messages(compact_text)
        if messages is None:
            raise RuntimeError("Compact daily text could not be split safely")

    for message in messages:
        send_message(bot_token, channel_id, message)


def parse_args():
    parser = argparse.ArgumentParser(description="Publish daily Panchanga to Telegram.")
    parser.add_argument("--dry-run", action="store_true", help="Generate content without sending it.")
    parser.add_argument("--date", help="Date in YYYY-MM-DD format. Defaults to today in Moscow.")
    parser.add_argument("--hour", type=int, default=int(os.getenv("PANCHANGA_HOUR", DEFAULT_CALC_HOUR)))
    parser.add_argument("--minute", type=int, default=int(os.getenv("PANCHANGA_MINUTE", DEFAULT_CALC_MINUTE)))
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env_file()
    args = parse_args()

    bot_token = os.getenv("BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID")
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
    )
    text = build_daily_text(panchanga)
    compact_text = build_compact_daily_text(panchanga)

    with tempfile.TemporaryDirectory(prefix="vedascope_daily_") as temp_dir:
        output_dir = Path(temp_dir)
        try:
            images = generate_chart_images(target_date, args.hour, args.minute, output_dir)
        except Exception:
            LOGGER.exception("Chart image generation failed")
            raise

        LOGGER.info("Generated south chart: %s (%s bytes)", images["south"], images["south"].stat().st_size)
        LOGGER.info("Generated north chart: %s (%s bytes)", images["north"], images["north"].stat().st_size)

        if args.dry_run:
            LOGGER.info("Dry run enabled; Telegram sending skipped")
            LOGGER.info("Daily text:\n%s", text)
            chunks = split_html_messages(text)
            if chunks is None:
                LOGGER.warning("Dry run: full text cannot be split safely; compact text would be used")
                chunks = split_html_messages(compact_text)
            LOGGER.info("Daily text message count: %s", len(chunks or []))
            return

        if not bot_token or not channel_id:
            raise RuntimeError("BOT_TOKEN and CHANNEL_ID must be set in environment or .env")

        try:
            send_media_group(bot_token, channel_id, images)
            LOGGER.info("Chart album sent to %s", channel_id)
            send_daily_text(bot_token, channel_id, text, compact_text)
            LOGGER.info("Daily Panchanga text sent to %s", channel_id)
        except Exception:
            LOGGER.exception("Telegram publication failed")
            raise


if __name__ == "__main__":
    main()
