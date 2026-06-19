from html import escape
import json
import re
import sqlite3
import string
from datetime import date, datetime
from pathlib import Path
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Query, Response

from astro.panchanga import calculate_panchanga
from astro.chart import calculate_chart

from astro.south_chart import generate_south_indian_svg

from astro.text_builder import build_panchanga_text
from astro.html_builder import build_panchanga_html


app = FastAPI()

LOCATION_SEED_PATH = Path(__file__).resolve().parent / "data" / "locations.seed.json"
LOCATION_DB_PATH = Path(__file__).resolve().parent / "data" / "locations.sqlite"
NAKSHATRA_SPAN = 360 / 27
PADA_SPAN = 360 / 108
GRAHA_OUTPUT = [
    ("Su", "sun", "Sun"),
    ("Mo", "moon", "Moon"),
    ("Ma", "mars", "Mars"),
    ("Me", "mercury", "Mercury"),
    ("Ju", "jupiter", "Jupiter"),
    ("Ve", "venus", "Venus"),
    ("Sa", "saturn", "Saturn"),
    ("Ra", "rahu", "Rahu"),
    ("Ke", "ketu", "Ketu"),
]


SEARCH_PUNCTUATION = str.maketrans({char: " " for char in string.punctuation + "«»“”„’‘´`№"})


def normalize_search_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.strip().lower().replace("ё", "е")
    text = text.translate(SEARCH_PUNCTUATION)
    return re.sub(r"\s+", " ", text).strip()


def load_seed_locations():
    with LOCATION_SEED_PATH.open(encoding="utf-8") as file:
        data = json.load(file)

    return data if isinstance(data, list) else []


def location_search_text(location):
    values = [
        location.get("name"),
        location.get("country"),
        location.get("region"),
        *(location.get("aliases") or []),
    ]

    return " ".join(normalize_search_text(value) for value in values if value)


def score_location(location, query):
    normalized_query = normalize_search_text(query)
    name = normalize_search_text(location.get("name"))
    aliases = [normalize_search_text(alias) for alias in location.get("aliases") or []]

    if name == normalized_query or normalized_query in aliases:
        return 0
    if name.startswith(normalized_query) or any(alias.startswith(normalized_query) for alias in aliases):
        return 1
    if normalized_query in location_search_text(location):
        return 2
    return 9


def sqlite_location_is_seed_duplicate(location, seed_locations):
    try:
        latitude = float(location["latitude"])
        longitude = float(location["longitude"])
    except (KeyError, TypeError, ValueError):
        return False

    timezone = location.get("timezone")
    for seed in seed_locations:
        if timezone != seed.get("timezone"):
            continue
        try:
            seed_latitude = float(seed["latitude"])
            seed_longitude = float(seed["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if abs(latitude - seed_latitude) <= 0.35 and abs(longitude - seed_longitude) <= 0.35:
            return True
    return False


def db_available():
    return LOCATION_DB_PATH.exists()


def search_sqlite_locations(query, limit):
    if not db_available():
        return []

    normalized_query = normalize_search_text(query)
    like_prefix = f"{normalized_query}%"
    like_contains = f"%{normalized_query}%"

    sql = """
        WITH ranked_names AS (
            SELECT
                geoname_id,
                name AS matched_name,
                kind,
                CASE
                    WHEN normalized = :query THEN 0
                    WHEN normalized LIKE :prefix THEN 1
                    WHEN normalized LIKE :contains THEN 2
                    ELSE 9
                END AS match_rank,
                CASE kind
                    WHEN 'canonical' THEN 0
                    WHEN 'ascii' THEN 1
                    ELSE 2
                END AS kind_rank
            FROM location_names
            WHERE normalized = :query
               OR normalized LIKE :prefix
               OR normalized LIKE :contains
        ),
        best_names AS (
            SELECT
                geoname_id,
                matched_name,
                kind,
                match_rank,
                kind_rank,
                ROW_NUMBER() OVER (
                    PARTITION BY geoname_id
                    ORDER BY match_rank, kind_rank, length(matched_name)
                ) AS row_number
            FROM ranked_names
        )
        SELECT
            l.geoname_id,
            l.name,
            l.ascii_name,
            l.alternate_names,
            l.country_code,
            l.admin1_code,
            l.admin2_code,
            l.latitude,
            l.longitude,
            l.timezone,
            l.population,
            l.feature_code,
            b.matched_name,
            b.match_rank,
            b.kind_rank
        FROM best_names b
        JOIN locations l ON l.geoname_id = b.geoname_id
        WHERE b.row_number = 1
        ORDER BY b.match_rank, l.population DESC, b.kind_rank, l.name
        LIMIT :limit
    """

    with sqlite3.connect(f"file:{LOCATION_DB_PATH}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            sql,
            {
                "query": normalized_query,
                "prefix": like_prefix,
                "contains": like_contains,
                "limit": limit,
            },
        ).fetchall()

    results = []
    for row in rows:
        aliases = []
        for value in [row["ascii_name"], row["matched_name"]]:
            if value and value != row["name"] and value not in aliases:
                aliases.append(value)

        results.append({
            "id": f"geonames:{row['geoname_id']}",
            "name": row["name"],
            "country": row["country_code"],
            "region": row["admin1_code"] or row["admin2_code"] or "",
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "timezone": row["timezone"],
            "aliases": aliases,
            "source": "geonames",
        })

    return results


def parse_local_datetime(date_value, time_value):
    try:
        return datetime.strptime(f"{date_value} {time_value}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid date or time. Use date=YYYY-MM-DD and time=HH:MM.",
        ) from exc


def resolve_timezone_offset(local_dt, tz, timezone):
    if tz:
        try:
            zoned_dt = local_dt.replace(tzinfo=ZoneInfo(tz))
        except ZoneInfoNotFoundError as exc:
            if timezone is None:
                raise HTTPException(
                    status_code=400,
                    detail="Unknown IANA timezone and no numeric timezone fallback provided.",
                ) from exc
        else:
            offset = zoned_dt.utcoffset()
            if offset is None:
                raise HTTPException(status_code=400, detail="Timezone offset could not be resolved.")
            return offset.total_seconds() / 3600, tz

    if timezone is None:
        raise HTTPException(status_code=400, detail="Timezone is required. Pass tz=IANA or numeric timezone.")

    return timezone, f"UTC{timezone:+g}"


def build_graha_payload(short_key, key, name, planet):
    longitude = planet["longitude"] % 360
    sign_index = int(longitude // 30)
    nakshatra_index = int(longitude // NAKSHATRA_SPAN)
    pada_index = int(longitude // PADA_SPAN)
    pada_in_nakshatra = int((longitude % NAKSHATRA_SPAN) // PADA_SPAN) + 1

    return {
        "key": key,
        "name": name,
        "shortKey": short_key,
        "longitude": round(longitude, 4),
        "signIndex": sign_index,
        "degreeInSign": round(longitude % 30, 4),
        "nakshatraIndex": nakshatra_index,
        "nakshatraNumber": nakshatra_index + 1,
        "padaIndex": pada_index,
        "padaNumber": pada_index + 1,
        "padaInNakshatra": pada_in_nakshatra,
    }


@app.get("/")
def root():
    return {"status": "Panchanga API running"}


@app.get("/locations/search")
def locations_search(q: str = "", limit: int = Query(10, ge=1, le=20)):
    normalized_query = normalize_search_text(q)
    if not normalized_query:
        return []

    seed_locations = load_seed_locations()
    seed_matches = [
        location
        for location in seed_locations
        if normalized_query in location_search_text(location)
    ]
    seed_results = sorted(
        seed_matches,
        key=lambda location: score_location(location, normalized_query),
    )

    remaining_limit = limit - len(seed_results)
    if remaining_limit <= 0:
        return seed_results[:limit]

    sqlite_results = [
        location
        for location in search_sqlite_locations(normalized_query, remaining_limit + len(seed_locations))
        if not sqlite_location_is_seed_duplicate(location, seed_locations)
    ]

    return (seed_results + sqlite_results)[:limit]


@app.get("/grahas")
def grahas(
    date: str = Query(...),
    time: str = Query("09:00"),
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    tz: str | None = None,
    timezone: float | None = Query(None, ge=-12, le=14),
):
    local_dt = parse_local_datetime(date, time)
    timezone_offset, timezone_name = resolve_timezone_offset(local_dt, tz, timezone)

    chart_data = calculate_chart(
        local_dt.year,
        local_dt.month,
        local_dt.day,
        local_dt.hour,
        local_dt.minute,
        timezone_offset,
        lat,
        lon,
    )

    return {
        "input": {
            "date": date,
            "time": time,
            "timezone": timezone_name,
        },
        "location": {
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone_name,
            "utc_offset": timezone_offset,
            "used_default": False,
        },
        "calculation": {
            "ayanamsa": "Lahiri",
            "ayanamsaValue": chart_data.get("ayanamsa"),
            "zodiac": "sidereal",
        },
        "grahas": [
            build_graha_payload(short_key, key, name, chart_data["planets"][short_key])
            for short_key, key, name in GRAHA_OUTPUT
        ],
    }


@app.get("/panchanga")
def panchanga(
    year: int,
    month: int,
    day: int,
    hour: int = 9,
    minute: int = 0,
    timezone: float = 3,
    latitude: float = 55.7558,
    longitude: float = 37.6173,
):
    return calculate_panchanga(
        year,
        month,
        day,
        timezone,
        latitude,
        longitude,
        hour,
        minute,
    )


@app.get("/panchanga/text")
def panchanga_text(
    year: int,
    month: int,
    day: int,
    hour: int = 9,
    minute: int = 0,
    timezone: float = 3,
    latitude: float = 55.7558,
    longitude: float = 37.6173,
):
    data = calculate_panchanga(
        year,
        month,
        day,
        timezone,
        latitude,
        longitude,
        hour,
        minute,
    )

    return {
        "text": build_panchanga_text(data)
    }


@app.get("/panchanga/html")
def panchanga_html(
    year: int,
    month: int,
    day: int,
    hour: int = 9,
    minute: int = 0,
    timezone: float = 3,
    latitude: float = 55.7558,
    longitude: float = 37.6173,
):
    data = calculate_panchanga(
        year,
        month,
        day,
        timezone,
        latitude,
        longitude,
        hour,
        minute,
    )

    html = build_panchanga_html(data)

    return Response(
        content=html,
        media_type="text/html"
    )


@app.get("/full/html")
def full_html(
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    hour: int = 9,
    minute: int = 0,
    timezone: float = 3,
    latitude: float = 55.7558,
    longitude: float = 37.6173,
    city: str = "Москва",
):
    today = date.today()
    year = year or today.year
    month = month or today.month
    day = day or today.day

    safe_city = escape(city)
    input_date = f"{year:04d}-{month:02d}-{day:02d}"
    input_time = f"{hour:02d}:{minute:02d}"
    latitude_display = f"{latitude:.2f}"
    longitude_display = f"{longitude:.2f}"
    timezone_display = f"{timezone:+.0f}"

    panchanga_data = calculate_panchanga(
        year,
        month,
        day,
        timezone,
        latitude,
        longitude,
        hour,
        minute,
    )

    chart_data = calculate_chart(
        year,
        month,
        day,
        hour,
        minute,
        timezone,
        latitude,
        longitude,
    )
    chart_data["city"] = city
    chart_data["latitude"] = latitude
    chart_data["longitude"] = longitude

    svg_chart = generate_south_indian_svg(chart_data)

    text = build_panchanga_text(panchanga_data)

    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">

        <style>

            body {{
                --button-radius: 25px;
                --form-gap: 16px;
                font-family: Arial, sans-serif;
                background: #f5f1e8;
                color: #222;
                padding: 40px;
                line-height: 1.6;
                max-width: 1000px;
                margin: auto;
            }}

            .card {{
                background: white;
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            }}

            .intro {{
                margin-bottom: 28px;
            }}

            .intro h1 {{
                margin: 0 0 12px;
                font-size: 32px;
                line-height: 1.2;
                color: #5B3A1A;
            }}

            .intro p {{
                max-width: 860px;
                margin: 0;
                font-size: 17px;
                line-height: 1.65;
                color: #4c4338;
            }}

            .controls {{
                display: grid;
                grid-template-columns: minmax(132px, 1fr) minmax(110px, 0.8fr) minmax(280px, 1.8fr) 96px 96px 72px;
                column-gap: var(--form-gap);
                row-gap: var(--form-gap);
                align-items: start;
                margin-bottom: var(--form-gap);
            }}

            .field {{
                display: flex;
                flex-direction: column;
                gap: 6px;
            }}

            .field-city {{
                position: relative;
            }}

            label {{
                font-size: 13px;
                color: #5f5548;
            }}

            input {{
                box-sizing: border-bo
                width: 100%;
                min-height: 42px;
                border: 1px solid #d8cbb7;
                border-radius: 6px;
                padding: 8px 10px;
                font: inherit;
                background: #fffdf8;
                color: #222;
            }}

            .suggestions {{
                position: absolute;
                z-index: 10;
                top: 100%;
                left: 0;
                right: 0;
                display: none;
                max-height: 240px;
                overflow-y: auto;
                margin-top: 4px;
                border: 1px solid #d8cbb7;
                border-radius: 6px;
                background: #fffdf8;
                box-shadow: 0 8px 18px rgba(0,0,0,0.12);
            }}

            .suggestions.is-open {{
                display: block;
            }}

            .suggestion {{
                width: 100%;
                min-height: 38px;
                border: 0;
                border-radius: 0;
                padding: 8px 10px;
                background: transparent;
                color: #222;
                font-weight: 400;
                text-align: left;
                cursor: pointer;
            }}

            .suggestion:hover,
            .suggestion:focus {{
                background: #f5ead8;
                outline: none;
            }}

            .field-note {{
                font-size: 12px;
                line-height: 1.3;
                color: #7a6b58;
            }}

            button {{
                position: relative;
                overflow: hidden;
                min-height: 42px;
                border: 0;
                border-radius: var(--button-radius);
                padding: 9px 16px;
                font: inherit;
                font-weight: 600;
                background: #7b4f20;
                color: white;
                cursor: pointer;
                transition:
                    background-color 120ms ease,
                    transform 120ms ease,
                    box-shadow 120ms ease;
            }}

            button:hover {{
                background: #94612d;
            }}

            button:active {{
                animation: button-press 180ms ease;
                background: #6f4318;
                box-shadow: inset 0 2px 8px rgba(0,0,0,0.18);
                transform: scale(0.98);
            }}

            button::after {{
                content: "";
                position: absolute;
                inset: 0;
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.28), transparent);
                transform: translateX(-120%);
            }}

            button:active::after {{
                animation: button-shine 220ms ease;
            }}

            @keyframes button-press {{
                0% {{
                    transform: scale(1);
                }}
                50% {{
                    transform: scale(0.97);
                }}
                100% {{
                    transform: scale(0.98);
                }}
            }}

            @keyframes button-shine {{
                from {{
                    transform: translateX(-120%);
                }}
                to {{
                    transform: translateX(120%);
                }}
            }}

            .submit-button {{
                grid-column: 1 / -1;
                justify-self: center;
                margin: 10px 0;
            }}

            .chart {{
                text-align: center;
                margin-bottom: 30px;
            }}

            .chart svg {{
                width: 420px;
                height: 420px;
            }}

            pre {{
                white-space: pre-wrap;
                font-family: Arial, sans-serif;
                font-size: 17px;
                line-height: 1.8;
            }}

            @media (max-width: 820px) {{
                body {{
                    padding: 16px;
                }}

                .card {{
                    padding: 18px;
                }}

                .intro {{
                    margin-bottom: 22px;
                }}

                .intro h1 {{
                    font-size: 24px;
                }}

                .intro p {{
                    font-size: 15px;
                }}

                .controls {{
                    grid-template-columns: repeat(6, minmax(0, 1fr));
                }}

                .field-date,
                .field-time {{
                    grid-column: span 3;
                }}

                .field-city {{
                    grid-column: span 6;
                }}

                .field-timezone {{
                    grid-column: 1 / span 2;
                    grid-row: 4;
                }}

                .field-latitude {{
                    grid-column: 3 / span 2;
                    grid-row: 4;
                }}

                .field-longitude {{
                    grid-column: 5 / span 2;
                    grid-row: 4;
                }}

                .submit-button {{
                    grid-column: 1 / -1;
                    grid-row: 5;
                    width: min(100%, 240px);
                }}
            }}

        </style>
        <script>
            function syncDateTimeFields(form) {{
                const dateValue = form.querySelector("#date").value;
                const timeValue = form.querySelector("#time").value || "09:00";

                if (dateValue) {{
                    const parts = dateValue.split("-");
                    form.querySelector("[name='year']").value = parts[0];
                    form.querySelector("[name='month']").value = parts[1];
                    form.querySelector("[name='day']").value = parts[2];
                }}

                const timeParts = timeValue.split(":");
                form.querySelector("[name='hour']").value = timeParts[0];
                form.querySelector("[name='minute']").value = timeParts[1];
            }}

            function debounce(fn, delay) {{
                let timer = null;
                return (...args) => {{
                    window.clearTimeout(timer);
                    timer = window.setTimeout(() => fn(...args), delay);
                }};
            }}

            function formatTimezoneOffset(hours) {{
                const roundedHours = Math.round(Number(hours));
                return `${{roundedHours >= 0 ? "+" : ""}}${{roundedHours}}`;
            }}

            function estimateTimezoneFromLongitude(longitude) {{
                return Math.max(-12, Math.min(14, Math.round(longitude / 15)));
            }}

            function formatCoordinate(value) {{
                return Number(value).toFixed(2);
            }}

            async function resolveTimezone(latitude, longitude) {{
                const url = new URL("https://timeapi.io/api/TimeZone/coordinate");
                url.searchParams.set("latitude", latitude);
                url.searchParams.set("longitude", longitude);

                const response = await fetch(url);
                if (!response.ok) {{
                    throw new Error("Timezone lookup failed");
                }}

                const data = await response.json();
                const offsetSeconds = data.currentUtcOffset && data.currentUtcOffset.seconds;
                if (typeof offsetSeconds !== "number") {{
                    throw new Error("Timezone response has no offset");
                }}

                return offsetSeconds / 3600;
            }}

            async function fetchCities(query, countryCode) {{
                const url = new URL("https://nominatim.openstreetmap.org/search");
                url.searchParams.set("q", query);
                url.searchParams.set("format", "jsonv2");
                url.searchParams.set("addressdetails", "1");
                url.searchParams.set("limit", "10");
                url.searchParams.set("featuretype", "city");
                url.searchParams.set("accept-language", "ru");
                if (countryCode) {{
                    url.searchParams.set("countrycodes", countryCode);
                }}

                const response = await fetch(url);
                if (!response.ok) {{
                    throw new Error("City lookup failed");
                }}

                return await response.json();
            }}

            function placeKey(place) {{
                const title = getCityTitle(place).toLowerCase();
                const lat = Number(place.lat).toFixed(2);
                const lon = Number(place.lon).toFixed(2);
                return `${{title}}|${{lat}}|${{lon}}`;
            }}

            function dedupePlaces(places) {{
                const seen = new Set();
                const unique = [];

                for (const place of places) {{
                    const key = placeKey(place);
                    if (seen.has(key)) {{
                        continue;
                    }}

                    seen.add(key);
                    unique.push(place);
                }}

                return unique;
            }}

            function sortRussianFirst(places) {{
                return places.sort((a, b) => {{
                    const aCountry = ((a.address && a.address.country_code) || "").toLowerCase();
                    const bCountry = ((b.address && b.address.country_code) || "").toLowerCase();
                    if (aCountry === "ru" && bCountry !== "ru") {{
                        return -1;
                    }}
                    if (aCountry !== "ru" && bCountry === "ru") {{
                        return 1;
                    }}
                    return 0;
                }});
            }}

            function normalizeAddressPart(part) {{
                return String(part || "")
                    .trim()
                    .toLowerCase()
                    .replace(/^город\\s+/, "")
                    .replace(/^городской округ\\s+/, "")
                    .replace("ё", "е");
            }}

            function getPlaceCity(place) {{
                const address = place.address || {{}};
                return (
                    address.city ||
                    address.town ||
                    address.village ||
                    address.municipality ||
                    place.name
                );
            }}

            function sortExactCityFirst(places, query) {{
                const normalizedQuery = normalizeAddressPart(query);

                return places.sort((a, b) => {{
                    const aExact = normalizeAddressPart(getPlaceCity(a)) === normalizedQuery;
                    const bExact = normalizeAddressPart(getPlaceCity(b)) === normalizedQuery;
                    if (aExact && !bExact) {{
                        return -1;
                    }}
                    if (!aExact && bExact) {{
                        return 1;
                    }}
                    return 0;
                }});
            }}

            async function searchCities(query) {{
                const russianPlaces = await fetchCities(query, "ru");
                if (russianPlaces.length >= 8) {{
                    return sortExactCityFirst(dedupePlaces(russianPlaces), query).slice(0, 8);
                }}

                const globalPlaces = await fetchCities(query);
                return sortExactCityFirst(sortRussianFirst(
                    dedupePlaces([...russianPlaces, ...globalPlaces])
                ), query).slice(0, 8);
            }}

            function getCityTitle(place) {{
                const address = place.address || {{}};
                const city = getPlaceCity(place);
                const region = address.state || address.region || address.county || "";
                const parts = [city, region].filter(Boolean);
                const seen = new Set();

                return parts.filter((part) => {{
                    const key = normalizeAddressPart(part);

                    if (seen.has(key)) {{
                        return false;
                    }}

                    seen.add(key);
                    return true;
                }}).join(", ");
            }}

            function setupCityAutocomplete() {{
                const cityInput = document.querySelector("#city");
                const latInput = document.querySelector("#latitude");
                const lonInput = document.querySelector("#longitude");
                const timezoneInput = document.querySelector("#timezone");
                const suggestions = document.querySelector("#city-suggestions");
                const note = document.querySelector("#city-note");

                function closeSuggestions() {{
                    suggestions.classList.remove("is-open");
                    suggestions.innerHTML = "";
                }}

                async function selectCity(place) {{
                    const latitude = Number(place.lat);
                    const longitude = Number(place.lon);
                    const fallbackTimezone = estimateTimezoneFromLongitude(longitude);

                    cityInput.value = getCityTitle(place);
                    latInput.value = formatCoordinate(latitude);
                    lonInput.value = formatCoordinate(longitude);
                    timezoneInput.value = formatTimezoneOffset(fallbackTimezone);
                    note.textContent = "Координаты подставлены, уточняю UTC.";
                    closeSuggestions();

                    try {{
                        const timezone = await resolveTimezone(latitude, longitude);
                        timezoneInput.value = formatTimezoneOffset(timezone);
                        note.textContent = "Координаты и UTC подставлены для текущей даты.";
                    }} catch (error) {{
                        note.textContent = "Координаты подставлены, UTC рассчитан приблизительно.";
                    }}
                }}

                function renderSuggestions(places) {{
                    suggestions.innerHTML = "";

                    if (!places.length) {{
                        closeSuggestions();
                        return;
                    }}

                    for (const place of places) {{
                        const button = document.createElement("button");
                        button.type = "button";
                        button.className = "suggestion";
                        button.textContent = getCityTitle(place);
                        button.addEventListener("click", () => selectCity(place));
                        suggestions.appendChild(button);
                    }}

                    suggestions.classList.add("is-open");
                }}

                const handleInput = debounce(async () => {{
                    const query = cityInput.value.trim();
                    if (query.length < 2) {{
                        note.textContent = "";
                        closeSuggestions();
                        return;
                    }}

                    note.textContent = "Ищу город.";
                    try {{
                        const places = await searchCities(query);
                        renderSuggestions(places);
                        note.textContent = places.length ? "Выберите город из списка." : "Город не найден.";
                    }} catch (error) {{
                        note.textContent = "Не удалось загрузить базу городов.";
                        closeSuggestions();
                    }}
                }}, 350);

                cityInput.addEventListener("input", handleInput);
                document.addEventListener("click", (event) => {{
                    if (!cityInput.parentElement.contains(event.target)) {{
                        closeSuggestions();
                    }}
                }});
            }}

            function setupInfoblockToggle() {{
                const toggle = document.querySelector("#toggle-infoblock");
                const infoblock = document.querySelector(".chart-infoblock-data");
                const eyeOn = document.querySelector(".chart-eye-on");
                const eyeOff = document.querySelector(".chart-eye-off");
                if (!toggle || !infoblock || !eyeOn || !eyeOff) {{
                    return;
                }}

                let hidden = false;

                function updateToggle() {{
                    infoblock.style.display = hidden ? "none" : "";
                    eyeOn.style.display = hidden ? "none" : "";
                    eyeOff.style.display = hidden ? "" : "none";
                    toggle.setAttribute(
                        "aria-label",
                        hidden ? "Показать данные инфоблока карты" : "Скрыть данные инфоблока карты"
                    );
                }}

                function toggleInfoblock() {{
                    hidden = !hidden;
                    updateToggle();
                }}

                toggle.addEventListener("click", toggleInfoblock);
                toggle.addEventListener("keydown", (event) => {{
                    if (event.key === "Enter" || event.key === " ") {{
                        event.preventDefault();
                        toggleInfoblock();
                    }}
                }});
                updateToggle();
            }}

            window.addEventListener("DOMContentLoaded", () => {{
                setupCityAutocomplete();
                setupInfoblockToggle();
            }});
        </script>
    </head>

    <body>

        <div class="card">

            <section class="intro">
                <h1>Ведический календарь Панчанга и астрологическая карта на каждый день</h1>
                <p>Профессиональный астролог всегда начинает день со взгляда на небо и понимания качества времени. Здесь вы можете построить Джйотиш-карту на каждый день, согласно Ведическому лунному календарю Панчанга с автоматическим анализом характеристик дня. Вы сможете оценить день недели, лунные сутки, накшатру (созвездие) в котором сейчас находится Луна и получить полезные рекомендации.</p>
            </section>

            <form class="controls" method="get" action="/full/html" onsubmit="syncDateTimeFields(this)">
                <div class="field field-date">
                    <label for="date">Дата</label>
                    <input id="date" type="date" value="{input_date}">
                    <input name="year" type="hidden" value="{year}">
                    <input name="month" type="hidden" value="{month}">
                    <input name="day" type="hidden" value="{day}">
                </div>

                <div class="field field-time">
                    <label for="time">Время</label>
                    <input id="time" type="time" value="{input_time}">
                    <input name="hour" type="hidden" value="{hour}">
                    <input name="minute" type="hidden" value="{minute}">
                </div>

                <div class="field field-city">
                    <label for="city">Город</label>
                    <input id="city" name="city" type="text" value="{safe_city}">
                    <div id="city-suggestions" class="suggestions"></div>
                    <div id="city-note" class="field-note" aria-live="polite"></div>
                </div>

                <div class="field field-latitude">
                    <label for="latitude">Широта</label>
                    <input id="latitude" name="latitude" type="number" step="0.01" value="{latitude_display}">
                </div>

                <div class="field field-longitude">
                    <label for="longitude">Долгота</label>
                    <input id="longitude" name="longitude" type="number" step="0.01" value="{longitude_display}">
                </div>

                <div class="field field-timezone">
                    <label for="timezone">UTC</label>
                    <input id="timezone" name="timezone" type="text" inputmode="numeric" pattern="[+-]?[0-9]+" value="{timezone_display}">
                </div>

                <button class="submit-button" type="submit">Рассчитать</button>
            </form>

            <div class="chart">
                {svg_chart}
            </div>

            <pre>{text}</pre>

        </div>

    </body>
    </html>
    """

    return Response(
        content=html,
        media_type="text/html"
    )


@app.get("/chart/svg")
def chart_svg(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    timezone: float,
    latitude: float,
    longitude: float,
    city: str = "Москва",
    chart_title: str = "Панчанга",
):
    data = calculate_chart(
        year,
        month,
        day,
        hour,
        minute,
        timezone,
        latitude,
        longitude,
    )
    data["city"] = city
    data["title"] = chart_title
    data["latitude"] = latitude
    data["longitude"] = longitude

    svg = generate_south_indian_svg(data)

    return Response(
        content=svg,
        media_type="image/svg+xml"
    )
