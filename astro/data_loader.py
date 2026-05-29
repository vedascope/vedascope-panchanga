import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def load_json(filename):
    path = BASE_DIR / "data" / filename

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


VARAS = load_json("varas.json")
TITHIS_DATA = load_json("tithis.json")
NAKSHATRAS_DATA = load_json("nakshatras.json")
NAKSHATRA_TYPES = load_json("nakshatra_types.json")
MOON_SIGNS = load_json("moon_signs.json")