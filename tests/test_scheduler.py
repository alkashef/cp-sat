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


def test_fixed_days_task_produces_one_entry_per_selected_day():
    task = {
        "name": "Standup",
        "duration_minutes": 30,
        "schedule_mode": "fixed_days",
        "days": ["Mon", "Wed", "Fri"],
        "hour": None,
    }

    schedule = scheduler.solve([task])["schedule"]

    assert sorted(entry["day"] for entry in schedule) == ["Fri", "Mon", "Wed"]
    assert all(entry["name"] == "Standup" for entry in schedule)
    assert all(entry["end_minutes"] - entry["start_minutes"] == 30 for entry in schedule)
    assert all(entry["fixed"] is False for entry in schedule)


def test_fixed_hour_task_always_starts_at_the_given_hour_on_any_day():
    task = {
        "name": "Check email",
        "duration_minutes": 15,
        "schedule_mode": "fixed_hour",
        "days": [],
        "hour": 14,
    }

    schedule = scheduler.solve([task])["schedule"]

    assert len(schedule) == 1
    assert schedule[0]["start_minutes"] == 14 * 60
    assert schedule[0]["fixed"] is False


def test_fixed_task_lands_at_the_exact_day_and_hour_every_solve():
    task = {
        "name": "Standup",
        "duration_minutes": 30,
        "schedule_mode": "fixed",
        "days": ["Tue", "Thu"],
        "hour": 9,
    }

    schedule = scheduler.solve([task])["schedule"]

    assert sorted((entry["day"], entry["start_minutes"]) for entry in schedule) == [
        ("Thu", 9 * 60),
        ("Tue", 9 * 60),
    ]
    assert all(entry["fixed"] is True for entry in schedule)


def test_fixed_ranges_returns_slot_ranges_only_for_fixed_tasks():
    fixed_task = {
        "name": "Standup",
        "duration_minutes": 30,
        "schedule_mode": "fixed",
        "days": ["Tue"],
        "hour": 9,
    }
    day_index = scheduler.DAYS.index("Tue")
    expected_start = day_index * scheduler.SLOTS_PER_DAY + 9 * scheduler.SLOTS_PER_HOUR

    assert scheduler.fixed_ranges(fixed_task) == [(expected_start, expected_start + 2)]
    for mode in ("flexible", "fixed_hour", "fixed_days"):
        assert scheduler.fixed_ranges({**fixed_task, "schedule_mode": mode}) == []


def test_describe_model_domain_is_union_joined_for_a_fixed_hour_task():
    task = {
        "name": "Check email",
        "duration_minutes": 15,
        "schedule_mode": "fixed_hour",
        "days": [],
        "hour": 14,
    }

    variables = scheduler.describe_model([task])["variables"]
    domain = next(v["domain"] for v in variables if v["kind"] == "IntVar (start slot)")

    # 7 candidate days (any day, but this exact hour), joined by 6 "∪"s.
    assert domain.count("∪") == 6
