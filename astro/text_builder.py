from datetime import datetime
import html

from astro.text_catalog import (
    get_nakshatra_text,
    get_tithi_text,
    normalize_catalog_text,
)


VARA_SHORT = {
    "Monday": "Mo",
    "Tuesday": "Ma",
    "Wednesday": "Me",
    "Thursday": "Ju",
    "Friday": "Ve",
    "Saturday": "Sa",
    "Sunday": "Su",
}


WEEKDAY_ACCUSATIVE_RU = {
    "Понедельник": "понедельник",
    "Вторник": "вторник",
    "Среда": "среду",
    "Четверг": "четверг",
    "Пятница": "пятницу",
    "Суббота": "субботу",
    "Воскресенье": "воскресенье",
}


MONTHS_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def escape_html(value):
    return html.escape(str(value), quote=True)


def compact_blank_lines(text):
    lines = [line.rstrip() for line in text.splitlines()]
    compacted = []
    previous_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and previous_blank:
            continue
        compacted.append(line)
        previous_blank = is_blank
    return "\n".join(compacted).strip()


def lower_first(value):
    value = str(value or "").strip()
    return value[:1].lower() + value[1:] if value else ""


def date_label(panchanga):
    date_obj = datetime.strptime(panchanga["date"], "%Y-%m-%d")
    weekday_name = (panchanga.get("vara") or {}).get("data", {}).get("ru", "")
    weekday = WEEKDAY_ACCUSATIVE_RU.get(weekday_name, lower_first(weekday_name))
    return f"{weekday} {date_obj:%d.%m.%Y}".strip()


def period_value(periods, key):
    period = (periods or {}).get(key) or {}
    start = period.get("start")
    end = period.get("end")
    return f"{start} - {end}" if start and end else "нет данных"


def segment_name(segment):
    return (
        segment.get("display")
        or segment.get("name")
        or segment.get("key")
        or str(segment.get("index", ""))
    )


def segment_types(segment, entry):
    data = segment.get("data") or {}
    types = data.get("types") or entry.get("types") or ()
    return ", ".join(types)


def segment_start_label(segment):
    return segment.get("starts_at_time") or segment.get("starts_at")


def segment_end_label(segment):
    end = segment.get("ends_at_time") or segment.get("ends_at")
    return None if end == "конца суток" else end


def format_day_segment_line(kind, segment, segments, entry=None):
    name = segment_name(segment)
    if kind == "nakshatra":
        types = segment_types(segment, entry or {})
        name = f"{name} ({types})" if types else name
    if len(segments) == 1:
        if segment.get("publication_window"):
            return name
        return f"{name} — весь день"
    index = segments.index(segment)
    start = segment_start_label(segment)
    end = segment_end_label(segment)
    if index == 0:
        return f"до {end} — {name}" if end else name
    if index == len(segments) - 1:
        return f"с {start} — {name}" if start else name
    return f"с {start} до {end} — {name}" if start and end else name


def describe_tithi_interval(segment, segments):
    return format_day_segment_line("tithi", segment, segments)


def describe_nakshatra_interval(segment, segments, entry):
    return format_day_segment_line("nakshatra", segment, segments, entry)


def factor_text_lines(entry):
    lines = []
    short_description = entry.get("short_description")
    full_description = entry.get("full_description")
    if short_description:
        lines.append(short_description)
    if full_description and full_description != short_description:
        lines.append(full_description)
    return lines


def build_tithi_items(panchanga):
    segments = (panchanga.get("day_dynamics") or {}).get("tithi_segments") or []
    if not segments:
        tithi = panchanga.get("tithi") or {}
        data = tithi.get("data") or {}
        segments = [{
            "number": tithi.get("number"),
            "index": tithi.get("number"),
            "display": data.get("display"),
            "name": data.get("ru"),
            "data": data,
        }]

    items = []
    for segment in segments:
        entry = get_tithi_text(segment)
        items.append({
            "line": describe_tithi_interval(segment, segments),
            "name": segment_name(segment),
            "texts": factor_text_lines(entry),
        })
    return items


def build_nakshatra_items(panchanga):
    segments = (panchanga.get("day_dynamics") or {}).get("nakshatra_segments") or []
    if not segments:
        nakshatra = panchanga.get("nakshatra") or {}
        data = nakshatra.get("data") or {}
        segments = [{
            "number": nakshatra.get("number"),
            "index": nakshatra.get("number"),
            "key": nakshatra.get("key"),
            "name": data.get("ru"),
            "data": data,
        }]

    items = []
    for segment in segments:
        entry = get_nakshatra_text(segment)
        items.append({
            "line": describe_nakshatra_interval(segment, segments, entry),
            "name": segment_name(segment),
            "texts": factor_text_lines(entry),
        })
    return items


def build_current_tithi_items(panchanga):
    return build_tithi_items(panchanga)


def build_current_nakshatra_items(panchanga):
    return build_nakshatra_items(panchanga)


def build_recommendation_items(panchanga):
    items = []
    vara_item = build_vara_item(panchanga)
    moon_item = build_moon_item(panchanga)

    if vara_item:
        items.append(vara_item)
    if moon_item:
        items.append(moon_item)

    for yoga in panchanga.get("yogas") or []:
        title = yoga.get("title") or "Йога"
        description = yoga.get("description")
        if description:
            items.append({"title": title, "texts": [description]})

    return items


def build_vara_item(panchanga):
    vara_data = (panchanga.get("vara") or {}).get("data") or {}
    if vara_data.get("ru") and vara_data.get("description"):
        return {"title": vara_data["ru"], "bold_title": True, "texts": [vara_data["description"]]}
    return None


def build_moon_item(panchanga):
    moon_data = (panchanga.get("moon") or {}).get("data") or {}

    if moon_data.get("ru"):
        moon_texts = []
        if moon_data.get("summary"):
            moon_texts.append(moon_data["summary"])
        if moon_data.get("description"):
            moon_texts.append(moon_data["description"])
        if moon_texts:
            return {
                "title": f"Луна в {moon_data['ru']}",
                "bold_title": True,
                "bold_title_part": moon_data["ru"],
                "texts": moon_texts,
            }
    return None


def build_panchanga_content(panchanga, view="daily"):
    muhurta = panchanga.get("muhurta") or {}
    vedic_yoga = panchanga.get("vedic_yoga") or {}
    karana = panchanga.get("karana") or {}
    current_view = view == "current"
    return {
        "date_label": date_label(panchanga),
        "calculation_time": panchanga.get("calculation_time_local") if current_view else None,
        "sunrise": muhurta.get("sunrise"),
        "sunset": muhurta.get("sunset"),
        "rahu_kalam": period_value(muhurta, "rahu_kalam"),
        "abhijit_muhurta": period_value(muhurta, "abhijit_muhurta"),
        "tithi_items": build_current_tithi_items(panchanga) if current_view else build_tithi_items(panchanga),
        "nakshatra_items": build_current_nakshatra_items(panchanga) if current_view else build_nakshatra_items(panchanga),
        "vedic_yoga": vedic_yoga.get("ru", "нет данных"),
        "karana": karana.get("ru", "нет данных"),
        "vara_item": build_vara_item(panchanga),
        "moon_item": build_moon_item(panchanga),
        "recommendations": build_recommendation_items(panchanga),
    }


def render_telegram_title(value, bold_part=None):
    rendered = escape_html(value)
    if not bold_part:
        return rendered

    escaped_part = escape_html(bold_part)
    return rendered.replace(escaped_part, f"<b>{escaped_part}</b>", 1)


def render_telegram_factor_items(items):
    blocks = []
    for item in items:
        lines = [f"<b>{escape_html(item['line'])}</b>"]
        lines.extend(escape_html(text) for text in item["texts"] if text)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_telegram_recommendations(items):
    blocks = []
    for item in items:
        lines = [render_telegram_title(item["title"], item.get("bold_title_part"))]
        lines.extend(escape_html(text) for text in item["texts"] if text)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_telegram_item(item):
    if not item:
        return ""
    if item.get("bold_title"):
        title = f"<b>{escape_html(item['title'])}</b>"
    else:
        title = render_telegram_title(item["title"], item.get("bold_title_part"))
    lines = [title]
    lines.extend(escape_html(text) for text in item["texts"] if text)
    return "\n".join(lines)


def render_telegram_services():
    return "\n\n".join([
        "<b>Сервисы vedascope</b>",
        "Панчанга - Ведический календарь на каждый день: www.vedascope.ru/panchanga",
        "Набхаса - Реальное положение планет на сегодня: www.vedascope.ru/nabhasa",
    ])


def build_telegram_panchanga_text(panchanga):
    content = build_panchanga_content(panchanga)
    quote_lines = []
    if content["sunrise"]:
        quote_lines.append(f"🌅 Восход Солнца: {escape_html(content['sunrise'])}")
    if content["sunset"]:
        quote_lines.append(f"🌇 Закат Солнца: {escape_html(content['sunset'])}")
    quote_lines.extend([
        "",
        f"Раху-кала: {escape_html(content['rahu_kalam'])}",
        f"Абхиджит-мухурта: {escape_html(content['abhijit_muhurta'])}",
    ])

    lines = [
        f"<b>🌞 Панчанга на {escape_html(content['date_label'])}</b>",
        "",
        "<blockquote>" + "\n".join(quote_lines) + "</blockquote>",
        "",
    ]
    vara_block = render_telegram_item(content.get("vara_item"))
    if vara_block:
        lines.extend([vara_block, ""])

    lines.extend([
        "<b>🌙 Титхи</b>",
        render_telegram_factor_items(content["tithi_items"]),
        "",
    ])

    moon_block = render_telegram_item(content.get("moon_item"))
    if moon_block:
        lines.extend([moon_block, ""])

    lines.extend([
        "<b>⭐ Накшатра</b>",
        render_telegram_factor_items(content["nakshatra_items"]),
        "",
        "<b>🧘 Йога / 🔱 Карана</b>",
        f"{escape_html(content['vedic_yoga'])} / {escape_html(content['karana'])}",
    ])
    recommendations_block = render_telegram_recommendations(content["recommendations"])
    if recommendations_block:
        lines.extend(["", "<b>✨ Рекомендации</b>", recommendations_block])
    lines.extend(["", "___________", "", render_telegram_services()])
    return compact_blank_lines("\n".join(lines))


def build_telegram_compact_panchanga_text(panchanga):
    return build_telegram_panchanga_text(panchanga)


def render_html_factor_items(items):
    html_parts = []
    for item in items:
        text_parts = "".join(f"<p>{escape_html(text)}</p>" for text in item["texts"] if text)
        html_parts.append(f"<div class=\"period-item\"><strong>{escape_html(item['line'])}</strong>{text_parts}</div>")
    return "".join(html_parts)


def render_html_recommendations(items):
    html_parts = []
    for item in items:
        text_parts = "".join(f"<p>{escape_html(text)}</p>" for text in item["texts"] if text)
        html_parts.append(f"<section class=\"recommendation-item\"><h3>{escape_html(item['title'])}</h3>{text_parts}</section>")
    return "".join(html_parts)


def build_panchanga_text(panchanga, view="daily"):
    content = build_panchanga_content(panchanga, view=view)
    recommendations_html = ""
    if content["recommendations"]:
        recommendations_html = f"""
<h2>✨ Рекомендации</h2>
{render_html_recommendations(content["recommendations"])}
"""

    return f"""
<div class="panchanga-text"><style>
.panchanga-text {{ font-family: "IBM Plex Mono", "Space Mono", monospace; line-height: 1.54; color: inherit; }}
.panchanga-text h1 {{ font-size: 28px; margin: 0 0 14px 0; line-height: 1.14; font-weight: 600; }}
.panchanga-text h2 {{ font-size: 20px; margin: 22px 0 8px 0; line-height: 1.2; font-weight: 600; }}
.panchanga-text h3 {{ font-size: 15px; margin: 10px 0 4px 0; line-height: 1.24; font-weight: 600; }}
.panchanga-text p {{ margin: 0; }}
.panchanga-text p + p {{ margin-top: 0.72em; }}
.period-line {{ margin: 0; padding: 0; }}
.period-item {{ margin: 0 0 14px; padding: 0; }}
.period-item strong {{ display: block; font-weight: 600; margin-bottom: 4px; }}
.recommendation-item {{ margin: 0 0 16px; }}
</style>
<h1>🌞 Панчанга на {escape_html(content['date_label'])}</h1>
{f'<div class="period-line">Расчёт на текущее время: {escape_html(content["calculation_time"])}</div>' if content.get('calculation_time') else ''}
<div class="period-line">🌅 Восход Солнца: {escape_html(content['sunrise'] or 'нет данных')}</div>
<div class="period-line">🌇 Закат Солнца: {escape_html(content['sunset'] or 'нет данных')}</div>
<br>
<div class="period-line">Раху-кала: {escape_html(content['rahu_kalam'])}</div>
<div class="period-line">Абхиджит-мухурта: {escape_html(content['abhijit_muhurta'])}</div>
<h2>🌙 Титхи</h2>
{render_html_factor_items(content['tithi_items'])}
<h2>⭐ Накшатра</h2>
{render_html_factor_items(content['nakshatra_items'])}
<h2>🧘 Йога / 🔱 Карана</h2>
<p>{escape_html(content['vedic_yoga'])} / {escape_html(content['karana'])}</p>
{recommendations_html}
</div>
""".strip()


# Backward-compatible names used by existing tests/scripts while the user-facing
# output now uses build_telegram_panchanga_text/build_panchanga_text.
def build_tithi_task(day_dynamics):
    tithi_text = get_tithi_text((day_dynamics or {}).get("dominant_tithi"))
    return f"Задача по титхи ({tithi_text['name']}): сегодня основная задача — {tithi_text.get('task_summary', '')}."


def build_nakshatra_tone(day_dynamics):
    nakshatra_text = get_nakshatra_text((day_dynamics or {}).get("dominant_nakshatra"))
    return f"Окраска по накшатре ({nakshatra_text['name']}): энергия проходит через {nakshatra_text.get('style_summary', '')}."


def build_integrated_recommendation(day_dynamics):
    parts = [build_tithi_task(day_dynamics), build_nakshatra_tone(day_dynamics)]
    return " ".join(part for part in parts if part)


def build_final_recommendation(day_dynamics):
    return build_integrated_recommendation(day_dynamics)
