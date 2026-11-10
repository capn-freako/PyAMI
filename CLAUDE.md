# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands, except make commands, must be prefixed with `uv run`. The project uses `uv` for environment and dependency management.

```bash
# Run all tests (current Python only)
uv run pytest tests/

# Run a single test file
uv run pytest tests/ami/test_model.py

# Run a single test by name
uv run pytest tests/ami/test_model.py::TestClass::test_name -k "test_name"

# Run tests across all supported Python versions (3.11 through 3.14)
make test

# Run the core-only (no extras) import tests, in an isolated core-only install
make test-core

# Lint (ruff + flake8)
make lint

# Type check (mypy)
make type-check

# Format (isort + black, line-length 119)
make format

# Build package
make build

# Build docs (output: docs/build/index.html)
make docs
```

Hooks: on every file change, `make lint && make type-check` run automatically. Tests run at session end.

## Architecture

The code and its docstrings are the API reference; this section only maps the packages and records what the code
doesn't make obvious. Don't add per-feature or per-API detail here.

`src/pyibisami/`:

- `ami/`: AMI side. `parser.py` (`.ami` S-expressions), `parameter.py` (`AMIParameter`, `AmiParamTuner`),
  `configurator.py` (`AMIParamConfigurator`: the user's parameter values; `get_init()` builds the
  `AMIModelInitializer`), `model.py` (ctypes wrappers for `AMI_Init`/`AMI_GetWave`/`AMI_Close`), `config.py`
  (`ami-config` CLI).
- `ibis/`: IBIS side. `parser.py` (`.ibs`), `model.py` (`Component`, `Model`), `file.py` (`IBISModel`: a parsed file
  plus a component/pin/model selection), `iv.py` / `vt.py` (I-V and V-T data), `analog.py` (`Pin`).
- `testing/`: `[AMI Test Configuration]` runner (`check-ami`); `test_defs.py` is imported by users' sweep files, so
  don't move it.
- `gui/` (`gui` extra): Qt widgets, dialogs behind `open_gui()`, and the `pyibisami-gui` app.
- `report/` (`report` extra): `test-model` PDF report. `tools/`: `run-notebook`, `run-tests` CLIs.
- `events.py` (`Signal`, `InvalidValueError`), `cli_logging.py`, `common.py`, `util/`.

Core = everything except `gui/` and `report/` (and the extras-backed `tools/`).

### Invariants and gotchas

- `.ami` parameter names are what the model sees (`input_ami_params`, `fetch_param_val()`/`set_param_val()` paths,
  tuner `branch_names`); display names (`display_name()`: taps `-1`/`0`/`1` → `pre1`/`post0`/`post1`) are for
  showing only.
- `NA` means "use typ" in `typminmax` (e.g. `[Voltage Range]`), but "no data" in I-V and V-T table cells; those are
  kept per cell and left out of plots (I-V calculations use values interpolated within the column).
- A bad `.ami` parameter is skipped with a `Skipped parameter …` warning; the rest of the file still loads. IBIS spec
  violations that don't stop loading go to `Model.spec_warnings` / `IBISModel.ibis_parsing_errors`.
- `Signal` callbacks run on the emitting thread (e.g. an optimizer). Widgets never act in a core callback: they
  listen through `gui.bridge.SignalBridge` and re-read the core object on the GUI thread.
- Known spec gap: `[Voltage Range]` is required (the `[… Reference]` keywords aren't read).

## Key patterns

**Headless core / optional extras**: `gui` (pyside6, matplotlib), `report` (matplotlib, reportlab, scipy), `notebook` (jupyter, papermill, …, plus `report`), `all`. Never import an extra's packages at module level in a core module; put such code in `gui/` or `report/` (each guarded on import) and import it lazily. `tests/test_core_only.py` enforces this (it blocks the optional packages); `make test-core` runs it in a core-only install. traits/traitsui/chaco/enable/pyface were removed in 11.0 and stay blocked there as regressions.

**Logging & CLI output**: the library only logs (module loggers under `pyibisami`; it never configures logging or prints). CLIs call `setup_cli_logging(debug)` and accept `-d/--debug`; a command's results go to stdout via `click.echo()`, progress/diagnostics go through logging to stderr; failures raise `click.ClickException` (exit 1).

**Warning/error text**: short and useful to the user: what's wrong and what it affects. No spec citations (section, table, page) in messages; put those in a code comment next to the check.

**Parsec parsers**: use `@generate` + `yield`. The `ignore` combinator is always safe to call (matches zero or more whitespace/comment tokens). `word(p) = ignore >> p`. Keyword-keyed blocks use `keyword("name") >> parser`.

**AMIModelInitializer construction**: always pass `bit_time=c_double(...)` and `sample_interval=c_double(...)` as keyword args, not positional. Set `channel_response` via the property setter after construction.

**DLL path resolution**: `ibis_file_dir / dll_name`. If `dll_name` is an absolute path string (e.g. from a test mock), Python's pathlib resolves it to the absolute path regardless of `ibis_file_dir`.

**Test DLLs**: pre-compiled example model binaries live in `tests/examples/`. Tests that require them are marked with a `needs_dll` skip marker when the binary is absent. The platform-specific name follows `example_tx_x86_amd64{_osx}.so` / `.dll` convention.

**Plain models, no Traits**: state lives in plain classes; setters validate and raise `InvalidValueError`; change notification is `events.Signal`. GUI tests (`tests/gui/`) use pytest-qt with `QT_QPA_PLATFORM=offscreen`.

## Compact Instructions

When compacting, always preserve: the list of modified files, current test status, and any unresolved issues.

## Git workflow

- Never commit to master directly
- Commit messages: conventional commits format
