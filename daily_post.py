import argparse
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


def format_periods(periods):
    if not periods:
        return "нет данных"

    lines = []
    for period in periods:
        name = period.get("display") or period.get("name")
        lines.append(f"• {name}: с {period['starts_at']} до {period['ends_at']}")
    return "\n".join(lines)


def get_period(periods, name):
    if not periods:
        return "нет данных"

    period = periods.get(name)
    if not period:
        return "нет данных"

    return f"{period['start']} - {period['end']}"


def build_daily_text(panchanga):
    date_text = datetime.strptime(panchanga["date"], "%Y-%m-%d").strftime("%d.%m.%Y")
    tithi = panchanga["tithi"]
    nakshatra = panchanga["nakshatra"]
    vara = panchanga["vara"]["data"]
    vedic_yoga = panchanga.get("vedic_yoga", {})
    karana = panchanga.get("karana", {})
    muhurta = panchanga.get("muhurta") or {}
    moon_yogas = panchanga.get("yogas") or []

    recommendation_parts = []
    if tithi.get("data", {}).get("summary"):
        recommendation_parts.append(tithi["data"]["summary"])
    if nakshatra.get("data", {}).get("summary"):
        recommendation_parts.append(nakshatra["data"]["summary"])
    recommendation = " ".join(recommendation_parts)

    lines = [
        f"Панчанга на {date_text}, {DEFAULT_CITY}",
        "",
        f"Вара: {vara['ru']}",
        "",
        "Титхи:",
        format_periods(tithi.get("day_periods")),
        "",
        "Накшатра:",
        format_periods(nakshatra.get("day_periods")),
        "",
        f"Йога: {vedic_yoga.get('ru', 'нет данных')}",
        f"Карана: {karana.get('ru', 'нет данных')}",
        "",
        f"Раху Кала: {get_period(muhurta, 'rahu_kalam')}",
        f"Ямаганда: {get_period(muhurta, 'yamaganda')}",
        f"Гулика: {get_period(muhurta, 'gulika')}",
        f"Абхиджит-мухурта: {get_period(muhurta, 'abhijit_muhurta')}",
    ]

    if moon_yogas:
        lines += ["", "Дополнительные влияния:"]
        lines += [f"• {yoga['title']}" for yoga in moon_yogas[:3]]

    if recommendation:
        lines += ["", "Краткая рекомендация:", recommendation]

    text = "\n".join(lines).strip()
    if len(text) > TELEGRAM_MESSAGE_LIMIT:
        LOGGER.warning("Daily text is %s chars; trimming to Telegram limit", len(text))
        text = text[: TELEGRAM_MESSAGE_LIMIT - 1].rstrip() + "…"

    return text


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


def send_photo(bot_token, channel_id, image_path, caption):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    with open(image_path, "rb") as photo:
        try:
            response = requests.post(
                url,
                data={
                    "chat_id": channel_id,
                    "caption": caption,
                },
                files={"photo": photo},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Telegram sendPhoto failed: {exc}") from exc

    return check_telegram_response(response, "sendPhoto")


def send_message(bot_token, channel_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = requests.post(
            url,
            data={
                "chat_id": channel_id,
                "text": text,
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Telegram sendMessage failed: {exc}") from exc

    return check_telegram_response(response, "sendMessage")


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
            return

        if not bot_token or not channel_id:
            raise RuntimeError("BOT_TOKEN and CHANNEL_ID must be set in environment or .env")

        try:
            send_photo(bot_token, channel_id, images["south"], "Карта дня, южный стиль")
            LOGGER.info("South chart sent to %s", channel_id)
            send_photo(bot_token, channel_id, images["north"], "Карта дня, северный стиль")
            LOGGER.info("North chart sent to %s", channel_id)
            send_message(bot_token, channel_id, text)
            LOGGER.info("Daily Panchanga text sent to %s", channel_id)
        except Exception:
            LOGGER.exception("Telegram publication failed")
            raise


if __name__ == "__main__":
    main()
