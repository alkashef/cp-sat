# Requirements

Requirements are written using EARS (Easy Approach to Requirements Syntax).

## Scope

This app is a learning exercise for using Google OR-Tools CP-SAT to solve a
constraint satisfaction/optimization problem. It is not intended to be a real,
production-grade scheduling tool. The problem: the user adds tasks, and CP-SAT
places them onto a generic weekly calendar (Sunday–Saturday, no real dates,
24/7 availability).

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
- WHEN the user triggers a solve, the system shall assign every task a start
  time within the week such that total idle time (unscheduled gaps between
  tasks) across the week is minimized.
- IF no feasible arrangement of all tasks exists within the week, THEN the
  system shall display an error message stating that no feasible schedule was
  found, and shall leave the calendar unchanged.

## Solve Trigger

- REQ-12: The system shall not run the CP-SAT solver automatically when a task
  is added, edited, or removed.
- WHEN the user clicks the "Solve" button, the system shall run the CP-SAT
  solver against the current task list and update the calendar with the
  result.

## Calendar Display

- REQ-14: The system shall display the solved schedule as a weekly grid
  calendar, with days of the week as columns and time of day as rows.
- REQ-15: The system shall display each scheduled task as a labeled block on
  the calendar spanning its assigned start and end time.
