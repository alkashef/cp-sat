# Requirements

Requirements are written using EARS (Easy Approach to Requirements Syntax).

## Scope

**Timetable Solver** is an educational app for learning Google OR-Tools
CP-SAT by using it to solve a constraint satisfaction/optimization problem.
It is not intended to be a real, production-grade scheduling tool. The
problem: the user adds tasks, and CP-SAT places them onto a generic weekly
calendar (Sunday–Saturday, no real dates, 24/7 availability). Because the
app exists to teach CP-SAT, the solver's own parameters are exposed and
tunable, not hidden behind a fixed configuration.

## Task Management

- REQ-1: The system shall allow the user to add a task with a required, unique
  name and a duration in minutes.
- REQ-2: The system shall reject adding a task whose name matches an existing
  task's name.
- REQ-3: The system shall require task duration to be a multiple of 15 minutes.
- REQ-4: The system shall allow the user to edit the name and/or duration of an
  existing task.
- REQ-5: The system shall allow the user to remove an existing task.
- REQ-6: The system shall retain the task list across restarts of the app.

## Scheduling Model

- REQ-7: The scheduling horizon shall be one generic week, Sunday through
  Saturday, with no calendar dates.
- REQ-8: The system shall treat the entire week (24 hours a day, all 7 days) as
  available for scheduling tasks.
- REQ-9: The system shall ensure no two scheduled tasks overlap in time.
- REQ-10: WHEN the user triggers a solve, the system shall assign every task a
  start time within the week such that total idle time (unscheduled gaps
  between tasks) across the week is minimized.
- REQ-11: IF no feasible arrangement of all tasks exists within the week, THEN
  the system shall display an error message stating that no feasible schedule
  was found, and shall leave the calendar unchanged.

## Solve Trigger

- REQ-12: The system shall not run the CP-SAT solver automatically when a task
  is added, edited, or removed.
- REQ-13: WHEN the user clicks the "Solve" button, the system shall run the
  CP-SAT solver against the current task list and update the calendar with
  the result.

## Calendar Display

- REQ-14: The system shall display the solved schedule as a weekly grid
  calendar, with days of the week as columns and time of day as rows.
- REQ-15: The system shall display each scheduled task as a labeled block on
  the calendar spanning its assigned start and end time.

## Architecture

- REQ-16: The system shall expose task management and solve operations via a
  local HTTP API served by the Python backend.
- REQ-17: The system shall use a plain HTML/CSS/JavaScript frontend, with no
  frontend framework, to call the HTTP API and render the calendar.

## Solver Parameters

- REQ-18: The system shall display the CP-SAT solver parameters that affect
  the next solve: number of search workers, maximum solve time, whether
  search progress is logged, whether search is randomized, and the relative
  gap limit for early stopping.
- REQ-19: The system shall allow the user to edit the value of each
  displayed solver parameter.
- REQ-20: WHEN the user clicks the "Solve" button, the system shall run the
  CP-SAT solver using the currently edited parameter values.

## Model Inspection

- REQ-23: The system shall display, for the current task list, the CP-SAT
  model's decision variables with their domains, its constraints, and its
  objective.
- REQ-24: The system shall display the raw CP-SAT model handed to the solver,
  in the solver's own text representation.
- REQ-25: The system shall build the displayed model from the current task
  list alone, without running the solver and without requiring the user to
  click "Solve".

## In-App Learning

- REQ-21: The system shall display a help icon next to each CP-SAT concept
  presented in the UI (e.g. each solver parameter, and the no-overlap and
  objective/idle-time-minimization concepts behind the schedule).
- REQ-22: WHEN the user activates a help icon, the system shall display a
  plain-language explanation of that CP-SAT concept for a reader who has
  never used OR-Tools before.
