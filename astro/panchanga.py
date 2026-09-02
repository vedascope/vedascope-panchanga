import swisseph as swe
from datetime import datetime, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astro.data_loader import (
    VARAS,
    TITHIS_DATA,
    NAKSHATRAS_DATA,
    MOON_SIGNS
)

from astro.special_conditions import calculate_gandanta
from astro.yogas import calculate_moon_yogas
from astro.muhurta import calculate_day_periods
from astro.muhurta import (
    find_next_index_change,
    get_nakshatra_index,
    get_tithi_index,
    julday_to_datetime,
)


TITHIS = [
    "Pratipada", "Dvitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dvadashi", "Trayodashi", "Chaturdashi", "Purnima",
    "Pratipada", "Dvitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dvadashi", "Trayodashi", "Chaturdashi", "Amavasya"
]


NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira",
    "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
    "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra",
    "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula",
    "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]


DYNAMICS_WINDOW_HOURS = 24
TRANSITIONAL_SHARE_THRESHOLD = 0.30
TRANSITION_EPSILON_DAYS = 1 / 86400
DAY_BOUNDARY_TOLERANCE_DAYS = 0.5 / 86400


VEDIC_YOGAS = [
    ("Vishkambha", "Вишкамбха"),
    ("Priti", "Прити"),
    ("Ayushman", "Аюшман"),
    ("Saubhagya", "Саубхагья"),
    ("Shobhana", "Шобхана"),
    ("Atiganda", "Атиганда"),
    ("Sukarman", "Сукарма"),
    ("Dhriti", "Дхрити"),
    ("Shula", "Шула"),
    ("Ganda", "Ганда"),
    ("Vriddhi", "Вриддхи"),
    ("Dhruva", "Дхрува"),
    ("Vyaghata", "Вьягхата"),
    ("Harshana", "Харшана"),
    ("Vajra", "Ваджра"),
    ("Siddhi", "Сиддхи"),
    ("Vyatipata", "Вьятипата"),
    ("Variyana", "Варияна"),
    ("Parigha", "Паригха"),
    ("Shiva", "Шива"),
    ("Siddha", "Сиддха"),
    ("Sadhya", "Садхья"),
    ("Shubha", "Шубха"),
    ("Shukla", "Шукла"),
    ("Brahma", "Брахма"),
    ("Indra", "Индра"),
    ("Vaidhriti", "Вайдхрити"),
]


KARANAS = {
    "Bava": "Бава",
    "Balava": "Балава",
    "Kaulava": "Каулава",
    "Taitila": "Тайтила",
    "Gara": "Гара",
    "Vanija": "Ваниджа",
    "Vishti": "Вишти",
    "Shakuni": "Шакуни",
    "Chatushpada": "Чатушпада",
    "Naga": "Нага",
    "Kimstughna": "Кимстугхна",
}


def normalize(deg):
    return deg % 360


def calculate_vedic_yoga(sun, moon):
    yoga_index = int(normalize(sun + moon) // (360 / 27))
    key, ru = VEDIC_YOGAS[yoga_index]
    return {
        "number": yoga_index + 1,
        "key": key,
        "ru": ru,
    }


def calculate_karana(diff):
    half_tithi_index = int(diff // 6)
    movable = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]

    if half_tithi_index == 0:
        key = "Kimstughna"
    elif 1 <= half_tithi_index <= 56:
        key = movable[(half_tithi_index - 1) % len(movable)]
    elif half_tithi_index == 57:
        key = "Shakuni"
    elif half_tithi_index == 58:
        key = "Chatushpada"
    else:
        key = "Naga"

    return {
        "number": half_tithi_index + 1,
        "key": key,
        "ru": KARANAS[key],
    }


def format_local_time(dt):
    return dt.strftime("%H:%M")


def resolve_calendar_timezone(timezone, timezone_name=None):
    zone_name = timezone_name
    numeric_timezone = timezone

    if not zone_name and isinstance(timezone, str):
        raw_timezone = timezone.strip()
        try:
            numeric_timezone = float(raw_timezone)
        except ValueError:
            zone_name = raw_timezone

    if zone_name:
        try:
            return ZoneInfo(zone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown IANA timezone: {zone_name}") from exc

    return datetime_timezone(timedelta(hours=float(numeric_timezone)))


def aware_datetime_to_julday(value):
    utc_value = value.astimezone(datetime_timezone.utc)
    hour = (
        utc_value.hour
        + utc_value.minute / 60
        + utc_value.second / 3600
        + utc_value.microsecond / 3600000000
    )
    return swe.julday(utc_value.year, utc_value.month, utc_value.day, hour)


def calendar_day_bounds(year, month, day, timezone, timezone_name=None):
    zone = resolve_calendar_timezone(timezone, timezone_name)
    day_start = datetime(year, month, day, tzinfo=zone)
    next_date = day_start.date() + timedelta(days=1)
    day_end = datetime(next_date.year, next_date.month, next_date.day, tzinfo=zone)
    return day_start, day_end, aware_datetime_to_julday(day_start), aware_datetime_to_julday(day_end)


def jd_to_local_datetime(jd, timezone, timezone_name=None):
    zone = resolve_calendar_timezone(timezone, timezone_name)
    utc_value = julday_to_datetime(jd).replace(tzinfo=datetime_timezone.utc)
    return utc_value.astimezone(zone)


def get_tithi_period_data(index):
    number = index + 1
    data = TITHIS_DATA.get(str(number), {})
    return {
        "number": number,
        "sanskrit": TITHIS[index],
        "name": data.get("ru", TITHIS[index]),
        "display": data.get("display", TITHIS[index]),
    }


def get_nakshatra_period_data(index):
    key = NAKSHATRAS[index]
    data = NAKSHATRAS_DATA.get(key, {})
    return {
        "number": index + 1,
        "key": key,
        "name": data.get("ru", key),
    }


def format_local_iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def segment_display_name(segment):
    return segment.get("display") or segment.get("name") or segment.get("key") or str(segment.get("index"))


def build_day_segments(
    year,
    month,
    day,
    timezone,
    kind,
    timezone_name=None,
    index_getter=None,
    period_data_getter=None,
    transition_finder=None,
):
    if kind == "tithi":
        index_getter = index_getter or get_tithi_index
        period_data_getter = period_data_getter or get_tithi_period_data
    elif kind == "nakshatra":
        index_getter = index_getter or get_nakshatra_index
        period_data_getter = period_data_getter or get_nakshatra_period_data
    else:
        raise ValueError(f"Unsupported lunar segment kind: {kind}")

    transition_finder = transition_finder or find_next_index_change
    day_start, day_end, day_start_jd, day_end_jd = calendar_day_bounds(
        year,
        month,
        day,
        timezone,
        timezone_name,
    )
    day_minutes = max(1, round((day_end_jd - day_start_jd) * 24 * 60))
    current_start_jd = day_start_jd
    current_index = index_getter(day_start_jd + TRANSITION_EPSILON_DAYS)
    segments = []

    while current_start_jd < day_end_jd - DAY_BOUNDARY_TOLERANCE_DAYS:
        search_start_jd = current_start_jd + TRANSITION_EPSILON_DAYS
        change_jd = transition_finder(search_start_jd, index_getter)
        transition_inside_day = (
            change_jd is not None
            and change_jd > day_start_jd + DAY_BOUNDARY_TOLERANCE_DAYS
            and change_jd < day_end_jd - DAY_BOUNDARY_TOLERANCE_DAYS
        )
        segment_end_jd = change_jd if transition_inside_day else day_end_jd
        segment_start_local = (
            day_start
            if not segments
            else jd_to_local_datetime(current_start_jd, timezone, timezone_name)
        )
        segment_end_local = (
            jd_to_local_datetime(segment_end_jd, timezone, timezone_name)
            if transition_inside_day
            else day_end
        )
        period_data = period_data_getter(current_index)
        number = period_data.get("number", current_index + 1)
        duration_minutes = max(0, round((segment_end_jd - current_start_jd) * 24 * 60))
        segment = {
            "kind": kind,
            "index": number,
            "number": number,
            "name": period_data.get("name") or period_data.get("display") or period_data.get("key"),
            "starts_at": format_local_iso(segment_start_local),
            "starts_at_time": format_local_time(segment_start_local),
            "ends_at": format_local_iso(segment_end_local),
            "ends_at_time": format_local_time(segment_end_local),
            "duration_minutes": duration_minutes,
            "is_day_start": not segments,
            "is_day_end": not transition_inside_day,
            "is_current_at_publish_time": False,
            "share_of_window": round(duration_minutes / day_minutes, 4),
            "role": "secondary",
        }
        for key in ("display", "sanskrit", "key"):
            if period_data.get(key) is not None:
                segment[key] = period_data[key]
        if kind == "tithi":
            segment["data"] = TITHIS_DATA.get(str(number), {})
        else:
            segment["data"] = NAKSHATRAS_DATA.get(segment.get("key"), {})
        segments.append(segment)

        if not transition_inside_day:
            break

        current_start_jd = segment_end_jd
        current_index = index_getter(segment_end_jd + TRANSITION_EPSILON_DAYS)

    return segments


def build_lunar_day_periods(year, month, day, hour, minute, timezone, kind, timezone_name=None):
    return build_day_segments(year, month, day, timezone, kind, timezone_name=timezone_name)


def build_lunar_window_segments(
    year,
    month,
    day,
    hour,
    minute,
    timezone,
    kind,
    window_hours=DYNAMICS_WINDOW_HOURS,
    timezone_name=None,
):
    return build_day_segments(year, month, day, timezone, kind, timezone_name=timezone_name)


def mark_dominant_segments(segments):
    if not segments:
        return None
    dominant = max(segments, key=lambda segment: segment.get("duration_minutes", 0))
    for segment in segments:
        segment["role"] = "dominant" if segment is dominant else "secondary"
        segment["is_transitional_at_publish_time"] = (
            segment.get("is_current_at_publish_time")
            and segment.get("share_of_window", 0) < TRANSITIONAL_SHARE_THRESHOLD
            and segment is not dominant
        )
    return dominant


def build_transitions(kind, segments):
    transitions = []
    for current, next_segment in zip(segments, segments[1:]):
        transitions.append({
            "kind": kind,
            "at": current["ends_at"],
            "at_time": current["ends_at_time"],
            "from": segment_display_name(current),
            "from_index": current.get("index"),
            "to": segment_display_name(next_segment),
            "to_index": next_segment.get("index"),
        })
    return transitions


def mark_current_segment(segments, current_index):
    current_number = current_index + 1
    matched = None
    for segment in segments:
        is_current = matched is None and segment.get("number") == current_number
        segment["is_current_at_publish_time"] = is_current
        if is_current:
            matched = segment
    return matched


def build_day_dynamics(year, month, day, hour, minute, timezone, timezone_name=None):
    start_local, end_local, start_jd, end_jd = calendar_day_bounds(
        year,
        month,
        day,
        timezone,
        timezone_name,
    )
    zone = resolve_calendar_timezone(timezone, timezone_name)
    publish_local = datetime(year, month, day, hour, minute, tzinfo=zone)
    publish_jd = aware_datetime_to_julday(publish_local)
    tithi_segments = build_day_segments(year, month, day, timezone, "tithi", timezone_name=timezone_name)
    nakshatra_segments = build_day_segments(year, month, day, timezone, "nakshatra", timezone_name=timezone_name)
    mark_current_segment(tithi_segments, get_tithi_index(publish_jd))
    mark_current_segment(nakshatra_segments, get_nakshatra_index(publish_jd))
    dominant_tithi = mark_dominant_segments(tithi_segments)
    dominant_nakshatra = mark_dominant_segments(nakshatra_segments)
    transitions = build_transitions("tithi", tithi_segments) + build_transitions("nakshatra", nakshatra_segments)

    return {
        "window_start": format_local_iso(start_local),
        "window_start_time": format_local_time(start_local),
        "window_end": format_local_iso(end_local),
        "window_end_time": format_local_time(end_local),
        "window_minutes": round((end_jd - start_jd) * 24 * 60),
        "publish_time": format_local_time(publish_local),
        "tithi_segments": tithi_segments,
        "nakshatra_segments": nakshatra_segments,
        "dominant_tithi": dominant_tithi,
        "dominant_nakshatra": dominant_nakshatra,
        "transitions": transitions,
    }


def calculate_panchanga(
    year,
    month,
    day,
    latitude,
    longitude,
    timezone,
    hour=9,
    minute=0,
    timezone_name=None,
):
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    local_hour = hour + minute / 60
    utc_hour = local_hour - timezone

    jd = swe.julday(
        year,
        month,
        day,
        utc_hour
    )

    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

    sun = normalize(
        swe.calc_ut(jd, swe.SUN, flags)[0][0]
    )

    moon = normalize(
        swe.calc_ut(jd, swe.MOON, flags)[0][0]
    )

    mars = normalize(
        swe.calc_ut(jd, swe.MARS, flags)[0][0]
    )

    jupiter = normalize(
        swe.calc_ut(jd, swe.JUPITER, flags)[0][0]
    )

    venus = normalize(
        swe.calc_ut(jd, swe.VENUS, flags)[0][0]
    )

    saturn = normalize(
        swe.calc_ut(jd, swe.SATURN, flags)[0][0]
    )

    mean_node = normalize(
        swe.calc_ut(jd, swe.MEAN_NODE, flags)[0][0]
    )

    rahu = mean_node
    ketu = normalize(mean_node + 180)

    diff = normalize(moon - sun)

    tithi_index = int(diff // 12)
    nakshatra_index = int(moon // (360 / 27))
    vedic_yoga = calculate_vedic_yoga(sun, moon)
    karana = calculate_karana(diff)

    dt = datetime(year, month, day)

    vara_key = dt.strftime("%A")

    day_periods = calculate_day_periods(
        year=year,
        month=month,
        day=day,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        hour=hour,
        minute=minute,
    )
    day_dynamics = build_day_dynamics(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        timezone=timezone,
        timezone_name=timezone_name,
    )

    tithi_number = tithi_index + 1
    tithi_key = str(tithi_number)

    nakshatra_key = NAKSHATRAS[nakshatra_index]

    degree_in_nakshatra = moon % (360 / 27)

    gandanta = calculate_gandanta(
        nakshatra_key,
        degree_in_nakshatra
    )

    moon_rashi_number = int(moon // 30) + 1

    chart_data = {
        "planets": {

            "Mo": {
                "longitude": moon,
                "rashi_number": moon_rashi_number,
            },

            "Ma": {
                "longitude": mars,
                "rashi_number": int(mars // 30) + 1,
            },

            "Ju": {
                "longitude": jupiter,
                "rashi_number": int(jupiter // 30) + 1,
            },

            "Ve": {
                "longitude": venus,
                "rashi_number": int(venus // 30) + 1,
            },

            "Sa": {
                "longitude": saturn,
                "rashi_number": int(saturn // 30) + 1,
            },

            "Ra": {
                "longitude": rahu,
                "rashi_number": int(rahu // 30) + 1,
            },

            "Ke": {
                "longitude": ketu,
                "rashi_number": int(ketu // 30) + 1,
            },
        }
    }

    yogas = calculate_moon_yogas(chart_data)
    tithi_periods = day_dynamics["tithi_segments"]
    nakshatra_periods = day_dynamics["nakshatra_segments"]

    return {

        "date": f"{year}-{month:02d}-{day:02d}",

        "calculation_time_local": f"{hour:02d}:{minute:02d}",

        "location": {
            "timezone": timezone,
            "timezone_name": timezone_name,
            "latitude": latitude,
            "longitude": longitude,
        },

        "vara": {
            "key": vara_key,
            "data": VARAS.get(vara_key),
        },

        "tithi": {
            "number": tithi_number,
            "sanskrit": TITHIS[tithi_index],
            "data": TITHIS_DATA.get(tithi_key),
            "day_periods": tithi_periods,
        },

        "moon": {
            "longitude": round(moon, 4),
            "rashi_number": moon_rashi_number,
            "data": MOON_SIGNS[str(moon_rashi_number)],
        },

        "nakshatra": {
            "number": nakshatra_index + 1,
            "key": nakshatra_key,
            "degree_in_nakshatra": round(
                degree_in_nakshatra,
                4
            ),
            "data": NAKSHATRAS_DATA.get(
                nakshatra_key
            ),
            "gandanta": gandanta,
            "day_periods": nakshatra_periods,
        },

        "vedic_yoga": vedic_yoga,

        "karana": karana,

        "lunar_day_periods": {
            "tithi": tithi_periods,
            "nakshatra": nakshatra_periods,
        },

        "day_dynamics": day_dynamics,

        "muhurta": day_periods,

        "yogas": yogas,
    }
