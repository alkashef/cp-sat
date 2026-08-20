"""Flask app for the Timetable Solver."""
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

import scheduler
import storage

# Load configuration from config/.env
config_path = Path(__file__).parent.parent / "config" / ".env"
load_dotenv(config_path)

app = Flask(
    __name__,
    template_folder=Path(__file__).parent.parent / "frontend",
    static_folder=Path(__file__).parent.parent / "frontend" / "static",
)

VALID_SCHEDULE_MODES = {"flexible", "fixed_hour", "fixed_days", "fixed"}


def _parsed_schedule_fields(schedule_mode, days, hour, duration_minutes):
    """Validate and normalize a task's schedule_mode/days/hour values.

    Callers supply `schedule_mode`/`days`/`hour` already defaulted to
    whatever "not specified" should mean for the request (the "flexible"/[]/
    None task defaults on add, or the task's existing values on a partial
    edit). Returns `(schedule_mode, days, hour, error)`; `error` is None on
    success, otherwise a message to return as a 400. `days`/`hour` are
    normalized to []/None when the chosen mode doesn't use them, so a stray
    value sent for an irrelevant field is silently dropped rather than
    validated (REQ-26).
    """
    if schedule_mode not in VALID_SCHEDULE_MODES:
        return None, None, None, f"schedule_mode must be one of {sorted(VALID_SCHEDULE_MODES)}."

    uses_days = schedule_mode in ("fixed_days", "fixed")
    uses_hour = schedule_mode in ("fixed_hour", "fixed")

    if uses_days:
        if not days or any(day not in scheduler.DAYS for day in days):
            return None, None, None, "days must be a non-empty list of valid weekdays for this scheduling mode."
    else:
        days = []

    if uses_hour:
        if not isinstance(hour, int) or isinstance(hour, bool) or not (0 <= hour <= 23):
            return None, None, None, "hour must be an integer from 0 to 23 for this scheduling mode."
    else:
        hour = None

    # A non-flexible task's occurrence(s) must each fit inside a single day
    # (schedule_mode "flexible" is the only mode allowed to run past
    # midnight, per today's existing whole-week behavior).
    if schedule_mode != "flexible":
        if duration_minutes > scheduler.MINUTES_PER_DAY:
            return None, None, None, "Duration must fit within a single day for this scheduling mode."
        if uses_hour and hour * 60 + duration_minutes > scheduler.MINUTES_PER_DAY:
            return None, None, None, "Duration doesn't fit in a day starting at that hour."

    return schedule_mode, days, hour, None


def _fixed_conflict(task, other_tasks):
    """Return the name of an existing "fixed" task overlapping `task`, or None.

    Only meaningful when `task` is itself in "fixed" mode: a "fixed" task's
    occurrences are pinned to an exact day and hour (via
    `scheduler.fixed_ranges`), so two fixed tasks overlapping can be detected
    directly, without running the solver (REQ-31).
    """
    ranges = scheduler.fixed_ranges(task)
    for other in other_tasks:
        for start, end in ranges:
            for other_start, other_end in scheduler.fixed_ranges(other):
                if start < other_end and other_start < end:
                    return other["name"]
    return None


@app.route("/")
def index():
    """Serve the main page, passing the solver defaults and persisted schedule."""
    return render_template(
        "index.html",
        solver_defaults=scheduler.default_parameters(),
        schedule=storage.load()["schedule"],
        schedule_visible_start_hour=int(os.getenv("SCHEDULE_VISIBLE_START_HOUR", 7)),
        schedule_visible_end_hour=int(os.getenv("SCHEDULE_VISIBLE_END_HOUR", 24)),
    )


@app.route("/tasks", methods=["GET"])
def list_tasks():
    """Return the current task list."""
    return jsonify(storage.load()["tasks"])


@app.route("/tasks", methods=["POST"])
def add_task():
    """Add a new task, enforcing unique name, 15-minute duration, and valid scheduling fields."""
    body = request.get_json()
    name = body["name"]
    duration_minutes = body["duration_minutes"]

    data = storage.load()
    if any(task["name"] == name for task in data["tasks"]):
        return jsonify({"error": f"A task named '{name}' already exists."}), 409
    if duration_minutes <= 0 or duration_minutes % 15 != 0:
        return jsonify({"error": "Duration must be a positive multiple of 15 minutes."}), 400

    schedule_mode, days, hour, error = _parsed_schedule_fields(
        body.get("schedule_mode", "flexible"), body.get("days") or [], body.get("hour"), duration_minutes
    )
    if error:
        return jsonify({"error": error}), 400

    task = {
        "name": name,
        "duration_minutes": duration_minutes,
        "schedule_mode": schedule_mode,
        "days": days,
        "hour": hour,
    }

    if schedule_mode == "fixed":
        conflict = _fixed_conflict(task, data["tasks"])
        if conflict:
            return jsonify({"error": f"This fixed task overlaps '{conflict}'."}), 409

    data["tasks"].append(task)
    storage.save(data)
    return jsonify(task), 201


@app.route("/tasks/<name>", methods=["PUT"])
def edit_task(name):
    """Edit an existing task's name, duration, and/or scheduling fields.

    Any field omitted from the request body keeps the task's current value —
    the same partial-update behavior `duration_minutes` already had.
    """
    body = request.get_json()
    new_name = body.get("name", name)

    data = storage.load()
    task = next((t for t in data["tasks"] if t["name"] == name), None)
    if task is None:
        return jsonify({"error": f"No task named '{name}'."}), 404
    if new_name != name and any(t["name"] == new_name for t in data["tasks"]):
        return jsonify({"error": f"A task named '{new_name}' already exists."}), 409

    duration_minutes = body.get("duration_minutes", task["duration_minutes"])
    if duration_minutes <= 0 or duration_minutes % 15 != 0:
        return jsonify({"error": "Duration must be a positive multiple of 15 minutes."}), 400

    schedule_mode, days, hour, error = _parsed_schedule_fields(
        body.get("schedule_mode", task.get("schedule_mode", "flexible")),
        body.get("days", task.get("days")) or [],
        body.get("hour", task.get("hour")),
        duration_minutes,
    )
    if error:
        return jsonify({"error": error}), 400

    updated = {
        "name": new_name,
        "duration_minutes": duration_minutes,
        "schedule_mode": schedule_mode,
        "days": days,
        "hour": hour,
    }

    if schedule_mode == "fixed":
        other_tasks = [t for t in data["tasks"] if t["name"] != name]
        conflict = _fixed_conflict(updated, other_tasks)
        if conflict:
            return jsonify({"error": f"This fixed task overlaps '{conflict}'."}), 409

    task.clear()
    task.update(updated)
    storage.save(data)
    return jsonify(task)


@app.route("/tasks/<name>", methods=["DELETE"])
def delete_task(name):
    """Remove an existing task by name."""
    data = storage.load()
    data["tasks"] = [t for t in data["tasks"] if t["name"] != name]
    storage.save(data)
    return "", 204


@app.route("/model", methods=["GET"])
def describe_model():
    """Return a description of the CP-SAT model for the current task list.

    Read-only and independent of solving: it builds the model to inspect it,
    never runs the solver, and persists nothing.
    """
    return jsonify(scheduler.describe_model(storage.load()["tasks"]))


@app.route("/solve", methods=["POST"])
def solve():
    """Solve the current task list and persist the schedule on success.

    Never runs implicitly on task add/edit/remove; the stored schedule is
    left untouched when the solve fails (e.g. the tasks don't fit in a week).
    """
    body = request.get_json(silent=True) or {}
    parameters = body.get("parameters")

    data = storage.load()
    result = scheduler.solve(data["tasks"], parameters=parameters)

    if "error" in result:
        return jsonify(result), 400

    data["schedule"] = result["schedule"]
    storage.save(data)
    return jsonify(result)


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host=host, port=port, debug=debug)
