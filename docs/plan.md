# Plan

Implementation milestones for Timetable Solver, in build order. Each milestone
lists: the requirements it covers, its pytest coverage, a manual user-test
checklist, and the recommended Claude configuration for implementing it.

"Model" is one of Sonnet 5, Opus 5, or Haiku 4.5, chosen per milestone by
complexity: Haiku 4.5 for mechanical/low-risk work, Sonnet 5 for standard
implementation, Opus 5 reserved for the milestone that most needs strong
reasoning (the CP-SAT model itself).

## Milestone 1 — Project scaffolding & config

Directory structure, `config/.env`, `requirements.txt`, empty `backend/` and
`frontend/` packages, Flask app that boots and serves a placeholder page.

- **Covers:** REQ-16, REQ-17 (architecture)
- **pytest:** none — nothing with logic to test yet.
- **User tests:**
  - Run the Flask app; confirm it starts without error and serves a page at
    `http://<FLASK_HOST>:<FLASK_PORT>/`.
  - Confirm no config values are hardcoded outside `config/.env`.
- **Model:** claude-haiku-4-5
- **Thinking mode:** off
- **Effort level:** low

## Milestone 2 — Task storage & CRUD API

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
  - Add a task via the API (or a temporary client), confirm it appears in
    `GET /tasks`.
  - Restart the Flask process and confirm the task is still there.
  - Try adding a duplicate name and a non-15-multiple duration; confirm both
    are rejected with a clear error.
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium

## Milestone 3 — CP-SAT scheduling core

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
  - Add a handful of tasks and confirm the returned schedule has no
    overlapping tasks and looks reasonably packed (little idle time).
  - Add tasks totaling more than a week's worth of minutes; confirm a clean
    "no feasible schedule" result rather than a crash.
  - Change `max_time_in_seconds` to a very small value and confirm the solver
    still returns a result (possibly suboptimal) rather than hanging.
- **Model:** claude-opus-5
- **Thinking mode:** on
- **Effort level:** high

## Milestone 4 — Solve endpoint & wiring

`POST /solve`: reads tasks + parameters, calls `scheduler.py`, persists the
schedule on success via `storage.py`, returns the error shape on failure.

- **Covers:** REQ-12, REQ-13
- **pytest:**
  - `test_solve_api.py`: `POST /solve` with a feasible task list returns a
    schedule and it's persisted to `data/tasks.json`; an infeasible task list
    returns an error and leaves the previously stored schedule untouched;
    adding/editing/removing a task does not itself trigger a solve.
- **User tests:**
  - Add tasks, click Solve (or call the endpoint), confirm the schedule
    returned matches what storage now holds on disk.
  - Confirm editing a task afterward does not change the displayed/stored
    schedule until Solve is clicked again.
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium

## Milestone 5 — Tasks tab UI

Banner, 3-tab shell, and the Tasks tab: task form, task list with inline
edit/remove, Solve button with loading/error states.

- **Covers:** REQ-1, REQ-4, REQ-5, REQ-11 (error display), REQ-14 (tab
  switch on success), REQ-16, REQ-17
- **pytest:** none — this is frontend JS/HTML/CSS; no pytest coverage.
- **User tests:**
  - Add, edit, and remove tasks in the browser; confirm the list updates
    without a page reload.
  - Trigger a duplicate-name and an invalid-duration error; confirm inline
    messages appear (no browser `alert()`).
  - Click Solve with zero tasks (button should be disabled) and with an
    infeasible task set (error shown, stays on Tasks tab).
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium

## Milestone 6 — Solver tab UI

Parameter table (name, description, help icon, editable input) wired to the
in-memory state consumed by the Solve button.

- **Covers:** REQ-18, REQ-19, REQ-20
- **pytest:** none — frontend only.
- **User tests:**
  - Change each parameter's value, click Solve, confirm the new values are
    sent (e.g. via browser dev tools network tab).
  - Use "Reset to defaults" and confirm all fields return to their default
    values without touching saved tasks/schedule.
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium

## Milestone 7 — Schedule tab UI

CSS Grid weekly calendar rendering the solved schedule, including the
page-load-from-persisted-schedule path.

- **Covers:** REQ-14, REQ-15
- **pytest:** none — frontend only.
- **User tests:**
  - After a successful solve, confirm each task appears as a correctly
    positioned, correctly sized, labeled block with no visual overlap.
  - Reload the page without clicking Solve; confirm the last persisted
    schedule still renders.
  - Resize the browser window and confirm the grid stays usable (no
    horizontal page scroll, labels truncate rather than overflow).
- **Model:** claude-sonnet-5
- **Thinking mode:** off
- **Effort level:** medium

## Milestone 8 — Help icons & in-app learning content

Help icon component, popover behavior, and the explanation text for every
solver parameter and the Schedule tab's no-overlap/idle-time concepts.

- **Covers:** REQ-21, REQ-22
- **pytest:** none — frontend only.
- **User tests:**
  - Activate every help icon (mouse and keyboard) and confirm the popover
    text matches the content specified in `docs/design.md`.
  - Confirm only one popover is open at a time, and that clicking elsewhere
    or pressing `Escape` closes it.
- **Model:** claude-sonnet-5 (mechanically simple, but writing accurate
  beginner-level CP-SAT explanations benefits from a stronger model than
  Haiku)
- **Thinking mode:** off
- **Effort level:** low

## Milestone 9 — Color scheme & visual polish

Apply the Signal palette tokens across `style.css`; final pass on spacing,
empty states, and responsive behavior.

- **Covers:** (visual design, not requirement-tied)
- **pytest:** none — frontend only.
- **User tests:**
  - Visually compare the running app against the Signal palette swatch in
    `docs/design.md` for each surface (banner, tabs, panels, buttons).
  - Click through all empty states (no tasks, no schedule yet) and confirm
    they render sensibly rather than blank/broken.
- **Model:** claude-haiku-4-5
- **Thinking mode:** off
- **Effort level:** low

## Milestone 10 — Source code documentation pass

Docstrings on every module/class/function in `scheduler.py`, and CP-SAT
concept comments throughout, per CLAUDE.md's "Source Code Documentation
Rules." Also a docs sync pass (README, requirements.md, design.md) against
whatever changed during implementation.

- **Covers:** (documentation quality, not requirement-tied)
- **pytest:** none.
- **User tests:**
  - Read through `scheduler.py` as if new to OR-Tools; confirm each CP-SAT
    concept (interval variables, `AddNoOverlap`, the objective, parameters,
    solve status) is explained where it's used.
  - Confirm `README.md` and `docs/` accurately describe the app as built.
- **Model:** claude-sonnet-5 (accurate CP-SAT explanations warrant more than
  Haiku)
- **Thinking mode:** off
- **Effort level:** low
