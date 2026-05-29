from datetime import date, datetime, timedelta

import swisseph as swe


RAHU_KALAM_SEGMENTS = {
    6: 8,  # Sunday
    0: 2,  # Monday
    1: 7,  # Tuesday
    2: 5,  # Wednesday
    3: 6,  # Thursday
    4: 4,  # Friday
    5: 3,  # Saturday
}

YAMAGANDA_SEGMENTS = {
    6: 5,  # Sunday
    0: 4,  # Monday
    1: 3,  # Tuesday
    2: 2,  # Wednesday
    3: 1,  # Thursday
    4: 7,  # Friday
    5: 6,  # Saturday
}

GULIKA_SEGMENTS = {
    6: 7,  # Sunday
    0: 6,  # Monday
    1: 5,  # Tuesday
    2: 4,  # Wednesday
    3: 3,  # Thursday
    4: 2,  # Friday
    5: 1,  # Saturday
}


ABHIJIT_DESCRIPTION = (
    "Абхиджит-мухурта считается благоприятным временем для важных начинаний, "
    "особенно если нет возможности подобрать отдельную мухурту."
)

RAHU_KALAM_DESCRIPTION = (
    "Раху Кала считается неблагоприятным временем для начала важных дел. "
    "Лучше не начинать новые проекты, поездки, покупки и важные переговоры."
)

YAMAGANDA_DESCRIPTION = (
    "Ямаганда считается неблагоприятным временем для начала поездок, "
    "путешествий и новых дел. Текущие дела можно продолжать, но важные "
    "старты лучше перенести."
)

GULIKA_DESCRIPTION = (
    "Период Гулики связан с энергией Сатурна. Подходит для дисциплины, "
    "исследования, уединения и долгосрочных процессов, но не считается "
    "лучшим временем для легких развлечений и быстрых результатов."
)


def normalize(degrees):
    return degrees % 360


def datetime_to_julday(dt):
    hour = dt.hour + dt.minute / 60 + dt.second / 3600 + dt.microsecond / 3600000000
    return swe.julday(dt.year, dt.month, dt.day, hour)


def julday_to_datetime(jd):
    year, month, day, hour = swe.revjul(jd)
    whole_hours = int(hour)
    minute_float = (hour - whole_hours) * 60
    whole_minutes = int(minute_float)
    seconds = round((minute_float - whole_minutes) * 60)

    dt = datetime(year, month, day, whole_hours, whole_minutes)
    dt += timedelta(seconds=seconds)
    return dt.replace(second=0, microsecond=0)


def format_time(dt):
    return dt.strftime("%H:%M")


def local_datetime_to_utc_julday(year, month, day, hour, minute, timezone):
    local_dt = datetime(year, month, day, hour, minute)
    utc_dt = local_dt - timedelta(hours=timezone)
    return datetime_to_julday(utc_dt)


def jd_to_local_time(jd, timezone):
    utc_dt = julday_to_datetime(jd)
    return format_time(utc_dt + timedelta(hours=timezone))


def get_sidereal_sun_moon(jd):
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    sun = normalize(swe.calc_ut(jd, swe.SUN, flags)[0][0])
    moon = normalize(swe.calc_ut(jd, swe.MOON, flags)[0][0])
    return sun, moon


def get_tithi_index(jd):
    sun, moon = get_sidereal_sun_moon(jd)
    return int(normalize(moon - sun) // 12)


def get_nakshatra_index(jd):
    _, moon = get_sidereal_sun_moon(jd)
    return int(moon // (360 / 27))


def find_next_index_change(start_jd, index_getter, max_days=4):
    start_index = index_getter(start_jd)
    step = 1 / 24
    previous_jd = start_jd
    current_jd = start_jd + step
    end_jd = start_jd + max_days

    while current_jd <= end_jd:
        if index_getter(current_jd) != start_index:
            low = previous_jd
            high = current_jd
            for _ in range(32):
                mid = (low + high) / 2
                if index_getter(mid) == start_index:
                    low = mid
                else:
                    high = mid
            return high

        previous_jd = current_jd
        current_jd += step

    return None


def calculate_tithi_end_time(year, month, day, hour, minute, timezone):
    start_jd = local_datetime_to_utc_julday(year, month, day, hour, minute, timezone)
    end_jd = find_next_index_change(start_jd, get_tithi_index)
    if end_jd is None:
        return None

    return {
        "ends_at": jd_to_local_time(end_jd, timezone),
    }


def calculate_nakshatra_end_time(year, month, day, hour, minute, timezone):
    start_jd = local_datetime_to_utc_julday(year, month, day, hour, minute, timezone)
    end_jd = find_next_index_change(start_jd, get_nakshatra_index)
    if end_jd is None:
        return None

    return {
        "ends_at": jd_to_local_time(end_jd, timezone),
    }


def calculate_solar_event(year, month, day, latitude, longitude, timezone, event_flag):
    local_midnight = datetime.combine(date(year, month, day), datetime.min.time())
    utc_start = local_midnight - timedelta(hours=timezone)
    jd_start = datetime_to_julday(utc_start)
    geopos = (longitude, latitude, 0)

    try:
        result, event_times = swe.rise_trans(
            jd_start,
            swe.SUN,
            event_flag,
            geopos,
            flags=swe.FLG_SWIEPH,
        )
    except swe.Error:
        return None

    if result != 0:
        return None

    event_utc = julday_to_datetime(event_times[0])
    return event_utc + timedelta(hours=timezone)


def calculate_sunrise_sunset(year, month, day, latitude, longitude, timezone):
    sunrise = calculate_solar_event(
        year,
        month,
        day,
        latitude,
        longitude,
        timezone,
        swe.CALC_RISE,
    )
    sunset = calculate_solar_event(
        year,
        month,
        day,
        latitude,
        longitude,
        timezone,
        swe.CALC_SET,
    )

    if sunrise is None or sunset is None:
        return None

    return {
        "sunrise": format_time(sunrise),
        "sunset": format_time(sunset),
        "sunrise_dt": sunrise,
        "sunset_dt": sunset,
    }


def calculate_abhijit_muhurta(sunrise, sunset):
    day_duration = sunset - sunrise
    muhurta_duration = day_duration / 15
    solar_midday = sunrise + day_duration / 2
    start = solar_midday - muhurta_duration / 2
    end = solar_midday + muhurta_duration / 2

    return {
        "start": format_time(start),
        "end": format_time(end),
        "description": ABHIJIT_DESCRIPTION,
    }


def calculate_day_segment(year, month, day, sunrise, sunset, segment_table, description):
    weekday = date(year, month, day).weekday()
    segment_number = segment_table[weekday]
    day_duration = sunset - sunrise
    segment_duration = day_duration / 8
    start = sunrise + segment_duration * (segment_number - 1)
    end = start + segment_duration

    return {
        "start": format_time(start),
        "end": format_time(end),
        "description": description,
    }


def calculate_rahu_kalam(year, month, day, sunrise, sunset):
    return calculate_day_segment(
        year,
        month,
        day,
        sunrise,
        sunset,
        RAHU_KALAM_SEGMENTS,
        RAHU_KALAM_DESCRIPTION,
    )


def calculate_yamaganda(year, month, day, sunrise, sunset):
    return calculate_day_segment(
        year,
        month,
        day,
        sunrise,
        sunset,
        YAMAGANDA_SEGMENTS,
        YAMAGANDA_DESCRIPTION,
    )


def calculate_gulika(year, month, day, sunrise, sunset):
    return calculate_day_segment(
        year,
        month,
        day,
        sunrise,
        sunset,
        GULIKA_SEGMENTS,
        GULIKA_DESCRIPTION,
    )


def calculate_day_periods(year, month, day, latitude, longitude, timezone, hour=9, minute=0):
    solar_times = calculate_sunrise_sunset(
        year=year,
        month=month,
        day=day,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
    )

    if solar_times is None:
        return None

    sunrise = solar_times["sunrise_dt"]
    sunset = solar_times["sunset_dt"]

    if sunset <= sunrise:
        return None

    return {
        "sunrise": solar_times["sunrise"],
        "sunset": solar_times["sunset"],
        "abhijit_muhurta": calculate_abhijit_muhurta(sunrise, sunset),
        "rahu_kalam": calculate_rahu_kalam(year, month, day, sunrise, sunset),
        "yamaganda": calculate_yamaganda(year, month, day, sunrise, sunset),
        "gulika": calculate_gulika(year, month, day, sunrise, sunset),
        "tithi_end": calculate_tithi_end_time(
            year,
            month,
            day,
            hour,
            minute,
            timezone,
        ),
        "nakshatra_end": calculate_nakshatra_end_time(
            year,
            month,
            day,
            hour,
            minute,
            timezone,
        ),
    }
