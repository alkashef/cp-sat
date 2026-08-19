# Plan

Implementation milestones for Timetable Solver, in build order. Each milestone
lists: the requirements it covers, its pytest coverage, a manual user-test
checklist, and the recommended Claude configuration for implementing it.

"Model" is one of Sonnet 5, Opus 5, or Haiku 4.5, chosen per milestone by
complexity: Haiku 4.5 for mechanical/low-risk work, Sonnet 5 for standard
implementation, Opus 5 reserved for the milestone that most needs strong
reasoning (the CP-SAT model itself).

| Milestone | Description | Status | Model | Thinking | Effort |
| --- | --- | --- | --- | --- | --- |
| 1 | Project scaffolding & config | DONE | claude-haiku-4-5 | off | low |
| 2 | Task storage & CRUD API | DONE | claude-sonnet-5 | off | medium |
| 3 | CP-SAT scheduling core | DONE | claude-opus-5 | on | high |
| 4 | Solve endpoint & wiring | DONE | claude-sonnet-5 | off | medium |
| 5 | Tasks tab UI | DONE | claude-sonnet-5 | off | medium |
| 6 | Solver tab UI | DONE | claude-sonnet-5 | off | medium |
| 7 | Schedule tab UI | DONE | claude-sonnet-5 | off | medium |
| 8 | Help icons & in-app learning content | DONE | claude-sonnet-5 | off | low |
| 9 | Color scheme & visual polish | DONE | claude-haiku-4-5 | off | low |
| 10 | Source code documentation pass | DONE | claude-sonnet-5 | off | low |
| 11 | Model inspection panel | DONE | claude-sonnet-5 | off | medium |

## Milestone 1 — Project scaffolding & config [DONE]

Directory structure, `config/.env`, `requirements.txt`, empty `backend/` and
`frontend/` packages, Flask app that boots and serves a placeholder page.

- **Covers:** REQ-16, REQ-17 (architecture)
- **pytest:** none — nothing with logic to test yet.
- **User tests:**
  - Start the app from the repo root with the project's Python:

    ```cmd
    python backend/app.py
    ```

    Confirm it starts without a traceback and prints that it's running on
    `http://<FLASK_HOST>:<FLASK_PORT>/` (values from `config/.env`).
  - In a browser, visit `http://<FLASK_HOST>:<FLASK_PORT>/` (e.g.
    `http://127.0.0.1:5000/`) and confirm the placeholder page loads (not a
    404 or 500).
  - Confirm no config values are hardcoded outside `config/.env`:

    ```cmd
    grep -rn "127.0.0.1\|5000" backend/ frontend/
    ```

    (PowerShell: `Select-String -Path backend\*.py,frontend\* -Pattern "127.0.0.1|5000" -Recurse`)
    The only hits should be the fallback defaults in `os.getenv(...)` calls,
    not values used directly.
- **Model:** claude-haiku-4-5
- **Thinking mode:** off
- **Effort level:** low

## Milestone 2 — Task storage & CRUD API [DONE]

`storage.py` (load/save `data/tasks.json`), `POST/GET/PUT/DELETE /tasks`
routes, name-uniqueness and duration-multiple-of-15 validation.

- **Covers:** REQ-1, REQ-2, REQ-3, REQ-4, REQ-5, REQ-6
- **pytest:**
  - `test_storage.py`: round-trips tasks through `data/tasks.json` (save then
    load returns the same tasks); starting from a missing file yields an
    empty task list.
  - `test_tasks_api.py`: add task succeeds; duplicate name returns 409;
    duration not a multiple of 15 returns 400; edit updates name/duration;
    delete removes the task; task list persists across a simulated restart
    (re-instantiate storage from the same file).
- **User tests:**
  - Start the app (`python backend/app.py`), then in a separate terminal add
    a task and confirm it's returned and shows up in the list:

    ```cmd
    curl.exe -X POST http://127.0.0.1:5000/tasks -H "Content-Type: application/json" -d "{\"name\": \"Write report\", \"duration_minutes\": 90}"
    curl.exe http://127.0.0.1:5000/tasks
    ```

    (PowerShell equivalent:
    `Invoke-RestMethod -Uri http://127.0.0.1:5000/tasks -Method Post -ContentType "application/json" -Body '{"name": "Write report", "duration_minutes": 90}'`
    then `Invoke-RestMethod -Uri http://127.0.0.1:5000/tasks -Method Get`.)
    Expect `201` with the task echoed back, then a `GET` showing
    `[{"duration_minutes":90,"name":"Write report"}]`.
  - Stop the Flask process (Ctrl+C) and restart it (`python backend/app.py`),
    then re-run the `GET /tasks` command above; confirm the same task is
    still returned (proves persistence to `data/tasks.json`, not just
    in-memory state).
  - Try adding a duplicate name — re-run the same `POST` command again and
    confirm it now returns `409`:

    ```cmd
    curl.exe -i -X POST http://127.0.0.1:5000/tasks -H "Content-Type: application/json" -d "{\"name\": \"Write report\", \"duration_minutes\": 30}"
    ```

    (the `-i` flag prints the status line so you can see `HTTP/1.1 409`.)
  - Try a non-15-multiple duration and confirm it returns `400`:

    ```cmd
    curl.exe -i -X POST http://127.0.0.1:5000/tasks -H "Content-Type: application/json" -d "{\"name\": \"Bad Duration Task\", \"duration_minutes\": 20}"
    ```
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium

## Milestone 3 — CP-SAT scheduling core [DONE]

`scheduler.py`: builds the CP-SAT model (interval variables, `AddNoOverlap`,
makespan objective), runs it with configurable parameters, and converts the
result back to day/time. This is the heart of the app and the milestone most
worth extra reasoning budget.

- **Covers:** REQ-7, REQ-8, REQ-9, REQ-10, REQ-11, REQ-18, REQ-19, REQ-20
- **pytest:**
  - `test_scheduler.py`: a small task set solves to a non-overlapping,
    idle-time-minimized schedule; total scheduled duration equals the sum of
    task durations; a task set whose total duration exceeds the week (>10080
    minutes) returns the infeasible/error result instead of raising; passing
    each solver parameter (workers, time limit, logging, randomization, gap
    limit) doesn't change correctness of a feasible solve.
- **User tests:**
  - `scheduler.py` has no route of its own yet (that's Milestone 4), so
    exercise its entry point, `scheduler.solve(tasks, parameters=None)`,
    directly from a Python shell:

    ```cmd
    python -c "import sys; sys.path.insert(0, 'backend'); import scheduler; print(scheduler.solve([{'name': 'A', 'duration_minutes': 60}, {'name': 'B', 'duration_minutes': 90}]))"
    ```

    Inspect the printed schedule and confirm no two tasks' time ranges
    overlap and idle gaps look small.
  - Add tasks totaling more than a week's worth of minutes (>10080) with the
    same approach and confirm it returns the infeasible/error result rather
    than raising an exception, e.g.:

    ```cmd
    python -c "import sys; sys.path.insert(0, 'backend'); import scheduler; print(scheduler.solve([{'name': 'Huge', 'duration_minutes': 10095}]))"
    ```
  - Set `SOLVER_MAX_TIME_SECONDS` to a very small value (e.g. `1`) in
    `config/.env`, re-run the first command with a larger task set, and
    confirm it returns promptly with a (possibly suboptimal) result instead
    of hanging.
- **Model:** claude-opus-5
- **Thinking mode:** on
- **Effort level:** high

## Milestone 4 — Solve endpoint & wiring [DONE]

`POST /solve`: reads tasks + parameters, calls `scheduler.py`, persists the
schedule on success via `storage.py`, returns the error shape on failure.

- **Covers:** REQ-12, REQ-13
- **pytest:**
  - `test_solve_api.py`: `POST /solve` with a feasible task list returns a
    schedule and it's persisted to `data/tasks.json`; an infeasible task list
    returns an error and leaves the previously stored schedule untouched;
    adding/editing/removing a task does not itself trigger a solve.
- **User tests:**
  - With the app running, add a couple of tasks, then call `POST /solve` and
    confirm it returns a schedule:

    ```cmd
    curl.exe -X POST http://127.0.0.1:5000/tasks -H "Content-Type: application/json" -d "{\"name\": \"Write report\", \"duration_minutes\": 90}"
    curl.exe -X POST http://127.0.0.1:5000/solve
    ```

    Then confirm it was persisted by reading the file directly:

    ```cmd
    type data\tasks.json
    ```

    (PowerShell: `Get-Content data\tasks.json`.) Confirm the `schedule` field
    in the file matches what `/solve` returned.
  - Edit the task afterward and confirm the stored/displayed schedule is
    unchanged until `/solve` is called again:

    ```cmd
    curl.exe -X PUT "http://127.0.0.1:5000/tasks/Write report" -H "Content-Type: application/json" -d "{\"duration_minutes\": 45}"
    type data\tasks.json
    ```

    The `tasks` entry should now show 45 minutes, but the `schedule` field
    should still reflect the old 90-minute solve until you `POST /solve`
    again.
  - Force an infeasible task list (e.g. a single task over 10080 minutes),
    call `POST /solve`, and confirm it returns an error response while
    `data/tasks.json`'s `schedule` field still holds the last successful
    solve, not the failed attempt.
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium

## Milestone 5 — Tasks tab UI [DONE]

Banner, 3-tab shell, and the Tasks tab: task form, task list with inline
edit/remove, Solve button with loading/error states.

- **Covers:** REQ-1, REQ-4, REQ-5, REQ-11 (error display), REQ-14 (tab
  switch on success), REQ-16, REQ-17
- **pytest:** none — this is frontend JS/HTML/CSS; no pytest coverage.
- **User tests:**
  - Start the app (`python backend/app.py`) and open
    `http://127.0.0.1:5000/` in a browser.
  - Add a task: fill in the name field (e.g. `Write report`) and duration
    field (e.g. `90`), click Add. Confirm it appears in the task list
    immediately, with no full-page reload (watch the browser tab's loading
    spinner — it shouldn't flash).
  - Edit that task inline: click its edit control, change the duration to
    `45`, save. Confirm the list updates in place.
  - Remove the task: click its remove control. Confirm it disappears from
    the list.
  - Trigger a duplicate-name error: add a task named `Write report`, then
    add another task with the same name. Confirm an inline error message
    appears near the form — open the browser dev tools Console (F12) first
    and confirm no `alert()` dialog fires and no uncaught JS errors are
    logged.
  - Trigger an invalid-duration error: try adding a task with duration `20`
    (not a multiple of 15). Confirm an inline error appears the same way.
  - With zero tasks in the list, confirm the Solve button is disabled
    (greyed out / unclickable).
  - Add a task with an infeasible duration (e.g. `10800` minutes, over a
    week), click Solve, and confirm an inline error is shown and the UI
    stays on the Tasks tab (does not switch to the Schedule tab).
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium

## Milestone 6 — Solver tab UI [DONE]

Parameter table (name, description, help icon, editable input) wired to the
in-memory state consumed by the Solve button.

- **Covers:** REQ-18, REQ-19, REQ-20
- **pytest:** none — frontend only.
- **User tests:**
  - With the app running and at least one task added, open the browser dev
    tools (F12) and switch to the Network tab. Go to the Solver tab in the
    app, change each parameter's input value (e.g. set `workers` to `2`,
    `max_time_in_seconds` to `5`), then switch back to Tasks and click Solve.
  - In the Network tab, click the `solve` request and inspect its request
    payload (Payload/Body panel). Confirm the changed parameter values are
    present in the JSON body, not the `config/.env` defaults.
  - Click "Reset to defaults" on the Solver tab. Confirm every input field
    reverts to the default shown in `config/.env`
    (`SOLVER_WORKERS`, `SOLVER_MAX_TIME_SECONDS`, etc.).
  - After resetting, switch to the Tasks tab and the Schedule tab and confirm
    both are unaffected — resetting solver parameters must not clear or
    alter saved tasks or the last persisted schedule shown there.
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium

## Milestone 7 — Schedule tab UI [DONE]

CSS Grid weekly calendar rendering the solved schedule, including the
page-load-from-persisted-schedule path.

- **Covers:** REQ-14, REQ-15
- **pytest:** none — frontend only.
- **User tests:**
  - With the app running, add two or three tasks with distinct durations
    (e.g. `Write report` 90 min, `Team sync` 30 min), click Solve, and let
    the UI switch to the Schedule tab.
  - Visually confirm each task renders as a labeled block positioned at its
    solved day/time, sized proportionally to its duration, with no block
    visually overlapping another.
  - Reload the browser page (F5) without clicking Solve again. Confirm the
    same schedule still renders on the Schedule tab, unchanged (it's read
    from the persisted schedule, not recomputed).
  - Resize the browser window from full width down to a narrow width (e.g.
    drag it to ~400px, or use dev tools' device toolbar, Ctrl+Shift+M).
    Confirm the page never grows a horizontal scrollbar and task labels
    truncate (e.g. with an ellipsis) rather than overflowing their block.
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium

## Milestone 8 — Help icons & in-app learning content [DONE]

Help icon component, popover behavior, and the explanation text for every
solver parameter and the Schedule tab's no-overlap/idle-time concepts.

- **Covers:** REQ-21, REQ-22
- **pytest:** none — frontend only.
- **User tests:**
  - With the app running, go through each solver parameter's help icon and
    the Schedule tab's help icon(s) one at a time:
    - Mouse: click (or hover, per the implemented trigger) the icon.
    - Keyboard: `Tab` to focus the icon, then press `Enter` or `Space`.
    In both cases, confirm the popover text appears and matches the
    corresponding explanation in `docs/design.md`.
  - With one popover open, activate a second help icon and confirm the
    first popover closes (only one open at a time).
  - With a popover open, click elsewhere on the page and confirm it closes;
    reopen it and press `Escape` and confirm it closes that way too.
- **Model:** claude-sonnet-5 (mechanically simple, but writing accurate
  beginner-level CP-SAT explanations benefits from a stronger model than
  Haiku)
- **Thinking mode:** off
- **Effort level:** low

## Milestone 9 — Color scheme & visual polish [DONE]

Apply the Signal palette tokens across `style.css`; final pass on spacing,
empty states, and responsive behavior.

- **Covers:** (visual design, not requirement-tied)
- **pytest:** none — frontend only.
- **User tests:**
  - With the app running, open the browser dev tools (F12), use the color
    picker/inspector on each surface (banner, tab bar, panels, buttons,
    schedule blocks), and compare the sampled color values against the
    Signal palette swatch in `docs/design.md`.
  - Delete all tasks (via the UI or by clearing `data/tasks.json`'s `tasks`
    array and restarting the app) and load the Tasks tab; confirm the empty
    state renders a sensible message/illustration rather than a blank area.
  - With no schedule yet solved (`schedule` is `null` in `data/tasks.json`),
    load the Schedule tab; confirm it also shows a sensible empty state
    rather than a blank or broken grid.
- **Model:** claude-haiku-4-5
- **Thinking mode:** off
- **Effort level:** low

## Milestone 10 — Source code documentation pass [DONE]

Docstrings on every module/class/function in `scheduler.py`, and CP-SAT
concept comments throughout, per CLAUDE.md's "Source Code Documentation
Rules." Also a docs sync pass (README, requirements.md, design.md) against
whatever changed during implementation.

- **Covers:** (documentation quality, not requirement-tied)
- **pytest:** none.
- **User tests:**
  - Open [scheduler.py](backend/scheduler.py) and read it top to bottom as
    if new to OR-Tools. For each of these concepts, confirm there's a
    comment at its point of use explaining what it is and why it's needed
    (not just what the line does): interval variables, `AddNoOverlap`, the
    objective/`Minimize` call, solver parameters, and the solve status
    check.
  - Diff the current state of `README.md`, `docs/requirements.md`, and
    `docs/design.md` against the app as actually built:

    ```cmd
    git diff --stat README.md docs/
    ```

    Read each changed section and confirm it still matches the shipped
    behavior (routes, config keys, directory layout, UI flow).
- **Model:** claude-sonnet-5 (accurate CP-SAT explanations warrant more than
  Haiku)
- **Thinking mode:** off
- **Effort level:** low

## Milestone 11 — Model inspection panel [DONE]

`scheduler.describe_model(tasks)` plus `GET /model`, and a "Model" section on
the Solver tab showing the model's variables and their domains, its
constraints, and the raw `model.Proto()` dump — built from the current task
list on every visit to the tab, without solving. `_build_model` now returns
its interval and makespan variables too, so `solve()` and `describe_model()`
share one construction. See `docs/model-vis-plan.md` for the full plan.

- **Covers:** REQ-23, REQ-24, REQ-25 (and REQ-21/REQ-22 for the section's
  help icon)
- **pytest:**
  - `test_scheduler.py`: `describe_model()` lists a start and an interval
    variable per task plus the makespan; start domains stop at
    `HORIZON_SLOTS - duration`; the constraint entries name every task; the
    objective minimizes the makespan; the raw proto contains CP-SAT's own
    `no_overlap`/`lin_max` constraints; an empty task list returns an empty
    description without building a model.
  - `test_model_api.py`: `GET /model` returns 200 with the expected variable
    /constraint/objective/raw-proto shape for a populated task list, an empty
    description when there are no tasks, and never solves or persists a
    schedule.
- **User tests:**
  - Start the app (`python backend/app.py`), add 2-3 tasks with distinct
    durations on the Tasks tab, then switch to the Solver tab. Confirm the
    Model section lists a `start` variable per task with its domain, an
    `IntervalVar` entry per task, the `makespan`, the `AddNoOverlap` and
    `AddMaxEquality` constraints in plain English, and the task names and
    durations you just entered.
  - Expand "Raw CP-SAT model" and confirm it shows protobuf text listing the
    same variables and constraints in CP-SAT's native form.
  - Confirm all of the above appears without ever clicking Solve.
  - Edit a task's duration on the Tasks tab, return to the Solver tab, and
    confirm the variable's domain updates to match.
  - Remove all tasks and revisit the Solver tab; confirm the empty state
    ("No tasks yet — add tasks to see the model.") shows instead of an empty
    or broken table.
  - Click the help icon next to the "Model" heading and confirm the popover
    explains variables, domains, and constraints.
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium
