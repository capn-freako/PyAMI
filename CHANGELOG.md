# Changelog

Notable changes to *PyIBIS-AMI* (`pyibis-ami` on PyPI).
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Releases before 10.0.0 are summarized from their
[GitHub release notes](https://github.com/capn-freako/PyAMI/releases), which have the full details.

For help porting code from v9.x, see
[Upgrading from v9.x](https://pyibis-ami.readthedocs.io/en/latest/install.html#upgrading-from-v9-x).

## [10.0.0] - Unreleased

### Changed (breaking)

- The GUI, report and notebook dependencies are optional extras now: `gui` (chaco, enable, traitsui),
  `report` (matplotlib, reportlab, scipy), `notebook` (jupyter, papermill, ..., plus `report`) and `all`.
  The core (AMI/IBIS parsing, AMI DLL calls, `ami-config`, `check-ami`) needs none of them.
  The `gui` extra installs no Qt binding.
- SciPy is now in the `report` extra. `common.deconv_same()` uses NumPy only;
  `testing.test_defs.lossy_channel()`/`reflective_channel()` need SciPy.
- The PDF/plot reporting modules moved to the new `pyibisami.report` package
  (`testing.test_models`, `testing.ami_tests`, `testing.ami_tests_helpers`, `testing.ibis_file_tests`,
  `util.plot`, `util.reportlab`).
- `make_gui()`/`make_gui_items()` moved to `pyibisami.gui.ami_config`, and no longer return `Trait`s.
  `make_param_traits()` builds those.
- `AMIParamConfigurator`, `make_param_traits()` and `trait_name_part()` moved from `pyibisami.ami.parser`
  to the new `pyibisami.ami.configurator`. The old imports still work.
- Tap parameters (`-1`, `0`, `1`, ...) get trait names `pre1`, `post0`, `post1`, ...
  The names sent to the model, and the `fetch_param_val()`/`set_param_val()` paths, stay as written in the `.ami` file.
- *PyIBIS-AMI* only logs now, through loggers under `pyibisami`; it never prints or opens dialogs itself.
  `IBISModel.log()`, `IBISModel.log_txt` and the `debug` and `gui` arguments of `IBISModel` and
  `parse_ibis_file()` were removed. `IBISModel` sends its notices through its new `alert` event;
  `pyibisami.gui.ibis.show_alerts()` shows them as dialogs. CLIs take `-d/--debug`.
- `IBISModel` raises `ValueError` (`Couldn't parse IBIS file ...`, with the line and column) when the file
  doesn't parse, instead of logging a warning.
- `IBISModel.dll_file`/`ami_file` come from the selected model, not the file.
  The private `Model._exec32Wins`, etc., were removed; `Model.ami_files` and `Model.executables` remain.
- `Model.zout`/`slew`/`zin` are `None` (and the model has no such trait) where its `Model_type` or data
  gives no value.
- A Boolean `List` with no `Default` starts at its first value, not `False`.
- Viewer titles no longer mention *PyBERT*; the IBIS model selector's view `id` is now
  `pyibisami_ibis_model_selector`.

### Added

- `IBISModel(..., model_types=...)` offers only the pins and models of the given `Model_type`s
  (e.g. `TX_MODEL_TYPES`, `RX_MODEL_TYPES`); it can be changed later through the `model_types` trait.
- Direction-aware AMI executables for `I/O` models: `Model.get_ami_files(is_tx)`, `Model.ami_executables`
  (`AmiExecutable` tuples, with `Executable_Tx`/`Executable_Rx` direction) and `Model.is_io`.
- `IBISModel.ibis_dir`, `resolve_file()`, `dll_path` and `ami_path`, for the paths of the files an `.ibs` names.
- `IBISModel.comps`, the components offered for selection (those with a usable pin).
- `Model.iv_data` (`pyibisami.ibis.iv.IVData`/`IVCurve`): I-V tables without any GUI dependency.
  `Model.plot_iv` is built on first access and needs the `gui` extra.
- IBIS spec-rule warnings (`Model.spec_warnings`, the parsed file's `"warnings"`, and `ibis_parsing_errors`):
  `[Algorithmic Model]` use for each `Model_type`, `Executable` vs. `Executable_Tx`/`_Rx`, `.ami` extensions,
  missing `Vinl`/`Vinh`.
- Every `.ami` `Format` parses: `Increment` and `Steps` (offered as their legal values), `Corner` (follows the new
  `AMIParamConfigurator.sim_corner`), `Table`, `Gaussian`, `Dual-Dirac` and `DjRj` (sent as written).
  Usage `Dep` is accepted.
- `model.ami_params_string()` builds the `AMI_parameters_in` string.
- The AMI_Version 7.2 and 8.0 reserved parameter names
  (`Modulation_Levels`, `PAM_Offsets`, `PAM_Thresholds`, `Tx_Impulse_Input`, `Adaptation_Valid`,
  `Rx_Port_Order`, `Tx_Port_Order`).
- IBIS parsing of:
  true differential `*_diff` `Model_type`s; any OS in `Executable` lines; pin, signal and model names with
  punctuation (e.g. `TX+`, `DQ<0>`); `NA` for either of min/max; `NA` in a pin's R/L/C columns;
  `[Comment Char]`; `name=value` without spaces; `[Pin]` header words in any case.

### Fixed

- `.ami` parameter names and `Default` values are sent to the model as written (`Default` is read with the
  parameter's `Type`). Empty groups aren't sent. Descriptions lose their quotes.
- A parameter that can't be built is skipped, with a warning; the rest of the `.ami` file loads.
  Subparameters named like tags (e.g. `Corner`) are kept.
- A `List` parameter's dropdown no longer offers its default value twice.
- `set_param_val()` validates through the parameter's trait; tap tuners read their values from the traits.
- `IBISModel.get_pins_qualified()` used a removed `is_tx` attribute; it now goes by the pin's models'
  `Model_type`s (any model of a `[Model Selector]`).
- A component change to a pin of the same name updates the models offered; `pin_` is no longer stale.
- `zout`/`slew`/`zin` are found for every `Model_type` the data supports (e.g. `3-state`, `Open_*`).
- A `Vmeas` outside an I-V table no longer fails the file; the first table row no longer wraps around.
- Trailing `|` comments are dropped from text values; text after `[End]` is ignored, with a warning;
  `CIRCUITCALL` pins are dropped.
- `test-model` picks the executable by the interpreter's bitness and OS.
- `run-notebook` works on Python 3.10 and 3.11, and picks the `.ami` file for `--is_tx` on `I/O` models.
- The model viewers no longer crash on their `zout`/`slew`/`zin` and display values.

### Deprecated

- `ami-config` / `ami.config.ami_config()` now warn when used. Make your model configurator executable and
  have it call `ami.config.mk_model()` instead.

### Dependencies

- `click>=8.4.2,<9`, `traits>=7.1,<8` (were pinned); `reportlab==5.0.1`.

## [9.3.1] - 2026-08-17

### Added

- The source distribution includes a `requirements.txt` exported from `uv.lock`.

## [9.3.0] - 2026-08-15

### Added

- What *PyBERT* needs to tune IBIS-AMI model equalization: `AMIParamConfigurator.tunable_params` (#92).

### Fixed

- Hierarchical AMI parameter naming (#92).

## [9.2.0] - 2026-07-20

### Added

- Python 3.13 support (#91).

### Fixed

- The tap parser, and test sweep file naming (#89).

## [9.1.0] - 2026-06-18

### Added

- `check-ami` command: runs the IBIS 8.0 `[AMI Test Configuration]`s of an IBIS file and checks the results
  against their golden data (#85).

## [9.0.0] - 2026-05-25

### Changed (breaking)

- New model testing infrastructure, in plain Python, with PDF reports made with ReportLab: `test-model`.
  Parameter sweeps are `TestSweep` subclasses in Python modules (a `defaults_template.py` is generated).
- `ami.parser.parse_ami_file_contents()` returns separate lists of errors and warnings, and raises
  `RuntimeError` when the file doesn't parse.
- `ami.model.get_responses()` takes a maximum run length in place of `pad_bits` (it no longer overrides
  `Ignore_Bits`), returns a more specific type, and takes a `debug` flag.
- `IBISModel` no longer takes an `is_tx` argument.
- Stricter types for `ami.config.mk_model()`, `make_gui()` and `make_gui_items()`.

### Added

- Modules `testing`, `util.ami`, `util.misc`, `util.plot` and `util.reportlab`.
- `run-notebook` builds a default parameter sweep (#65).

### Fixed

- The `Clocks` array size, to prevent access violations (#78).

### Deprecated

- The `tools` modules; use `testing`.

## [8.1.0] - 2026-02-13

### Changed

- Better type specification of the recursive `AmiNode` type (#62).

## [8.0.0] - 2026-01-25

### Changed

- Development moved from pip and Tox to uv, still driven by `make` (#60).

### Fixed

- `(Format Corner ...)` AMI parameters (#58).

## [7.3.1] - 2025-12-24

### Changed (breaking)

- `AMIModel.ami_params_out` is a decoded `str`.

### Fixed

- The AMI parameter configuration dialog no longer grows wider than the screen (#56).
- Some IBIS and AMI parsing bugs.

## [7.2.7] - 2025-10-18

### Fixed

- Negative tap indices in AMI files.

## [7.2.5] - 2025-07-23

### Fixed

- Miscellaneous fixes made for *PyBERT* v9.1.2.

## [7.2.4] - 2025-07-12

### Fixed

- A crash when a String parameter's `Format` was left as `None`.

## [7.2.3] - 2025-05-01

### Fixed

- Passing String parameters to the model.

### Changed

- Assertions removed from the code base, except in notebooks (#52).

## [7.2.2] - 2025-04-06

### Fixed

- AMI model initialization no longer crashes when no `Info` parameters are given.

### Changed

- Build infrastructure improvements.

## [7.2.0] - 2025-03-18

### Changed (breaking)

- Python 3.9 support dropped; Python 3.10-3.12 supported.
- Wheel and sdist file names are lower case.

### Added

- Type annotations throughout.
- `Tap` parameter type.
- AMI reserved parameter names as a `dataclass`.
- Cleaner AMI parameter configurator GUIs, and more documentation.

### Fixed

- A crash on models with only one of `[POWER Clamp]` and `[GND Clamp]`.
- Like-named AMI parameters below the top level were conflated.

### Deprecated

- Non-executable model configurators; use executable ones.

## [6.2.2] - 2025-02-23

### Fixed

- `run-notebook` with models generated by *ibisami*.

## [6.2.1] - 2025-02-22

### Added

- `run-notebook` command: runs the IBIS-AMI model testing notebook on a model (#48).

## [6.2.0] - 2024-09-09

### Changed (breaking)

- `ami.model.get_responses()` returns only the impulse responses.

### Added

- Output parameters are captured from each `GetWave()` call.

### Fixed

- One extra clock-times slot, to prevent segmentation faults.
- CTLE step response shifted one UI right; `GetWave()` input gets a prequel, to remove step response noise.
- Fixes for macOS on Apple silicon; `IBIS_AMI_Checker` notebook finishing touches.

## [5.1.4] - 2024-04-23

### Fixed

- `FLOAT`/`TAP` parameters use C type `double`, not `float`.

## [5.1.3] - 2024-04-11

### Changed

- Model configurators (e.g. `rx.py`) are executable and drive model configuration, using the library.

## [5.1.2] - 2024-04-09

### Changed

- Updated to the current Enable/Chaco/Traits/UI; pip-installable.

## [5.1.1] - 2024-02-12

### Fixed

- Rx input termination in generated IBIS models.

## [4.1.1] - 2023-04-20

### Changed

- Single-source versioning.

## [4.0.0] - 2022-11-16

### Changed

- pip-installable, with a `src/` layout and `pyproject.toml`.

## [3.5.5] - 2022-02-19

### Fixed

- AMI parameter parsing fragilities.

## [3.4.1] - 2021-08-16

### Changed

- Clean-ups for the *DesignCon 2021 Bootcamp* exercises.

## [3.3.2] - 2020-01-21

### Fixed

- IBIS files without `[Date]`, and models with incomplete `[Algorithmic Model]` sections, failed to parse.

## [3.3] - 2019-12-02

### Changed

- Python 3 support.

## [2.0.1] - 2017-01-02

### Fixed

- Fixes made while testing *PyBERT* v2.0.1 against several IBIS-AMI models.

## [1.1.2] - 2015-05-13

### Fixed

- A crash when loading models without `GetWave()`.

## [1.1] - 2015-04-17

### Fixed

- `AMIModelInitializer.__init__()` handling of extra keyword arguments.

[10.0.0]: https://github.com/capn-freako/PyAMI/compare/v9.3.1...HEAD
[9.3.1]: https://github.com/capn-freako/PyAMI/compare/v9.3.0...v9.3.1
[9.3.0]: https://github.com/capn-freako/PyAMI/releases/tag/v9.3.0
[9.2.0]: https://github.com/capn-freako/PyAMI/releases/tag/v9.2.0
[9.1.0]: https://github.com/capn-freako/PyAMI/releases/tag/v9.1.0
[9.0.0]: https://github.com/capn-freako/PyAMI/releases/tag/v9.0.0
[8.1.0]: https://github.com/capn-freako/PyAMI/releases/tag/v8.1.0
[8.0.0]: https://github.com/capn-freako/PyAMI/releases/tag/v8.0.0
[7.3.1]: https://github.com/capn-freako/PyAMI/releases/tag/v7.3.1
[7.2.7]: https://github.com/capn-freako/PyAMI/releases/tag/v7.2.7
[7.2.5]: https://github.com/capn-freako/PyAMI/releases/tag/v7.2.5
[7.2.4]: https://github.com/capn-freako/PyAMI/releases/tag/v7.2.4
[7.2.3]: https://github.com/capn-freako/PyAMI/releases/tag/v7.2.3
[7.2.2]: https://github.com/capn-freako/PyAMI/releases/tag/v7.2.2
[7.2.0]: https://github.com/capn-freako/PyAMI/releases/tag/v7.2.0
[6.2.2]: https://github.com/capn-freako/PyAMI/releases/tag/v6.2.2
[6.2.1]: https://github.com/capn-freako/PyAMI/releases/tag/v6.2.1
[6.2.0]: https://github.com/capn-freako/PyAMI/releases/tag/v6.2.0
[5.1.4]: https://github.com/capn-freako/PyAMI/releases/tag/v5.1.4
[5.1.3]: https://github.com/capn-freako/PyAMI/releases/tag/v5.1.3
[5.1.2]: https://github.com/capn-freako/PyAMI/releases/tag/v5.1.2
[5.1.1]: https://github.com/capn-freako/PyAMI/releases/tag/5.1.1
[4.1.1]: https://github.com/capn-freako/PyAMI/releases/tag/4.1.1
[4.0.0]: https://github.com/capn-freako/PyAMI/releases/tag/4.0.0
[3.5.5]: https://github.com/capn-freako/PyAMI/releases/tag/3.5.5
[3.4.1]: https://github.com/capn-freako/PyAMI/releases/tag/v3.4.1
[3.3.2]: https://github.com/capn-freako/PyAMI/releases/tag/v3.3.2
[3.3]: https://github.com/capn-freako/PyAMI/releases/tag/v3.3
[2.0.1]: https://github.com/capn-freako/PyAMI/releases/tag/v2.0.1
[1.1.2]: https://github.com/capn-freako/PyAMI/releases/tag/v1.1.2
[1.1]: https://github.com/capn-freako/PyAMI/releases/tag/v1.1
