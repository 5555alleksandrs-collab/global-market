from datetime import datetime
from zoneinfo import ZoneInfo
import unittest

from competitor_price_monitor.auto_refresh_schedule import (
    calculate_next_daily_run,
    format_daily_schedule_text,
    normalize_daily_time,
    seconds_until_next_daily_run,
)


class AutoRefreshScheduleTests(unittest.TestCase):
    def test_normalize_daily_time_defaults_invalid_value(self):
        self.assertEqual(normalize_daily_time("25:99"), "10:00")
        self.assertEqual(normalize_daily_time("9:5"), "09:05")

    def test_calculate_next_daily_run_same_day_before_target(self):
        now = datetime(2026, 3, 30, 9, 15, tzinfo=ZoneInfo("Europe/Moscow"))

        next_run = calculate_next_daily_run(
            now=now,
            daily_time="10:00",
            timezone_name="Europe/Moscow",
        )

        self.assertEqual(next_run, datetime(2026, 3, 30, 10, 0, tzinfo=ZoneInfo("Europe/Moscow")))

    def test_calculate_next_daily_run_moves_to_next_day_after_target(self):
        now = datetime(2026, 3, 30, 10, 0, 1, tzinfo=ZoneInfo("Europe/Moscow"))

        next_run = calculate_next_daily_run(
            now=now,
            daily_time="10:00",
            timezone_name="Europe/Moscow",
        )

        self.assertEqual(next_run, datetime(2026, 3, 31, 10, 0, tzinfo=ZoneInfo("Europe/Moscow")))

    def test_seconds_until_next_daily_run(self):
        now = datetime(2026, 3, 30, 9, 30, tzinfo=ZoneInfo("Europe/Moscow"))

        seconds = seconds_until_next_daily_run(
            now=now,
            daily_time="10:00",
            timezone_name="Europe/Moscow",
        )

        self.assertEqual(seconds, 1800)

    def test_format_daily_schedule_text_for_moscow(self):
        self.assertEqual(
            format_daily_schedule_text("10:00", "Europe/Moscow"),
            "каждый день в 10:00 МСК",
        )


if __name__ == "__main__":
    unittest.main()
