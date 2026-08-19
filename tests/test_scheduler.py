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


def test_describe_model_lists_a_start_and_interval_per_task_plus_the_makespan():
    variables = scheduler.describe_model(TASKS)["variables"]

    names = [variable["name"] for variable in variables]
    assert len(variables) == 2 * len(TASKS) + 1
    assert names.count("Write report") == 2
    assert names[-1] == "makespan"


def test_describe_model_start_domains_keep_each_task_inside_the_week():
    variables = scheduler.describe_model(TASKS)["variables"]

    domains = {
        variable["name"]: variable["domain"]
        for variable in variables
        if variable["kind"].startswith("IntVar")
    }
    assert domains["Write report"] == f"[0, {scheduler.HORIZON_SLOTS - 6}]"
    assert domains["Team sync"] == f"[0, {scheduler.HORIZON_SLOTS - 2}]"
    assert domains["makespan"] == f"[0, {scheduler.HORIZON_SLOTS}]"


def test_describe_model_constraints_reference_every_task():
    constraints = {c["type"]: c for c in scheduler.describe_model(TASKS)["constraints"]}

    task_names = [task["name"] for task in TASKS]
    assert constraints["AddNoOverlap"]["variables"] == task_names
    assert constraints["AddMaxEquality"]["variables"] == ["makespan"] + task_names


def test_describe_model_objective_minimizes_the_makespan():
    objective = scheduler.describe_model(TASKS)["objective"]

    assert objective["type"] == "Minimize"
    assert objective["expression"] == "makespan"


def test_describe_model_raw_proto_holds_the_cp_sat_constraints():
    raw_proto = scheduler.describe_model(TASKS)["raw_proto"]

    assert "no_overlap" in raw_proto
    assert "lin_max" in raw_proto
    assert all(task["name"] in raw_proto for task in TASKS)


def test_describe_model_with_no_tasks_returns_an_empty_description():
    assert scheduler.describe_model([]) == {
        "variables": [],
        "constraints": [],
        "objective": None,
        "raw_proto": "",
    }
