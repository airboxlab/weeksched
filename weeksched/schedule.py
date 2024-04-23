from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pytz
from calendra.core import Calendar


class Day(Enum):
    """A simple enum to represent the days of the week."""

    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6


class WeeklySchedule:
    """Weekly schedule class.

    This class is used to define a weekly schedule for control loops. It's implemented as a
    7x24x60 matrix where each cell represents a 1-minute slot. The schedule is defined by
    setting the slots to True or False. This implementation trades memory and instantiation
    time for a fast evaluation and easy manipulation of the schedule.
    """

    def __init__(self):
        self._schedule: np.array = np.zeros((7, 24, 60), dtype=bool)
        self._timezone: str | None = None
        self._pytz: Any | None = None
        self._is_working_day_fun: Calendar | callable | None = None

    def __str__(self):
        return (
            f"WeeklySchedule("
            f"schedule={self.formatted_schedule}, "
            f"timezone={self._timezone}, "
            f"is_working_day_fun={self._is_working_day_fun}"
            f")"
        )

    def __eq__(self, other):
        if not isinstance(other, WeeklySchedule):
            return False
        return (
            np.array_equal(self.schedule, other.schedule)
            and self.timezone == other.timezone
            and self.is_working_day_fun == other.is_working_day_fun
        )

    def format_schedule(self) -> dict:
        """Format the schedule as a dict.

        :return: formatted schedule as a dict. Format is {day: ((slot_1_hour, slot_1_min),
            (slot_n_hour, slot_n_min))}
        """

        # special cases for all True or all False schedule
        if np.all(self._schedule):
            return {day: ((0, 0), (24, 0)) for day in range(7)}
        elif not np.any(self._schedule):
            return {}

        formated_schedule = {}
        # loop over the days
        for day in range(7):
            day_schedule = self._schedule[day]

            # special cases for all True or all False schedule
            if np.all(day_schedule):
                formated_schedule[day] = ((0, 0), (24, 0))
            elif not np.any(day_schedule):
                continue
            # normal case
            else:
                # transform the slots back into a raw schedule
                flat_slots = day_schedule.reshape(24 * 60)
                # roll the slots by 1 minute
                rolled_slots = np.roll(flat_slots, 1, axis=0)
                # keep the first slot unchanged (roll wraps around and may change the first slot)
                rolled_slots[0] = flat_slots[0]
                # find where slots start and end
                slot_indexes = np.argwhere(rolled_slots != flat_slots).reshape(-1, 1)
                # add a dummy slot at the start and the end if day schedule starts or ends at 0 or 24, respectively
                if day_schedule[0, 0]:
                    slot_indexes = np.vstack((0, slot_indexes))
                if day_schedule[-1, -1]:
                    slot_indexes = np.vstack((slot_indexes, 24 * 60))

                # retain a 1D array
                # ie content will be [0, 420, 1200, 1440] for the
                # 2-slot schedule (((0, 0), (7, 0)), ((20, 0), (24, 0)))
                slot_indexes = slot_indexes.squeeze(-1)

                # loop over the slot indexes and group them into start/end pairs
                day_slots = []
                start = end = None
                for idx, slot_index in np.ndenumerate(slot_indexes):
                    # convert slot index to hour and minute
                    hour, minute = divmod(slot_index, 60)
                    # convert numpy int to python int
                    hour = hour.item()  # type: ignore
                    minute = minute.item()  # type: ignore

                    # if idx is even, it's a start, if it's odd, it's an end
                    if idx[0] % 2 == 0:
                        start = (hour, minute)
                    else:
                        end = (hour, minute)

                    if start and end:
                        day_slots.append((start, end))
                        start = end = None

                # squeeze 1 dimension if day has only 1 slot but is a 3D array
                # ie (((7, 0), (20, 0)),) -> ((7, 0), (20, 0))
                if np.array(day_slots).ndim == 3 and len(day_slots) == 1:
                    day_slots = day_slots[0]

                formated_schedule[day] = tuple(day_slots)

        return formated_schedule

    def for_timezone(self, tz: str) -> WeeklySchedule:
        """Set the timezone for the schedule.

        :param tz: timezone string. Expected format: "Europe/Paris"
        :return: self
        """
        self._timezone = tz
        self._pytz = pytz.timezone(tz)
        return self

    def with_working_days_calendar(self, calendar: Calendar | callable) -> WeeklySchedule:
        """Register a calendar or a function that can evaluate if a day is a working day. When a
        schedule has a working day calendar, it is used by action providers to determine if the
        control loop should step.

        :param calendar: calendar or callable that takes a datetime and returns a boolean.
            If a callable is passed, it must take a datetime as argument and return a
            boolean indicating if the day is a working day.
        :return: self
        """
        if callable(calendar):
            self._is_working_day_fun = calendar
        else:
            self._is_working_day_fun = calendar.is_working_day
        return self

    @staticmethod
    def from_raw(raw_sched: dict | np.ndarray, time_zone: str = "UTC") -> WeeklySchedule:
        """Build a weekly schedule from a raw schedule.

        The given schedule can be a dictionary or a 7x24x60 matrix. If a dictionary
        are given, it should have the following format:
        {
            0: ((0, 0), (24, 0)),  # Monday
            1: ((0, 0), (24, 0)),  # Tuesday
            ...
            6: ((0, 0), (24, 0)),  # Sunday
        }

        :param raw_sched: raw schedule as a dictionary or a 7x24x60 matrix.
        :param time_zone: timezone string. Expected format: "Europe/Paris", default is "UTC"
        """
        assert isinstance(raw_sched, (dict, np.ndarray)), "raw_sched should be a dict or np.ndarray"
        assert isinstance(time_zone, str), "time_zone should be a string"

        sched = WeeklySchedule()

        if isinstance(raw_sched, dict):
            assert raw_sched, "raw schedule can't be empty"
            sched._schedule = WeeklySchedule.to_matrix(raw_sched)
        elif isinstance(raw_sched, np.ndarray):
            sched._schedule = raw_sched

        sched.for_timezone(time_zone)
        sched._validate()
        return sched

    @staticmethod
    def never() -> WeeklySchedule:
        """Builds a schedule which never allows control."""
        return WeeklySchedule().for_timezone("UTC")

    @staticmethod
    def always() -> WeeklySchedule:
        """Builds a schedule for 24/7 control."""
        return WeeklySchedule.from_raw(np.ones((7, 24, 60), dtype=bool)).for_timezone("UTC")

    @staticmethod
    def invert(other: WeeklySchedule) -> WeeklySchedule:
        """Invert a weekly schedule.

        Creates a new weekly schedule with the same time zone as the given one, but with the
        schedule inverted. Other properties are not copied.
        :param other: weekly schedule to invert
        """
        return WeeklySchedule.from_raw(~other.schedule).for_timezone(other.timezone)

    @staticmethod
    def from_to(day_start: Day, day_end: Day, day_sched: tuple) -> WeeklySchedule:
        """Apply same day schedule to a range of week days.

        :param day_start: start day of schedule
        :param day_end: end day of schedule
        :param day_sched: day schedule instruction to apply
        :return:
        """
        sched = WeeklySchedule()
        for day in range(day_start.value, day_end.value + 1):
            sched._set_day_schedule(day, day_sched)
        return sched

    def monday(self, day_sched: tuple) -> WeeklySchedule:
        """Set Monday schedule."""
        self._set_day_schedule(0, day_sched)
        return self

    def tuesday(self, day_sched: tuple) -> WeeklySchedule:
        """Set Tuesday schedule."""
        self._set_day_schedule(1, day_sched)
        return self

    def wednesday(self, day_sched: tuple) -> WeeklySchedule:
        """Set Wednesday schedule."""
        self._set_day_schedule(2, day_sched)
        return self

    def thursday(self, day_sched: tuple) -> WeeklySchedule:
        self._set_day_schedule(3, day_sched)
        return self

    def friday(self, day_sched: tuple) -> WeeklySchedule:
        """Set Friday schedule."""
        self._set_day_schedule(4, day_sched)
        return self

    def saturday(self, day_sched: tuple) -> WeeklySchedule:
        """Set Saturday schedule."""
        self._set_day_schedule(5, day_sched)
        return self

    def sunday(self, day_sched: tuple) -> WeeklySchedule:
        """Set Sunday schedule."""
        self._set_day_schedule(6, day_sched)
        return self

    def shift_start(self, hours: int, minutes: int) -> WeeklySchedule:
        """Shift start hour of existing WeeklySchedule by given number of hours.

        Total shift must be positive. Shifts the start only, the end time of each slot
        remains unchanged.

        :param hours: number of hours to shift start
        :param minutes: number of minutes to shift start
        """
        total_minutes_shift = hours * 60 + minutes
        assert total_minutes_shift >= 0, "start should be postponed by a positive number of minutes"

        # flatten schedule so we can roll it
        day_schedules = self._schedule.reshape(7, 24 * 60)

        for day in range(7):
            # apply shift to slots
            shifted_slots = np.concatenate(
                (np.zeros(total_minutes_shift, dtype=bool), day_schedules[day])
            )
            # remove items that were shifted at end
            shifted_slots = shifted_slots[:-total_minutes_shift]

            # mask out items that were shifted at end of each slot.
            # ie
            # initial: 0 0 0 1 1 1 0 0 0
            # shifted: 0 0 0 0 1 1 1 0 0
            # result:  0 0 0 0 1 1 0 0 0
            day_schedules[day] = day_schedules[day] & shifted_slots

        self._schedule = day_schedules.reshape(7, 24, 60)
        self._validate()

        return self

    def clone(self) -> WeeklySchedule:
        """Create a deep copy of the weekly schedule."""
        new_sched = WeeklySchedule()
        new_sched._schedule = self._schedule.copy()
        if self._timezone:
            new_sched._timezone = str(self._timezone)
            new_sched._pytz = pytz.timezone(self._timezone) if self._pytz else None
        if self._is_working_day_fun:
            new_sched._is_working_day_fun = self._is_working_day_fun
        return new_sched

    @property
    def schedule(self) -> np.array:
        """Returns the raw schedule as a (7, 24, 60) matrix of 1-minute slots."""
        return self._schedule

    @property
    def formatted_schedule(self) -> dict:
        """Returns the formated schedule."""
        return self.format_schedule()

    @property
    def timezone(self) -> str | None:
        """Returns the timezone of the weekly schedule."""
        return self._timezone

    @property
    def is_working_day_fun(self) -> Calendar | callable | None:
        """Returns the function that evaluates if a day is a working day."""
        return self._is_working_day_fun

    def is_on(self) -> bool:
        """Checks if current time, expressed in given time zone, falls in defined weekly schedule.
        If a working day calendar is set, it is also used to determine if the day is a working day.

        :return: True if current time falls in defined weekly schedule.
        """
        return self.is_on_at(datetime.now(self._pytz))

    def is_on_at(self, dt: datetime) -> bool:
        """Checks if given time, expressed in given time zone, falls in defined weekly schedule. If
        a working day calendar is set, it is also used to determine if the day is a working day.

        :param dt: datetime to evaluate
        :return: True if given time falls in defined weekly schedule.
        """
        assert dt is not None, "dt should not be None"
        assert isinstance(dt, datetime), "dt should be a datetime"

        # evaluate if day is a working day
        if self._is_working_day_fun is not None and not self._is_working_day_fun(dt):
            return False

        # evaluate weekly schedule
        return self._is_on_weekly_schedule(dt.weekday(), dt.hour, dt.minute)

    def is_defined_for_day(self, day: Day | int) -> bool:
        """Checks if a day schedule is defined for a given day.

        :param day: day to check
        :return: True if a day schedule is defined for the given day.
        """
        return np.any(self._schedule[day.value if isinstance(day, Day) else day])

    def _is_on_weekly_schedule(self, weekday: int, hour: int, minute: int) -> bool:
        """Checks if given time falls in defined weekly schedule for a given weekday."""
        return self._schedule[weekday, hour, minute]

    def _set_day_schedule(self, day: int, sched: tuple):
        """Set a day schedule."""
        self._schedule[day] = self.to_vector(sched).reshape(24, 60)
        self._validate()

    @staticmethod
    def to_matrix(ctrl_sched: dict) -> np.array:
        """Transform a weekly schedule into a 7x24x60 matrix."""
        slots = np.zeros((7, 24, 60), dtype=bool)
        for day, day_sched in ctrl_sched.items():
            assert day in range(7), "day should be in range 0-6"
            slots[day] = WeeklySchedule.to_vector(day_sched).reshape(24, 60)
        return slots

    @staticmethod
    def to_vector(day_sched: tuple) -> np.array:
        """Transform a day schedule into a 1-minute slot vector of shape (24, 60)."""
        slots = np.zeros(24 * 60, dtype=bool)

        def define_slot(s, e):
            """Define a slot in the slots vector."""
            for t, lbl in zip([s, e], ["start", "end"]):
                assert isinstance(t, tuple), f"{lbl} time should be a tuple"
                assert (0, 0) <= t <= (24, 0), f"{lbl} time should be 00:00 <= x <= 24:00"
            assert s < e, "start time should be before end time"

            start_idx = s[0] * 60 + s[1]
            end_idx = e[0] * 60 + e[1]
            slots[start_idx:end_idx] = 1

        # depending on the day schedule format, we may have a 2D or 3D tuple
        ndim = np.array(day_sched).ndim
        if ndim == 2:
            start = day_sched[0]
            end = day_sched[1]
            define_slot(start, end)
        elif ndim == 3:
            for sched in day_sched:
                if isinstance(sched[0], tuple):
                    start = sched[0]
                    end = sched[1]
                else:
                    raise ValueError("Invalid day schedule format. Expected 2D or 3D tuple.")

                define_slot(start, end)
        else:
            raise ValueError(f"Invalid day schedule format. Expected 2D or 3D tuple. Got {ndim}D.")

        return slots

    def _validate(self):
        """Validate the weekly schedule.

        It essentially checks that the underlying structure is correct.
        """
        assert len(self._schedule) > 0, "weekly schedule can't be empty"
        assert self._schedule.shape == (7, 24, 60), "weekly schedule should be a 7x24x60 matrix"
        assert np.all(self._schedule >= 0), "weekly schedule should have positive values"
        assert np.all(self._schedule <= 1), "weekly schedule should have values <= 1"
