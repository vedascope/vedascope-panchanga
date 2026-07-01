import unittest

from fastapi import HTTPException, Response

from astro.veda_clock import build_veda_clock_state, derive_graha
from main import grahas, panchanga, veda_clock_state


class VedaClockStateTests(unittest.TestCase):
    def get_state(self, **params):
        payload = {
            "latitude": 55.7558,
            "longitude": 37.6173,
            "timezone": "Europe/Moscow",
            **params,
        }
        return build_veda_clock_state(**payload)

    def test_no_datetime_returns_local_current_date_time_for_timezone(self):
        data = self.get_state()

        self.assertEqual(data["timezone"], "Europe/Moscow")
        self.assertTrue(data["datetime"].endswith("+03:00"))
        self.assertEqual(data["dateLabel"], local_date_label(data["datetime"]))
        self.assertEqual(data["time"]["hour"], int(data["datetime"][11:13]))
        self.assertEqual(data["time"]["minute"], int(data["datetime"][14:16]))
        self.assertTrue(data["calculationInstantUtc"].endswith("Z"))

    def test_datetime_with_offset_preserves_instant(self):
        data = self.get_state(datetime_value="2026-07-01T10:08:30+03:00")

        self.assertEqual(data["datetime"], "2026-07-01T10:08:30+03:00")
        self.assertEqual(data["calculationInstantUtc"], "2026-07-01T07:08:30Z")
        self.assertEqual(data["dateLabel"], "01.07.26")
        self.assertEqual(data["time"], {"hour": 10, "minute": 8, "second": 30})

    def test_datetime_without_offset_is_interpreted_in_timezone(self):
        data = self.get_state(datetime_value="2026-07-01T10:08:30")

        self.assertEqual(data["datetime"], "2026-07-01T10:08:30+03:00")
        self.assertEqual(data["calculationInstantUtc"], "2026-07-01T07:08:30Z")

    def test_endpoint_route_sets_cache_header(self):
        response = Response()
        data = veda_clock_state(
            response=response,
            datetime="2026-07-01T10:08:00+03:00",
            lat=55.7558,
            lon=37.6173,
            timezone="Europe/Moscow",
        )

        self.assertEqual(response.headers["Cache-Control"], "public, max-age=30")
        self.assertEqual(data["schemaVersion"], "veda-clock-state/v1")

    def test_all_required_grahas_are_present_and_normalized(self):
        data = self.get_state(datetime_value="2026-07-01T10:08:00+03:00")
        keys = [graha["key"] for graha in data["grahas"]]

        self.assertEqual(keys, ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"])
        for graha in data["grahas"]:
            self.assertGreaterEqual(graha["longitude"], 0)
            self.assertLess(graha["longitude"], 360)
            self.assertEqual(graha["rashi"], int(graha["longitude"] // 30) + 1)
            self.assertEqual(graha["nakshatra"], int(graha["longitude"] // (360 / 27)) + 1)
            self.assertEqual(graha["globalPada"], int(graha["longitude"] // (360 / 108)) + 1)
            self.assertEqual(graha["pada"], ((graha["globalPada"] - 1) % 4) + 1)

    def test_active_segments_have_no_duplicates_and_come_from_grahas(self):
        data = self.get_state(datetime_value="2026-07-01T10:08:00+03:00")

        self.assertEqual(data["activeNakshatras"], sorted({graha["nakshatra"] for graha in data["grahas"]}))
        self.assertEqual(data["activePadas"], sorted({graha["globalPada"] for graha in data["grahas"]}))

    def test_boundary_derivations(self):
        zero = derive_graha("Su", 360)
        final = derive_graha("Mo", 359.999)

        self.assertEqual(zero["longitude"], 0)
        self.assertEqual(zero["rashi"], 1)
        self.assertEqual(zero["nakshatra"], 1)
        self.assertEqual(zero["globalPada"], 1)
        self.assertEqual(final["rashi"], 12)
        self.assertEqual(final["nakshatra"], 27)
        self.assertEqual(final["globalPada"], 108)

    def test_invalid_params_return_errors(self):
        cases = [
            {"timezone": "Not/AZone"},
            {"datetime_value": "not-a-date"},
            {"ayanamsha": "raman"},
            {"latitude": 91},
        ]

        for params in cases:
            with self.subTest(params=params):
                with self.assertRaises(HTTPException) as context:
                    self.get_state(**params)
                self.assertEqual(context.exception.status_code, 400)

    def test_existing_panchanga_and_grahas_endpoints_still_work(self):
        panchanga_data = panchanga(
            year=2026,
            month=7,
            day=1,
            hour=10,
            minute=8,
            timezone=3,
            latitude=55.7558,
            longitude=37.6173,
        )
        grahas_data = grahas(
            date="2026-07-01",
            time="10:08",
            lat=55.7558,
            lon=37.6173,
            tz="Europe/Moscow",
        )

        self.assertIn("tithi", panchanga_data)
        self.assertEqual(len(grahas_data["grahas"]), 9)


def local_date_label(datetime_value):
    year = datetime_value[2:4]
    month = datetime_value[5:7]
    day = datetime_value[8:10]
    return f"{day}.{month}.{year}"


if __name__ == "__main__":
    unittest.main()
