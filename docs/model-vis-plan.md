# Model inspection panel — visualize variables, constraints, and domains

## Context

This app exists to teach CP-SAT, but right now the actual model CP-SAT solves
is invisible — the Solver tab only shows editable *search* parameters
(`num_search_workers`, etc.) plus a hardcoded, static objective label. There is
no view of the decision variables, their domains, or the constraints linking
them for the task list currently entered. The user wants to be able to
print/visualize that model — variables, constraints, and domains — as a
learning aid, matching this repo's stated purpose of teaching CP-SAT concepts,
not just running them.

Decisions made with the user before drafting this plan:
- **Where:** extend the existing Solver tab (not a new tab, not a
  backend-only script).
- **Detail level:** both a friendly, human-readable summary (variables tied to
  task names, constraints in plain English) *and* the raw CP-SAT
  `model.Proto()` text dump, the literal representation handed to the solver.
- **Timing:** on-demand and standalone — the model is *built* (never solved)
  from the current task list whenever the Solver tab is viewed, independent of
  clicking Solve.

## Backend changes

### `backend/scheduler.py`

`_build_model(tasks)` (scheduler.py:65-104) currently discards `intervals` and
`makespan` after use, returning only `(model, starts)`. Change it to return
`(model, starts, intervals, makespan)` so both `solve()` and the new
introspection function can reuse the exact same construction logic — no
duplicated model-building code. `solve()` (scheduler.py:43) updates its
unpacking accordingly; it still only needs `model` and `starts`.

Add a new function `describe_model(tasks)`:
- Empty `tasks` → return an empty description (mirroring `solve()`'s existing
  empty-task early return at scheduler.py:40-41) without invoking CP-SAT.
- Otherwise call `_build_model(tasks)` and build a JSON-serializable dict:
  - `variables`: one entry per task's `start` IntVar (name, domain
    `[0, HORIZON_SLOTS - duration]`) and one per task's interval var
    (name, a short description like `"start + {duration} = end"` since an
    interval var's "domain" isn't a single numeric range), plus the
    `makespan` IntVar (domain `[0, HORIZON_SLOTS]`). Domain bounds are the
    same values already computed while building the model — no need to read
    them back from CP-SAT's internals.
  - `constraints`: one entry for `AddNoOverlap` (type, plain-language
    description, the list of task names involved) and one for
    `AddMaxEquality` (type, description, `makespan` + task names involved).
  - `objective`: `{"type": "Minimize", "expression": "makespan", "description": ...}`.
  - `raw_proto`: `str(model.Proto())` — CP-SAT's own protobuf text dump,
    listing every variable and constraint in the model's native form. This is
    the literal answer to "the model given to the solver," complementing the
    friendly summary above which is built from the same task/duration data,
    not parsed back out of the proto.
- Per `CLAUDE.md`'s Source Code Documentation Rules, `describe_model` needs a
  docstring plus CP-SAT-concept comments at `model.Proto()` explaining what
  the proto is and why dumping it is useful for a reader new to OR-Tools —
  the same treatment already given to `AddNoOverlap`/`AddMaxEquality`/etc. in
  this file.

### `backend/app.py`

Add `GET /model`, following the exact pattern of `list_tasks()` (app.py:33-36):
loads tasks via `storage.load()`, calls `scheduler.describe_model(tasks)`,
returns `jsonify(...)`. No body, no persistence — read-only, matching
`GET /tasks`. Reading from `storage.load()` rather than a request body keeps
it consistent with how the Tasks tab already persists every change
immediately (unlike solver parameters, which are local-only until Solve).

## Frontend changes

### `frontend/index.html`

Inside `#tab-solver` (index.html:39-100), add a "Model" section — reuse the
existing `#solver-params` table styling and `.empty-state` pattern
(style.css:206-251, :165) rather than introducing new table CSS:
- A variables table (name, kind, domain) and a constraints list, populated
  from `GET /model`.
- A collapsible `<details><summary>Raw CP-SAT model</summary><pre>...</pre></details>`
  for the `raw_proto` text — native HTML disclosure widget, no new JS state
  needed, consistent with this project's no-framework/minimal-JS approach.
- An empty-state message ("No tasks yet — add tasks to see the model.") for
  the zero-task case, matching `#task-list-empty`/`#schedule-empty`.

Leave the existing hardcoded `objective` row (index.html:49-56) as-is — it's
already correct and static text is fine there; this plan only adds the new
variables/constraints section rather than rewiring existing UI.

### `frontend/static/app.js`

- `fetchModel()` (mirrors `fetchTasks()`, app.js:58-61) and `renderModel(data)`
  to populate the new table/list/`<pre>` from the `GET /model` response.
- Call `fetchModel().then(renderModel)` from `switchTab`'s `"solver"` case,
  the same lazy-on-switch pattern already used for the Schedule tab's
  `applyScheduleVisibleWindow()` (app.js:14-19) — refetches fresh model info
  each time the user opens the tab, so it always reflects the current task
  list without needing a manual refresh button or a fetch on every task edit
  (task edits can't happen while the Solver tab is open, since editing lives
  on the Tasks tab).

## Docs & plan tracking

- `docs/requirements.md`: add a new section/requirements for on-demand model
  inspection (variables/constraints/domains) and the raw proto view, e.g.
  REQ-23/REQ-24.
- `docs/design.md`: extend "Tab 2: Solver" with the new Model section's
  layout, and add `GET /model` to the Flask API table (design.md:136-142).
- `docs/plan.md`: add **Milestone 11 — Model inspection panel [TODO]**
  following the established format (Covers/pytest/User tests/Model/Thinking/
  Effort), and add its row to the milestone table (plan.md:12-23).

## Tests

- `tests/test_scheduler.py`: extend with tests for `describe_model()` —
  correct variable count/domains for a small task list (reusing the existing
  `TASKS` fixture), constraint entries reference the right task names, and
  the empty-task-list case returns an empty description without touching
  CP-SAT.
- New `tests/test_model_api.py` (mirrors `test_solve_api.py`): `GET /model`
  returns 200 with the expected shape for a populated task list, and an
  empty/no-tasks response when no tasks exist — matching this repo's existing
  scoped-to-the-plan test style (no broader test suite growth).

## Verification

1. `python backend/app.py`, open the app, add 2-3 tasks with distinct
   durations on the Tasks tab.
2. Switch to the Solver tab and confirm the new Model section shows: a
   `start` variable per task with its domain, an `interval` entry per task, a
   `makespan` variable, the `NoOverlap` and `MaxEquality` constraints
   described in plain English, and the objective — all matching the task
   names/durations just entered.
3. Expand the "Raw CP-SAT model" details element and confirm it shows
   protobuf text listing the same variables/constraints in CP-SAT's native
   form.
4. Remove all tasks and revisit the Solver tab; confirm the empty state shows
   instead of an empty/broken table.
5. Confirm this works without ever clicking Solve — the Model section must
   populate from the task list alone.
6. `pytest tests/test_scheduler.py tests/test_model_api.py` — new tests pass.
