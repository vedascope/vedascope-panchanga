from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException

from astro.panchanga import NAKSHATRAS, calculate_panchanga
from astro.chart import calculate_chart


GRAHA_KEYS = ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]
SUPPORTED_AYANAMSHAS = {"lahiri"}
DEFAULT_LATITUDE = 55.7558
DEFAULT_LONGITUDE = 37.6173
DEFAULT_TIMEZONE = "Europe/Moscow"


def normalize360(value):
    return ((float(value) % 360) + 360) % 360


def derive_graha(key, longitude):
    normalized = normalize360(longitude)
    rashi = int(normalized // 30) + 1
    nakshatra = int(normalized // (360 / 27)) + 1
    global_pada = int(normalized // (360 / 108)) + 1

    return {
        "key": key,
        "longitude": round(normalized, 6),
        "rashi": min(rashi, 12),
        "degreeInRashi": round(normalized % 30, 6),
        "nakshatra": min(nakshatra, 27),
        "nakshatraName": NAKSHATRAS[min(nakshatra, 27) - 1],
        "pada": ((min(global_pada, 108) - 1) % 4) + 1,
        "globalPada": min(global_pada, 108),
    }


def resolve_ayanamsha(value):
    ayanamsha = str(value or "lahiri").strip().lower()
    if ayanamsha not in SUPPORTED_AYANAMSHAS:
        raise HTTPException(status_code=400, detail="Unsupported ayanamsha.")
    return ayanamsha


def resolve_timezone(value):
    timezone = value or DEFAULT_TIMEZONE
    try:
        return timezone, ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=400, detail="Invalid timezone.") from exc


def parse_calculation_datetimes(datetime_value, timezone_info):
    if not datetime_value:
        instant_utc = datetime.now(UTC)
        return instant_utc, instant_utc.astimezone(timezone_info)

    try:
        parsed = datetime.fromisoformat(str(datetime_value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid datetime.") from exc

    if parsed.tzinfo is None:
        local_dt = parsed.replace(tzinfo=timezone_info)
        return local_dt.astimezone(UTC), local_dt

    instant_utc = parsed.astimezone(UTC)
    return instant_utc, instant_utc.astimezone(timezone_info)


def utc_iso(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def local_iso(value):
    return value.isoformat(timespec="seconds")


def date_label(value):
    return value.strftime("%d.%m.%y")


def panchanga_summary(data):
    return {
        "tithi": display_value(data.get("tithi")),
        "vara": display_value(data.get("vara")),
        "yoga": display_value(data.get("vedic_yoga")),
        "karana": display_value(data.get("karana")),
        "lunarNakshatra": display_value(data.get("nakshatra")),
    }


def display_value(source):
    if not source:
        return None
    if isinstance(source, str):
        return source
    data = source.get("data") if isinstance(source, dict) else None
    value = data or source
    if not isinstance(value, dict):
        return None
    return value.get("display") or value.get("ru") or value.get("en") or value.get("name") or value.get("key")


def build_veda_clock_state(
    *,
    datetime_value=None,
    latitude=DEFAULT_LATITUDE,
    longitude=DEFAULT_LONGITUDE,
    timezone=DEFAULT_TIMEZONE,
    ayanamsha="lahiri",
    lang="ru",
):
    validate_location(latitude, longitude)
    effective_ayanamsha = resolve_ayanamsha(ayanamsha)
    timezone_name, timezone_info = resolve_timezone(timezone)
    instant_utc, local_dt = parse_calculation_datetimes(datetime_value, timezone_info)
    offset = local_dt.utcoffset()
    if offset is None:
        raise HTTPException(status_code=400, detail="Timezone offset could not be resolved.")
    timezone_offset = offset.total_seconds() / 3600

    chart_data = calculate_chart(
        local_dt.year,
        local_dt.month,
        local_dt.day,
        local_dt.hour,
        local_dt.minute,
        timezone_offset,
        latitude,
        longitude,
        second=local_dt.second,
    )
    planets = chart_data.get("planets") or {}
    missing = [key for key in GRAHA_KEYS if key not in planets or "longitude" not in planets[key]]
    if missing:
        raise HTTPException(status_code=500, detail=f"Required grahas could not be calculated: {', '.join(missing)}")

    grahas = [derive_graha(key, planets[key]["longitude"]) for key in GRAHA_KEYS]

    panchanga_data = calculate_panchanga(
        local_dt.year,
        local_dt.month,
        local_dt.day,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone_offset,
        hour=local_dt.hour,
        minute=local_dt.minute,
    )

    return {
        "schemaVersion": "veda-clock-state/v1",
        "datetime": local_iso(local_dt),
        "timezone": timezone_name,
        "dateLabel": date_label(local_dt),
        "time": {
            "hour": local_dt.hour,
            "minute": local_dt.minute,
            "second": local_dt.second,
        },
        "calculationInstantUtc": utc_iso(instant_utc),
        "grahas": grahas,
        "activeNakshatras": sorted({graha["nakshatra"] for graha in grahas}),
        "activePadas": sorted({graha["globalPada"] for graha in grahas}),
        "panchanga": panchanga_summary(panchanga_data),
        "meta": {
            "ayanamsha": effective_ayanamsha,
            "lang": lang,
            "location": {
                "lat": latitude,
                "lon": longitude,
            },
            "generatedAt": utc_iso(datetime.now(UTC)),
            "calculationSource": "existing-astro-core",
        },
    }


def validate_location(latitude, longitude):
    if latitude < -90 or latitude > 90:
        raise HTTPException(status_code=400, detail="Invalid latitude.")
    if longitude < -180 or longitude > 180:
        raise HTTPException(status_code=400, detail="Invalid longitude.")
