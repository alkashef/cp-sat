# Design

This document describes **how** the app implements the requirements in
`requirements.md`.

## Architecture

- REQ-16: The system shall expose task management and solve operations via a
  local HTTP API served by the Python backend.
- REQ-17: The system shall use a plain HTML/CSS/JavaScript frontend, with no
  frontend framework, to call the HTTP API and render the calendar.

Flask serves both the static frontend files and the JSON API from a single
process on one port. The user runs the Flask app and opens it in a browser;
there is no separate frontend server and no CORS configuration needed.

```text
Browser (index.html/style.css/app.js)
    |  fetch() JSON over HTTP
    v
Flask app (app.py)
    |-- routes: tasks CRUD + solve
    |-- scheduler.py: builds and runs the CP-SAT model
    |-- storage.py: reads/writes data/tasks.json
    v
data/tasks.json (tasks + last solved schedule)
```

## Directory Structure

```text
cp-sat/
├── config/
│   └── .env               # Flask, data path and solver-default settings
├── data/
│   └── tasks.json          # persisted tasks + last solved schedule
├── docs/
│   ├── requirements.md
│   └── design.md
├── backend/
│   ├── app.py                # Flask app: routes only
│   ├── scheduler.py          # builds/solves the CP-SAT model
│   └── storage.py            # reads/writes data/tasks.json
├── frontend/
│   ├── index.html
│   └── static/
│       ├── style.css
│       └── app.js
├── tests/                   # pytest suite for backend/
│   ├── conftest.py
│   ├── test_storage.py
│   ├── test_tasks_api.py
│   ├── test_scheduler.py
│   ├── test_solve_api.py
│   └── test_model_api.py
├── scripts/                 # repo maintenance/tooling (not runtime code)
└── requirements.txt
```

- `backend/` holds the Flask app and CP-SAT model code; `frontend/` holds the
  static HTML/CSS/JS files. Flask points its static/template folders at
  `frontend/` so it can still serve both from a single process.
- `tests/` holds all pytest tests for the backend, kept separate from the
  application code it exercises.

## Backend

- Single `app.py` Flask application: a handful of routes, no blueprints or
  app factory pattern.
- `scheduler.py`: builds the CP-SAT model from the task list and returns a
  solved schedule (see CP-SAT Model below).
- `storage.py`: loads/saves `data/tasks.json`.
- Config (host, port, data file path) is loaded from `config/.env` via
  `python-dotenv`; nothing else in the code hardcodes these values.
- Every module, class, and function in `scheduler.py` gets a docstring, and
  each CP-SAT concept it uses (interval variables, `AddNoOverlap`, the
  objective, solver parameters, solve status) gets a comment explaining the
  concept itself for a first-time OR-Tools reader — see CLAUDE.md's
  "Source Code Documentation Rules" section. `app.js`'s calendar/tab logic and
  `app.py`'s routes get ordinary docstrings/comments; the concept-level
  explanations belong to `scheduler.py`, where CP-SAT is actually used, and
  to the in-app help text described under Help Icons below.

### Persistence

Implements REQ-6 (task list retained across restarts): the task list is
persisted to a local file rather than kept only in memory.

`data/tasks.json` stores both the task list and the last solved schedule, so
the calendar still shows the most recent result after an app restart without
re-clicking Solve. Shape:

```json
{
  "tasks": [
    {"name": "Write report", "duration_minutes": 90}
  ],
  "schedule": [
    {"name": "Write report", "day": "Mon", "start_minutes": 540, "end_minutes": 630}
  ]
}
```

### CP-SAT Model

- Time is represented as 15-minute slots. Horizon = 7 days x 24 hours x 4
  slots/hour = 672 units. Each task's duration in minutes is converted to a
  slot count (`duration_minutes / 15`).
- Each task gets an interval variable:
  `start = NewIntVar(0, horizon - dur, name)`,
  `interval = NewIntervalVar(start, dur, start + dur, name)`.
- `model.AddNoOverlap(intervals)` enforces REQ-9 (no two tasks overlap).
- Idle time is minimized by minimizing the makespan (the end time of the
  last-finishing task): since total task duration is fixed, minimizing the
  last end time is equivalent to minimizing total idle time across the week.
  `model.AddMaxEquality(makespan, ends)`, `model.Minimize(makespan)`.
- If the solver status is not `OPTIMAL`/`FEASIBLE`, the solve endpoint returns
  an error and the stored schedule is left unchanged (REQ-11's infeasible
  case).
- Slot indices are converted back to day-of-week + minutes-of-day when
  building the API response. Day 0 is `Sun`; `start_minutes` is measured from
  that day's midnight, and `end_minutes` from the same midnight — so a task
  running past midnight ends beyond 1440 rather than moving to the next day,
  and the calendar is responsible for clipping it at the bottom of its column.

`scheduler.py`'s entry point is `solve(tasks, parameters=None)`, where `tasks`
is the stored task list and `parameters` optionally overrides individual solver
parameters (the Solver tab's values, forwarded by `POST /solve`). It returns the
same `{"schedule": [...]}` / `{"error": "..."}` shape the endpoint returns, so
an unschedulable task list is an ordinary return value rather than an exception.
An empty task list returns an empty schedule without invoking the solver.

`describe_model(tasks)` is the read-only counterpart behind `GET /model`
(REQ-23, REQ-24, REQ-25). It builds the same model through the shared
`_build_model(tasks)` helper — which returns the model along with each task's
start and interval variable and the makespan variable, so neither caller
duplicates the construction — and returns a JSON-serializable description of
it: `variables` (name, kind, domain), `constraints` (CP-SAT method, plain
description, variables involved), `objective`, and `raw_proto`, the model's
`str(model.Proto())` dump. It never calls the solver; an empty task list
returns an empty description without building a model at all.

## Flask API

Tasks are identified by name in the URL, since REQ-1/REQ-2 already require
names to be unique — no separate generated ID is needed.

| Method | Path            | Body                           | Response                                |
| ------ | --------------- | ------------------------------ | --------------------------------------- |
| GET    | `/tasks`        | —                              | list of tasks                           |
| POST   | `/tasks`        | `{name, duration_minutes}`     | created task, or 409 if name exists     |
| PUT    | `/tasks/<name>` | `{name?, duration_minutes?}`   | updated task                            |
| DELETE | `/tasks/<name>` | —                              | 204                                     |
| GET    | `/model`        | —                              | model description (see below)           |
| POST   | `/solve`        | `{parameters?}`                | `{schedule: [...]}` or `{error: "..."}` |

- `POST /tasks` and `PUT /tasks/<name>` validate that `duration_minutes` is a
  positive multiple of 15 (REQ-3).
- `POST /solve` runs `scheduler.py` against the current task list, persists
  the result via `storage.py` on success, and never runs implicitly on
  add/edit/remove (REQ-12).
- `GET /model` returns
  `{variables: [...], constraints: [...], objective: {...}, raw_proto: "..."}`
  for the current task list. Like `GET /tasks` it is read-only: it takes no
  body, reads the task list from `storage.py`, builds the model to describe
  it, and never solves or persists anything.

## Frontend

- Three flat files: `frontend/index.html`, `frontend/static/style.css`,
  `frontend/static/app.js`. No build step, no frontend framework.
- `app.js` handles: fetching/rendering the task list, the add/edit/remove
  form interactions, calling `POST /solve`, rendering the calendar, and
  fetching/rendering the Solver tab's model description.
- The weekly calendar is a CSS Grid (7 day columns x 96 rows, one row per
  15-minute slot) built by `app.js`; each scheduled task is rendered as a
  grid-positioned `<div>` labeled with its name, spanning its start/end slots.
  No calendar/charting library is used.
- When `POST /solve` returns `{error: ...}`, `app.js` shows the message
  inline near the Solve button and leaves the existing calendar as-is; the
  message is cleared on the next successful solve.

## UI Specs

The page has a fixed banner, a row of 3 tabs beneath it, and a content area
that shows whichever tab is active. Switching tabs is a client-side view
change in `app.js` — no page reload, no server round-trip.

### Banner

- Title "Timetable Solver" and subtitle "Using Google's OR-Tools", stacked,
  spanning the full width of the page above the tabs.

### Tabs

1. **Tasks** — add/edit/remove tasks and trigger Solve (REQ-1–REQ-6,
   REQ-12, REQ-13).
2. **Solver** — view and edit the CP-SAT parameters used by the next solve
   (REQ-18, REQ-19, REQ-20).
3. **Schedule** — the solved weekly calendar (REQ-14, REQ-15).

The active tab is highlighted with the accent color and an underline; the
last-active tab persists only for the current page session (not saved to
`data/tasks.json`).

### Tab 1: Tasks

#### Task form

- Two inputs: task name (text) and duration in minutes (number, `step="15"`,
  `min="15"`).
- One "Add" button, submits `POST /tasks`.
- On duplicate-name (409) or invalid-duration (400) response, an inline
  validation message appears under the form; no browser `alert()`.

#### Task list

- Plain list/table below the form, one row per task: name, duration
  (formatted as e.g. "1h 30m"), an "Edit" and a "Remove" action.
- "Remove" calls `DELETE /tasks/<name>` immediately (no confirmation dialog,
  given the app's minimal scope).
- "Edit" turns that row's name/duration into editable inputs in place, with
  "Save" (`PUT /tasks/<name>`) and "Cancel" actions; no separate edit modal.
- The list is empty-state aware: shows a plain "No tasks yet" message when
  empty.

#### Solve button

- A single "Solve" button below the task list, disabled when there are zero
  tasks.
- On click: calls `POST /solve`, sending the current parameter values from
  the Solver tab's state. While in flight, the button shows a "Solving…"
  state and is disabled.
- On success: switches to the Schedule tab and renders the calendar,
  clearing any previous error message.
- On error: shows the error message inline next to the button (REQ-11's
  infeasible case), stays on the Tasks tab, and leaves the calendar as
  whatever it showed before.

### Tab 2: Solver

- A leading read-only `objective` row states what CP-SAT is optimizing for
  (minimizing the schedule's makespan/idle time) before the editable
  parameter rows that control how it searches for that optimum. It follows
  the same name/description/help-icon layout as the parameter rows below,
  but its "value" cell is static text, not an input — the objective is
  fixed in `scheduler.py`'s model, not a solve-time parameter.
- One row per parameter, each showing: the parameter's name (as CP-SAT
  names it, e.g. `num_search_workers`), a short plain-language description,
  a help icon (see Help Icons below), and an editable input matched to its
  type.
- REQ-18/REQ-19 parameters and their inputs:

  | Parameter             | Input                     | Default from `config/.env`         |
  | --------------------- | ------------------------- | ---------------------------------- |
  | `num_search_workers`  | number, min 1             | `SOLVER_WORKERS` (8)               |
  | `max_time_in_seconds` | number, min 0.1, step 0.1 | `SOLVER_MAX_TIME_SECONDS` (10)     |
  | `log_search_progress` | checkbox                  | `SOLVER_LOG_SEARCH_PROGRESS` (off) |
  | `randomize_search`    | checkbox                  | `SOLVER_RANDOMIZE_SEARCH` (off)    |
  | `relative_gap_limit`  | number, min 0, step 0.01  | `SOLVER_GAP_LIMIT` (0.01)          |

  The values in brackets are today's `config/.env` values; `config/.env` is the
  source of truth, and `scheduler.py` falls back to a parameter's default only
  for parameters the request does not override.

- Edits update in-memory state in `app.js` only; there is no `PUT` endpoint
  for parameters — they are read by `POST /solve` from the request body
  (REQ-20's "next solve" scope) rather than persisted separately.
- A "Reset to defaults" link restores the table above without affecting any
  saved tasks or schedule.

#### Model section

Below the parameter table, a "Model" section shows the CP-SAT model built from
the current task list, so the model itself is visible in the UI and not just
the settings that control the search (REQ-23, REQ-24, REQ-25).

- Populated from `GET /model` every time the Solver tab becomes active, the
  same lazy-on-switch pattern the Schedule tab uses. Re-fetching on each visit
  keeps it in step with tasks edited on the Tasks tab, with no refresh button
  and no fetch on every task edit. It is independent of solving: the model is
  built to be read, never solved, so the section fills in without ever
  clicking Solve.
- A **Variables** table, styled like the parameter table above (both use the
  shared `.spec-table` class), with one row per variable: name, kind, and
  domain. Start variables are `IntVar (start slot)` with the numeric domain
  `[0, HORIZON_SLOTS - duration]`; interval variables have no numeric domain
  of their own, so an `IntervalVar` row shows the `start + duration = end`
  relationship instead; the makespan is `IntVar (objective)` over
  `[0, HORIZON_SLOTS]`.
- A **Constraints** list, one card per constraint: the CP-SAT method that
  created it (`AddNoOverlap`, `AddMaxEquality`), a plain-language description,
  and the variables it links.
- A collapsible **Raw CP-SAT model** `<details>` holding the `raw_proto` text
  — the same model in CP-SAT's own protobuf form, listing every variable and
  constraint as the solver receives them. The native HTML disclosure widget
  keeps this free of extra JS state.
- With zero tasks, the section shows an empty state ("No tasks yet — add tasks
  to see the model.") in place of the tables, matching `#task-list-empty` and
  `#schedule-empty`.
- The objective is not repeated here: the read-only `objective` row at the top
  of the parameter table already states it.

### Tab 3: Schedule

- CSS Grid, 7 columns (Sun–Sat) with a header row of day labels, and rows
  representing 15-minute slots across 24 hours (96 rows).
- Each scheduled task renders as a single labeled block spanning its
  day/start/end slots, showing the task name; text truncates with ellipsis
  if the block is too narrow/short to fit it.
- A lightweight hour gridline/label down the side (e.g. every 4th row) gives
  time-of-day reference without turning this into a full calendar-library
  feature set.
- The grid sits in a scrollable wrapper (`#schedule-grid-wrapper`) sized so
  only the configured visible window shows without scrolling; the rest of
  the day is reachable via a vertical scrollbar. `SCHEDULE_VISIBLE_START_HOUR`
  and `SCHEDULE_VISIBLE_END_HOUR` in `config/.env` (default 7–24, i.e. 7am–
  midnight) set that window. Sizing this wrapper requires measuring the
  grid's rendered row positions, which only exist once the Schedule panel is
  actually visible (a hidden `.tab-panel` lays out its contents at zero
  size), so `app.js` applies it when the Schedule tab becomes active rather
  than when the grid is (re)rendered.
- On page load (before any Solve click in the session), the grid renders
  from the persisted `schedule` in `data/tasks.json` if present, otherwise
  shows an empty grid.
- A help icon in the tab header (see Help Icons below) explains the
  no-overlap and idle-time-minimization concepts behind the layout.

### Help Icons

REQ-21/REQ-22 (in-app learning): a small circular "?" icon appears next to
each CP-SAT concept surfaced in the UI — every parameter row in the Solver
tab, once on its Model section heading, and once in the Schedule tab header.

- Implementation: a `<button class="help-icon" aria-label="What is this?">`
  next to the concept, with the explanation stored as a `data-help`
  attribute (or a small lookup object in `app.js` keyed by concept name) —
  no backend endpoint needed, since the explanations are static text.
- Activating the icon (click or keyboard `Enter`/`Space`) opens a small
  popover anchored to the icon, showing 2-4 sentences of plain-language
  explanation aimed at someone who has never used OR-Tools: what the concept
  is, and specifically how it's being used in this app. Only one popover is
  open at a time; clicking elsewhere or pressing `Escape` closes it.
- Explanation content, one entry per concept:
  - `objective` (Solver tab) — the quantity CP-SAT minimizes once it has a
    valid arrangement, as opposed to the parameters below it which only
    control how it searches; here that quantity is the makespan, and
    shrinking it packs the week tighter since it's equivalent to shrinking
    the idle gaps between tasks.
  - `model` (Solver tab) — what a model is before any search happens: the
    decision variables CP-SAT must assign, the domain of values each may
    take, and the constraints those values must satisfy; plus what this
    particular model contains (a start and interval variable per task and the
    makespan) and the fact that showing it requires no solve.
  - `num_search_workers` — CP-SAT can search for solutions on multiple
    threads at once ("parallel search"); more workers can find a solution
    faster but use more CPU.
  - `max_time_in_seconds` — the solver stops and returns its best answer so
    far once this many seconds pass, even if it hasn't proven optimality.
  - `log_search_progress` — when on, the solver prints its internal search
    log (bounds, branches explored) so you can watch it work.
  - `randomize_search` — shuffles the solver's internal search order, which
    can change how quickly it finds a solution on hard problems.
  - `relative_gap_limit` — lets the solver stop early once its best answer
    is within this fraction of the theoretical best possible, trading
    provable optimality for speed.
  - Schedule tab (no-overlap + idle time) — explains that CP-SAT is given
    one "interval" per task and a constraint that no two intervals may
    overlap, then is asked to arrange them so the gaps between tasks across
    the week are as small as possible.

## Color Scheme

The app uses the **Signal** palette: a deep navy ground with a single
electric-cyan accent, chosen for a high-contrast "control room"/instrument
feel that suits a page whose middle tab exposes solver internals.

| Token           | Hex       | Used for                                                  |
| --------------- | --------- | --------------------------------------------------------- |
| `--bg`          | `#0C2135` | page/banner background                                    |
| `--surface`     | `#173A56` | tab bar, panels, table rows                               |
| `--surface-alt` | `#123049` | cards nested inside panels                                |
| `--line`        | `#25405A` | borders, dividers, inactive gridlines                     |
| `--ink`         | `#EAF4FB` | primary text                                              |
| `--ink-muted`   | `#7FA8C2` | subtitle, labels, secondary text                          |
| `--accent`      | `#3EC6FF` | active tab underline, Solve button, scheduled task blocks |
| `--accent-ink`  | `#04202F` | text on top of solid `--accent` fills                     |

Applied via CSS custom properties in `style.css`; no separate dark/light
mode is defined, since the palette itself is already dark and this is a
single-purpose learning tool rather than a general-audience app.

## Libraries

| Library         | Purpose                                |
| ---------------- | --------------------------------------- |
| `flask`          | HTTP API + static file serving          |
| `ortools`        | CP-SAT constraint solver                |
| `python-dotenv`  | Loads config values from `config/.env`  |

No frontend libraries are used (plain HTML/CSS/JS).

## Configuration

Per `CLAUDE.md`, all configurable values live in `config/.env`:

```text
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=False

DATA_DIR=data
TASKS_FILE=data/tasks.json
SCHEDULE_FILE=data/schedule.json

SOLVER_WORKERS=8
SOLVER_MAX_TIME_SECONDS=10
SOLVER_LOG_SEARCH_PROGRESS=False
SOLVER_RANDOMIZE_SEARCH=False
SOLVER_GAP_LIMIT=0.01
```

`scheduler.py` loads `config/.env` itself rather than relying on `app.py`, so
the solver can be exercised directly from a Python shell with the same defaults
the app would use.
