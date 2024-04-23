[![tests](https://github.com/airboxlab/weeksched/actions/workflows/tests.yml/badge.svg)](https://github.com/airboxlab/weeksched/actions/workflows/tests.yml)
[![coverage](https://github.com/airboxlab/weeksched/blob/main/coverage.svg)](<>)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# weeksched

A tool to manage weekly schedules

# Installation

Requires Python 3.10 or later.

```bash
poetry install
```

# Usage

```python
from datetime import datetime
from weeksched.schedule import WeeklySchedule, Day

# a schedule that runs from 7:00 to 20:00 every week day
my_ctrl_schedule = WeeklySchedule.from_raw({
    0: ((7, 0), (20, 0)),
    1: ((7, 0), (20, 0)),
    2: ((7, 0), (20, 0)),
    3: ((7, 0), (20, 0)),
    4: ((7, 0), (20, 0)),
}).for_timezone("Europe/Paris")

# check if the schedule is active at current time
my_ctrl_schedule.is_on()

# check if the schedule is active at a specific time
my_ctrl_schedule.is_on_at(dt=datetime(year=2024, month=1, day=1, hour=12, minute=0))

# a schedule created using the `Day` class
my_ctrl_schedule_2 = WeeklySchedule.from_to(
    day_start=Day.Monday,
    day_end=Day.Friday,
    day_sched=((7, 0), (20, 0)),
).for_timezone("Europe/Paris")

assert my_ctrl_schedule == my_ctrl_schedule_2

# a schedule running 24/7
always_on_schedule = WeeklySchedule.always()

# a schedule that is running on the inverse of `my_ctrl_schedule`
inverse_ctrl_schedule = WeeklySchedule.invert(my_ctrl_schedule)

# shift the start of each time slot by 1 hour
shifted_schedule = my_ctrl_schedule.shift_start(hours=1, minutes=0)
```
