import datetime
import unittest

import freezegun
import numpy as np
import pytz
from calendra.europe import France

from weeksched.schedule import Day, WeeklySchedule


class TestCtrlSchedule(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_invalid_timezone(self):
        with self.assertRaises(pytz.UnknownTimeZoneError):
            WeeklySchedule().for_timezone("invalid")

    def test_from_raw_complex_schedule(self):
        complex_schedule = self.complex_schedule()
        ctrl = WeeklySchedule.from_raw(complex_schedule).for_timezone("Europe/Paris")
        self.assertIsNotNone(ctrl.schedule)
        self.assertDictEqual(complex_schedule, ctrl.formatted_schedule)
        self.assertEqual("Europe/Paris", ctrl.timezone)
        self.assertEqual(pytz.timezone("Europe/Paris"), ctrl._pytz)

    def test_from_raw_typical_schedule(self):
        typical_schedule = self.typical_weekly_schedule()
        ctrl = WeeklySchedule.from_raw(typical_schedule)
        self.assertIsNotNone(ctrl.schedule)
        self.assertDictEqual(typical_schedule, ctrl.formatted_schedule)

    def test_fluent(self):
        weekday = ((6, 0), (18, 0))
        saturday = ((6, 0), (12, 0))
        ctrl = (
            WeeklySchedule()
            .for_timezone("Europe/Paris")
            .monday(weekday)
            .tuesday(weekday)
            .wednesday(weekday)
            .thursday(weekday)
            .friday(weekday)
            .saturday(saturday)
        )

        self.assertDictEqual(
            {0: weekday, 1: weekday, 2: weekday, 3: weekday, 4: weekday, 5: saturday},
            ctrl.format_schedule(),
        )

    def test_empty(self):
        with self.assertRaises(AssertionError):
            WeeklySchedule.from_raw({})

    def test_invalid_week_day(self):
        with self.assertRaises(AssertionError) as e:
            WeeklySchedule.from_raw({7: ((0, 0), (24, 0))})
            self.assertEqual("day should be in range 0-6", str(e))

    def test_invalid_start_time(self):
        with self.assertRaises(AssertionError) as e:
            WeeklySchedule.from_raw({0: ((-1, 0), (9, 0))})
            self.assertEqual("start time should be 00:00 <= x <= 24:00", str(e))

    def test_invalid_end_time(self):
        with self.assertRaises(AssertionError) as e:
            WeeklySchedule.from_raw({0: ((9, 0), (25, 0))})
            self.assertEqual("end time should be 00:00 <= x <= 24:00", str(e))

    def test_invalid_start_end_overlap(self):
        with self.assertRaises(AssertionError) as e:
            WeeklySchedule.from_raw({0: ((10, 0), (9, 0))})
            self.assertEqual("start time should be before end time", str(e))

    def test_from_to(self):
        weekday = ((6, 0), (18, 0))
        saturday = ((6, 0), (12, 0))
        ctrl = (
            WeeklySchedule()
            .for_timezone("Europe/Paris")
            .from_to(Day.Monday, Day.Friday, weekday)
            .saturday(saturday)
        )

        self.assertDictEqual(
            {0: weekday, 1: weekday, 2: weekday, 3: weekday, 4: weekday, 5: saturday},
            ctrl.format_schedule(),
        )

    def test_equal(self):
        ctrl1 = WeeklySchedule().from_raw(self.typical_weekly_schedule()).for_timezone("UTC")
        ctrl2 = (
            WeeklySchedule().from_to(Day.Monday, Day.Friday, ((7, 0), (20, 0))).for_timezone("UTC")
        )
        self.assertEqual(ctrl1, ctrl2)

    def test_is_on(self):
        ctrl = WeeklySchedule.from_raw(self.complex_schedule()).for_timezone("UTC")

        with freezegun.freeze_time("2022-02-11 06:59:00+00:00"):
            self.assertTrue(ctrl.is_on())

        with freezegun.freeze_time("2022-02-11 07:00:00+00:00"):
            self.assertFalse(ctrl.is_on())

        with freezegun.freeze_time("2022-02-11 19:59:59+00:00"):
            self.assertFalse(ctrl.is_on())

        with freezegun.freeze_time("2022-02-11 20:00:00+00:00"):
            self.assertTrue(ctrl.is_on())

        with freezegun.freeze_time("2022-02-12 10:00:00+00:00"):
            self.assertTrue(ctrl.is_on())

    def test_is_on_working_days_calendar(self):
        ctrl_no_cal = WeeklySchedule.from_raw(self.typical_weekly_schedule()).for_timezone("UTC")

        with freezegun.freeze_time("2022-02-15 10:00:00+00:00"):
            self.assertTrue(ctrl_no_cal.is_on())

        with freezegun.freeze_time("2024-05-08 10:00:00+00:00"):
            self.assertTrue(ctrl_no_cal.is_on())

        calendar = France()
        ctrl_with_cal = (
            WeeklySchedule.from_raw(self.typical_weekly_schedule())
            .for_timezone("UTC")
            .with_working_days_calendar(calendar)
        )

        with freezegun.freeze_time("2022-02-15 10:00:00+00:00"):
            self.assertTrue(ctrl_with_cal.is_on())

        with freezegun.freeze_time("2024-05-08 10:00:00+00:00"):
            self.assertFalse(ctrl_with_cal.is_on())

        ctrl_with_cal = (
            WeeklySchedule.from_raw(self.typical_weekly_schedule())
            .for_timezone("UTC")
            .with_working_days_calendar(lambda d: False)
        )

        with freezegun.freeze_time("2022-02-15 10:00:00+00:00"):
            self.assertFalse(ctrl_with_cal.is_on())

        with freezegun.freeze_time("2024-05-08 10:00:00+00:00"):
            self.assertFalse(ctrl_with_cal.is_on())

    def test_all_time(self):
        ctrl = WeeklySchedule().always()
        self.assertTrue(np.all(ctrl.schedule))
        self.assertDictEqual({i: ((0, 0), (24, 0)) for i in range(7)}, ctrl.formatted_schedule)

    def test_shift_start(self):
        ctrl = (
            WeeklySchedule.from_raw(self.complex_schedule()).for_timezone("UTC").shift_start(1, 0)
        )

        with freezegun.freeze_time("2022-02-11 00:15:00+00:00"):
            self.assertFalse(ctrl.is_on())

        with freezegun.freeze_time("2022-02-11 01:15:00+00:00"):
            self.assertTrue(ctrl.is_on())

        # make sure end time is not affected
        with freezegun.freeze_time("2022-02-11 06:59:00+00:00"):
            self.assertTrue(ctrl.is_on())

        with freezegun.freeze_time("2022-02-11 07:00:00+00:00"):
            self.assertFalse(ctrl.is_on())

        # check start time of next slot
        with freezegun.freeze_time("2022-02-11 20:15:00+00:00"):
            self.assertFalse(ctrl.is_on())

        with freezegun.freeze_time("2022-02-11 21:15:00+00:00"):
            self.assertTrue(ctrl.is_on())

    def test_shift_start_long(self):
        ctrl = (
            WeeklySchedule.from_raw(self.complex_schedule()).for_timezone("UTC").shift_start(5, 0)
        )
        self.assertDictEqual(
            {
                **{i: ((5, 0), (7, 0)) for i in range(5)},
                **{i: ((5, 0), (24, 0)) for i in range(5, 7)},
            },
            ctrl.formatted_schedule,
        )

        with freezegun.freeze_time("2022-02-11 04:59:00+00:00"):
            self.assertFalse(ctrl.is_on())

        with freezegun.freeze_time("2022-02-11 05:00:00+00:00"):
            self.assertTrue(ctrl.is_on())

        with freezegun.freeze_time("2022-02-11 23:59:00+00:00"):
            self.assertFalse(ctrl.is_on())

    def test_shift_start_neg(self):
        with self.assertRaises(AssertionError):
            ctrl = (
                WeeklySchedule.from_raw(self.complex_schedule())
                .for_timezone("UTC")
                .shift_start(-1, 0)
            )

    def test_clone(self):
        ctrl = WeeklySchedule.from_raw(self.complex_schedule()).for_timezone("UTC")
        ctrl2 = ctrl.clone().for_timezone("Europe/Luxembourg")
        self.assertNotEqual(ctrl, ctrl2)
        self.assertTrue(np.array_equal(ctrl.schedule, ctrl2.schedule))
        self.assertNotEqual(ctrl.timezone, ctrl2.timezone)

    def test_invert(self):
        # invert a typical weekly schedule
        ctrl = WeeklySchedule.from_raw(self.typical_weekly_schedule()).for_timezone("UTC")
        ctrl2 = WeeklySchedule.invert(ctrl)
        self.assertNotEqual(ctrl, ctrl2)
        self.assertFalse(np.array_equal(ctrl.schedule, ctrl2.schedule))
        self.assertEqual(ctrl.timezone, ctrl2.timezone)

        self.assertDictEqual(
            {
                **{i: (((0, 0), (7, 0)), ((20, 0), (24, 0))) for i in range(5)},
                **{i: ((0, 0), (24, 0)) for i in range(5, 7)},
            },
            ctrl2.formatted_schedule,
        )

        # invert a complex schedule
        ctrl = WeeklySchedule.from_raw(self.complex_schedule()).for_timezone("UTC")
        ctrl2 = WeeklySchedule.invert(ctrl)
        self.assertNotEqual(ctrl, ctrl2)
        self.assertFalse(np.array_equal(ctrl.schedule, ctrl2.schedule))
        self.assertEqual(ctrl.timezone, ctrl2.timezone)

        self.assertDictEqual(
            {**{i: ((7, 0), (20, 0)) for i in range(5)}},
            ctrl2.formatted_schedule,
        )

    def test_is_defined_for_day(self):
        schedule = (
            WeeklySchedule().for_timezone("UTC").from_to(Day.Monday, Day.Friday, ((6, 0), (18, 0)))
        )

        for i in range(7):
            self.assertEqual(i in range(0, 5), schedule.is_defined_for_day(i))

    @staticmethod
    def typical_weekly_schedule():
        return {
            0: ((7, 0), (20, 0)),
            1: ((7, 0), (20, 0)),
            2: ((7, 0), (20, 0)),
            3: ((7, 0), (20, 0)),
            4: ((7, 0), (20, 0)),
        }

    @staticmethod
    def complex_schedule():
        return {
            0: (((0, 0), (7, 0)), ((20, 0), (24, 0))),
            1: (((0, 0), (7, 0)), ((20, 0), (24, 0))),
            2: (((0, 0), (7, 0)), ((20, 0), (24, 0))),
            3: (((0, 0), (7, 0)), ((20, 0), (24, 0))),
            4: (((0, 0), (7, 0)), ((20, 0), (24, 0))),
            5: ((0, 0), (24, 0)),
            6: ((0, 0), (24, 0)),
        }

    @staticmethod
    def _utc_offset(tz):
        now = datetime.datetime.now(tz)
        return now.utcoffset().total_seconds() / 60 / 60
