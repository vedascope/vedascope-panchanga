from html import escape
from datetime import date, timedelta
from typing import Annotated
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from astro.panchanga import calculate_panchanga
from astro.chart import calculate_chart

from astro.south_chart import generate_north_indian_svg, generate_south_indian_svg

from astro.text_builder import build_panchanga_text
from astro.html_builder import build_panchanga_html


app = FastAPI()

YearParam = Annotated[int, Query(ge=1900, le=2100)]
OptionalYearParam = Annotated[int | None, Query(ge=1900, le=2100)]
MonthParam = Annotated[int, Query(ge=1, le=12)]
OptionalMonthParam = Annotated[int | None, Query(ge=1, le=12)]
DayParam = Annotated[int, Query(ge=1, le=31)]
OptionalDayParam = Annotated[int | None, Query(ge=1, le=31)]
HourParam = Annotated[int, Query(ge=0, le=23)]
MinuteParam = Annotated[int, Query(ge=0, le=59)]
TimezoneParam = Annotated[float, Query(ge=-12, le=14)]
LatitudeParam = Annotated[float, Query(ge=-90, le=90)]
LongitudeParam = Annotated[float, Query(ge=-180, le=180)]


def validate_calendar_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid calendar date",
        ) from exc


def build_error_html(message):
    safe_message = escape(message)
    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{safe_message}</title>
        <style>
            body {{
                --mono-font: "IBM Plex Mono", "Space Mono", monospace;
                display: grid;
                min-height: 100vh;
                place-items: center;
                margin: 0;
                padding: 24px;
                box-sizing: border-box;
                font-family: var(--mono-font);
                background: #f5f1e8;
                color: #222;
            }}

            .card {{
                width: min(100%, 520px);
                padding: 28px;
                border-radius: 8px;
                background: #fffdf8;
                box-shadow: 0 2px 12px rgba(0,0,0,0.08);
                text-align: center;
            }}

            h1 {{
                margin: 0;
                font-size: 22px;
                line-height: 1.25;
                font-weight: 600;
                color: #5B3A1A;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>{safe_message}</h1>
        </div>
    </body>
    </html>
    """


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/full/html":
        return Response(
            content=build_error_html("Invalid request parameters"),
            media_type="text/html",
            status_code=400,
        )

    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors()},
    )


@app.get("/")
def root():
    return {"status": "Panchanga API running"}


@app.get("/panchanga")
def panchanga(
    year: YearParam,
    month: MonthParam,
    day: DayParam,
    hour: HourParam = 9,
    minute: MinuteParam = 0,
    timezone: TimezoneParam = 3,
    latitude: LatitudeParam = 55.7558,
    longitude: LongitudeParam = 37.6173,
):
    validate_calendar_date(year, month, day)

    return calculate_panchanga(
        year=year,
        month=month,
        day=day,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        hour=hour,
        minute=minute,
    )


@app.get("/panchanga/text")
def panchanga_text(
    year: YearParam,
    month: MonthParam,
    day: DayParam,
    hour: HourParam = 9,
    minute: MinuteParam = 0,
    timezone: TimezoneParam = 3,
    latitude: LatitudeParam = 55.7558,
    longitude: LongitudeParam = 37.6173,
):
    validate_calendar_date(year, month, day)

    data = calculate_panchanga(
        year=year,
        month=month,
        day=day,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        hour=hour,
        minute=minute,
    )

    return {
        "text": build_panchanga_text(data)
    }


@app.get("/panchanga/html")
def panchanga_html(
    year: YearParam,
    month: MonthParam,
    day: DayParam,
    hour: HourParam = 9,
    minute: MinuteParam = 0,
    timezone: TimezoneParam = 3,
    latitude: LatitudeParam = 55.7558,
    longitude: LongitudeParam = 37.6173,
):
    validate_calendar_date(year, month, day)

    data = calculate_panchanga(
        year=year,
        month=month,
        day=day,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        hour=hour,
        minute=minute,
    )

    html = build_panchanga_html(data)

    return Response(
        content=html,
        media_type="text/html"
    )


@app.get("/full/html")
def full_html(
    year: OptionalYearParam = None,
    month: OptionalMonthParam = None,
    day: OptionalDayParam = None,
    hour: HourParam = 9,
    minute: MinuteParam = 0,
    timezone: TimezoneParam = 3,
    latitude: LatitudeParam = 55.7558,
    longitude: LongitudeParam = 37.6173,
    city: str = "Москва",
    chart_style: str = "south",
):
    today = date.today()
    year = year or today.year
    month = month or today.month
    day = day or today.day

    try:
        current_date = validate_calendar_date(year, month, day)
    except HTTPException as exc:
        return Response(
            content=build_error_html(exc.detail),
            media_type="text/html",
            status_code=400,
        )

    safe_city = escape(city)
    input_date = f"{year:04d}-{month:02d}-{day:02d}"
    input_time = f"{hour:02d}:{minute:02d}"
    latitude_display = f"{latitude:.2f}"
    longitude_display = f"{longitude:.2f}"
    timezone_display = f"{timezone:+.0f}"
    current_chart_style = chart_style if chart_style in ("south", "north") else "south"
    south_chart_class = "chart-svg" if current_chart_style == "south" else "chart-svg is-hidden"
    north_chart_class = "chart-svg" if current_chart_style == "north" else "chart-svg is-hidden"

    def build_day_url(target_date):
        query = urlencode({
            "year": target_date.year,
            "month": target_date.month,
            "day": target_date.day,
            "hour": hour,
            "minute": minute,
            "timezone": timezone,
            "latitude": latitude,
            "longitude": longitude,
            "city": city,
            "chart_style": current_chart_style,
        })
        return f"/full/html?{query}#chart"

    previous_day_url = build_day_url(current_date - timedelta(days=1))
    next_day_url = build_day_url(current_date + timedelta(days=1))

    panchanga_data = calculate_panchanga(
        year=year,
        month=month,
        day=day,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        hour=hour,
        minute=minute,
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

    south_svg_chart = generate_south_indian_svg(chart_data)
    north_svg_chart = generate_north_indian_svg(chart_data)

    text = build_panchanga_text(panchanga_data)

    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Ведический календарь Панчанга на сегодня</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">

        <style>

            body {{
                --button-radius: 25px;
                --form-gap: 16px;
                --mono-font: "IBM Plex Mono", "Space Mono", monospace;
                font-family: var(--mono-font);
                background: #f5f1e8;
                color: #222;
                padding: 40px;
                line-height: 1.58;
                letter-spacing: 0;
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
                margin-bottom: 24px;
            }}

            .intro h1 {{
                margin: 0 0 12px;
                font-size: 32px;
                line-height: 1.16;
                font-weight: 600;
                color: #5B3A1A;
            }}

            .intro p {{
                max-width: 860px;
                margin: 0;
                font-size: 17px;
                line-height: 1.62;
                font-weight: 400;
                color: #4c4338;
            }}

            .controls {{
                display: grid;
                grid-template-columns: minmax(132px, 1fr) minmax(110px, 0.8fr) minmax(280px, 1.8fr) auto;
                column-gap: var(--form-gap);
                row-gap: var(--form-gap);
                align-items: start;
                margin-bottom: 8px;
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
                font-weight: 500;
                color: #5f5548;
            }}

            input {{
                box-sizing: border-box;
                width: 100%;
                min-height: 42px;
                border: 1px solid #d8cbb7;
                border-radius: 6px;
                padding: 8px 10px;
                font: inherit;
                font-weight: 400;
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
                font-weight: 400;
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
                grid-column: auto;
                align-self: start;
                justify-self: stretch;
                height: 42px;
                min-width: 140px;
                margin: 27px 0 0;
                padding-top: 0;
                padding-bottom: 0;
                white-space: nowrap;
            }}

            .chart {{
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 470px;
                text-align: center;
                margin-bottom: 4px;
                scroll-margin-top: 24px;
            }}

            .chart svg {{
                width: 420px;
                height: 420px;
            }}

            .chart-svg.is-hidden {{
                display: none;
            }}

            .day-nav {{
                display: flex;
                flex-wrap: wrap;
                justify-content: center;
                gap: 12px;
                margin: 0 0 18px;
            }}

            .day-nav a {{
                box-sizing: border-box;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 42px;
                border: 1px solid #d8cbb7;
                border-radius: var(--button-radius);
                padding: 9px 16px;
                background: #fffdf8;
                color: #5B3A1A;
                font-weight: 600;
                text-decoration: none;
                transition:
                    background-color 120ms ease,
                    border-color 120ms ease,
                    color 120ms ease,
                    transform 120ms ease;
            }}

            .day-nav a:hover {{
                border-color: #C69214;
                background: #f5ead8;
                color: #3f2812;
            }}

            .day-nav a:active {{
                transform: scale(0.98);
            }}

            @media (prefers-color-scheme: dark) {{
                .day-nav a {{
                    border-color: #8b765b;
                    background: #2a241d;
                    color: #f2dfbd;
                }}

                .day-nav a:hover {{
                    border-color: #D4AF37;
                    background: #3a3025;
                    color: #fff3d4;
                }}
            }}

            pre {{
                white-space: pre-wrap;
                font-family: var(--mono-font);
                font-size: 17px;
                line-height: 1.68;
                font-weight: 400;
            }}

            .panchanga-output {{
                white-space: normal;
                margin-top: 0;
            }}

            .page-footer {{
                margin-top: 34px;
                padding-top: 22px;
                border-top: 1px solid #eadcc6;
                color: #4c4338;
            }}

            .footer-title {{
                margin: 0 0 6px;
                font-size: 16px;
                line-height: 1.35;
                font-weight: 600;
                color: #5B3A1A;
            }}

            .footer-section {{
                padding: 0;
            }}

            .footer-section + .footer-section {{
                margin-top: 18px;
                padding-top: 18px;
                border-top: 1px solid #f0e4d2;
            }}

            .footer-copy {{
                max-width: 780px;
                margin: 0 0 12px;
                font-size: 14px;
                line-height: 1.48;
                color: #6b5c4b;
            }}

            .footer-links {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
            }}

            .footer-link {{
                box-sizing: border-box;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                min-height: 40px;
                border: 1px solid #d8cbb7;
                border-radius: var(--button-radius);
                padding: 8px 14px;
                background: #fffdf8;
                color: #5B3A1A;
                font-size: 14px;
                line-height: 1.25;
                font-weight: 600;
                text-decoration: none;
                transition:
                    background-color 120ms ease,
                    border-color 120ms ease,
                    color 120ms ease,
                    transform 120ms ease;
            }}

            .footer-link:hover {{
                border-color: #C69214;
                background: #f5ead8;
                color: #3f2812;
            }}

            .footer-link:active {{
                transform: scale(0.98);
            }}

            .footer-link svg {{
                width: 18px;
                height: 18px;
                flex: 0 0 auto;
                fill: currentColor;
            }}

            @media (prefers-color-scheme: dark) {{
                .page-footer {{
                    border-top-color: #4a3d30;
                    color: #e6d5ba;
                }}

                .footer-title {{
                    color: #f2dfbd;
                }}

                .footer-section + .footer-section {{
                    border-top-color: #4a3d30;
                }}

                .footer-copy {{
                    color: #d8c4a5;
                }}

                .footer-link {{
                    border-color: #8b765b;
                    background: #2a241d;
                    color: #f2dfbd;
                }}

                .footer-link:hover {{
                    border-color: #D4AF37;
                    background: #3a3025;
                    color: #fff3d4;
                }}
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

                .submit-button {{
                    grid-column: 1 / -1;
                    grid-row: 4;
                    justify-self: center;
                    width: min(100%, 240px);
                    margin: 0;
                }}

                .chart {{
                    min-height: 430px;
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
                const toggles = document.querySelectorAll(".chart-infoblock-toggle");
                const infoblocks = document.querySelectorAll(".chart-infoblock-data");
                const eyeOns = document.querySelectorAll(".chart-eye-on");
                const eyeOffs = document.querySelectorAll(".chart-eye-off");
                if (!toggles.length || !infoblocks.length || !eyeOns.length || !eyeOffs.length) {{
                    return;
                }}

                let hidden = false;

                function updateToggle() {{
                    infoblocks.forEach((infoblock) => {{
                        infoblock.style.display = hidden ? "none" : "";
                    }});
                    eyeOns.forEach((eyeOn) => {{
                        eyeOn.style.display = hidden ? "none" : "";
                    }});
                    eyeOffs.forEach((eyeOff) => {{
                        eyeOff.style.display = hidden ? "" : "none";
                    }});
                    toggles.forEach((toggle) => {{
                        toggle.setAttribute(
                            "aria-label",
                            hidden ? "Показать данные инфоблока карты" : "Скрыть данные инфоблока карты"
                        );
                    }});
                }}

                function toggleInfoblock() {{
                    hidden = !hidden;
                    updateToggle();
                }}

                toggles.forEach((toggle) => {{
                    toggle.addEventListener("click", toggleInfoblock);
                    toggle.addEventListener("keydown", (event) => {{
                        if (event.key === "Enter" || event.key === " ") {{
                            event.preventDefault();
                            toggleInfoblock();
                        }}
                    }});
                }});
                updateToggle();
            }}

            function setupChartStyleToggle() {{
                const toggles = document.querySelectorAll(".chart-style-toggle");
                const southChart = document.querySelector("[data-chart-style='south']");
                const northChart = document.querySelector("[data-chart-style='north']");
                const chartStyleInput = document.querySelector("[name='chart_style']");
                const dayNavLinks = document.querySelectorAll(".day-nav a");
                if (!toggles.length || !southChart || !northChart) {{
                    return;
                }}

                let currentStyle = "{current_chart_style}";

                function setLinkChartStyle(link) {{
                    const url = new URL(link.href, window.location.origin);
                    url.searchParams.set("chart_style", currentStyle);
                    url.hash = "chart";
                    link.href = `${{url.pathname}}${{url.search}}${{url.hash}}`;
                }}

                function updateStyle() {{
                    southChart.classList.toggle("is-hidden", currentStyle !== "south");
                    northChart.classList.toggle("is-hidden", currentStyle !== "north");
                    if (chartStyleInput) {{
                        chartStyleInput.value = currentStyle;
                    }}
                    dayNavLinks.forEach(setLinkChartStyle);
                    toggles.forEach((toggle) => {{
                        toggle.setAttribute(
                            "aria-label",
                            currentStyle === "south"
                                ? "Переключить на северный стиль карты"
                                : "Переключить на южный стиль карты"
                        );
                    }});
                }}

                function toggleStyle() {{
                    currentStyle = currentStyle === "south" ? "north" : "south";
                    updateStyle();
                }}

                toggles.forEach((toggle) => {{
                    toggle.addEventListener("click", toggleStyle);
                    toggle.addEventListener("keydown", (event) => {{
                        if (event.key === "Enter" || event.key === " ") {{
                            event.preventDefault();
                            toggleStyle();
                        }}
                    }});
                }});
                updateStyle();
            }}

            window.addEventListener("DOMContentLoaded", () => {{
                setupCityAutocomplete();
                setupInfoblockToggle();
                setupChartStyleToggle();
            }});
        </script>
    </head>

    <body>

        <div class="card">

            <section class="intro">
                <h1>Ведический календарь Панчанга на сегодня</h1>
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

                <input id="latitude" name="latitude" type="hidden" value="{latitude_display}">
                <input id="longitude" name="longitude" type="hidden" value="{longitude_display}">
                <input id="timezone" name="timezone" type="hidden" value="{timezone_display}">

                <input name="chart_style" type="hidden" value="{current_chart_style}">

                <button class="submit-button" type="submit">Рассчитать</button>
            </form>

            <div id="chart" class="chart">
                <div class="{south_chart_class}" data-chart-style="south">
                    {south_svg_chart}
                </div>
                <div class="{north_chart_class}" data-chart-style="north">
                    {north_svg_chart}
                </div>
            </div>

            <nav class="day-nav" aria-label="Навигация по дням">
                <a href="{previous_day_url}">← Предыдущий день</a>
                <a href="{next_day_url}">Следующий день →</a>
            </nav>

            <div class="panchanga-output">
                {text}
            </div>

            <footer class="page-footer">
                <section class="footer-section">
                    <p class="footer-title">Личные консультации</p>
                    <p class="footer-copy">Для личных консультаций и разбора натальной карты пишите в Telegram.</p>
                    <div class="footer-links">
                        <a class="footer-link" href="https://t.me/vedascopebot" target="_blank" rel="noopener noreferrer">
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                                <path d="M21.8 4.4 18.5 20c-.2 1-1 1.2-1.8.7l-5-3.7-2.4 2.3c-.3.3-.5.5-1 .5l.4-5.2 9.4-8.5c.4-.4-.1-.6-.6-.2L5.8 13.2.8 11.6c-1-.3-1-1 .2-1.5L20.4 2.6c.9-.3 1.7.2 1.4 1.8Z"/>
                            </svg>
                            Telegram @vedascopebot
                        </a>
                    </div>
                </section>

                <section class="footer-section">
                    <p class="footer-title">Канал о Джйотиш-астрологии Vedascope</p>
                    <p class="footer-copy">Подписывайтесь на Vedascope: примеры разборов, интервью с Гуру, обсуждения практики Джйотиш и другие материалы.</p>
                    <div class="footer-links">
                        <a class="footer-link" href="https://t.me/vedascope" target="_blank" rel="noopener noreferrer">
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                                <path d="M21.8 4.4 18.5 20c-.2 1-1 1.2-1.8.7l-5-3.7-2.4 2.3c-.3.3-.5.5-1 .5l.4-5.2 9.4-8.5c.4-.4-.1-.6-.6-.2L5.8 13.2.8 11.6c-1-.3-1-1 .2-1.5L20.4 2.6c.9-.3 1.7.2 1.4 1.8Z"/>
                            </svg>
                            Telegram @vedascope
                        </a>
                        <a class="footer-link" href="https://www.youtube.com/@vedascope" target="_blank" rel="noopener noreferrer">
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                                <path d="M23.5 6.2s-.2-1.7-.9-2.4c-.9-.9-1.8-.9-2.3-1C17.1 2.5 12 2.5 12 2.5s-5.1 0-8.3.3c-.5.1-1.5.1-2.3 1C.7 4.5.5 6.2.5 6.2S.2 8.1.2 10v1.8c0 1.9.3 3.8.3 3.8s.2 1.7.9 2.4c.9.9 2 .9 2.5 1 1.8.2 8.1.3 8.1.3s5.1 0 8.3-.3c.5-.1 1.5-.1 2.3-1 .7-.7.9-2.4.9-2.4s.3-1.9.3-3.8V10c0-1.9-.3-3.8-.3-3.8ZM9.6 14.1V7.5l6.4 3.3-6.4 3.3Z"/>
                            </svg>
                            YouTube @vedascope
                        </a>
                        <a class="footer-link" href="https://vk.com/vedascope" target="_blank" rel="noopener noreferrer">
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                                <path d="M13.2 17.8c-5.1 0-8-3.5-8.1-9.3h2.6c.1 4.3 2 6.1 3.5 6.5V8.5h2.5v3.7c1.5-.2 3-1.8 3.5-3.7h2.5c-.4 2.3-2.1 3.9-3.3 4.6 1.2.6 3.2 2 4 4.7h-2.8c-.5-1.8-1.9-3.2-3.4-3.5v3.5h-.5Z"/>
                            </svg>
                            VK @vedascope
                        </a>
                    </div>
                </section>
            </footer>

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
    year: YearParam,
    month: MonthParam,
    day: DayParam,
    hour: HourParam,
    minute: MinuteParam,
    timezone: TimezoneParam,
    latitude: LatitudeParam,
    longitude: LongitudeParam,
    city: str = "Москва",
    chart_title: str = "Панчанга",
):
    validate_calendar_date(year, month, day)

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
