# AGENTS

## Build / Lint
* **Build** – Not required. The project is pure Python.
* **Lint** – `ruff check .`
* **Format** – `ruff format .`

## Test
* All tests: `pytest`
* Single file: `pytest tests/test_<file>.py`
* Single test: `pytest tests/test_<file>.py::TestClass::test_method`

## Code style
* Imports: alphabetical, one per line, `isort` compatible.
* Formatting: PEP‑8, 4‑space indent, newline at EOF.
* Types: fully typed with `typing`/`mypy`.
* Naming: snake_case functions, CamelCase classes.
* Errors: raise descriptive exceptions, avoid silent failures.

## Additional rules
* No cursor rules bundled.
* No copilot rules bundled.

---
Ensure consistency and run `ruff` before committing.