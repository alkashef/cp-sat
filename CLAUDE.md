# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

A Python project demonstrating Google OR-Tools' **CP-SAT** constraint solver on an
example problem. Python backend, with a plain HTML/CSS/JS front end (no framework).

## Directory Structure

- `config/` — `.env` holds **all** configuration variables. No config values should
  be hardcoded elsewhere in the code.
- `docs/` — requirements, design, and plan documents for the project.
- `src/` — application source code: the Python backend and the CP-SAT model, plus
  the HTML/CSS/JS UI.
- `scripts/` — standalone utility scripts for repo maintenance/tooling. These are
  not part of the application's runtime program flow.

## Code Style Rules

- **Readability first.** Prefer clear, direct code over clever code.
- **No tests.** Do not add a test suite or test files.
- **No logging.** Do not add logging statements or a logging setup.
- **No exception handling.** Do not wrap code in try/except; let errors surface
  naturally.
- **Keep it simple.** No speculative abstractions, config knobs, or flexibility for
  hypothetical future needs. Solve exactly what's asked.

## Code Smells to Avoid

- **Duplication** — extract shared logic instead of copy-pasting; reuse existing
  functions/modules rather than rewriting.
- **Large classes** — keep classes small and single-purpose.
- **Long methods** — keep functions short and focused on one task.

## Dependencies

All Python dependencies are declared in `requirements.txt`. Whenever code changes
introduce, drop, or change the use of a package, update `requirements.txt` in the
same change — don't let it drift from what the code actually imports.

## Configuration

All configurable values (paths, solver parameters, ports, etc.) live in
`config/.env`. Nothing else in the codebase should hold configuration values.

## Documentation

- Keep `README.md` and the docs in `docs/` (requirements, design, plan) up to date
  as the project evolves — update them alongside code changes, not as an
  afterthought.

## Working With Claude Code in This Repo

- **Do not commit.** Never run `git commit` (or push) in this repo unless the user
  explicitly asks in that turn.
- **Model selection.** Let Claude Code pick the appropriate model/agent for each
  task automatically rather than forcing a specific one.

## Tech Stack

- Backend: Python
- Solver: Google OR-Tools, CP-SAT
- Frontend: HTML, CSS, JavaScript (no framework)
