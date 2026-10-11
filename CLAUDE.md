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

# Run tests across all supported Python versions (3.10, 3.11, 3.12, 3.13)
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

`src/pyibisami/` is organized into these subpackages. The core (`ami/`, `ibis/`, `testing/`, `util/ami.py`, `util/misc.py`, `common.py`, `cli_logging.py`) needs only the core dependencies; `gui/` and `report/` need optional extras.

### `ami/` — AMI DLL interaction layer
- **`model.py`**: Core ctypes wrappers.
  - `AMIModelInitializer`: holds all data needed to call `AMI_Init()` — channel response, timing, AMI params string. `channel_response` is set via property setter; `bit_time` and `sample_interval` must be `c_double` instances passed as keyword args.
  - `AMIModel`: loads a DLL/SO, binds `AMI_Init`/`AMI_GetWave`/`AMI_Close`, calls them. `__del__` calls `AMI_Close()` automatically. `initialize(AMIModelInitializer)` → `initOut` (impulse response), `ami_params_out`. `getWave(input_wave, bits_per_call)` → `(wave_out, clocks, params_list)`. Debug plots import matplotlib lazily (`_debug_plot()`).
- **`parser.py`**: Parsec-based parser for `.ami` S-expression files. Exports `ignore`, `root`, and `AMIParamConfigurator`. `AMIParamConfigurator.get_init()` is the standard way to build an `AMIModelInitializer` from a parsed `.ami` file. Its parameter values live on Traits built by `make_param_traits()` (`traits` only, no TraitsUI); its view comes from `gui.ami_config`, imported lazily.
- **`parameter.py`**: `AMIParameter` dataclass representing one leaf parameter with type/range/usage/value metadata.
- **`config.py`**: `ami-config` CLI entry point; reads a Python model-config file and renders `.ami`/`.ibs`/`.cpp` via EmPy templates (template errors raise; partial output is removed).

### `ibis/` — IBIS file parsing layer
- **`parser.py`**: Parsec-based parser for `.ibs` files. Entry point: `parse_ibis_file(content: str) → (status_str, ibis_dict)`. Parsers are `@generate`-decorated generator functions. The `ignore` combinator (whitespace + `|` comments) is called at the end of `rest_line`; `word(p)` = `ignore >> p`. The `[Algorithmic Model]` block parser (`algo_model`) returns `{"executables": [...], "test_configs": {...}}`. Parsing details are logged at `DEBUG` (no `debug` flag).
- **`iv.py`**: GUI-agnostic I-V data: `IVCurve` (one table; `impedance()`, `ground_referenced()`), `IVData` (a model's curves; `series()` gives toolkit-neutral plot traces).
- **`model.py`**: `Component` and `Model` (both `HasTraits`, no TraitsUI). `Model` unpacks the `algo_model` dict; exposes `.test_configs: dict`, `.ami_executables: list[AmiExecutable]` (`(direction, os, bits, dll, ami)`; direction `"tx"`/`"rx"`/`None` for `Executable_Tx`/`_Rx`/plain) and `.executables` (derived, old `((os, bits), [dll, ami])` shape, for `Executable_index`) alongside the direction-blind exec-split properties (`_exec64Lins`, etc.), `.get_ami_files(is_tx=None)` (the direction-aware `(dll, ami)` for the running platform; `ValueError` for `None` on an `I/O` model with both directions), `.dll_file`/`.ami_file` (direction-blind: first `Executable` for the running platform, `""` if none; `IBISModel.dll_file`/`.ami_file` return the selected model's), `.is_io`, and `.iv_data: IVData`. `TX_MODEL_TYPES`/`RX_MODEL_TYPES` live here (re-exported by `file.py`). `Model.plot_iv` is a lazy, cached Traits `Property` built by `gui.ibis` (needs the `gui` extra).
- **`file.py`**: `IBISModel(HasTraits)` — high-level object that holds the full parsed IBIS file, including all `Component` and `Model` instances. `ibis_dir`, `resolve_file(name)` (→ `ibis_dir / name`, `None` if empty) and `dll_path`/`ami_path` (the selected model's files, resolved) turn file names from the `.ibs` into paths. Reports through its module logger; user-facing notices are also fired via its `alert = Event(Str)` trait (it never opens dialogs itself).

### `gui/` — optional Traits/UI views (`gui` extra)
- **`__init__.py`**: import guard; raises `ImportError` with the install hint when chaco/enable/traitsui are missing.
- **`ami_config.py`**: `AMIParamConfigurator` view (`make_view()`); item names must match `make_param_traits()`'s trait names.
- **`ibis.py`**: `make_iv_plot(iv_data)` (Chaco), `Component`/`Model`/`IBISModel` views, `show_alerts(ibis)` (pops up `alert`s).

### `testing/` — model test definitions & runners (core)
- **`ami_test_config.py`**: IBIS 8.0 §10.11 runner. `run_ami_test_config(ibis_file_dir, model, config_name)` loads the files named in an `[AMI Test Configuration]` block, calls `AMI_Init()` (and `AMI_GetWave()` for `Time_domain`), and compares against golden data. Returns `AmiTestConfigResult`. `run_all_ami_test_configs()` runs every config in a model. Also exposes the `check-ami` CLI entry point.
- **`test_defs.py`**: shared test-definition helpers (user-generated sweep files import from here; don't move it).
- **`generic_test_sweep.py.em`**: default sweep file template (used by `report.ami_tests.SWEEP_TEMPLATE`).

### `report/` — PDF/plot reporting (`report` extra)
- **`__init__.py`**: import guard for matplotlib/reportlab.
- **`test_models.py`**: `test-model` CLI entry point; produces the PDF report.
- **`ami_tests.py` / `ami_tests_helpers.py` / `ibis_file_tests.py`**: report content; **`plot.py`** (matplotlib), **`pdf.py`** (ReportLab helpers).

### `tools/` — CLI wrappers
- **`run_notebook.py`**: `run-notebook` CLI; drives `papermill` on `IBIS_AMI_Tester.ipynb` (`notebook` extra); returns `NotebookRun`.
- **`run_tests.py`**: `run-tests` CLI; old EmPy-based XML test runner (`report` extra); returns the XML path.

### Other modules
- **`cli_logging.py`**: `setup_cli_logging(debug)`, called first by every CLI `main()`.
- **`util/ami.py`**: extracts CDR/DFE adaptation from `AMI_GetWave()` output parameters (skips, with a warning, if unparsable).

## Key patterns

**Headless core / optional extras**: `gui` (chaco, enable, traitsui), `report` (matplotlib, reportlab), `notebook` (jupyter, papermill, …, plus `report`), `all`. Never import an extra's packages at module level in a core module; put such code in `gui/` or `report/` (each guarded on import) and import it lazily. `tests/test_core_only.py` enforces this (it blocks the optional packages); `make test-core` runs it in a core-only install. `traits` itself stays a core dependency.

**Logging & CLI output**: the library only logs (module loggers under `pyibisami`; it never configures logging or prints). CLIs call `setup_cli_logging(debug)` and accept `-d/--debug`; a command's results go to stdout via `click.echo()`, progress/diagnostics go through logging to stderr; failures raise `click.ClickException` (exit 1).

**Parsec parsers**: use `@generate` + `yield`. The `ignore` combinator is always safe to call (matches zero or more whitespace/comment tokens). `word(p) = ignore >> p`. Keyword-keyed blocks use `keyword("name") >> parser`.

**AMIModelInitializer construction**: always pass `bit_time=c_double(...)` and `sample_interval=c_double(...)` as keyword args, not positional. Set `channel_response` via the property setter after construction.

**DLL path resolution**: `ibis_file_dir / dll_name`. If `dll_name` is an absolute path string (e.g. from a test mock), Python's pathlib resolves it to the absolute path regardless of `ibis_file_dir`.

**Test DLLs**: pre-compiled example model binaries live in `tests/examples/`. Tests that require them are marked with a `needs_dll` skip marker when the binary is absent. The platform-specific name follows `example_tx_x86_amd64{_osx}.so` / `.dll` convention.

**`HasTraits` models**: `Component` and `Model` (and `IBISModel`) use Enthought Traits for attribute validation. Do not assign arbitrary attributes; use the declared `Trait`/`Property` descriptors.

## Compact Instructions

When compacting, always preserve: the list of modified files, current test status, and any unresolved issues.

## Git workflow

- Never commit to master directly
- Commit messages: conventional commits format
