def build_recommendations(data):
    good_for = []
    avoid = []

    for section_name in ["vara", "tithi", "nakshatra"]:
        section = data.get(section_name)

        if section and section.get("data"):
            good_for += section["data"].get("good_for", [])
            avoid += section["data"].get("avoid", [])

    return {
        "good_for": list(dict.fromkeys(good_for)),
        "avoid": list(dict.fromkeys(avoid)),
    }