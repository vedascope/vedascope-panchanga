from datetime import datetime


VARA_SHORT = {
    "Monday": "Mo",
    "Tuesday": "Ma",
    "Wednesday": "Me",
    "Thursday": "Ju",
    "Friday": "Ve",
    "Saturday": "Sa",
    "Sunday": "Su",
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


def format_list(items):
    html = '<div class="compact-list">'

    for item in items:
        html += f"<div>• {item}</div>"

    html += "</div>"

    return html


def format_day_periods(periods):
    if not periods:
        return ""

    abhijit = periods.get("abhijit_muhurta")
    rahu_kalam = periods.get("rahu_kalam")
    yamaganda = periods.get("yamaganda")
    gulika = periods.get("gulika")
    tithi_end = periods.get("tithi_end")
    nakshatra_end = periods.get("nakshatra_end")

    html = """
<h2>Важные периоды дня</h2>
<div class="day-periods">
"""

    if periods.get("sunrise"):
        html += f'<div class="period-line">🌅 Восход: {periods["sunrise"]}</div>'
    if periods.get("sunset"):
        html += f'<div class="period-line">🌇 Закат: {periods["sunset"]}</div>'
    if abhijit:
        html += (
            f'<div class="period-item"><strong>🕉 Абхиджит-мухурта: '
            f'{abhijit["start"]}–{abhijit["end"]}</strong>'
            f'<span>Благоприятное время для важных начинаний и действий, '
            f'особенно если нет возможности подобрать отдельную мухурту.</span></div>'
        )
    if rahu_kalam:
        html += (
            f'<div class="period-item"><strong>☠️ Раху Кала: '
            f'{rahu_kalam["start"]}–{rahu_kalam["end"]}</strong>'
            f'<span>Нежелательно начинать новые проекты, поездки, крупные '
            f'покупки и важные переговоры.</span></div>'
        )
    if yamaganda:
        html += (
            f'<div class="period-item"><strong>🌑 Ямаганда: '
            f'{yamaganda["start"]}–{yamaganda["end"]}</strong>'
            f'<span>Неблагоприятна для начала поездок, путешествий и новых '
            f'инициатив.</span></div>'
        )
    if gulika:
        html += (
            f'<div class="period-item"><strong>⚫ Гулика: '
            f'{gulika["start"]}–{gulika["end"]}</strong>'
            f'<span>Подходит для дисциплины, исследований, уединенной работы '
            f'и долгосрочных процессов.</span></div>'
        )

    if tithi_end:
        html += f'<div class="period-line">⏳ Титхи действуют до {tithi_end["ends_at"]}</div>'
    if nakshatra_end:
        html += (
            f'<div class="period-line">⏳ Накшатра действует до '
            f'{nakshatra_end["ends_at"]}</div>'
        )

    html += "</div>"

    return html


def build_panchanga_text(panchanga):
    date_obj = datetime.strptime(panchanga["date"], "%Y-%m-%d")

    day = date_obj.day
    month = MONTHS_RU[date_obj.month]
    year = date_obj.year

    vara = panchanga["vara"]
    tithi = panchanga["tithi"]
    nakshatra = panchanga["nakshatra"]

    vara_data = vara["data"]
    tithi_data = tithi["data"]
    nak_data = nakshatra["data"]
    moon_data = panchanga["moon"]["data"]

    moon_rashi_name = moon_data["ru"]
    moon_rashi_emoji = moon_data["emoji"]

    vara_short = VARA_SHORT.get(vara["key"], "")
    nakshatra_types = ", ".join(nak_data["types"])

    subtitle = (
        f'{vara_data["ru"]} ({vara_short})'
        f' | {tithi_data["display"]}'
        f' | Луна в накшатре {nak_data["ru"]}'
    )

    html = f"""
<div class="panchanga-text"><style>
.panchanga-text {{ font-family: "IBM Plex Mono", "Space Mono", monospace; line-height: 1.54; color: inherit; }}
.panchanga-text h1 {{ font-size: 28px; margin: 0 0 6px 0; line-height: 1.14; font-weight: 600; }}
.panchanga-text h2 {{ font-size: 20px; margin: 20px 0 6px 0; line-height: 1.2; font-weight: 600; }}
.panchanga-text h3 {{ font-size: 15px; margin: 7px 0 0 0; line-height: 1.24; font-weight: 600; }}
.panchanga-text p {{ margin: 0; }}
.panchanga-text p + p {{ margin-top: 1.4em; }}
.compact-list {{ margin: 0; line-height: 1.42; }}
.compact-list div {{ margin: 0; padding: 0; }}
.day-periods {{ margin: 0 0 18px; line-height: 1.42; }}
.period-line {{ margin: 0; padding: 0; }}
.period-item {{ margin: 4px 0; padding: 0; }}
.period-item strong {{ display: block; font-weight: 600; }}
.period-item span {{ display: block; opacity: 0.86; }}
.subtitle {{ opacity: 0.72; margin-bottom: 10px; font-size: 13px; line-height: 1.34; }}
</style>
<h1>Панчанга на {day} {month} {year}</h1>
<p class="subtitle">{subtitle}</p>
{format_day_periods(panchanga.get("muhurta"))}
<h2>{vara_data["ru"]} — день {vara_data["planet_genitive"]} {vara_data["emoji"]}</h2>
<p>{vara_data["description"]}</p>
<h2>{tithi_data["display"]} ({tithi_data["ru"]})</h2>
<p><strong>{tithi_data["summary"]}</strong></p>
<p>{tithi_data["description"]}</p>
<h3>Благоприятно</h3>
{format_list(tithi_data["favorable"])}
<h3>Не рекомендуется</h3>
{format_list(tithi_data["unfavorable"])}
<h2>Луна в {moon_rashi_name} {moon_rashi_emoji}</h2>
<p><strong>{moon_data["summary"]}</strong></p>
<p>{moon_data["description"]}</p>
<h2>Луна в накшатре {nak_data["ru"]} ({nakshatra_types}) ⭐</h2>
<p><strong>{nak_data["summary"]}</strong></p>
<p>{nak_data["description"]}</p>
<h3>Благоприятно</h3>
{format_list(nak_data["favorable"])}
<h3>Не рекомендуется</h3>
{format_list(nak_data["unfavorable"])}
"""

    if tithi_data.get("rikta"):
        html += """
<h2>⚠️ Рикта-титхи — «пустые руки»</h2>
<p>Эти лунные сутки относятся к категории рикта. В классической мухурте считается, что важные дела, начатые в это время, могут не дать ожидаемого результата либо оставить ощущение неудовлетворенности итогом.</p>
<p>Лучше избегать начала долгосрочных проектов, крупных покупок и действий, направленных исключительно на получение выгоды.</p>
"""

    gandanta = nakshatra.get("gandanta")

    if gandanta and gandanta["active"]:
        html += f"""
<h2>⚠️ Ганданта Луны</h2>
<p>{gandanta["description"]}</p>
"""

    yogas = panchanga.get("yogas", [])

    if yogas:
        html += """
<h2>Йоги и влияния дня</h2>
<p>Транзит Луны формирует дополнительные психологические и событийные влияния на день.</p>
"""

        for yoga in yogas:
            html += f"""
<h3>{yoga["title"]}</h3>
<p>{yoga["description"]}</p>
"""

        html += """
<p><strong>Важно:</strong> для более точного анализа наложите транзит Луны на вашу натальную карту и посмотрите, по каким домам она проходит именно для вас. Если вас интересует личный разбор карты Джйотиш пишите в телеграм @vedascopebot</p>
"""

    html += "</div>"
    return html
