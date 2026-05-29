import swisseph as swe


GRAHAS = {
    "Su": swe.SUN,
    "Mo": swe.MOON,
    "Ma": swe.MARS,
    "Me": swe.MERCURY,
    "Ju": swe.JUPITER,
    "Ve": swe.VENUS,
    "Sa": swe.SATURN,
    "Ra": swe.MEAN_NODE,
}

RETRO_ALLOWED = ["Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]

RASHIS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]


def normalize(deg):
    return deg % 360


def is_retrograde_allowed(graha_name, speed):
    if graha_name not in RETRO_ALLOWED:
        return False

    return speed < 0


def calculate_chart(year, month, day, hour, minute, timezone, latitude, longitude):
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    local_hour = hour + minute / 60
    utc_hour = local_hour - timezone

    jd = swe.julday(year, month, day, utc_hour)

    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    cusps, ascmc = swe.houses_ex(
        jd,
        latitude,
        longitude,
        b"W",
        flags
    )

    lagna_lon = normalize(ascmc[0])
    lagna_sign = int(lagna_lon // 30)

    planets = {}

    for name, planet_id in GRAHAS.items():
        result = swe.calc_ut(jd, planet_id, flags)[0]

        lon = normalize(result[0])
        speed = result[3]

        sign_index = int(lon // 30)

        retrograde = is_retrograde_allowed(name, speed)
        display_name = name

        planets[name] = {
            "display_name": display_name,
            "is_retrograde": retrograde,
            "speed": round(speed, 6),
            "longitude": round(lon, 4),
            "rashi_number": sign_index + 1,
            "rashi": RASHIS[sign_index],
            "degree_in_rashi": round(lon % 30, 4),
            "house": ((sign_index - lagna_sign) % 12) + 1,
        }

    rahu_lon = planets["Ra"]["longitude"]
    rahu_speed = planets["Ra"]["speed"]

    ketu_lon = normalize(rahu_lon + 180)
    ketu_sign = int(ketu_lon // 30)

    ketu_retrograde = is_retrograde_allowed("Ke", rahu_speed)
    ketu_display_name = "Ke"

    planets["Ke"] = {
        "display_name": ketu_display_name,
        "is_retrograde": ketu_retrograde,
        "speed": round(rahu_speed, 6),
        "longitude": round(ketu_lon, 4),
        "rashi_number": ketu_sign + 1,
        "rashi": RASHIS[ketu_sign],
        "degree_in_rashi": round(ketu_lon % 30, 4),
        "house": ((ketu_sign - lagna_sign) % 12) + 1,
    }

    return {
        "date": f"{year}-{month:02d}-{day:02d}",
        "time_local": f"{hour:02d}:{minute:02d}",
        "timezone": timezone,
        "ayanamsa": round(swe.get_ayanamsa_ut(jd), 4),
        "lagna": {
            "longitude": round(lagna_lon, 4),
            "rashi_number": lagna_sign + 1,
            "rashi": RASHIS[lagna_sign],
            "degree_in_rashi": round(lagna_lon % 30, 4),
        },
        "planets": planets,
    }
