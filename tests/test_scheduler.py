"""Tests for scheduler.py's CP-SAT model and its solve results."""
import pytest

import scheduler

TASKS = [
    {"name": "Write report", "duration_minutes": 90},
    {"name": "Team sync", "duration_minutes": 30},
    {"name": "Review PRs", "duration_minutes": 45},
]


def _sorted_ranges(schedule):
    """Return each entry as (start, end) minutes from the start of the week, in time order."""
    ranges = []
    for entry in schedule:
        day_start = scheduler.DAYS.index(entry["day"]) * scheduler.MINUTES_PER_DAY
        ranges.append((day_start + entry["start_minutes"], day_start + entry["end_minutes"]))
    return sorted(ranges)


def _assert_no_overlap(schedule):
    ranges = _sorted_ranges(schedule)
    for (_, earlier_end), (later_start, _) in zip(ranges, ranges[1:]):
        assert later_start >= earlier_end


def test_small_task_set_is_non_overlapping_and_idle_free():
    schedule = scheduler.solve(TASKS)["schedule"]

    _assert_no_overlap(schedule)
    ranges = _sorted_ranges(schedule)
    assert ranges[0][0] == 0
    for (_, earlier_end), (later_start, _) in zip(ranges, ranges[1:]):
        assert later_start == earlier_end


def test_total_scheduled_duration_matches_task_durations():
    schedule = scheduler.solve(TASKS)["schedule"]

    scheduled_minutes = sum(end - start for start, end in _sorted_ranges(schedule))
    assert scheduled_minutes == sum(task["duration_minutes"] for task in TASKS)


@pytest.mark.parametrize(
    "tasks",
    [
        [{"name": f"Task {i}", "duration_minutes": 1440} for i in range(8)],
        [{"name": "Huge", "duration_minutes": 10095}],
    ],
)
def test_task_set_longer_than_a_week_returns_an_error(tasks):
    assert scheduler.solve(tasks) == {"error": scheduler.INFEASIBLE_MESSAGE}


@pytest.mark.parametrize(
    "parameters",
    [
        {"num_search_workers": 1},
        {"max_time_in_seconds": 1.0},
        {"log_search_progress": True},
        {"randomize_search": True},
        {"relative_gap_limit": 0.5},
    ],
)
def test_solver_parameters_do_not_change_correctness(parameters):
    schedule = scheduler.solve(TASKS, parameters)["schedule"]

    assert len(schedule) == len(TASKS)
    _assert_no_overlap(schedule)
