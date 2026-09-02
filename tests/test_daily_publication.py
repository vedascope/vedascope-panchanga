import re
import unittest
from datetime import datetime
from html.parser import HTMLParser
from unittest import mock
from zoneinfo import ZoneInfo

import daily_post
from astro.panchanga import calculate_panchanga
from astro.text_builder import (
    build_telegram_compact_panchanga_text,
    build_telegram_panchanga_text,
)
from astro.text_catalog import get_tithi_text


MOSCOW = ZoneInfo("Europe/Moscow")
MOSCOW_COORDS = {"latitude": 55.7558, "longitude": 37.6173}


def make_segment(kind, number, name, start, end):
    key = name if kind == "nakshatra" else None
    segment = {
        "kind": kind,
        "number": number,
        "index": number,
        "name": name,
        "display": name,
        "starts_at": f"2026-09-02T{start}",
        "starts_at_time": start,
        "ends_at": f"2026-09-{'03' if end == '00:00' else '02'}T{end}",
        "ends_at_time": end,
        "is_current_at_publish_time": False,
        "data": {},
    }
    if key:
        segment["key"] = key
    return segment


class BalancedTelegramHtml(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag in {"b", "blockquote", "a"}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in {"b", "blockquote", "a"}:
            if not self.stack or self.stack.pop() != tag:
                raise AssertionError(f"unbalanced Telegram tag: {tag}")


class DailyPublicationWindowTests(unittest.TestCase):
    def calculate(self, date_value):
        year, month, day = map(int, date_value.split("-"))
        return calculate_panchanga(
            year,
            month,
            day,
            timezone=3,
            hour=6,
            minute=0,
            timezone_name="Europe/Moscow",
            **MOSCOW_COORDS,
        )

    def test_period_ending_before_publish_time_is_removed(self):
        segments = [
            make_segment("tithi", 20, "20 лунные сутки", "00:00", "03:43"),
            make_segment("tithi", 21, "21 лунные сутки", "03:43", "00:00"),
        ]
        filtered = daily_post.filter_segments_for_publication(
            segments, datetime(2026, 9, 2, 6, 0, tzinfo=MOSCOW)
        )
        self.assertEqual([item["number"] for item in filtered], [21])
        self.assertTrue(filtered[0]["is_current_at_publish_time"])

    def test_period_ending_exactly_at_publish_time_is_removed(self):
        segments = [
            make_segment("tithi", 20, "20 лунные сутки", "00:00", "06:00"),
            make_segment("tithi", 21, "21 лунные сутки", "06:00", "00:00"),
        ]
        filtered = daily_post.filter_segments_for_publication(
            segments, datetime(2026, 9, 2, 6, 0, tzinfo=MOSCOW)
        )
        self.assertEqual([item["number"] for item in filtered], [21])

    def test_period_crossing_publish_time_is_kept_without_old_start(self):
        segments = [
            make_segment("tithi", 21, "21 лунные сутки", "03:43", "12:30"),
            make_segment("tithi", 22, "22 лунные сутки", "12:30", "00:00"),
        ]
        filtered = daily_post.filter_segments_for_publication(
            segments, datetime(2026, 9, 2, 6, 0, tzinfo=MOSCOW)
        )
        text = daily_post.format_lunar_periods(filtered)
        self.assertIn("до 12:30 — 21 лунные сутки", text)
        self.assertIn("с 12:30 — 22 лунные сутки", text)
        self.assertNotIn("03:43", text)

    def test_no_later_transition_renders_only_current_name(self):
        segment = make_segment("tithi", 21, "21 лунные сутки", "03:43", "00:00")
        filtered = daily_post.filter_segments_for_publication(
            [segment], datetime(2026, 9, 2, 6, 0, tzinfo=MOSCOW)
        )
        self.assertEqual(daily_post.format_lunar_periods(filtered), "21 лунные сутки")

    def test_multiple_transitions_after_publish_time_are_preserved(self):
        segments = [
            make_segment("tithi", 21, "21 лунные сутки", "03:43", "08:10"),
            make_segment("tithi", 22, "22 лунные сутки", "08:10", "14:20"),
            make_segment("tithi", 23, "23 лунные сутки", "14:20", "00:00"),
        ]
        filtered = daily_post.filter_segments_for_publication(
            segments, datetime(2026, 9, 2, 6, 0, tzinfo=MOSCOW)
        )
        text = daily_post.format_lunar_periods(filtered)
        self.assertEqual([item["number"] for item in filtered], [21, 22, 23])
        self.assertIn("до 08:10 — 21 лунные сутки", text)
        self.assertIn("с 08:10 до 14:20 — 22 лунные сутки", text)
        self.assertIn("с 14:20 — 23 лунные сутки", text)
        self.assertNotIn("03:43", text)

    def test_same_filter_is_applied_to_tithi_and_nakshatra(self):
        source = self.calculate("2026-09-02")
        prepared = daily_post.prepare_daily_publication_data(source, 6, 0)
        self.assertEqual(
            [item["number"] for item in prepared["day_dynamics"]["tithi_segments"]],
            [21],
        )
        self.assertEqual(
            [item["name"] for item in prepared["day_dynamics"]["nakshatra_segments"]],
            ["Бхарани", "Криттика"],
        )

    def test_real_september_second_removes_old_tithi_and_description(self):
        prepared = daily_post.prepare_daily_publication_data(self.calculate("2026-09-02"), 6, 0)
        telegram = build_telegram_panchanga_text(prepared)
        old_entry = get_tithi_text({"number": 20})
        self.assertNotIn("20 лунные сутки", telegram)
        for field in ("short_description", "full_description"):
            self.assertNotIn(old_entry[field], telegram)
        self.assertIn("<b>21 лунные сутки</b>", telegram)

    def test_full_compact_and_vk_have_identical_period_sets(self):
        prepared = daily_post.prepare_daily_publication_data(self.calculate("2026-09-02"), 6, 0)
        full = build_telegram_panchanga_text(prepared)
        compact = build_telegram_compact_panchanga_text(prepared)
        vk = daily_post.telegram_html_to_vk_text(full)
        expected = ["21 лунные сутки", "Бхарани", "Криттика"]
        self.assertEqual(full, compact)
        for name in expected:
            self.assertIn(name, full)
            self.assertIn(name, vk)
        self.assertNotIn("20 лунные сутки", full)
        self.assertNotIn("20 лунные сутки", vk)

    def test_entire_period_line_is_bold_and_descriptions_are_not(self):
        prepared = daily_post.prepare_daily_publication_data(self.calculate("2026-09-30"), 6, 0)
        telegram = build_telegram_panchanga_text(prepared)
        self.assertRegex(telegram, r"<b>до 12:25 — 19 лунные сутки</b>")
        self.assertRegex(telegram, r"<b>с 12:25 — 20 лунные сутки</b>")
        self.assertRegex(telegram, r"<b>Криттика(?: \([^<]+\))?</b>")
        self.assertNotRegex(telegram, r"<b>[^<]*(?:Описание|Энергия)[^<]*</b>")

    def test_telegram_chunks_keep_valid_markup_and_vk_has_no_html(self):
        prepared = daily_post.prepare_daily_publication_data(self.calculate("2026-09-02"), 6, 0)
        telegram = build_telegram_panchanga_text(prepared)
        chunks = daily_post.split_html_messages(telegram, limit=900)
        self.assertIsNotNone(chunks)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            parser = BalancedTelegramHtml()
            parser.feed(chunk)
            parser.close()
            self.assertEqual(parser.stack, [])
        self.assertIsNone(re.search(r"</?[A-Za-z][^>]*>", daily_post.telegram_html_to_vk_text(telegram)))

    def test_dry_run_never_calls_telegram_or_vk_network(self):
        argv = ["daily_post.py", "--dry-run", "--date", "2026-09-02", "--hour", "6", "--minute", "0"]
        with (
            mock.patch("sys.argv", argv),
            mock.patch.object(daily_post, "load_env_file"),
            mock.patch.object(daily_post, "calculate_panchanga", return_value=self.calculate("2026-09-02")),
            mock.patch.object(daily_post, "generate_chart_images", return_value={"south": mock.Mock(), "north": mock.Mock()}),
            mock.patch.object(daily_post, "telegram_api_request") as telegram_request,
            mock.patch.object(daily_post, "vk_api_request") as vk_request,
        ):
            for image in daily_post.generate_chart_images.return_value.values():
                image.stat.return_value.st_size = 1
            daily_post.main()
        telegram_request.assert_not_called()
        vk_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
