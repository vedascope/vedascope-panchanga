#!/usr/bin/env python3
import argparse
import csv
import re
import sqlite3
import string
import tempfile
import unicodedata
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


GEONAMES_CITIES1000_URL = "https://download.geonames.org/export/dump/cities1000.zip"
GEONAMES_CITIES1000_FALLBACK_URL = "http://download.geonames.org/export/dump/cities1000.zip"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "locations.sqlite"
SEARCH_PUNCTUATION = str.maketrans({char: " " for char in string.punctuation + "«»“”„’‘´`№"})


def normalize_search_text(value):
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.strip().lower().replace("ё", "е")
    text = text.translate(SEARCH_PUNCTUATION)
    return re.sub(r"\s+", " ", text).strip()


def parse_args():
    parser = argparse.ArgumentParser(description="Build vedascope GeoNames location SQLite database.")
    parser.add_argument(
        "--cities-zip",
        type=Path,
        help="Local path to GeoNames cities1000.zip. If omitted, the script downloads it.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output SQLite database path. Default: {DEFAULT_OUT}",
    )
    return parser.parse_args()


def download_cities_zip():
    handle = tempfile.NamedTemporaryFile(prefix="geonames-cities1000-", suffix=".zip", delete=False)
    handle.close()
    target = Path(handle.name)
    try:
        urllib.request.urlretrieve(GEONAMES_CITIES1000_URL, target)
    except urllib.error.URLError:
        urllib.request.urlretrieve(GEONAMES_CITIES1000_FALLBACK_URL, target)
    return target


def create_schema(connection):
    connection.executescript(
        """
        DROP TABLE IF EXISTS location_names;
        DROP TABLE IF EXISTS locations;

        CREATE TABLE locations (
            geoname_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            ascii_name TEXT,
            alternate_names TEXT,
            country_code TEXT NOT NULL,
            admin1_code TEXT,
            admin2_code TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timezone TEXT NOT NULL,
            population INTEGER DEFAULT 0,
            feature_code TEXT,
            source TEXT NOT NULL DEFAULT 'geonames'
        );

        CREATE TABLE location_names (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            geoname_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            normalized TEXT NOT NULL,
            kind TEXT NOT NULL,
            FOREIGN KEY (geoname_id) REFERENCES locations(geoname_id)
        );

        CREATE INDEX idx_location_names_normalized ON location_names(normalized);
        CREATE INDEX idx_location_names_geoname_id ON location_names(geoname_id);
        CREATE INDEX idx_locations_population ON locations(population DESC);
        CREATE INDEX idx_locations_country_admin ON locations(country_code, admin1_code);
        """
    )


def add_search_name(names, geoname_id, name, kind):
    normalized = normalize_search_text(name)
    if not normalized:
        return
    key = (geoname_id, normalized, kind)
    if key in names:
        return
    names[key] = (geoname_id, name.strip(), normalized, kind)


def iter_city_rows(zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        member = "cities1000.txt"
        if member not in archive.namelist():
            member = next((name for name in archive.namelist() if name.endswith(".txt")), None)
        if not member:
            raise RuntimeError("No GeoNames text file found in zip archive.")

        with archive.open(member) as raw_file:
            text_file = (line.decode("utf-8") for line in raw_file)
            yield from csv.reader(text_file, delimiter="\t")


def build_database(zip_path, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    imported_locations = 0
    skipped_rows = 0
    search_names = {}

    with sqlite3.connect(tmp_path) as connection:
        create_schema(connection)

        for row in iter_city_rows(zip_path):
            if len(row) < 19:
                skipped_rows += 1
                continue

            geoname_id = row[0]
            name = row[1]
            ascii_name = row[2]
            alternate_names = row[3]
            latitude = row[4]
            longitude = row[5]
            feature_class = row[6]
            feature_code = row[7]
            country_code = row[8]
            admin1_code = row[10]
            admin2_code = row[11]
            population = row[14] or 0
            timezone = row[17]

            if feature_class != "P" or not latitude or not longitude or not timezone:
                skipped_rows += 1
                continue

            try:
                geoname_id_int = int(geoname_id)
                latitude_float = float(latitude)
                longitude_float = float(longitude)
                population_int = int(population)
            except ValueError:
                skipped_rows += 1
                continue

            connection.execute(
                """
                INSERT INTO locations (
                    geoname_id, name, ascii_name, alternate_names, country_code,
                    admin1_code, admin2_code, latitude, longitude, timezone,
                    population, feature_code, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'geonames')
                """,
                (
                    geoname_id_int,
                    name,
                    ascii_name,
                    alternate_names,
                    country_code,
                    admin1_code,
                    admin2_code,
                    latitude_float,
                    longitude_float,
                    timezone,
                    population_int,
                    feature_code,
                ),
            )
            imported_locations += 1

            add_search_name(search_names, geoname_id_int, name, "canonical")
            add_search_name(search_names, geoname_id_int, ascii_name, "ascii")
            for alternate in alternate_names.split(","):
                add_search_name(search_names, geoname_id_int, alternate, "alternate")

        connection.executemany(
            """
            INSERT INTO location_names (geoname_id, name, normalized, kind)
            VALUES (?, ?, ?, ?)
            """,
            search_names.values(),
        )

        location_count = connection.execute("SELECT count(*) FROM locations").fetchone()[0]
        name_count = connection.execute("SELECT count(*) FROM location_names").fetchone()[0]
        if location_count <= 0 or name_count <= 0:
            raise RuntimeError("GeoNames import validation failed: empty locations or names table.")

        connection.execute("PRAGMA optimize")

    tmp_path.replace(out_path)
    return {
        "imported_locations": imported_locations,
        "imported_names": len(search_names),
        "skipped_rows": skipped_rows,
        "db_path": out_path,
    }


def main():
    args = parse_args()
    downloaded_zip = None
    zip_path = args.cities_zip
    if zip_path is None:
        downloaded_zip = download_cities_zip()
        zip_path = downloaded_zip

    try:
        summary = build_database(zip_path, args.out)
    finally:
        if downloaded_zip and downloaded_zip.exists():
            downloaded_zip.unlink()

    print(f"Imported locations: {summary['imported_locations']}")
    print(f"Imported names: {summary['imported_names']}")
    print(f"Skipped rows: {summary['skipped_rows']}")
    print(f"DB path: {summary['db_path']}")


if __name__ == "__main__":
    main()
