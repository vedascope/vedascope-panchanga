NAKSHATRA_LENGTH = 360 / 27
GANDANTA_ZONE_DEGREES = 0.8

GANDANTA_END_NAKSHATRAS = [
    "Ashlesha",
    "Jyeshtha",
    "Revati",
]

GANDANTA_START_NAKSHATRAS = [
    "Ashwini",
    "Magha",
    "Mula",
]


def calculate_gandanta(nakshatra_key, degree_in_nakshatra):
    is_end_gandanta = (
        nakshatra_key in GANDANTA_END_NAKSHATRAS
        and degree_in_nakshatra >= NAKSHATRA_LENGTH - GANDANTA_ZONE_DEGREES
    )

    is_start_gandanta = (
        nakshatra_key in GANDANTA_START_NAKSHATRAS
        and degree_in_nakshatra <= GANDANTA_ZONE_DEGREES
    )

    active = is_end_gandanta or is_start_gandanta

    return {
        "active": active,
        "type": "Ганданта Луны" if active else None,
        "description": (
            "Луна находится в зоне ганданты — чувствительном переходе между водной и огненной стихией. "
            "Такое положение может усиливать эмоциональную нестабильность, тревожность, внутреннее напряжение "
            "и ощущение неопределенности. В это время лучше избегать поспешных решений, конфликтов и важных новых начинаний. "
            "Период больше подходит для завершения старого, внутренней работы, молитвы, наблюдения и духовной практики."
            if active else None
        )
    }