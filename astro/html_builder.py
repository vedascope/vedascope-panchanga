from astro.text_builder import build_panchanga_text


def build_panchanga_html(data):

    text = build_panchanga_text(data)

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
                --mono-font: "IBM Plex Mono", "Space Mono", monospace;
                font-family: var(--mono-font);
                background: #f5f1e8;
                color: #222;
                padding: 40px;
                line-height: 1.58;
                letter-spacing: 0;
                max-width: 900px;
                margin: auto;
            }}

            .card {{
                background: white;
                padding: 30px;
                border-radius: 16px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            }}

            h1 {{
                margin-top: 0;
                font-size: 32px;
                line-height: 1.16;
                font-weight: 600;
            }}

            pre {{
                white-space: pre-wrap;
                font-family: var(--mono-font);
                font-size: 17px;
                line-height: 1.68;
                font-weight: 400;
            }}

        </style>
    </head>

    <body>

        <div class="card">

            <h1>Панчанга</h1>

            <pre>{text}</pre>

        </div>

    </body>
    </html>
    """

    return html
