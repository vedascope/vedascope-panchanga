from astro.data_loader import TITHIS_DATA, NAKSHATRAS_DATA


TEXT_REPLACEMENTS = {
    "дела ради выгоды": "рисковые действия ради быстрой выгоды",
    "избавление от хлама": "разбор лишнего, чистка, закрытие хвостов",
}


def normalize_catalog_text(value):
    text = str(value)
    return TEXT_REPLACEMENTS.get(text, text)


def normalize_catalog_items(items):
    return tuple(normalize_catalog_text(item) for item in items or ())


RECOMMENDATION_TEMPLATES = {
    "transition_morning": (
        "До {time} день проходит через переходную фазу: лучше мягко завершать начатое, "
        "не перегружать утро резкими стартами и дать дню войти в устойчивый ритм."
    ),
    "main_after": "После {time} основная энергия дня — {factors}.",
    "main": "Основная энергия дня — {factors}.",
    "aligned_tags": "Оба фактора усиливают тему {tags}: {fragment}.",
    "mixed_tags": (
        "День соединяет разные влияния: {first_factor} поддерживает {first_tags}, "
        "а {second_factor} поддерживает {second_tags}; лучше выбирать действия, "
        "где эти темы помогают друг другу."
    ),
    "conflicting_tags": (
        "Влияния дня частично разнонаправлены: {first_factor} поддерживает {first_tags}, "
        "а {second_factor} поддерживает {second_tags}; держите средний темп и избегайте крайностей."
    ),
    "good_for": "Практически день лучше направить на такие задачи, как {items}.",
    "avoid": "Лучше не ставить в центр такие темы, как {items}.",
}


INTEGRATED_RECOMMENDATION_TEMPLATES = {
    "transition": (
        "До {time} действует переходная энергия {factors}. "
        "Утро лучше использовать мягко, для настройки и завершения мелких дел."
    ),
    "tithi_task": "Задача по титхи ({name}): сегодня основная задача — {task_summary}.",
    "nakshatra_tone": "Окраска по накшатре ({name}): энергия проходит через {style_summary}.",
    "integrated": "Итог: лучше {combined_positive}.",
    "avoid": "Осторожнее с такими темами: {combined_avoid}.",
}

TITHI_ACTION_PRIORITY = (
    "cleanup",
    "completion",
    "caution",
    "start",
    "growth",
    "stability",
    "discipline",
    "movement",
    "learning",
    "softness",
    "relationships",
    "spiritual",
    "resources",
    "healing",
    "general",
)

NAKSHATRA_TONE_PRIORITY = (
    "rhythm",
    "collaboration",
    "movement",
    "softness",
    "stability",
    "creativity",
    "learning",
    "spiritual",
    "growth",
    "discipline",
    "caution",
    "conflict",
    "cleanup",
    "relationships",
    "healing",
    "resources",
    "general",
)

TITHI_ACTION_PROFILES = {
    "cleanup": {
        "action_type": "очищение и расчистка",
        "task_summary": "расчистить лишнее, убрать препятствия и освободить место для следующего шага",
        "phase_rule": "не начинать важное новое, пока не закрыт старый узел",
    },
    "completion": {
        "action_type": "завершение",
        "task_summary": "завершить хвосты, подвести итоги и довести начатое до понятного результата",
        "phase_rule": "сначала закрывать и укреплять, затем переходить к новому",
    },
    "caution": {
        "action_type": "осторожное действие",
        "task_summary": "действовать осмотрительно и не перегружать день необратимыми решениями",
        "phase_rule": "снижать риск и не делать ставку на резкие старты",
    },
    "start": {
        "action_type": "старт",
        "task_summary": "начать с ясного намерения и простого первого шага",
        "phase_rule": "новое начинать лучше спокойно, без суеты и лишнего давления",
    },
    "growth": {
        "action_type": "рост и развитие",
        "task_summary": "поддержать процессы, которым нужно вырасти и получить устойчивый импульс",
        "phase_rule": "наращивать постепенно, не распыляя внимание",
    },
    "stability": {
        "action_type": "закрепление",
        "task_summary": "укрепить то, что должно держаться долго",
        "phase_rule": "выбирать устойчивые решения вместо кратковременного эффекта",
    },
    "discipline": {
        "action_type": "упорядочивание",
        "task_summary": "навести порядок, выстроить структуру и вернуть процессам практический фокус",
        "phase_rule": "действовать через правила, последовательность и ответственность",
    },
    "movement": {
        "action_type": "подвижное действие",
        "task_summary": "дать делу движение и не застревать в лишнем ожидании",
        "phase_rule": "двигаться гибко, не превращая скорость в суету",
    },
    "learning": {
        "action_type": "обучение и настройка понимания",
        "task_summary": "учиться, планировать и уточнять понимание ситуации",
        "phase_rule": "сначала прояснять, затем действовать",
    },
    "softness": {
        "action_type": "мягкое развитие",
        "task_summary": "поддержать процесс мягко, без давления и резких решений",
        "phase_rule": "сохранять бережный темп и избегать жесткости",
    },
    "relationships": {
        "action_type": "отношения и согласование",
        "task_summary": "укрепить договоренности, контакт и взаимное доверие",
        "phase_rule": "не ломать связь ради быстрого результата",
    },
    "spiritual": {
        "action_type": "внутренняя настройка",
        "task_summary": "оставить место практике, смыслу и внутренней собранности",
        "phase_rule": "действовать из ясного состояния, а не из суеты",
    },
    "resources": {
        "action_type": "работа с ресурсами",
        "task_summary": "обращаться с ресурсами трезво, без азартного риска",
        "phase_rule": "не делать ставку на сомнительную выгоду",
    },
    "healing": {
        "action_type": "восстановление",
        "task_summary": "поддержать здоровье, восстановление и телесную заботу",
        "phase_rule": "выбирать бережное восстановление вместо перегруза",
    },
    "general": {
        "action_type": "ровное действие",
        "task_summary": "выбрать ровный, осознанный темп дня",
        "phase_rule": "держать внимание на главном и не дробить день",
    },
}

NAKSHATRA_TONE_PROFILES = {
    "rhythm": {
        "tone": "ритмичный",
        "style_summary": "ритм, согласованность, повторяемое действие и точный темп",
        "colors_action_by": "через ритм, согласованность и ясный темп",
    },
    "collaboration": {
        "tone": "коллективный",
        "style_summary": "сотрудничество, договоренности и действия через людей",
        "colors_action_by": "через сотрудничество, договоренности и командную координацию",
    },
    "movement": {
        "tone": "подвижный",
        "style_summary": "движение, гибкость и способность быстро перестраивать маршрут",
        "colors_action_by": "через движение, гибкость и короткие практические шаги",
    },
    "softness": {
        "tone": "мягкий",
        "style_summary": "мягкость, бережность и отсутствие лишнего давления",
        "colors_action_by": "через мягкий тон, бережность и спокойное согласование",
    },
    "stability": {
        "tone": "устойчивый",
        "style_summary": "устойчивость, закрепление и долгий горизонт",
        "colors_action_by": "через устойчивость, закрепление и надежную структуру",
    },
    "creativity": {
        "tone": "творческий",
        "style_summary": "творческое проявление, живость и работа с формой",
        "colors_action_by": "через творческий подход, живость и аккуратную форму",
    },
    "learning": {
        "tone": "обучающий",
        "style_summary": "обучение, планирование и обмен знаниями",
        "colors_action_by": "через обучение, планирование и внимательный обмен информацией",
    },
    "spiritual": {
        "tone": "смысловой",
        "style_summary": "духовная настройка, смысл и внутренняя собранность",
        "colors_action_by": "через практику, смысл и внутреннюю настройку",
    },
    "growth": {
        "tone": "развивающий",
        "style_summary": "рост, расширение и поддержка живого процесса",
        "colors_action_by": "через постепенный рост и поддержку процесса",
    },
    "discipline": {
        "tone": "собранный",
        "style_summary": "порядок, структура и практическая точность",
        "colors_action_by": "через порядок, структуру и практическую точность",
    },
    "caution": {
        "tone": "осторожный",
        "style_summary": "осторожность, наблюдение и снижение риска",
        "colors_action_by": "через осторожность, наблюдение и снижение риска",
    },
    "conflict": {
        "tone": "напряженный",
        "style_summary": "прояснение напряжения без перехода в конфликт",
        "colors_action_by": "через выдержку, прояснение и отказ от лишнего давления",
    },
    "cleanup": {
        "tone": "очищающий",
        "style_summary": "очищение, отсечение лишнего и работа с препятствиями",
        "colors_action_by": "через очищение, отсечение лишнего и точное устранение препятствий",
    },
    "relationships": {
        "tone": "согласующий",
        "style_summary": "отношения, контакт и уважительное согласование",
        "colors_action_by": "через контакт, уважение и аккуратное согласование",
    },
    "healing": {
        "tone": "восстанавливающий",
        "style_summary": "восстановление, лечение и телесная забота",
        "colors_action_by": "через восстановление, лечение и бережную заботу о теле",
    },
    "resources": {
        "tone": "ресурсный",
        "style_summary": "бережное обращение с ресурсами и практический расчет",
        "colors_action_by": "через трезвый расчет и бережное обращение с ресурсами",
    },
    "general": {
        "tone": "ровный",
        "style_summary": "ровный, осознанный темп без крайностей",
        "colors_action_by": "через ровный, осознанный темп",
    },
}

ENERGY_TAG_LABELS = {
    "start": "новые старты",
    "growth": "рост",
    "cleanup": "очищение",
    "completion": "завершение",
    "discipline": "порядок",
    "rhythm": "ритм",
    "collaboration": "сотрудничество",
    "creativity": "творчество",
    "movement": "движение",
    "learning": "обучение",
    "spiritual": "духовная практика",
    "softness": "мягкое развитие",
    "stability": "устойчивость",
    "conflict": "напряжение",
    "caution": "осторожность",
    "resources": "работа с ресурсами",
    "relationships": "отношения",
    "healing": "восстановление",
    "general": "обычный ритм дня",
}

TAG_RECOMMENDATION_FRAGMENTS = {
    "start": "начинайте с ясного намерения и простого первого шага",
    "growth": "поддерживайте процессы, которым нужно спокойно расти",
    "cleanup": "убирайте лишнее и освобождайте место для следующего этапа",
    "completion": "закрывайте хвосты и доводите начатое до понятного результата",
    "discipline": "держите порядок, структуру и практический фокус",
    "rhythm": "выбирайте ритмичные действия, где важны согласованность и темп",
    "collaboration": "опирайтесь на командность, договоренности и совместное действие",
    "creativity": "используйте день для творческого и живого проявления",
    "movement": "оставляйте место движению, поездкам и гибким задачам",
    "learning": "поддерживайте обучение, планирование и обмен знаниями",
    "spiritual": "оставьте время для практики, смысла и внутренней настройки",
    "softness": "действуйте мягко, без давления и лишней жесткости",
    "stability": "закрепляйте то, что должно держаться долго",
    "conflict": "не переводите напряжение в конфликт, используйте его для прояснения",
    "caution": "снижайте риск и не перегружайте день необратимыми решениями",
    "resources": "работайте с ресурсами трезво и без азартного риска",
    "relationships": "поддерживайте бережные договоренности и уважительный контакт",
    "healing": "уделяйте внимание восстановлению, лечению и телесной заботе",
    "general": "выбирайте ровный, осознанный темп дня",
}

TAG_KEYWORDS = (
    ("cleanup", ("очищ", "уборк", "хлам", "дезинфек", "стирк", "снос", "разруш", "отказ")),
    ("completion", ("заверш", "закрыт", "итог", "подведение", "долг", "обет")),
    ("start", ("начало", "новые начин", "старт", "запуск", "импульс", "инициатив")),
    ("growth", ("рост", "развит", "созид", "укреп", "расшир", "поддерж")),
    ("discipline", ("поряд", "дисциплин", "структур", "практич", "ответствен", "фокус")),
    ("rhythm", ("ритм", "музык", "танц", "концерт", "согласован")),
    ("collaboration", ("групп", "сотруднич", "команд", "переговор", "общени", "друж")),
    ("creativity", ("творч", "искус", "музык", "танц", "дизайн")),
    ("movement", ("подвиж", "поезд", "путеше", "транспорт", "переезд", "движ")),
    ("learning", ("обуч", "знани", "планирован", "самообраз", "курс", "тренинг")),
    ("spiritual", ("духов", "медитац", "паломнич", "храм", "благотвор")),
    ("softness", ("мягк", "гармони", "береж", "спокой", "отношен")),
    ("stability", ("устойчив", "долгоср", "фундамент", "стабил", "закреп")),
    ("conflict", ("конфликт", "суд", "соревн", "давлен")),
    ("caution", ("осторож", "риск", "не рекомендуется", "избег", "поспеш", "крайн")),
    ("resources", ("ресурс", "финанс", "покуп", "деньг", "выгод", "материал")),
    ("relationships", ("отношен", "семейн", "брак", "друж", "контакт")),
    ("healing", ("лечен", "здоров", "восстанов", "лекар", "тело", "массаж")),
)

QUALITY_TAGS = {
    "начальная": ("start",),
    "гармоничная": ("softness", "relationships"),
    "активная": ("movement", "start"),
    "напряженная": ("cleanup", "completion", "caution"),
    "благоприятная": ("growth", "softness"),
}

NAKSHATRA_TYPE_TAGS = {
    "Подвижная": ("movement",),
    "Мягкая": ("softness",),
    "Фиксированная": ("stability",),
    "Острая": ("conflict", "caution"),
    "Жесткая": ("conflict", "cleanup"),
    "Смешанная": ("caution",),
}

CONFLICTING_ENERGY_TAGS = {
    frozenset(("start", "completion")),
    frozenset(("start", "cleanup")),
    frozenset(("softness", "conflict")),
    frozenset(("stability", "movement")),
    frozenset(("growth", "cleanup")),
    frozenset(("resources", "caution")),
}


def first_sentence(text):
    if not text:
        return ""
    sentence = str(text).strip().split(".", 1)[0].strip()
    return f"{sentence}." if sentence else ""


def unique_preserve_order(items):
    result = []
    seen = set()
    for item in items or []:
        text = str(item).strip()
        key = text.lower()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return tuple(result)


def infer_energy_tags(data):
    tags = []
    quality = data.get("quality")
    if quality in QUALITY_TAGS:
        tags.extend(QUALITY_TAGS[quality])
    for nakshatra_type in data.get("types") or []:
        tags.extend(NAKSHATRA_TYPE_TAGS.get(nakshatra_type, ()))
    if data.get("rikta"):
        tags.extend(("cleanup", "completion", "caution"))

    haystack_parts = [
        data.get("summary", ""),
        data.get("description", ""),
        data.get("quality", ""),
        " ".join(data.get("types") or []),
        " ".join(data.get("favorable") or []),
    ]
    haystack = " ".join(haystack_parts).lower()
    for tag, keywords in TAG_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            tags.append(tag)

    return unique_preserve_order(tags) or ("general",)


def recommendation_fragments_for(tags):
    return tuple(TAG_RECOMMENDATION_FRAGMENTS[tag] for tag in tags if tag in TAG_RECOMMENDATION_FRAGMENTS)


def join_catalog_items(items):
    clean_items = unique_preserve_order(items)
    if len(clean_items) <= 1:
        return clean_items[0] if clean_items else ""
    return ", ".join(clean_items[:-1]) + " и " + clean_items[-1]


def choose_tag(tags, priority):
    for tag in priority:
        if tag in tags:
            return tag
    return tags[0] if tags else "general"


def make_base_catalog_entry(name, data):
    tags = infer_energy_tags(data)
    return {
        "name": name,
        "short_description": data.get("summary") or first_sentence(data.get("description", "")),
        "full_description": data.get("description", ""),
        "types": tuple(data.get("types") or ()),
        "good_for": normalize_catalog_items(data.get("favorable")),
        "avoid": normalize_catalog_items(data.get("unfavorable")),
        "energy_tags": tags,
        "recommendation_fragments": recommendation_fragments_for(tags),
    }


def make_tithi_entry(name, data):
    entry = make_base_catalog_entry(name, data)
    action_key = choose_tag(entry["energy_tags"], TITHI_ACTION_PRIORITY)
    action_profile = TITHI_ACTION_PROFILES[action_key]
    entry.update({
        "action_type": action_profile["action_type"],
        "supports": entry["good_for"],
        "task_summary": action_profile["task_summary"],
        "phase_rule": action_profile["phase_rule"],
    })
    return entry


def make_nakshatra_entry(name, data):
    entry = make_base_catalog_entry(name, data)
    tone_tags = tuple(tag for tag in NAKSHATRA_TONE_PRIORITY if tag in entry["energy_tags"])
    if not tone_tags:
        tone_tags = (choose_tag(entry["energy_tags"], NAKSHATRA_TONE_PRIORITY),)
    primary_tone = tone_tags[0]
    tone_profile = NAKSHATRA_TONE_PROFILES[primary_tone]
    style_profiles = [NAKSHATRA_TONE_PROFILES[tag] for tag in tone_tags[:3]]
    style_tones = [profile["tone"] for profile in style_profiles]
    style_labels = [ENERGY_TAG_LABELS.get(tag, tag) for tag in tone_tags[:3]]
    entry.update({
        "tone": tone_profile["tone"],
        "supports": entry["good_for"],
        "style_summary": f"{join_catalog_items(style_tones)} стиль",
        "colors_action_by": f"через {join_catalog_items(style_labels)}",
    })
    return entry


def build_tithi_catalog():
    catalog = {}
    for key, data in TITHIS_DATA.items():
        number = int(key)
        name = data.get("display") or data.get("ru") or key
        catalog[number] = make_tithi_entry(name, data)
    return catalog


def build_nakshatra_catalog():
    catalog = {}
    for key, data in NAKSHATRAS_DATA.items():
        name = data.get("ru") or key
        catalog[key] = make_nakshatra_entry(name, data)
    return catalog


TITHI_TEXTS = build_tithi_catalog()
NAKSHATRA_TEXTS = build_nakshatra_catalog()
TITHI_TEXT_CATALOG = TITHI_TEXTS
NAKSHATRA_TEXT_CATALOG = NAKSHATRA_TEXTS
NAKSHATRA_KEYS_BY_NUMBER = {
    index: key for index, key in enumerate(NAKSHATRA_TEXT_CATALOG.keys(), start=1)
}


def empty_entry(name="нет данных"):
    return {
        "name": name,
        "short_description": "",
        "good_for": (),
        "supports": (),
        "avoid": (),
        "energy_tags": ("general",),
        "recommendation_fragments": (TAG_RECOMMENDATION_FRAGMENTS["general"],),
        "action_type": TITHI_ACTION_PROFILES["general"]["action_type"],
        "task_summary": TITHI_ACTION_PROFILES["general"]["task_summary"],
        "phase_rule": TITHI_ACTION_PROFILES["general"]["phase_rule"],
        "tone": NAKSHATRA_TONE_PROFILES["general"]["tone"],
        "style_summary": NAKSHATRA_TONE_PROFILES["general"]["style_summary"],
        "colors_action_by": NAKSHATRA_TONE_PROFILES["general"]["colors_action_by"],
    }


def get_tithi_text(segment):
    if not segment:
        return empty_entry()
    number = segment.get("number") or segment.get("index")
    try:
        number = int(number)
    except (TypeError, ValueError):
        return empty_entry(segment.get("name") or "нет данных")
    return TITHI_TEXT_CATALOG.get(number) or empty_entry(segment.get("name") or str(number))


def get_nakshatra_text(segment):
    if not segment:
        return empty_entry()
    key = segment.get("key")
    if not key:
        number = segment.get("number") or segment.get("index")
        try:
            key = NAKSHATRA_KEYS_BY_NUMBER.get(int(number))
        except (TypeError, ValueError):
            key = None
    return NAKSHATRA_TEXT_CATALOG.get(key) or empty_entry(segment.get("name") or key or "нет данных")
