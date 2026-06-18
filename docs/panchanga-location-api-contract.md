# Panchanga backend API contract

## `GET /locations/search`

Seed-backed location search for panchanga clients.

Example:

```http
GET /locations/search?q=ам
```

Returns up to 10 location objects by default, capped at 20 via `limit`.
Empty query returns `[]`.

Location shape:

```json
{
  "id": "seed:amsterdam-nl",
  "name": "Амстердам",
  "country": "Нидерланды",
  "region": "Северная Голландия",
  "latitude": 52.3676,
  "longitude": 4.9041,
  "timezone": "Europe/Amsterdam",
  "aliases": ["Amsterdam"],
  "source": "seed"
}
```

Production nginx should expose this as:

```http
GET /api/locations/search?q=ам
```

## `GET /grahas`

Clean JSON endpoint for graha longitudes and derived sign/nakshatra/pada indexes.

Example:

```http
GET /grahas?date=2026-06-18&time=09:00&lat=52.3676&lon=4.9041&tz=Europe/Amsterdam
```

Required:

- `date` as `YYYY-MM-DD`;
- `time` as `HH:MM`;
- `lat`;
- `lon`;
- `tz` as IANA timezone, preferred.

Fallback:

- numeric `timezone` is accepted only when `tz` is absent or cannot be resolved.

Response includes:

- `input`;
- `location`;
- `calculation`;
- `grahas`.

Grahas returned:

- Sun;
- Moon;
- Mars;
- Mercury;
- Jupiter;
- Venus;
- Saturn;
- Rahu;
- Ketu.

Index formulas:

- `signIndex = floor(longitude / 30)`;
- `degreeInSign = longitude % 30`;
- `nakshatraIndex = floor(longitude / (360 / 27))`;
- `nakshatraNumber = nakshatraIndex + 1`;
- `padaIndex = floor(longitude / (360 / 108))`;
- `padaNumber = padaIndex + 1`;
- `padaInNakshatra = floor((longitude % (360 / 27)) / (360 / 108)) + 1`.

Production nginx should expose this as:

```http
GET /api/grahas?date=2026-06-18&time=09:00&lat=52.3676&lon=4.9041&tz=Europe/Amsterdam
```

## Existing routes

These routes must remain working:

- `/panchanga`;
- `/panchanga/text`;
- `/panchanga/html`;
- `/full/html`;
- `/chart/svg`.

Sky Clock is intentionally out of scope for this change.
