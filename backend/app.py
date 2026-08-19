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
    """Add a new task, enforcing unique name and 15-minute duration."""
    body = request.get_json()
    name = body["name"]
    duration_minutes = body["duration_minutes"]

    data = storage.load()
    if any(task["name"] == name for task in data["tasks"]):
        return jsonify({"error": f"A task named '{name}' already exists."}), 409
    if duration_minutes <= 0 or duration_minutes % 15 != 0:
        return jsonify({"error": "Duration must be a positive multiple of 15 minutes."}), 400

    task = {"name": name, "duration_minutes": duration_minutes}
    data["tasks"].append(task)
    storage.save(data)
    return jsonify(task), 201


@app.route("/tasks/<name>", methods=["PUT"])
def edit_task(name):
    """Edit an existing task's name and/or duration."""
    body = request.get_json()
    new_name = body.get("name", name)
    duration_minutes = body.get("duration_minutes")

    data = storage.load()
    task = next((t for t in data["tasks"] if t["name"] == name), None)
    if task is None:
        return jsonify({"error": f"No task named '{name}'."}), 404
    if new_name != name and any(t["name"] == new_name for t in data["tasks"]):
        return jsonify({"error": f"A task named '{new_name}' already exists."}), 409
    if duration_minutes is not None and (duration_minutes <= 0 or duration_minutes % 15 != 0):
        return jsonify({"error": "Duration must be a positive multiple of 15 minutes."}), 400

    task["name"] = new_name
    if duration_minutes is not None:
        task["duration_minutes"] = duration_minutes
    storage.save(data)
    return jsonify(task)


@app.route("/tasks/<name>", methods=["DELETE"])
def delete_task(name):
    """Remove an existing task by name."""
    data = storage.load()
    data["tasks"] = [t for t in data["tasks"] if t["name"] != name]
    storage.save(data)
    return "", 204


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
