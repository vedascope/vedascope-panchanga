def synthesize_day(data):
    vara = data["vara"]["data"]
    tithi = data["tithi"]["data"]
    nakshatra = data["nakshatra"]["data"]

    tones = []

    if nakshatra:
        for t in nakshatra.get("types", []):

            if t == "Мягкая":
                tones.append("гармоничный")

            elif t == "Резкая":
                tones.append("напряженный")

            elif t == "Подвижная":
                tones.append("активный")

            elif t == "Неподвижная":
                tones.append("стабильный")

            elif t == "Страшная":
                tones.append("жесткий")

    summary = "День нейтральный."

    if tones:
        summary = (
            "Сегодня преобладает "
            + ", ".join(tones)
            + " фон."
        )

    recommendations = []

    if vara:
        recommendations += vara.get("keywords", [])

    if tithi:
        recommendations += tithi.get("keywords", [])

    if nakshatra:
        recommendations += nakshatra.get("keywords", [])

    return {
        "summary": summary,
        "recommendations": list(set(recommendations)),
    }
