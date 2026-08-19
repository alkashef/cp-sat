"""Loads and saves task/schedule data to the JSON file on disk."""
import json
import os
from pathlib import Path


def _tasks_file_path():
    """Return the configured path to the tasks/schedule JSON file."""
    return Path(os.getenv("TASKS_FILE", "data/tasks.json"))


def load():
    """Return the persisted {"tasks": [...], "schedule": [...]} data.

    If the file does not exist yet, returns an empty tasks list and no
    schedule rather than raising.
    """
    path = _tasks_file_path()
    if not path.exists():
        return {"tasks": [], "schedule": None}
    with open(path, "r") as f:
        return json.load(f)


def save(data):
    """Write {"tasks": [...], "schedule": [...]} data to the tasks file."""
    path = _tasks_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
