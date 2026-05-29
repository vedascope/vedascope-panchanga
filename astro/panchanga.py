import swisseph as swe
from datetime import datetime, timedelta

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
    local_datetime_to_utc_julday,
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


def jd_to_local_datetime(jd, timezone):
    return julday_to_datetime(jd) + timedelta(hours=timezone)


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


def build_lunar_day_periods(year, month, day, hour, minute, timezone, kind):
    start_time = f"{hour:02d}:{minute:02d}"
    start_jd = local_datetime_to_utc_julday(year, month, day, hour, minute, timezone)
    local_day_end = datetime(year, month, day, 23, 59)

    if kind == "tithi":
        index_getter = get_tithi_index
        period_data_getter = get_tithi_period_data
    else:
        index_getter = get_nakshatra_index
        period_data_getter = get_nakshatra_period_data

    current_index = index_getter(start_jd)
    current_period = {
        **period_data_getter(current_index),
        "starts_at": start_time,
        "ends_at": "конца суток",
        "ends_at_time": None,
    }

    change_jd = find_next_index_change(start_jd, index_getter)
    if change_jd is None:
        return [current_period]

    change_local = jd_to_local_datetime(change_jd, timezone)
    if change_local.date() != local_day_end.date() or change_local > local_day_end:
        return [current_period]

    change_time = format_local_time(change_local)
    current_period["ends_at"] = change_time
    current_period["ends_at_time"] = change_time

    next_index = index_getter(change_jd + 1 / 86400)
    next_period = {
        **period_data_getter(next_index),
        "starts_at": change_time,
        "ends_at": "конца суток",
        "ends_at_time": None,
    }

    return [current_period, next_period]


def calculate_panchanga(
    year,
    month,
    day,
    latitude,
    longitude,
    timezone,
    hour=9,
    minute=0
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
    tithi_periods = build_lunar_day_periods(
        year,
        month,
        day,
        hour,
        minute,
        timezone,
        "tithi",
    )
    nakshatra_periods = build_lunar_day_periods(
        year,
        month,
        day,
        hour,
        minute,
        timezone,
        "nakshatra",
    )

    return {

        "date": f"{year}-{month:02d}-{day:02d}",

        "calculation_time_local": f"{hour:02d}:{minute:02d}",

        "location": {
            "timezone": timezone,
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

        "muhurta": day_periods,

        "yogas": yogas,
    }
