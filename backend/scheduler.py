"""Builds and solves the CP-SAT model that lays tasks out on a weekly calendar.

The problem given to the solver: place every task somewhere in a generic
Sunday-through-Saturday week, never let two tasks overlap, and pack them so the
idle gaps between them are as small as possible.

Time is discretized into 15-minute slots, which is why task durations must be a
multiple of 15: one week is then exactly 672 slots, and every duration is a
whole number of slots.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from ortools.sat.python import cp_model

# Solver defaults come from config/.env, which is not necessarily loaded yet
# when this module is used outside the Flask app.
load_dotenv(Path(__file__).parent.parent / "config" / ".env")

SLOT_MINUTES = 15
MINUTES_PER_DAY = 24 * 60
DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
SLOTS_PER_DAY = MINUTES_PER_DAY // SLOT_MINUTES
HORIZON_SLOTS = len(DAYS) * SLOTS_PER_DAY

INFEASIBLE_MESSAGE = "No feasible schedule was found: the tasks do not all fit within one week."


def solve(tasks, parameters=None):
    """Schedule `tasks` across the week and return the result.

    `tasks` is a list of {"name", "duration_minutes"} dicts and `parameters` is
    an optional dict of CP-SAT solver parameters overriding the config defaults.

    Returns {"schedule": [...]} when the solver found an arrangement, or
    {"error": "..."} when it did not — an unschedulable task list is a normal
    outcome here, not an exception.
    """
    if not tasks:
        return {"schedule": []}

    model, starts = _build_model(tasks)

    solver = cp_model.CpSolver()
    _apply_parameters(solver, parameters)
    status = solver.Solve(model)

    # Every solve ends with a status describing how the search finished.
    # OPTIMAL means CP-SAT found an arrangement and proved none is better;
    # FEASIBLE means it found one but stopped before proving that (for example
    # because it hit the time limit). Any other status — INFEASIBLE when the
    # tasks cannot all fit in the week, MODEL_INVALID when a single task is
    # longer than the week — means there is no schedule to show.
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"error": INFEASIBLE_MESSAGE}

    # solver.Value() reads the value the solver chose for a decision variable.
    schedule = [
        _to_calendar_entry(task, solver.Value(start)) for task, start in zip(tasks, starts)
    ]
    return {"schedule": schedule}


def _build_model(tasks):
    """Build the CP-SAT model for `tasks`, returning it with each task's start variable."""
    model = cp_model.CpModel()
    starts = []
    intervals = []
    ends = []

    for task in tasks:
        duration = task["duration_minutes"] // SLOT_MINUTES
        # A decision variable is an unknown the solver has to pick a value for.
        # Here that unknown is the slot the task begins at; its domain stops at
        # HORIZON_SLOTS - duration so the task cannot run past the end of the week.
        start = model.NewIntVar(0, HORIZON_SLOTS - duration, task["name"])
        # An interval variable bundles a start, a size and an end into one object
        # that CP-SAT's scheduling constraints understand. It adds no constraint
        # by itself; it is the handle AddNoOverlap below is expressed in terms of.
        intervals.append(model.NewIntervalVar(start, duration, start + duration, task["name"]))
        starts.append(start)
        ends.append(start + duration)

    # AddNoOverlap is the scheduling constraint that forces the intervals onto a
    # single timeline: whatever start times the solver picks, no two tasks may
    # occupy the same slot. Expressing "no two tasks overlap" this way, instead
    # of as a comparison between every pair of tasks, lets CP-SAT use the
    # specialized scheduling reasoning it has for intervals.
    model.AddNoOverlap(intervals)

    # The objective is the quantity the solver optimizes, as opposed to the
    # constraints above, which only say what is allowed. Minimize() asks for the
    # smallest value it can reach. The quantity minimized here is the makespan —
    # the end of the last-finishing task. Since the total work is fixed, the idle
    # time between tasks is makespan minus that total, so squeezing the makespan
    # squeezes the idle gaps.
    makespan = model.NewIntVar(0, HORIZON_SLOTS, "makespan")
    # AddMaxEquality pins makespan to the largest of the task end times; without
    # it, makespan would just be an unconstrained variable free to sit at 0.
    model.AddMaxEquality(makespan, ends)
    model.Minimize(makespan)

    return model, starts


def default_parameters():
    """Return the solver parameter defaults from `config/.env`.

    Shared by `_apply_parameters` below and by `app.py`'s index route, which
    passes these to the Solver tab so its "Reset to defaults" action doesn't
    need its own copy of the config values.
    """
    return {
        "num_search_workers": int(os.getenv("SOLVER_WORKERS", 8)),
        "max_time_in_seconds": float(os.getenv("SOLVER_MAX_TIME_SECONDS", 10)),
        "log_search_progress": os.getenv("SOLVER_LOG_SEARCH_PROGRESS", "False").lower() == "true",
        "randomize_search": os.getenv("SOLVER_RANDOMIZE_SEARCH", "False").lower() == "true",
        "relative_gap_limit": float(os.getenv("SOLVER_GAP_LIMIT", 0.01)),
    }


def _apply_parameters(solver, overrides):
    """Apply solver parameters, taking config/.env defaults for anything not overridden."""
    parameters = default_parameters()
    parameters.update(overrides or {})

    # Solver parameters tune *how* CP-SAT searches, never which schedules count
    # as valid: the same model with different parameters still yields a
    # non-overlapping schedule, it just may take more or less time to get there
    # and may stop at a good answer instead of a provably optimal one.
    solver.parameters.num_search_workers = int(parameters["num_search_workers"])
    solver.parameters.max_time_in_seconds = float(parameters["max_time_in_seconds"])
    solver.parameters.log_search_progress = bool(parameters["log_search_progress"])
    solver.parameters.randomize_search = bool(parameters["randomize_search"])
    solver.parameters.relative_gap_limit = float(parameters["relative_gap_limit"])


def _to_calendar_entry(task, start_slot):
    """Convert a solved start slot back into a day of the week and minutes of day.

    `end_minutes` is measured from the same midnight as `start_minutes`, so a
    task that runs past midnight ends beyond 1440 rather than moving to the
    next day.
    """
    day_index, slot_of_day = divmod(start_slot, SLOTS_PER_DAY)
    start_minutes = slot_of_day * SLOT_MINUTES
    return {
        "name": task["name"],
        "day": DAYS[day_index],
        "start_minutes": start_minutes,
        "end_minutes": start_minutes + task["duration_minutes"],
    }
