# VedaClock State API

`GET /api/v1/veda-clock/state` is a presentation endpoint for VedaScope Clock.

It does not introduce a new astrology calculation engine. It reuses the existing astro core:

- `astro.chart.calculate_chart()` for sidereal graha longitudes;
- `astro.panchanga.calculate_panchanga()` for panchanga summary fields.

## Query Parameters

- `lat`: latitude, default `55.7558`.
- `lon`: longitude, default `37.6173`.
- `timezone`: IANA timezone, default `Europe/Moscow`.
- `datetime`: optional ISO datetime.
- `ayanamsha`: optional, default `lahiri`.
- `lang`: optional, default `ru`.

## Timezone Behavior

When `datetime` is absent, the endpoint uses the current instant and converts it to the requested timezone.

When `datetime` has an offset, that exact instant is used and displayed in the requested timezone.

When `datetime` has no offset, it is interpreted as local time in the requested timezone.

The response includes:

- `datetime`: effective local datetime with offset;
- `dateLabel`: local `DD.MM.YY`;
- `time`: local hour/minute/second;
- `calculationInstantUtc`: UTC instant used for graha calculation.

## Ayanamsha

Current supported value:

- `lahiri`

Unsupported values return `400`.

## Response Example

```json
{
  "schemaVersion": "veda-clock-state/v1",
  "datetime": "2026-07-01T10:08:00+03:00",
  "timezone": "Europe/Moscow",
  "dateLabel": "01.07.26",
  "time": {
    "hour": 10,
    "minute": 8,
    "second": 0
  },
  "calculationInstantUtc": "2026-07-01T07:08:00Z",
  "grahas": [
    {
      "key": "Mo",
      "longitude": 250.1234,
      "rashi": 9,
      "degreeInRashi": 10.1234,
      "nakshatra": 19,
      "nakshatraName": "Mula",
      "pada": 4,
      "globalPada": 76
    }
  ],
  "activeNakshatras": [19],
  "activePadas": [76],
  "panchanga": {
    "tithi": "…",
    "vara": "…",
    "yoga": "…",
    "karana": "…",
    "lunarNakshatra": "…"
  },
  "meta": {
    "ayanamsha": "lahiri",
    "lang": "ru",
    "location": {
      "lat": 55.7558,
      "lon": 37.6173
    },
    "generatedAt": "2026-07-01T07:08:00Z",
    "calculationSource": "existing-astro-core"
  }
}
```

The real response contains all required grahas:

`Su`, `Mo`, `Ma`, `Me`, `Ju`, `Ve`, `Sa`, `Ra`, `Ke`.

## Error Cases

- Invalid timezone: `400`.
- Invalid datetime: `400`.
- Unsupported ayanamsha: `400`.
- Invalid lat/lon: FastAPI validation error.
- Missing required graha calculation: no partial success; endpoint returns an error.

## Caching

The endpoint currently returns:

```http
Cache-Control: public, max-age=30
```

This is intended for short-lived web preview refreshes.

## Local Preview CORS

For local static preview testing, the backend allows browser requests from:

```text
http://localhost:<port>
http://127.0.0.1:<port>
```

Production should normally use same-origin reverse proxy routing for `/api/v1/veda-clock/*` instead of `apiBase`.

The site repository documents the production nginx route and rollback checklist in
`docs/veda-clock-production-routing.md`.
This backend repository also includes `deploy/nginx/veda-clock-location.conf.example`.
