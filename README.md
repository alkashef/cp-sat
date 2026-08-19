# Timetable Solver

An educational app for learning Google OR-Tools' **CP-SAT** constraint
solver. You add tasks with a name and duration; CP-SAT lays them out on a
generic weekly calendar (Sunday–Saturday, no real dates) so that no two
tasks overlap and idle time between them is minimized.

This isn't a production scheduling tool — it's a small, readable codebase
built to show CP-SAT concepts (interval variables, `AddNoOverlap`, the
objective, solver parameters) in a working app, with the solver's own
parameters exposed in the UI rather than hidden.

## Features

- Add, edit, and remove tasks (name + duration in 15-minute increments);
  the task list persists across restarts.
- Click **Solve** to run CP-SAT and lay out all tasks on a weekly calendar
  with minimal idle time between them.
- Tune the solver's own parameters (search workers, time limit, gap limit,
  logging, randomization) from the UI before solving.
- Inspect the CP-SAT model itself — every decision variable with its domain,
  the constraints linking them, and the raw protobuf model handed to the
  solver — built from the current task list without running a solve.
- In-app help icons explain each CP-SAT concept in plain language.

## Requirements

- Python 3.9+

## Getting Started

```cmd
pip install -r requirements.txt
python backend/app.py
```

Then open `http://127.0.0.1:5000/` (or whatever `FLASK_HOST`/`FLASK_PORT`
are set to in `config/.env`) in a browser.

## Configuration

All configuration lives in [config/.env](config/.env) — Flask host/port,
data file paths, and default solver parameters. Nothing else in the code
hardcodes these values.

## Project Structure

```text
cp-sat/
├── config/.env       # all configuration values
├── data/              # persisted tasks + last solved schedule
├── docs/              # requirements, design, and plan documents
├── backend/           # Flask app and CP-SAT model/solver code
├── frontend/          # static HTML/CSS/JS UI
├── tests/             # pytest suite for backend/
└── scripts/           # repo maintenance/tooling (not runtime code)
```

## API

| Method | Path            | Body                          | Response                                |
| ------ | --------------- | ------------------------------ | --------------------------------------- |
| GET    | `/tasks`        | —                               | list of tasks                           |
| POST   | `/tasks`        | `{name, duration_minutes}`     | created task, or 409 if name exists     |
| PUT    | `/tasks/<name>` | `{name?, duration_minutes?}`   | updated task                            |
| DELETE | `/tasks/<name>` | —                               | 204                                     |
| GET    | `/model`        | —                               | variables, constraints, objective, raw proto |
| POST   | `/solve`        | `{parameters?}`                | `{schedule: [...]}` or `{error: "..."}` |

## Running Tests

```cmd
pytest
```

## Documentation

- [docs/requirements.md](docs/requirements.md) — functional requirements (EARS format)
- [docs/design.md](docs/design.md) — architecture, CP-SAT model, API, and UI design
- [docs/plan.md](docs/plan.md) — implementation milestones and status

## Tech Stack

- Backend: Python, Flask
- Solver: Google OR-Tools, CP-SAT
- Testing: pytest
- Frontend: HTML, CSS, JavaScript (no framework)
