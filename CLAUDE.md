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

# Run tests across all supported Python versions (3.10, 3.11, 3.12)
make test

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

`src/pyibisami/` is organized into four subpackages:

### `ami/` — AMI DLL interaction layer
- **`model.py`**: Core ctypes wrappers.
  - `AMIModelInitializer`: holds all data needed to call `AMI_Init()` — channel response, timing, AMI params string. `channel_response` is set via property setter; `bit_time` and `sample_interval` must be `c_double` instances passed as keyword args.
  - `AMIModel`: loads a DLL/SO, binds `AMI_Init`/`AMI_GetWave`/`AMI_Close`, calls them. `__del__` calls `AMI_Close()` automatically. `initialize(AMIModelInitializer)` → `initOut` (impulse response), `ami_params_out`. `getWave(input_wave, bits_per_call)` → `(wave_out, clocks, params_list)`.
- **`parser.py`**: Parsec-based parser for `.ami` S-expression files. Exports `ignore`, `root`, and `AMIParamConfigurator`. `AMIParamConfigurator.get_init()` is the standard way to build an `AMIModelInitializer` from a parsed `.ami` file.
- **`parameter.py`**: `AMIParameter` dataclass representing one leaf parameter with type/range/usage/value metadata.
- **`config.py`**: `ami-config` CLI entry point; reads a Python model-config file and renders `.ami`/`.ibs` via EmPy templates.

### `ibis/` — IBIS file parsing layer
- **`parser.py`**: Parsec-based parser for `.ibs` files. Entry point: `parse_ibis_file(content: str) → (status_str, ibis_dict)`. Parsers are `@generate`-decorated generator functions. The `ignore` combinator (whitespace + `|` comments) is called at the end of `rest_line`; `word(p)` = `ignore >> p`. The `[Algorithmic Model]` block parser (`algo_model`) returns `{"executables": [...], "test_configs": {...}}`.
- **`model.py`**: `Component` and `Model` (both `HasTraits`). `Model` unpacks the `algo_model` dict; exposes `.test_configs: dict` and `.executables: list` properties alongside the existing exec-split properties (`_exec64Lins`, etc.).
- **`file.py`**: `IBISModel(HasTraits)` — high-level object that holds the full parsed IBIS file, including all `Component` and `Model` instances.

### `testing/` — Model test runners
- **`ami_test_config.py`**: IBIS 8.0 §10.11 runner. `run_ami_test_config(ibis_file_dir, model, config_name)` loads the files named in an `[AMI Test Configuration]` block, calls `AMI_Init()` (and `AMI_GetWave()` for `Time_domain`), and compares against golden data. Returns `AmiTestConfigResult`. `run_all_ami_test_configs()` runs every config in a model. Also exposes the `check-ami` CLI entry point.
- **`test_models.py`**: `test-model` CLI entry point; runs the notebook-based testing pipeline.
- **`ami_tests.py` / `ami_tests_helpers.py`**: older EmPy-template-based test infrastructure (used by `run-tests` CLI).
- **`test_defs.py`**: shared test-definition helpers consumed by both the old and new test runners.

### `tools/` — CLI wrappers
- **`run_notebook.py`**: `run-notebook` CLI; drives `papermill` on `IBIS_AMI_Tester.ipynb`.
- **`run_tests.py`**: `run-tests` CLI; old EmPy-based XML test runner.

## Key patterns

**Parsec parsers**: use `@generate` + `yield`. The `ignore` combinator is always safe to call (matches zero or more whitespace/comment tokens). `word(p) = ignore >> p`. Keyword-keyed blocks use `keyword("name") >> parser`.

**AMIModelInitializer construction**: always pass `bit_time=c_double(...)` and `sample_interval=c_double(...)` as keyword args, not positional. Set `channel_response` via the property setter after construction.

**DLL path resolution**: `ibis_file_dir / dll_name`. If `dll_name` is an absolute path string (e.g. from a test mock), Python's pathlib resolves it to the absolute path regardless of `ibis_file_dir`.

**Test DLLs**: pre-compiled example model binaries live in `tests/examples/`. Tests that require them are marked with a `needs_dll` skip marker when the binary is absent. The platform-specific name follows `example_tx_x86_amd64{_osx}.so` / `.dll` convention.

**`HasTraits` models**: `Component` and `Model` (and `IBISModel`) use Enthought Traits for attribute validation. Do not assign arbitrary attributes; use the declared `Trait`/`Property` descriptors.
