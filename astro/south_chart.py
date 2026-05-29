from html import escape


PLANET_COLORS = {
    "Su": "#8B1A1A",
    "Mo": "#2E91E5",
    "Ma": "#D00000",
    "Me": "#11823B",
    "Ju": "#F26A1B",
    "Ve": "#E0569A",
    "Sa": "#102A83",
    "Ra": "#6B3A1A",
    "Ke": "#000000",
    "Asc": "#F05A24",
}

LONGITUDE_DEGREE_MARK = "'"
PLANET_FONT_SIZE = 47
DEGREE_FONT_SIZE = 27
PLANET_BLOCK_HEIGHT = 92
GRID_ITEM_GAP = 5
HOUSE_PADDING = 32

BASE_NAME_FONT_SIZE = PLANET_FONT_SIZE
BASE_DEGREE_FONT_SIZE = DEGREE_FONT_SIZE
BASE_RETRO_LINE_WIDTH = 4
CHART_SWITCH_ICON_CLASS = "chart-switch-icon"
SVG_FONT_FAMILY = "IBM Plex Mono, Space Mono, monospace"


def estimate_text_width(text, font_size, factor=0.58):
    return len(text) * font_size * factor


def format_date(date_text):
    year, month, day = date_text.split("-")
    return f"{day}.{month}.{year}"


def format_time_with_seconds(time_text):
    if time_text.count(":") == 1:
        return f"{time_text}:00"

    return time_text


def get_center_city_layout(city_text):
    max_width = 400
    font_size = 42
    estimated_width = len(city_text) * font_size * 0.58

    if estimated_width > max_width:
        font_size = max(24, max_width / max(len(city_text) * 0.58, 1))

    if font_size == 24 and len(city_text) > 29:
        city_text = city_text[:28].rstrip() + "..."

    return city_text, round(font_size, 1)


def generate_south_indian_chart(chart_data):
    rashis = {i: [] for i in range(1, 13)}

    lagna_rashi = chart_data["lagna"]["rashi_number"]
    rashis[lagna_rashi].append("Asc")

    for graha, pdata in chart_data["planets"].items():
        rashis[pdata["rashi_number"]].append(graha)

    return {
        "rashis": rashis,
        "lagna_rashi": lagna_rashi,
    }


def get_north_indian_chart(chart_data):
    lagna_rashi = chart_data["lagna"]["rashi_number"]
    houses = {i: [] for i in range(1, 13)}
    house_rashis = {
        house: ((lagna_rashi + house - 2) % 12) + 1
        for house in range(1, 13)
    }

    houses[1].append("Asc")
    for graha, pdata in chart_data["planets"].items():
        house = ((pdata["rashi_number"] - lagna_rashi) % 12) + 1
        houses[house].append(graha)

    return {
        "houses": houses,
        "house_rashis": house_rashis,
        "lagna_rashi": lagna_rashi,
    }


def get_display_name(item, chart_data):
    if item == "Asc":
        return "As"

    return chart_data["planets"][item]["display_name"]


def get_degree(item, chart_data):
    if item == "Asc":
        return round(chart_data["lagna"]["degree_in_rashi"])

    return round(chart_data["planets"][item]["degree_in_rashi"])


def get_south_grid_shape(item_count):
    if item_count <= 1:
        return 1, 1
    if item_count == 2:
        return 1, 2
    if item_count in (3, 4):
        return 2, 2
    if item_count <= 6:
        return 2, 3
    if item_count <= 9:
        return 3, 3
    return 4, 3


def get_south_grid_slot(index, item_count, columns):
    if item_count == 3 and index == 2:
        return 1, 0.5

    row = index // columns
    column = index % columns
    return row, column


def get_house_layout(item_count, x1, y1, x2, y2, items=None, chart_data=None):
    if item_count <= 0:
        return None

    rows, columns = get_south_grid_shape(item_count)
    inner_left = x1 + HOUSE_PADDING
    inner_right = x2 - HOUSE_PADDING
    inner_top = y1 + HOUSE_PADDING
    inner_bottom = y2 - HOUSE_PADDING
    inner_width = inner_right - inner_left
    inner_height = inner_bottom - inner_top
    slot_width = (inner_width - GRID_ITEM_GAP * (columns - 1)) / columns
    slot_height = (inner_height - GRID_ITEM_GAP * (rows - 1)) / rows

    max_text_width = 1
    if items and chart_data:
        for item in items:
            display_name = get_display_name(item, chart_data)
            degree_text = f"{get_degree(item, chart_data)}{LONGITUDE_DEGREE_MARK}"
            max_text_width = max(
                max_text_width,
                estimate_text_width(display_name, PLANET_FONT_SIZE, factor=0.68),
                estimate_text_width(degree_text, DEGREE_FONT_SIZE, factor=0.56),
            )

    scale = min(1, slot_height / PLANET_BLOCK_HEIGHT, slot_width / max_text_width)
    min_scale = 0.22 if item_count > 4 else 0.34
    scale = max(min_scale, scale)

    name_font_size = PLANET_FONT_SIZE * scale
    degree_font_size = DEGREE_FONT_SIZE * scale
    retro_line_width = max(1, BASE_RETRO_LINE_WIDTH * scale)
    retro_line_offset = name_font_size / 2 + 3 * scale + retro_line_width / 2
    degree_line_offset = name_font_size / 2 + degree_font_size * 0.95
    top_extent = name_font_size / 2
    bottom_extent = degree_line_offset + degree_font_size / 2

    return {
        "mode": "grid" if item_count in (2, 3, 4) else "vertical",
        "rows": rows,
        "columns": columns,
        "inner_left": inner_left,
        "inner_top": inner_top,
        "slot_width": slot_width,
        "slot_height": slot_height,
        "name_font_size": name_font_size,
        "degree_font_size": degree_font_size,
        "retro_line_offset": retro_line_offset,
        "degree_line_offset": degree_line_offset,
        "retro_line_half_width": max(10, 28 * scale),
        "retro_line_width": retro_line_width,
        "top_extent": top_extent,
        "bottom_extent": bottom_extent,
        "horizontal_padding": HOUSE_PADDING,
        "vertical_padding": HOUSE_PADDING,
    }


def get_house_item_position(layout, index, item_count, x1, y1, x2, y2):
    row, column = get_south_grid_slot(index, item_count, layout["columns"])
    px = (
        layout["inner_left"]
        + layout["slot_width"] * column
        + GRID_ITEM_GAP * column
        + layout["slot_width"] / 2
    )
    py = (
        layout["inner_top"]
        + layout["slot_height"] * row
        + GRID_ITEM_GAP * row
        + layout["slot_height"] / 2
    )

    return px, py


def get_north_house_layout(item_count, x1, y1, x2, y2, show_degrees=True):
    if item_count <= 0:
        return None

    height = y2 - y1
    base_item_height = BASE_NAME_FONT_SIZE / 2
    if show_degrees:
        base_degree_line_offset = BASE_NAME_FONT_SIZE / 2 + BASE_DEGREE_FONT_SIZE * 0.95
        base_item_height += base_degree_line_offset + BASE_DEGREE_FONT_SIZE / 2
    else:
        base_item_height += BASE_NAME_FONT_SIZE / 2
    scale = 1 if item_count <= 3 else min(1, height / (item_count * base_item_height))

    name_font_size = max(7, BASE_NAME_FONT_SIZE * scale)
    degree_font_size = max(6, BASE_DEGREE_FONT_SIZE * scale)
    retro_line_width = max(1, BASE_RETRO_LINE_WIDTH * scale)
    retro_line_offset = name_font_size / 2 + 2 + retro_line_width / 2
    degree_line_offset = name_font_size / 2 + degree_font_size * 0.95
    top_extent = name_font_size / 2
    bottom_extent = (
        degree_line_offset + degree_font_size / 2
        if show_degrees
        else name_font_size / 2
    )
    item_height = top_extent + bottom_extent
    item_gap = 0
    if item_count > 1:
        item_gap = min(5, max(0, (height - item_height * item_count) / (item_count - 1)))
    stack_height = item_height * item_count + item_gap * (item_count - 1)

    return {
        "mode": "vertical",
        "start_y": y1 + (height - stack_height) / 2 + top_extent,
        "item_gap": item_height + item_gap,
        "name_font_size": name_font_size,
        "degree_font_size": degree_font_size,
        "retro_line_offset": retro_line_offset,
        "degree_line_offset": degree_line_offset,
        "retro_line_half_width": max(8, 18 * scale),
        "retro_line_width": retro_line_width,
        "horizontal_padding": 0,
        "vertical_padding": 0,
    }


def get_north_house_item_position(layout, index, item_count, x1, y1, x2, y2):
    return (x1 + x2) / 2, layout["start_y"] + index * layout["item_gap"]


def get_item_render_metrics(item, chart_data, layout):
    display_name = get_display_name(item, chart_data)
    degree = get_degree(item, chart_data)
    degree_text = f"{degree}{LONGITUDE_DEGREE_MARK}"
    name_width = estimate_text_width(
        display_name,
        layout["name_font_size"],
        factor=0.68,
    )
    degree_width = estimate_text_width(
        degree_text,
        layout["degree_font_size"],
        factor=0.56,
    )

    return {
        "display_name": display_name,
        "degree_text": degree_text,
        "name_width": name_width,
        "degree_width": degree_width,
        "total_width": max(name_width, degree_width),
    }


def get_chart_header(chart_data):
    date_text = format_date(chart_data["date"])
    time_text = format_time_with_seconds(chart_data.get("time_local", "09:00"))
    city_text = escape(chart_data.get("city", "Москва"))
    city_text, city_font_size = get_center_city_layout(city_text)
    latitude = chart_data.get("latitude")
    longitude = chart_data.get("longitude")
    coordinates_text = ""
    if latitude is not None and longitude is not None:
        coordinates_text = f"{latitude:.2f}, {longitude:.2f}"

    datetime_text = f"{date_text} {time_text}"
    return datetime_text, city_text, city_font_size, coordinates_text


def get_chart_controls_svg(
    switch_label,
    include_infoblock_toggle=True,
    switch_transform="translate(610 270)",
):
    infoblock_toggle = ""
    if include_infoblock_toggle:
        infoblock_toggle = """
        <g class="chart-infoblock-toggle"
           role="button"
           tabindex="0"
           aria-label="Скрыть данные инфоблока карты"
           transform="translate(670 270)"
           style="cursor:pointer">
            <rect width="60"
                  height="50"
                  fill="transparent"/>
            <g transform="translate(6 1) scale(2 2)"
               class="chart-eye-icon"
               fill="none"
               stroke-width="1.6"
               stroke-linecap="round"
               stroke-linejoin="round">
                <g class="chart-eye-on">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12Z"/>
                    <circle cx="12" cy="12" r="3"/>
                </g>
                <g class="chart-eye-off" style="display:none">
                    <path d="M17.94 17.94A10.9 10.9 0 0 1 12 20C7 20 2.73 16.89 1 12a18.45 18.45 0 0 1 5.06-6.94"/>
                    <path d="M9.9 4.24A10.5 10.5 0 0 1 12 4c5 0 9.27 3.11 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                    <path d="M14.12 14.12A3 3 0 0 1 9.88 9.88"/>
                    <path d="M1 1l22 22"/>
                </g>
            </g>
        </g>
        """

    return f"""
        {infoblock_toggle}

        <g class="chart-style-toggle"
           role="button"
           tabindex="0"
           aria-label="{switch_label}"
           transform="{switch_transform}"
           style="cursor:pointer">
            <rect width="60"
                  height="50"
                  fill="transparent"/>
            <g transform="translate(12 7) scale(1.5 1.5)"
               class="{CHART_SWITCH_ICON_CLASS}"
               fill="none"
               stroke-width="1.8"
               stroke-linecap="round"
               stroke-linejoin="round">
                <path d="M21 7H3"/>
                <path d="M18 4l3 3-3 3"/>
                <path d="M3 17h18"/>
                <path d="M6 14l-3 3 3 3"/>
            </g>
        </g>
    """


def get_chart_base_svg(
    datetime_text,
    city_text,
    city_font_size,
    coordinates_text,
    switch_label,
    show_infoblock=True,
    include_infoblock_toggle=True,
    switch_transform="translate(610 270)",
):
    infoblock_svg = ""
    if show_infoblock:
        infoblock_svg = f"""
        <g class="chart-infoblock-data">
            <text x="500"
                  y="430"
                  text-anchor="middle"
                  font-family="{SVG_FONT_FAMILY}"
                  fill="#5B3A1A">

                <tspan x="500" font-size="40">
                    {datetime_text}
                </tspan>

                <tspan x="500" dy="70" font-size="{city_font_size}">
                    {city_text}
                </tspan>

                <tspan x="500" dy="42" font-size="28">
                    {coordinates_text}
                </tspan>

            </text>
        </g>
        """

    return f"""
    <svg width="1000"
         height="1000"
         viewBox="0 0 1000 1000"
         xmlns="http://www.w3.org/2000/svg">

        <style>
            .chart-infoblock-toggle .chart-eye-icon,
            .chart-style-toggle .{CHART_SWITCH_ICON_CLASS} {{
                stroke: #5B3A1A;
                transition: stroke 120ms ease, opacity 120ms ease;
            }}

            .chart-infoblock-toggle:hover .chart-eye-icon,
            .chart-style-toggle:hover .{CHART_SWITCH_ICON_CLASS} {{
                stroke: #C69214;
                opacity: 0.9;
            }}

            .chart-infoblock-toggle:active .chart-eye-icon,
            .chart-style-toggle:active .{CHART_SWITCH_ICON_CLASS} {{
                stroke: #7B4F20;
                opacity: 0.72;
            }}
        </style>

        <rect width="1000"
              height="1000"
              fill="#FFFDF7"/>

        <rect x="20"
              y="20"
              width="960"
              height="960"
              rx="24"
              ry="24"
              fill="none"
              stroke="#D4AF37"
              stroke-width="4"/>

        {infoblock_svg}

        {get_chart_controls_svg(
            switch_label,
            include_infoblock_toggle=include_infoblock_toggle,
            switch_transform=switch_transform,
        )}
    """


def generate_south_indian_svg(chart_data):
    chart = generate_south_indian_chart(chart_data)

    rashis = chart["rashis"]
    lagna_rashi = chart["lagna_rashi"]

    date_text = format_date(chart_data["date"])
    time_text = format_time_with_seconds(chart_data.get("time_local", "09:00"))
    city_text = escape(chart_data.get("city", "Москва"))
    city_text, city_font_size = get_center_city_layout(city_text)
    latitude = chart_data.get("latitude")
    longitude = chart_data.get("longitude")
    coordinates_text = ""
    if latitude is not None and longitude is not None:
        coordinates_text = f"{latitude:.2f}, {longitude:.2f}"

    cells = {
        12: (20, 20, 260, 260),
        1: (260, 20, 500, 260),
        2: (500, 20, 740, 260),
        3: (740, 20, 980, 260),

        11: (20, 260, 260, 500),
        4: (740, 260, 980, 500),

        10: (20, 500, 260, 740),
        5: (740, 500, 980, 740),

        9: (20, 740, 260, 980),
        8: (260, 740, 500, 980),
        7: (500, 740, 740, 980),
        6: (740, 740, 980, 980),
    }

    svg = f"""
    <svg width="1000"
         height="1000"
         viewBox="0 0 1000 1000"
         xmlns="http://www.w3.org/2000/svg">

        <style>
            .chart-infoblock-toggle .chart-eye-icon,
            .chart-style-toggle .chart-switch-icon {{
                stroke: #5B3A1A;
                transition: stroke 120ms ease, opacity 120ms ease;
            }}

            .chart-infoblock-toggle:hover .chart-eye-icon,
            .chart-style-toggle:hover .chart-switch-icon {{
                stroke: #C69214;
                opacity: 0.9;
            }}

            .chart-infoblock-toggle:active .chart-eye-icon,
            .chart-style-toggle:active .chart-switch-icon {{
                stroke: #7B4F20;
                opacity: 0.72;
            }}
        </style>

        <rect width="1000"
              height="1000"
              fill="#FFFDF7"/>

        <rect x="20"
              y="20"
              width="960"
              height="960"
              rx="24"
              ry="24"
              fill="none"
              stroke="#D4AF37"
              stroke-width="4"/>

        <g stroke="#D4AF37"
           stroke-width="2.5"
           fill="none">

            <line x1="260" y1="20" x2="260" y2="980"/>
            <line x1="500" y1="20" x2="500" y2="980"/>
            <line x1="740" y1="20" x2="740" y2="980"/>

            <line x1="20" y1="260" x2="980" y2="260"/>
            <line x1="20" y1="500" x2="980" y2="500"/>
            <line x1="20" y1="740" x2="980" y2="740"/>

        </g>

        <rect x="260"
              y="260"
              width="480"
              height="480"
              fill="#FFF8EA"
              stroke="#D4AF37"
              stroke-width="2"/>

        <g class="chart-infoblock-data">
            <text x="500"
                  y="430"
                  text-anchor="middle"
                  font-family="{SVG_FONT_FAMILY}"
                  fill="#5B3A1A">

                <tspan x="500" font-size="40">
                    {date_text}
                </tspan>

                <tspan x="500" dy="46" font-size="36">
                    {time_text}
                </tspan>

                <tspan x="500" dy="66" font-size="{city_font_size}">
                    {city_text}
                </tspan>

                <tspan x="500" dy="42" font-size="28">
                    {coordinates_text}
                </tspan>

            </text>
        </g>

        <g class="chart-infoblock-toggle"
           role="button"
           tabindex="0"
           aria-label="Скрыть данные инфоблока карты"
           transform="translate(670 270)"
           style="cursor:pointer">
            <rect width="60"
                  height="50"
                  fill="transparent"/>
            <g transform="translate(6 1) scale(2 2)"
               class="chart-eye-icon"
               fill="none"
               stroke-width="1.6"
               stroke-linecap="round"
               stroke-linejoin="round">
                <g class="chart-eye-on">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12Z"/>
                    <circle cx="12" cy="12" r="3"/>
                </g>
                <g class="chart-eye-off" style="display:none">
                    <path d="M17.94 17.94A10.9 10.9 0 0 1 12 20C7 20 2.73 16.89 1 12a18.45 18.45 0 0 1 5.06-6.94"/>
                    <path d="M9.9 4.24A10.5 10.5 0 0 1 12 4c5 0 9.27 3.11 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                    <path d="M14.12 14.12A3 3 0 0 1 9.88 9.88"/>
                    <path d="M1 1l22 22"/>
                </g>
            </g>
        </g>

        <g class="chart-style-toggle"
           role="button"
           tabindex="0"
           aria-label="Переключить на северный стиль карты"
           transform="translate(610 270)"
           style="cursor:pointer">
            <rect width="60"
                  height="50"
                  fill="transparent"/>
            <g transform="translate(12 7) scale(1.5 1.5)"
               class="chart-switch-icon"
               fill="none"
               stroke-width="1.8"
               stroke-linecap="round"
               stroke-linejoin="round">
                <path d="M21 7H3"/>
                <path d="M18 4l3 3-3 3"/>
                <path d="M3 17h18"/>
                <path d="M6 14l-3 3 3 3"/>
            </g>
        </g>
    """

    x1, y1, x2, y2 = cells[lagna_rashi]

    svg += f"""
    <line x1="{x2 - 72}"
          y1="{y2}"
          x2="{x2}"
          y2="{y2 - 72}"
          stroke="#D4AF37"
          stroke-width="3"/>
    """

    for rashi_num, items in rashis.items():
        x1, y1, x2, y2 = cells[rashi_num]

        house_num = ((rashi_num - lagna_rashi) % 12) + 1

        svg += f"""
        <text x="{x2 - 24}"
              y="{y1 + 42}"
              text-anchor="end"
              font-size="34"
              font-family="{SVG_FONT_FAMILY}"
              font-weight="400"
              fill="#C69214">
              {house_num}
        </text>
        """

        layout = get_house_layout(len(items), x1, y1, x2, y2, items, chart_data)
        if layout is None:
            continue
        item_metrics = [
            get_item_render_metrics(item, chart_data, layout)
            for item in items
        ]

        for index, item in enumerate(items):
            color = PLANET_COLORS.get(item, "#222")
            metrics = item_metrics[index]
            display_name = metrics["display_name"]
            is_retrograde = (
                item != "Asc"
                and chart_data["planets"][item].get("is_retrograde", False)
            )

            px, py = get_house_item_position(layout, index, len(items), x1, y1, x2, y2)

            name_width = metrics["name_width"]
            degree_text = metrics["degree_text"]
            name_right_x = px + name_width / 2
            retro_line_start = name_right_x - name_width
            retro_line_end = name_right_x

            svg += f"""
            <text x="{name_right_x}"
                  y="{py}"
                  text-anchor="end"
                  dominant-baseline="middle"
                  font-size="{layout["name_font_size"]}"
                  font-family="{SVG_FONT_FAMILY}"
                  font-weight="500"
                  fill="{color}">
                  {display_name}
            </text>

            <text x="{px}"
                  y="{py + layout["degree_line_offset"]}"
                  text-anchor="middle"
                  dominant-baseline="middle"
                  font-size="{layout["degree_font_size"]}"
                  font-family="{SVG_FONT_FAMILY}"
                  font-weight="400"
                  fill="{color}">
                  {degree_text}
            </text>
            """

            if is_retrograde:
                svg += f"""
                <line x1="{retro_line_start}"
                      y1="{py + layout["retro_line_offset"]}"
                      x2="{retro_line_end}"
                      y2="{py + layout["retro_line_offset"]}"
                      stroke="{color}"
                      stroke-width="{layout["retro_line_width"]}"
                      stroke-linecap="round"/>
                """

    svg += "</svg>"

    return svg


def render_house_items_svg(
    items,
    chart_data,
    x1,
    y1,
    x2,
    y2,
    compact=False,
    show_degrees=True,
):
    if compact:
        layout = get_north_house_layout(
            len(items),
            x1,
            y1,
            x2,
            y2,
            show_degrees=show_degrees,
        )
    else:
        layout = get_house_layout(len(items), x1, y1, x2, y2, items, chart_data)
    if layout is None:
        return ""

    item_metrics = [
        get_item_render_metrics(item, chart_data, layout)
        for item in items
    ]
    svg = ""

    for index, item in enumerate(items):
        color = PLANET_COLORS.get(item, "#222")
        metrics = item_metrics[index]
        display_name = metrics["display_name"]
        is_retrograde = (
            item != "Asc"
            and chart_data["planets"][item].get("is_retrograde", False)
        )

        if compact:
            px, py = get_north_house_item_position(
                layout,
                index,
                len(items),
                x1,
                y1,
                x2,
                y2,
            )
        else:
            px, py = get_house_item_position(layout, index, len(items), x1, y1, x2, y2)

        name_width = metrics["name_width"]
        name_right_x = px + name_width / 2
        retro_line_start = name_right_x - name_width
        retro_line_end = name_right_x

        svg += f"""
        <text x="{name_right_x}"
              y="{py}"
              text-anchor="end"
              dominant-baseline="middle"
              font-size="{layout["name_font_size"]}"
              font-family="{SVG_FONT_FAMILY}"
              font-weight="500"
              fill="{color}">
              {display_name}
        </text>
        """

        if show_degrees:
            degree_text = metrics["degree_text"]
            svg += f"""
            <text x="{px}"
                  y="{py + layout["degree_line_offset"]}"
                  text-anchor="middle"
                  dominant-baseline="middle"
                  font-size="{layout["degree_font_size"]}"
                  font-family="{SVG_FONT_FAMILY}"
                  font-weight="400"
                  fill="{color}">
                  {degree_text}
            </text>
            """

        if is_retrograde:
            svg += f"""
            <line x1="{retro_line_start}"
                  y1="{py + layout["retro_line_offset"]}"
                  x2="{retro_line_end}"
                  y2="{py + layout["retro_line_offset"]}"
                  stroke="{color}"
                  stroke-width="{layout["retro_line_width"]}"
                  stroke-linecap="round"/>
            """

    return svg


def generate_north_indian_svg(chart_data):
    chart = get_north_indian_chart(chart_data)
    houses = chart["houses"]
    house_rashis = chart["house_rashis"]

    datetime_text, city_text, city_font_size, coordinates_text = get_chart_header(chart_data)
    svg = get_chart_base_svg(
        datetime_text,
        city_text,
        city_font_size,
        coordinates_text,
        "Переключить на южный стиль карты",
        show_infoblock=False,
        include_infoblock_toggle=False,
        switch_transform="translate(470 32)",
    )

    svg += """
        <g stroke="#D4AF37"
           stroke-width="2.5"
           fill="none">
            <line x1="20" y1="20" x2="980" y2="980"/>
            <line x1="980" y1="20" x2="20" y2="980"/>
            <line x1="500" y1="20" x2="980" y2="500"/>
            <line x1="980" y1="500" x2="500" y2="980"/>
            <line x1="500" y1="980" x2="20" y2="500"/>
            <line x1="20" y1="500" x2="500" y2="20"/>
            <line x1="20" y1="20" x2="500" y2="500"/>
            <line x1="980" y1="20" x2="500" y2="500"/>
            <line x1="980" y1="980" x2="500" y2="500"/>
            <line x1="20" y1="980" x2="500" y2="500"/>
        </g>
    """

    house_boxes = {
        1: (415, 137, 585, 383),
        2: (175, 20, 345, 260),
        3: (50, 140, 210, 380),
        4: (175, 375, 345, 625),
        5: (50, 620, 210, 860),
        6: (175, 760, 345, 1000),
        7: (415, 617, 585, 863),
        8: (655, 760, 825, 1000),
        9: (790, 620, 950, 860),
        10: (655, 375, 825, 625),
        11: (790, 140, 950, 380),
        12: (655, 0, 825, 240),
    }
    rashi_positions = {
        1: (500, 455),
        2: (260, 225),
        3: (236, 260),
        4: (455, 500),
        5: (236, 740),
        6: (260, 775),
        7: (500, 545),
        8: (740, 775),
        9: (764, 740),
        10: (545, 500),
        11: (764, 260),
        12: (740, 225),
    }
    rashi_anchors = {
        1: "middle",
        2: "middle",
        3: "end",
        4: "end",
        5: "end",
        6: "middle",
        7: "middle",
        8: "middle",
        9: "start",
        10: "start",
        11: "start",
        12: "middle",
    }

    for house_num in range(1, 13):
        rx, ry = rashi_positions[house_num]
        svg += f"""
        <text x="{rx}"
              y="{ry}"
              text-anchor="{rashi_anchors[house_num]}"
              dominant-baseline="middle"
              font-size="30"
              font-family="{SVG_FONT_FAMILY}"
              font-weight="400"
              fill="#C69214">
              {house_rashis[house_num]}
        </text>
        """

        x1, y1, x2, y2 = house_boxes[house_num]
        svg += render_house_items_svg(
            houses[house_num],
            chart_data,
            x1,
            y1,
            x2,
            y2,
            compact=True,
            show_degrees=False,
        )

    svg += "</svg>"
    return svg
