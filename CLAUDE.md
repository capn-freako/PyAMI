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

`src/pyibisami/` is organized into these subpackages. The core (`ami/`, `ibis/`, `testing/`, `util/ami.py`, `util/misc.py`, `common.py`, `events.py`, `cli_logging.py`) needs only the core dependencies; `gui/` and `report/` need optional extras.

### `ami/` — AMI DLL interaction layer
- **`model.py`**: Core ctypes wrappers.
  - `AMIModelInitializer`: holds all data needed to call `AMI_Init()` — channel response, timing, AMI params string. `channel_response` is set via property setter; `bit_time` and `sample_interval` must be `c_double` instances passed as keyword args.
  - `AMIModel`: loads a DLL/SO, binds `AMI_Init`/`AMI_GetWave`/`AMI_Close`, calls them. `__del__` calls `AMI_Close()` automatically. `initialize(AMIModelInitializer)` → `initOut` (impulse response), `ami_params_out`. `getWave(input_wave, bits_per_call)` → `(wave_out, clocks, params_list)`. Debug plots import matplotlib lazily (`_debug_plot()`).
- **`parser.py`**: Parsec-based parser for `.ami` S-expression files. Exports `ignore`, `root`, `ami_parse` and `parse_ami_file_contents()` (→ errors, warnings, root name, description, Reserved and Model_Specific dicts), plus the parameter-tree type aliases (`ParamName`, `ParamValues`, `AmiLeaf`, …). `Default` is read with the parameter's `Type` and is the initial Range/List value. Problems that don't stop a parameter loading (`AMIParameter.msg`) are returned as warnings (the configurator's `ami_parsing_errors`). A parameter that can't be built is skipped with a `"Skipped parameter <path>: …"` warning; the rest of the file loads. All Formats parse.
- **`configurator.py`**: `AMIParamConfigurator`, built from a `.ami` file's contents. `AMIParamConfigurator.get_init()` is the standard way to build an `AMIModelInitializer` from a parsed `.ami` file. Plain class: current values live in `_values`, keyed by `.ami` path tuple (`ParamPath`, rooted at `"Model_Specific"`), one per settable leaf (`AMIParameter.is_settable`: Usage In/InOut, not a `FIXED_FORMATS` one), starting at `initial_value`; `set_param_val()` checks with `AMIParameter.validate()` (raises `events.InvalidValueError`) and emits `values_changed(path, old, new)`; `sim_corner` is a validated property (`sim_corner_changed`). Also `iter_settable()`, `current_values()`, `apply_values()` (tuple or `/`-joined keys; presets), `reset_to_defaults()`; `open_gui()` imports `gui.dialogs` lazily; `get_init()` without `ami_params` sends `input_ami_params`. `ami_param_defs`/`model_specific_dict` are the parsed definitions (`pvalue` keeps the file's value). Parameter names stay as written in the `.ami` file everywhere the model sees them (`input_ami_params`, `fetch_param_val()`/`set_param_val()` paths, tuner `branch_names`); only display names go through `display_name_part()`/`display_name()` (tap numbers `-1`/`0`/`1` → `pre1`/`post0`/`post1`). Increment/Steps offer only their legal values (`pvalues`, also `choices`); Corner, Table, Gaussian, Dual-Dirac and DjRj (`parameter.FIXED_FORMATS`) aren't settable; a Corner's value follows `AMIParamConfigurator.sim_corner` (`typ`/`min`/`max`), and a Table is sent row-flattened. `model.ami_params_string()` builds the `AMI_parameters_in` string.
- **`parameter.py`**: `AMIParameter` (one leaf parameter's type/range/usage/value metadata; `validate()`, `is_settable`, `choices`, `initial_value`) and `AmiParamTuner` (a dataclass; `mk_tap_tuners()` rows).
- **`config.py`**: `ami-config` CLI entry point; reads a Python model-config file and renders `.ami`/`.ibs`/`.cpp` via EmPy templates (template errors raise; partial output is removed).

### `ibis/` — IBIS file parsing layer
- **`parser.py`**: Parsec-based parser for `.ibs` files. Entry point: `parse_ibis_file(content: str) → (status_str, ibis_dict)`. Parsers are `@generate`-decorated generator functions. The `ignore` combinator (whitespace + `|` comments) is called at the end of `rest_line`; `word(p)` = `ignore >> p`. The `[Algorithmic Model]` block parser (`algo_model`) returns `{"executables": [...], "test_configs": {...}}`; `Executable` lines accept any OS field (lower-cased; `linux…`/`windows…` become `"linux"`/`"windows"`), and `Model` keeps the others in `executables` but never selects them. Pin, signal and model names are any non-blank token (`token`; e.g. `TX+`, `DQ<0>`), and `typminmax` accepts `NA` for either of min/max (→ typ; `typ NA NA` stays `[typ]`); `_preprocess()` applies `[Comment Char]` (cutting such comments before parsing; known limit: after a change the grammar still reads `|` as a comment) and drops text after the first `[End]` (with a warning). `rest_line` treats a `[` after column 1 as text and drops a trailing `|` comment; `name=value` needs no spaces; the `[Pin]` header words are matched in any case, and a per-pin R/L/C column may be `NA` (left out: the `[Package]` default). A parse failure's status gives a 1-based `line L, column C`, and `IBISModel` raises it (`Couldn't parse IBIS file …`). All Model_types parse, including the true differential `*_diff` ones (their `[External Model]` block is skipped, as is any other unparsed `[Model]` keyword). `[Rising Waveform]`/`[Falling Waveform]` parse (`vt_waveform`: fixture subparameters, then `(t, typ, min|None, max|None)` rows); `model()` collects every one into `sub_dict["waveforms"]` (a `dict()` would keep only the last); `[Composite Current]` is skipped. On success the status stays `"Success!"`; spec-rule violations that don't stop loading (each model's `Model.spec_warnings`, plus `[Algorithmic Model]` outside a `[Model]`) are logged at `WARNING` and returned as `ibis_dict["warnings"]`, which `IBISModel.ibis_parsing_errors` appends. Parsing details are logged at `DEBUG` (no `debug` flag).
- **`iv.py`**: GUI-agnostic I-V data: `IVCurve` (one table; `impedance()` (`ValueError` if the point is off the table; `Model` then treats a clamp as off and gives `zout = None`), `ground_referenced()`), `IVData` (a model's curves; `vdd`/`vdd_min`/`vdd_max` from `[Voltage Range]`, `supply(corner)`; `series()` gives toolkit-neutral traces against pin voltage: Vcc-relative tables (`[Pullup]`/`[POWER Clamp]`) converted with each corner's own supply, currents kept in IBIS sense (positive into the pin), all-`NA` min/max columns left out: `IVCurve.na_min`/`na_max`).
- **`vt.py`**: GUI-agnostic V-T data: `Fixture`, `VTWaveform` (`at(corner)` → `(t, v, v_fixture)` without `NA` rows; `series()`), in Plan 3's shape.
- **`analog.py`**: `Pin` record (`pin, signal, model, r_pin, l_pin, c_pin`; `key` = `pin(signal)`), Plan 3's fields.
- **`model.py`**: `Component` (`name`, `manufacturer`, `package`, `pins` dict, `pin_table`; `Component(subDict, name=...)`) and `Model` (plain classes; keyword values are read-only properties: `name`, `model_type`, `c_comp`, `vref`, ...; `waveforms`/`rising`/`falling`; bad waveform tables are skipped into `spec_warnings`). `Model` unpacks the `algo_model` dict; exposes `.test_configs: dict`, `.ami_executables: list[AmiExecutable]` (`(direction, os, bits, dll, ami)`; direction `"tx"`/`"rx"`/`None` for `Executable_Tx`/`_Rx`/plain) and `.executables` (derived, old `((os, bits), [dll, ami])` shape, for `Executable_index`), `.ami_files` (direction-blind `{"64-bit": {"lin": [dll, ami], "win": …}, …}`), `.get_ami_files(is_tx=None)` (the direction-aware `(dll, ami)` for the running platform; `ValueError` for `None` on an `I/O` model with both directions), `.dll_file`/`.ami_file` (direction-blind: first `Executable` for the running platform, `""` if none; `IBISModel.dll_file`/`.ami_file` return the selected model's), `.is_io`, and `.iv_data: IVData`. `TX_MODEL_TYPES`/`RX_MODEL_TYPES` live here (re-exported by `file.py`). `.zout`/`.slew`/`.zin` are `Optional[float]` and never raise: `None` where the Model_type has no driver/receiver side, the data is missing, or the type isn't supported yet (`*_ECL`, `*_diff`); the type groups are the `_PUSH_PULL_TYPES`/`_PULLDOWN_ONLY_TYPES`/`_PULLUP_ONLY_TYPES`/`_RECEIVER_TYPES` constants. `Model(subDict, name=...)` takes the `[Model]` name for log messages.
- **`file.py`**: `IBISModel` — plain class holding the full parsed IBIS file (`from_text()` builds one from a string). Selection is named after IBIS keywords: `component_name`/`pin_name`/`model_name` (validated setters; a new component selects its first offered pin, a new pin its first model), `select(component=, pin=, model=)` (one `selection_changed`), over `component_choices`/`pin_choices`/`model_choices`; `component`, `pin` (a `Pin`) and `model` are the selected objects. `_commit()` stores a checked selection and announces a new model (`_announce_model()`), `choices_changed` (any change of the choice lists, e.g. a `model_types` change that keeps the selection) and `selection_changed`. `components`/`component_names`/`model_names`/`model_selectors` replace `model_dict`. The keyword-only `model_types` (also a property; `None` = all, any case, e.g. `TX_MODEL_TYPES`) limits them to pins/models of those Model_types (a later change that leaves nothing is undone, keeping the selection, and fires `alert`). `ibis_dir`, `resolve_file(name)` (→ `ibis_dir / name`, `None` if empty) and `dll_path`/`ami_path` (the selected model's files, resolved) turn file names from the `.ibs` into paths. Reports through its module logger; user-facing notices are also fired via its `alert` `Signal`, the latest kept in `last_alert` (the first model's fires while loading, before anyone can connect) (it never opens dialogs itself; `open_gui()` imports `gui.dialogs` lazily).

### `gui/` — optional Qt (PySide6) widgets (`gui` extra: pyside6, matplotlib)
- **`__init__.py`**: import guard (`ImportError` with the install hint); exports the widgets.
- **`bridge.py`**: `SignalBridge`: core `Signal` callbacks (any thread) → queued Qt signal → ~30 Hz single-shot timer → `changed` on the GUI thread. Widgets refresh by re-reading the core object; they never touch widgets from core callbacks.
- **`ami_config.py`**: `AmiParamEditor(cfg)` (tree; per-Format editors; read-only rows for unsettable params; corner combo; reset; `save_preset()`/`load_preset()` JSON).
- **`ibis.py`**: `IbisSelector` (type-to-filter combos, match anywhere/any case; `selectionChanged`), `ModelInfo` (selected pin's `[Pin]` row + model values; `AMI:` row is a check/cross/warning for this platform's executable, every `Executable` line in its tool tip), `IbisBrowser` (selector over info on the left; one tab per plot: Pulldown, Pullup, GND Clamp, POWER Clamp, Rising, Falling; `show_tab()` hides empty ones; `visible_tabs()`), `show_alerts(ibis, parent)` (queued pop-ups of later alerts; one relay per model, a repeat call only changes the parent).
- **`plots.py`**: `IVPlot(keyword=pulldown|pullup|gnd_clamp|power_clamp)` (`IVCurve.at()`, `NA` cells left out), `VTPlot(direction=rising|falling)`: one matplotlib axes each, corner check boxes, `has_data`; I-V plots shade 0 V..typ Vcc and draw each shown corner's Vcc line in its style (labels start with `_`, so legend/`shown_labels` skip them); hover shows (x, y) in the toolbar.
- **`dialogs.py`**: `ensure_app()`, `edit_ami_params()`, `select_ibis_model()` (behind `open_gui()`; each dialog is `deleteLater()`'d after `exec()`, so a parent doesn't keep it listening).
- **`app.py`**: `pyibisami-gui` CLI/`MainWindow` (opens `.ibs`/`.ami`; AMI tab follows the selected model, configurators cached per path; Tools menu's Edit IBIS/AMI file actions call `open_in_text_editor()`; AMI tab hidden when the model has no executable for this platform, rebuilt only when its `.ami` changes, the OS editor: Windows "edit" verb else Notepad, macOS `open -t`, else `xdg-open`).

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
- **`events.py`**: `InvalidValueError(ValueError)` and `Signal` (thread-safe `connect()`→disconnect fn, `emit()`; callback errors logged).
- **`util/ami.py`**: extracts CDR/DFE adaptation from `AMI_GetWave()` output parameters (skips, with a warning, if unparsable).

## Key patterns

**Headless core / optional extras**: `gui` (pyside6, matplotlib), `report` (matplotlib, reportlab, scipy), `notebook` (jupyter, papermill, …, plus `report`), `all`. Never import an extra's packages at module level in a core module; put such code in `gui/` or `report/` (each guarded on import) and import it lazily. `tests/test_core_only.py` enforces this (it blocks the optional packages); `make test-core` runs it in a core-only install. traits/traitsui/chaco/enable/pyface were removed in 11.0 and stay blocked there as regressions.

**Logging & CLI output**: the library only logs (module loggers under `pyibisami`; it never configures logging or prints). CLIs call `setup_cli_logging(debug)` and accept `-d/--debug`; a command's results go to stdout via `click.echo()`, progress/diagnostics go through logging to stderr; failures raise `click.ClickException` (exit 1).

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
