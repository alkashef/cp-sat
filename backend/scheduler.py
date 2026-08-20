"""Builds and solves the CP-SAT model that lays tasks out on a weekly calendar.

The problem given to the solver: place every task somewhere in a generic
Sunday-through-Saturday week, never let two tasks overlap, and pack them so the
idle gaps between them are as small as possible. A task's `schedule_mode` can
narrow where it's allowed to land — see `_task_occurrences` below — from fully
open (the default) down to an exact day and hour that isn't optimized at all.

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
SLOTS_PER_HOUR = 60 // SLOT_MINUTES
HORIZON_SLOTS = len(DAYS) * SLOTS_PER_DAY

INFEASIBLE_MESSAGE = "No feasible schedule was found: the tasks do not all fit within one week."


def solve(tasks, parameters=None):
    """Schedule `tasks` across the week and return the result.

    `tasks` is a list of task dicts (see `_task_occurrences` for the
    `schedule_mode`/`days`/`hour` fields that shape their placement) and
    `parameters` is an optional dict of CP-SAT solver parameters overriding
    the config defaults.

    Returns {"schedule": [...]} when the solver found an arrangement, or
    {"error": "..."} when it did not — an unschedulable task list is a normal
    outcome here, not an exception.
    """
    if not tasks:
        return {"schedule": []}

    model, occurrences, _ = _build_model(tasks)

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
    # A recurring task (schedule_mode "fixed_days"/"fixed" with more than one
    # selected day) has more than one occurrence here, so it naturally
    # produces more than one calendar entry, all sharing its name.
    schedule = [
        _to_calendar_entry(occurrence["task"], solver.Value(occurrence["start"]))
        for occurrence in occurrences
    ]
    return {"schedule": schedule}


def describe_model(tasks):
    """Describe the CP-SAT model built for `tasks`, without solving it.

    Returns a JSON-serializable dict holding the model's decision variables
    and their domains, its constraints, its objective, and CP-SAT's own text
    dump of the model. The Solver tab renders this so the model handed to the
    solver is visible from the task list alone, before any solve is run.

    An empty task list has no model to describe, so it returns an empty
    description rather than building one.
    """
    if not tasks:
        return {"variables": [], "constraints": [], "objective": None, "raw_proto": ""}

    model, occurrences, makespan = _build_model(tasks)

    variables = []
    for occurrence in occurrences:
        # A decision variable's domain is the set of values the solver is
        # allowed to pick from. For a Flexible task that's every slot up to
        # HORIZON_SLOTS minus the task's own length; other scheduling modes
        # narrow it further, sometimes to a handful of disjoint slots or a
        # single fixed one (see _task_occurrences), which is why the domain
        # isn't always printed as one contiguous range.
        variables.append(
            {
                "name": occurrence["label"],
                "kind": "IntVar (start slot)",
                "domain": _format_domain(occurrence["domain"]),
            }
        )
        # An interval variable has no numeric domain of its own: it is the
        # (start, size, end) triple built on top of the start variable above,
        # so the relationship between those three is shown instead of a range.
        variables.append(
            {
                "name": occurrence["label"],
                "kind": "IntervalVar",
                "domain": f"start + {occurrence['duration']} = end",
            }
        )
    variables.append(
        {
            "name": makespan.Name(),
            "kind": "IntVar (objective)",
            "domain": f"[0, {HORIZON_SLOTS}]",
        }
    )

    occurrence_labels = [occurrence["label"] for occurrence in occurrences]
    constraints = [
        {
            "type": "AddNoOverlap",
            "description": (
                "No two task intervals may cover the same slot, so every task "
                "lands somewhere on a single shared timeline."
            ),
            "variables": occurrence_labels,
        },
        {
            "type": "AddMaxEquality",
            "description": (
                "makespan is held equal to the largest task end time — the "
                "moment the last task finishes."
            ),
            "variables": [makespan.Name()] + occurrence_labels,
        },
    ]

    objective = {
        "type": "Minimize",
        "expression": makespan.Name(),
        "description": (
            "Finish the last task as early as possible. The total work is "
            "fixed, so pulling the finish time in squeezes the idle gaps "
            "between tasks."
        ),
    }

    # model.Proto() is the protocol buffer CP-SAT is actually handed: every
    # variable with its domain as a pair of bounds, and every constraint in
    # the solver's own vocabulary (`interval`, `no_overlap`, `lin_max`, the
    # objective) instead of the Python calls that created them. Printing it is
    # the standard way to check what a model really contains, and comparing it
    # against the friendly summary above shows how a handful of model.Add...()
    # calls turn into the solver's flat list of variables and constraints.
    return {
        "variables": variables,
        "constraints": constraints,
        "objective": objective,
        "raw_proto": str(model.Proto()),
    }


def fixed_ranges(task):
    """Return the (start_slot, end_slot) ranges a "fixed"-mode task occupies.

    A "fixed" task's occurrences are pinned to an exact day and hour, so their
    placement is known without running the solver. `app.py` uses this to
    reject an add/edit that would make two fixed tasks overlap immediately,
    rather than letting it surface later as a solve-time infeasibility.
    Returns an empty list for any task not in "fixed" mode.
    """
    if task.get("schedule_mode") != "fixed":
        return []
    duration = _duration_slots(task)
    return [
        (_fixed_slot(day, task["hour"]), _fixed_slot(day, task["hour"]) + duration)
        for day in task.get("days") or []
    ]


def _build_model(tasks):
    """Build the CP-SAT model for `tasks`.

    Each task expands into one or more "occurrences" via `_task_occurrences`
    (more than one for a recurring "fixed_days"/"fixed" task with multiple
    selected days). Returns the model along with a flat list of every
    occurrence — its task, label, domain, duration, start and interval
    variable — plus the makespan variable, so `solve()` and `describe_model()`
    can both work from the same construction rather than each building their
    own model.
    """
    model = cp_model.CpModel()
    occurrences = []
    ends = []

    for task in tasks:
        duration = _duration_slots(task)
        for label, domain in _task_occurrences(task, duration):
            # A decision variable is an unknown the solver has to pick a value
            # for. Building it from a Domain rather than a plain (lo, hi) pair
            # lets that unknown's allowed values be a set of disjoint ranges —
            # e.g. "start at this exact hour, but any day" — not just one
            # contiguous range, which is how a task's scheduling mode narrows
            # its placement without a separate "which day" variable.
            start = model.NewIntVarFromDomain(domain, label)
            # An interval variable bundles a start, a size and an end into one
            # object that CP-SAT's scheduling constraints understand. It adds
            # no constraint by itself; it is the handle AddNoOverlap below is
            # expressed in terms of. Every occurrence gets one, even a "fixed"
            # one whose start has only a single legal value, because it still
            # occupies real space that other tasks must be scheduled around.
            interval = model.NewIntervalVar(start, duration, start + duration, label)
            occurrences.append(
                {
                    "task": task,
                    "label": label,
                    "domain": domain,
                    "duration": duration,
                    "start": start,
                    "interval": interval,
                }
            )
            ends.append(start + duration)

    # AddNoOverlap is the scheduling constraint that forces the intervals onto a
    # single timeline: whatever start times the solver picks, no two
    # occurrences may occupy the same slot. Expressing "no two tasks overlap"
    # this way, instead of as a comparison between every pair of occurrences,
    # lets CP-SAT use the specialized scheduling reasoning it has for
    # intervals.
    model.AddNoOverlap([occurrence["interval"] for occurrence in occurrences])

    # The objective is the quantity the solver optimizes, as opposed to the
    # constraints above, which only say what is allowed. Minimize() asks for the
    # smallest value it can reach. The quantity minimized here is the makespan —
    # the end of the last-finishing occurrence. Since the total work is fixed, the
    # idle time between occurrences is makespan minus that total, so squeezing
    # the makespan squeezes the idle gaps.
    makespan = model.NewIntVar(0, HORIZON_SLOTS, "makespan")
    # AddMaxEquality pins makespan to the largest of the occurrence end times;
    # without it, makespan would just be an unconstrained variable free to sit
    # at 0.
    model.AddMaxEquality(makespan, ends)
    model.Minimize(makespan)

    return model, occurrences, makespan


def _task_occurrences(task, duration):
    """Return `(label, domain)` pairs for each occurrence a task expands into.

    A task's `schedule_mode` (default "flexible") controls both how many
    occurrences it has and what slots each occurrence's start variable may
    take:

    - "flexible": one occurrence, free anywhere in the week — today's
      original, unconstrained behavior.
    - "fixed_hour": one occurrence that must start at `task["hour"]`, on
      whichever of the 7 days minimizes idle time; `task["days"]` plays no
      part in this, since the day is left entirely to the solver.
    - "fixed_days": one occurrence per day in `task["days"]`, each free to
      start anywhere within that specific day.
    - "fixed": one occurrence per day in `task["days"]`, each pinned to the
      exact slot at `task["hour"]` on that day — not subject to optimization.
    """
    mode = task.get("schedule_mode", "flexible")
    days = task.get("days") or []
    hour = task.get("hour")

    if mode == "fixed_hour":
        # Building a Domain from an explicit list of values, rather than a
        # (lo, hi) range, tells the solver "the start must be exactly one of
        # these" — here, the same hour on each of the 7 days — without
        # needing a separate variable for which day was chosen.
        candidates = [_fixed_slot(day, hour) for day in DAYS]
        return [(task["name"], cp_model.Domain.FromValues(candidates))]

    if mode == "fixed_days":
        return [
            (
                _occurrence_label(task, day),
                cp_model.Domain(
                    DAYS.index(day) * SLOTS_PER_DAY,
                    DAYS.index(day) * SLOTS_PER_DAY + SLOTS_PER_DAY - duration,
                ),
            )
            for day in days
        ]

    if mode == "fixed":
        # A domain of exactly one value still makes this a proper decision
        # variable — just one the solver has no real choice over — so a fixed
        # occurrence reuses the same interval-variable machinery as an
        # optimized one instead of needing a special case.
        return [
            (_occurrence_label(task, day), cp_model.Domain.FromValues([_fixed_slot(day, hour)]))
            for day in days
        ]

    return [(task["name"], cp_model.Domain(0, HORIZON_SLOTS - duration))]


def _occurrence_label(task, day):
    """Return the CP-SAT variable label for one of a task's occurrences.

    A task with a single occurrence keeps its own name as the label, matching
    the one-variable-per-task naming a "flexible"/"fixed_hour" task already
    uses; a recurring task's occurrences are distinguished by day so each
    shows up individually in the model description.
    """
    days = task.get("days") or []
    if len(days) <= 1:
        return task["name"]
    return f"{task['name']} ({day})"


def _fixed_slot(day, hour):
    """Return the slot index for the start of `hour` (0-23) on `day` (e.g. "Mon")."""
    return DAYS.index(day) * SLOTS_PER_DAY + hour * SLOTS_PER_HOUR


def _format_domain(domain):
    """Render a cp_model.Domain as its range(s), e.g. "[0, 671]", or several
    ranges joined with "∪" when the domain isn't one contiguous span (as with
    a "fixed_hour" task, whose start may land on any of several disjoint
    slots)."""
    parts = domain.FlattenedIntervals()
    ranges = [f"[{parts[i]}, {parts[i + 1]}]" for i in range(0, len(parts), 2)]
    return " ∪ ".join(ranges)


def _duration_slots(task):
    """Return a task's duration as a whole number of 15-minute slots."""
    return task["duration_minutes"] // SLOT_MINUTES


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
    next day. `fixed` mirrors the task's "fixed" scheduling mode so the
    frontend can shade this entry without a second lookup against the task
    list.
    """
    day_index, slot_of_day = divmod(start_slot, SLOTS_PER_DAY)
    start_minutes = slot_of_day * SLOT_MINUTES
    return {
        "name": task["name"],
        "day": DAYS[day_index],
        "start_minutes": start_minutes,
        "end_minutes": start_minutes + task["duration_minutes"],
        "fixed": task.get("schedule_mode") == "fixed",
    }
