# GeoNames location search

`GET /locations/search` uses a local SQLite database built from GeoNames, with
`data/locations.seed.json` kept as a manual override and fallback.

## Source

Default source:

- GeoNames `cities1000.zip`
- URL: `https://download.geonames.org/export/dump/cities1000.zip`

The importer keeps populated places with feature class `P` and skips rows without
latitude, longitude, or IANA timezone.

GeoNames data requires attribution. See the GeoNames license and terms before
publishing generated city data.

## Import

Build the database:

```bash
python scripts/import_geonames_locations.py --out data/locations.sqlite
```

Use a local archive instead of downloading:

```bash
python scripts/import_geonames_locations.py \
  --cities-zip /tmp/cities1000.zip \
  --out data/locations.sqlite
```

The script writes `data/locations.sqlite.tmp`, validates row counts, then renames
it to `data/locations.sqlite`.

The generated SQLite database is intentionally ignored by git:

- `data/*.sqlite`
- `data/*.sqlite.tmp`

## Runtime behavior

`/locations/search` searches in this order:

1. `data/locations.seed.json`
2. `data/locations.sqlite`

Results first rank by match quality (exact, prefix, then contains), preferring a
canonical match over an alternate-name match of the same type. Within equally
direct matches, Russian cities rank first, followed by nearby/CIS countries,
then other countries; population breaks ties within each group. Seed entries
remain manual overrides for localized labels and coordinates, and duplicate
GeoNames entries are omitted.

When available, a Cyrillic alternate name is used as the display name. The
canonical/ASCII spelling is retained in the bounded alias list. Common country
codes are displayed in Russian; admin region codes remain unchanged.

This behavior uses the existing `alternate_names`, `country_code`, and
`population` columns, so an existing database does not need regeneration.

If `data/locations.sqlite` is missing, the endpoint still works with seed data
only.

Response shape remains compatible:

```json
{
  "id": "geonames:2759794",
  "name": "Amsterdam",
  "country": "Нидерланды",
  "region": "NH",
  "latitude": 52.37403,
  "longitude": 4.88969,
  "timezone": "Europe/Amsterdam",
  "aliases": ["Amsterdam"],
  "source": "geonames"
}
```

When localized country or region names are unavailable, the endpoint returns
GeoNames country and admin codes.

## Deployment

```bash
cd /root/vedascope-panchanga
python -m py_compile main.py scripts/import_geonames_locations.py
# Regeneration is only needed when refreshing the underlying GeoNames data:
python scripts/import_geonames_locations.py --out data/locations.sqlite
sqlite3 data/locations.sqlite 'select count(*) from locations;'
systemctl restart vedascope-panchanga.service
systemctl status vedascope-panchanga.service
```

Production nginx already maps:

```text
/api/locations/search -> /locations/search
```

## Checks

```bash
curl 'http://127.0.0.1:8000/locations/search?q=Amsterdam'
curl 'http://127.0.0.1:8000/locations/search?q=New%20York'
curl 'http://127.0.0.1:8000/locations/search?q=Delhi'
curl 'http://127.0.0.1:8000/locations/search?q=Tokyo'
curl 'http://127.0.0.1:8000/locations/search?q=Sydney'
curl 'http://127.0.0.1:8000/locations/search?q=Gatchina'
curl 'http://127.0.0.1:8000/locations/search?q=гатч'
curl 'http://127.0.0.1:8000/locations/search?q=минск'
curl 'http://127.0.0.1:8000/locations/search?q=алматы'
curl 'http://127.0.0.1:8000/locations/search?q=ташкент'
```

## TODO

- Add localized region names.
- Add external geocoder fallback with cache for places absent from `cities1000`.
- Consider `alternateNamesV2.zip` for richer language-specific aliases.
