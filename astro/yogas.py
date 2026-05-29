MOON_CONJUNCTION_ORB = 8


def angular_distance(a, b):
    diff = abs(a - b) % 360

    if diff > 180:
        diff = 360 - diff

    return diff


def get_house_distance(from_rashi, to_rashi):
    return ((to_rashi - from_rashi) % 12) + 1


def is_conjunct(moon_lon, planet_lon, orb=MOON_CONJUNCTION_ORB):
    return angular_distance(moon_lon, planet_lon) <= orb


def calculate_moon_yogas(chart_data):
    planets = chart_data["planets"]

    moon = planets["Mo"]
    moon_lon = moon["longitude"]
    moon_rashi = moon["rashi_number"]

    yogas = []

    malefics = {
        "Sa": {
            "title": "Луна соединяется с Сатурном",
            "description": (
                "Такое положение может усиливать серьезность, внутреннюю тяжесть, "
                "требовательность к себе и другим, ощущение одиночества или депрессивный фон. "
                "День лучше использовать для дисциплины, ответственности и спокойной работы, "
                "не перегружая себя эмоционально."
            )
        },
        "Ma": {
            "title": "Луна соединяется с Марсом",
            "description": (
                "Ум становится активнее и быстрее реагирует на раздражители. "
                "Может усиливаться вспыльчивость, нетерпение, резкость в словах и желание действовать немедленно. "
                "Полезны физическая активность и задачи, где нужна энергия, но важно избегать конфликтов."
            )
        },
        "Ra": {
            "title": "Луна соединяется с Раху",
            "description": (
                "Раху может усиливать хаотичность восприятия, тревожные желания, иллюзии, "
                "ментальный шум и стремление получить слишком много сразу. "
                "В этот день важно проверять факты, не принимать решения из состояния возбуждения "
                "и не поддаваться навязчивым желаниям."
            )
        },
        "Ke": {
            "title": "Луна соединяется с Кету",
            "description": (
                "Кету может поднимать внутренние страхи, старые переживания и непережитые эмоциональные состояния. "
                "Может казаться, что проблема глубже, чем она есть. "
                "Важно помнить: это транзитное состояние, и через день-два эмоциональный фон обычно отпускает."
            )
        },
    }

    for planet_key, info in malefics.items():
        if planet_key in planets:
            planet_lon = planets[planet_key]["longitude"]

            if is_conjunct(moon_lon, planet_lon):
                yogas.append({
                    "type": "moon_malefic_conjunction",
                    "planet": planet_key,
                    "title": info["title"],
                    "description": info["description"],
                })

    # Gaja Kesari Yoga:
    # Jupiter in kendra from Moon: 1, 4, 7, 10
    if "Ju" in planets:
        jupiter_rashi = planets["Ju"]["rashi_number"]
        distance = get_house_distance(moon_rashi, jupiter_rashi)

        if distance in [1, 4, 7, 10]:
            yogas.append({
                "type": "gaja_kesari_yoga",
                "planet": "Ju",
                "title": "Гаджа Кешари йога",
                "description": (
                    "Юпитер находится в кендре от Луны. Это считается благоприятной йогой, "
                    "которая поддерживает мудрость, здравое суждение, защиту, благородство, "
                    "уважение и способность принимать более зрелые решения. "
                    "День лучше использовать для обучения, наставничества, духовной практики, "
                    "переговоров и действий, где важны смысл, этика и долгосрочная польза."
                )
            })

    # Moon + Venus
    if "Ve" in planets:
        venus_lon = planets["Ve"]["longitude"]

        if is_conjunct(moon_lon, venus_lon):
            yogas.append({
                "type": "moon_venus_conjunction",
                "planet": "Ve",
                "title": "Луна соединяется с Венерой",
                "description": (
                    "Соединение Луны и Венеры усиливает мягкость, привлекательность, чувственность, "
                    "творчество, желание красоты, гармонии и приятного общения. "
                    "День благоприятен для искусства, отношений, покупок красивых вещей, ухода за собой, "
                    "встреч, примирения и создания эстетичной атмосферы."
                )
            })

    return yogas