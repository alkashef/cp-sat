# Design

## Architecture

- REQ-16: The system shall expose task management and solve operations via a
  local HTTP API served by the Python backend.
- REQ-17: The system shall use a plain HTML/CSS/JavaScript frontend, with no
  frontend framework, to call the HTTP API and render the calendar.

## Persistence

- REQ-6-DESIGN: The task list shall be persisted to a local file (implements
  REQ-6 in requirements.md).
