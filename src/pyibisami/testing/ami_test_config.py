"""
Runner for [AMI Test Configuration] blocks (IBIS 8.0, section 10.11).

Each [AMI Test Configuration] block in a model's [Algorithmic Model] section
embeds golden input/output data so any EDA tool can verify the model produces
the same output the model-maker intended.  This module drives that verification.
"""

import sys
import re
from ctypes    import c_double
from dataclasses import dataclass, field
from pathlib   import Path
from typing    import Optional

import click
import numpy as np
from parsec    import many

from ..ami.model  import AMIModel, AMIModelInitializer
from ..ami.parser import ignore, root
from ..ibis.model import Model


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class AmiTestConfigResult:
    "Outcome of running one [AMI Test Configuration] block."

    config_name:       str
    passed:            bool
    message:           str
    ir_max_abs_error:  Optional[float] = None
    ir_rms_error:      Optional[float] = None
    wave_max_abs_error: Optional[float] = None
    wave_rms_error:    Optional[float] = None
    params_out_match:  bool = False

    def __str__(self) -> str:
        lines = [
            f"[AMI Test Configuration] '{self.config_name}': {'PASS' if self.passed else 'FAIL'}",
            f"  {self.message}",
        ]
        if self.ir_max_abs_error is not None:
            lines.append(f"  IR max|err|={self.ir_max_abs_error:.3e}  RMS={self.ir_rms_error:.3e}")
        if self.wave_max_abs_error is not None:
            lines.append(f"  Wave max|err|={self.wave_max_abs_error:.3e}  RMS={self.wave_rms_error:.3e}")
        lines.append(f"  params_out match: {self.params_out_match}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ami_sections_parser = ignore >> many(root)


def _parse_ami_input_params_file(content: str) -> tuple[dict, dict, str]:
    """
    Parse an AMI_input_parameters_file into its two sections.

    The file contains two top-level S-expressions::

        (Simulator_parameters
          (Sample_interval <float>)
          (Symbol_time    <float>)
          (Number_of_rows <int>)   | Statistical
          (Wave_size      <int>)   | Time_domain
          (Aggressors     <int>)
        )
        (Model_parameters
          (<root_name>
            (<param> <value>) ...
          )
        )

    Returns:
        (sim_params, model_params, root_name) where *sim_params* has lowercase
        keys mapping to raw strings (e.g. ``{"sample_interval": "25e-12"}``),
        *model_params* maps parameter names to raw string values, and
        *root_name* is the AMI root name string.
    """
    sections = dict(_ami_sections_parser.parse(content))

    sim_params: dict[str, str] = {}
    for child_label, child_values in sections.get("Simulator_parameters", []):
        sim_params[child_label.lower()] = child_values[0] if child_values else ""

    model_params: dict = {}
    root_name = ""
    mp_children = sections.get("Model_parameters", [])
    if mp_children:
        root_name, param_children = mp_children[0]
        for pname, pvalues in param_children:
            model_params[pname] = pvalues[0] if len(pvalues) == 1 else pvalues

    return sim_params, model_params, root_name


def _coerce_param_value(v):
    """Convert a raw AMI parameter value (usually a string) to int/float/bool/str."""
    if isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        try:
            if "." not in v and "e" not in v.lower():
                return int(v)
            return float(v)
        except ValueError:
            return v
    return v


def _load_numeric_file(path: Path) -> np.ndarray:
    """Load a whitespace-separated numeric file (no header) into a NumPy array."""
    return np.loadtxt(str(path))


def _diff_metrics(diff: np.ndarray) -> tuple[float, float]:
    "Return (max absolute error, RMS error) for a difference array."
    return float(np.max(np.abs(diff))), float(np.sqrt(np.mean(diff ** 2)))


def _compare_params_out(
    ami_model: "AMIModel",
    ibis_dir: Path,
    config: dict,
) -> tuple[bool, bool, list[str]]:
    """Compare ami_params_out against the golden params file.

    Returns:
        (attempted, matched, error_messages) — *attempted* is False when the
        config key is absent (treated as optional), True otherwise.
    """
    golden_path_str = config.get("ami_output_parameters_file", "").strip()
    if not golden_path_str:
        return False, False, []
    try:
        with open(ibis_dir / golden_path_str, encoding="utf-8") as fh:
            golden_str = fh.read()
        actual_norm = _normalize_params_str(ami_model.ami_params_out)
        golden_norm = _normalize_params_str(golden_str)
        matched = (actual_norm == golden_norm)
        msgs = [] if matched else [
            f"params_out mismatch.\n"
            f"  Got:      {actual_norm}\n"
            f"  Expected: {golden_norm}"
        ]
        return True, matched, msgs
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return True, False, [f"params_out comparison failed: {exc}"]


def _compare_ir(
    ami_model: "AMIModel",
    ibis_dir: Path,
    config: dict,
    tol_ir: float,
) -> tuple[bool, list[str], Optional[float], Optional[float]]:
    """Compare AMI_Init() output IR against the golden file named in config."""
    try:
        golden_ir  = _load_numeric_file(ibis_dir / config["golden_ir_file"])
        golden_amp = golden_ir[:, 1] if golden_ir.ndim == 2 else golden_ir
        init_out   = np.array(ami_model.initOut)
        n          = min(len(init_out), len(golden_amp))
        diff       = init_out[:n] - golden_amp[:n]
        ir_max, ir_rms = _diff_metrics(diff)
        ok        = ir_max <= tol_ir
        msgs      = [] if ok else [f"IR max|err|={ir_max:.3e} exceeds tolerance {tol_ir:.3e}"]
        return ok, msgs, ir_max, ir_rms
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, [f"IR comparison failed: {exc}"], None, None


def _normalize_params_str(s: str) -> str:
    """Collapse internal whitespace for string-level params_out comparison."""
    return re.sub(r"\s+", " ", s.strip())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_ami_test_config(
    ibis_file_dir: Path,
    model: Model,
    config_name: str,
    *,
    tol_ir:   float = 1e-6,
    tol_wave: float = 1e-6,
) -> AmiTestConfigResult:
    """
    Run one [AMI Test Configuration] block and compare outputs against golden data.

    The function loads the executable and data files named in the config, calls
    ``AMI_Init()`` (and ``AMI_GetWave()`` for Time_domain configs), then
    numerically compares the outputs with the golden files provided by the
    model-maker.

    Args:
        ibis_file_dir: Directory containing the ``.ibs`` file.  All filenames
            inside the config block are resolved relative to this directory.
        model: The parsed IBIS ``Model`` object for the device under test.
        config_name: Name of the ``[AMI Test Configuration]`` block to run.

    Keyword Args:
        tol_ir:   Absolute tolerance for impulse-response comparison.
        tol_wave: Absolute tolerance for waveform comparison.

    Returns:
        An :class:`AmiTestConfigResult` with pass/fail status and error metrics.
    """
    # ------------------------------------------------------------------ setup
    config = model.test_configs.get(config_name)
    if config is None:
        return AmiTestConfigResult(
            config_name=config_name, passed=False,
            message=f"No [AMI Test Configuration] named '{config_name}' found.")

    cfg_type = config.get("type", "").strip().lower()
    exe_idx  = int(config.get("executable_index", "1")) - 1  # convert to 0-based

    # Resolve executable (DLL/SO + .ami file).
    executables = model.executables
    if not (0 <= exe_idx < len(executables)):
        return AmiTestConfigResult(
            config_name=config_name, passed=False,
            message=(f"executable_index {exe_idx + 1} is out of range "
                     f"(model has {len(executables)} Executable line(s))."))
    ((_os, _bits), (dll_name, _ami_name)) = executables[exe_idx]
    dll_path = ibis_file_dir / dll_name

    # --------------------------------------------------------- parse input params
    try:
        params_path = ibis_file_dir / config["ami_input_parameters_file"]
        with open(params_path, encoding="utf-8") as fh:
            sim_params, model_params, root_name = _parse_ami_input_params_file(fh.read())
    except Exception as exc:
        return AmiTestConfigResult(
            config_name=config_name, passed=False,
            message=f"Failed to parse AMI_input_parameters_file: {exc}")

    sample_interval = float(sim_params.get("sample_interval", "25e-12"))
    symbol_time     = float(sim_params.get("symbol_time",     "100e-12"))
    num_aggressors  = int(sim_params.get("aggressors", "0"))

    # --------------------------------------------------------- load Input_IR_file
    try:
        input_ir = _load_numeric_file(ibis_file_dir / config["input_ir_file"])
    except Exception as exc:
        return AmiTestConfigResult(
            config_name=config_name, passed=False,
            message=f"Failed to load Input_IR_file: {exc}")

    num_rows = input_ir.shape[0]
    # Two-column files (time, amplitude) — keep only the amplitude column.
    ir_amplitudes = input_ir[:, 1] if input_ir.ndim == 2 else input_ir

    # --------------------------------------------------------- build AMIModelInitializer
    ami_params: dict = {"root_name": root_name}
    ami_params.update({k: _coerce_param_value(v) for k, v in model_params.items()})

    try:
        ami_model = AMIModel(str(dll_path))
    except Exception as exc:
        return AmiTestConfigResult(
            config_name=config_name, passed=False,
            message=f"Failed to load AMI DLL/SO '{dll_path}': {exc}")

    try:
        initializer = AMIModelInitializer(
            ami_params,
            bit_time=c_double(symbol_time),
            row_size=num_rows,
            sample_interval=c_double(sample_interval),
            num_aggressors=num_aggressors,
        )
        # Use the property setter so the ctypes array is built correctly.
        initializer.channel_response = ir_amplitudes.tolist()
        ami_model.initialize(initializer)
    except Exception as exc:
        return AmiTestConfigResult(
            config_name=config_name, passed=False,
            message=f"AMI_Init() failed: {exc}")

    # ======================================================= Statistical path
    if cfg_type == "statistical":
        return _check_statistical(
            config_name, config, ibis_file_dir, ami_model, tol_ir)

    # ======================================================= Time_domain path
    if cfg_type == "time_domain":
        return _check_time_domain(
            config_name, config, ibis_file_dir, ami_model,
            sim_params, num_rows, tol_ir, tol_wave)

    return AmiTestConfigResult(
        config_name=config_name, passed=False,
        message=f"Unknown Type '{cfg_type}'; expected 'Statistical' or 'Time_domain'.")


# ---------------------------------------------------------------------------
# Per-type verification helpers
# ---------------------------------------------------------------------------

def _check_statistical(
    config_name: str,
    config: dict,
    ibis_dir: Path,
    ami_model: AMIModel,
    tol_ir: float,
) -> AmiTestConfigResult:
    "Compare AMI_Init() output IR and params_out against golden data."

    passed   = True
    messages: list[str] = []
    ir_max = ir_rms = None
    params_out_match = False

    # --- IR comparison (optional) ---
    if config.get("golden_ir_file", "").strip():
        ok, msgs, ir_max, ir_rms = _compare_ir(ami_model, ibis_dir, config, tol_ir)
        if not ok:
            passed = False
            messages.extend(msgs)

    # --- params_out comparison ---
    _, params_out_match, msgs = _compare_params_out(ami_model, ibis_dir, config)
    if msgs:
        passed = False
        messages.extend(msgs)

    msg = "PASS" if passed else "FAIL: " + "; ".join(messages)
    return AmiTestConfigResult(
        config_name=config_name, passed=passed, message=msg,
        ir_max_abs_error=ir_max, ir_rms_error=ir_rms,
        params_out_match=params_out_match)


def _check_time_domain(
    config_name: str,
    config: dict,
    ibis_dir: Path,
    ami_model: AMIModel,
    sim_params: dict,
    num_rows: int,
    tol_ir:   float,
    tol_wave: float,
) -> AmiTestConfigResult:
    "Run AMI_GetWave() and compare waveform (and optionally IR) against golden data."

    passed   = True
    messages: list[str] = []
    ir_max = ir_rms = None
    wave_max = wave_rms = None
    params_out_match = False

    # --- Optional IR comparison ---
    if config.get("golden_ir_file", "").strip():
        ok, msgs, ir_max, ir_rms = _compare_ir(ami_model, ibis_dir, config, tol_ir)
        if not ok:
            passed = False
            messages.extend(msgs)

    # --- Waveform comparison via AMI_GetWave() ---
    if not ami_model.has_getwave:
        passed = False
        messages.append("Model has no AMI_GetWave(); Time_domain config requires it.")
    else:
        try:
            input_wave  = _load_numeric_file(ibis_dir / config["input_waveform_file"])
            golden_wave = _load_numeric_file(ibis_dir / config["golden_waveform_file"])
        except Exception as exc:
            passed = False
            messages.append(f"Failed to load waveform file: {exc}")
        else:
            # Compute bits_per_call from wave_size (fixed samples per AMI_GetWave call).
            wave_size     = int(sim_params.get("wave_size", str(num_rows)))
            bits_per_call = max(1, wave_size // max(1, ami_model._samps_per_bit))

            getwave_ok = False
            try:
                wave_out, _clocks, _params_list = ami_model.getWave(
                    input_wave, bits_per_call=bits_per_call)
                n        = min(len(wave_out), len(golden_wave))
                diff     = wave_out[:n] - golden_wave[:n]
                wave_max, wave_rms = _diff_metrics(diff)
                if wave_max > tol_wave:
                    passed = False
                    messages.append(
                        f"Waveform max|err|={wave_max:.3e} exceeds tolerance {tol_wave:.3e}")
                getwave_ok = True
            except Exception as exc:
                passed = False
                messages.append(f"GetWave comparison failed: {exc}")

            # --- params_out: only meaningful after a successful getWave() call ---
            if getwave_ok:
                _, params_out_match, msgs = _compare_params_out(ami_model, ibis_dir, config)
                if msgs:
                    passed = False
                    messages.extend(msgs)

    msg = "PASS" if passed else "FAIL: " + "; ".join(messages)
    return AmiTestConfigResult(
        config_name=config_name, passed=passed, message=msg,
        ir_max_abs_error=ir_max, ir_rms_error=ir_rms,
        wave_max_abs_error=wave_max, wave_rms_error=wave_rms,
        params_out_match=params_out_match)


def run_all_ami_test_configs(
    ibis_file_dir: Path,
    model: Model,
    *,
    tol_ir:   float = 1e-6,
    tol_wave: float = 1e-6,
) -> list[AmiTestConfigResult]:
    """
    Run every [AMI Test Configuration] block found in *model* and return results.

    Args:
        ibis_file_dir: Directory containing the ``.ibs`` file and data files.
        model: The parsed IBIS ``Model`` object.

    Keyword Args:
        tol_ir:   Absolute tolerance for impulse-response comparison.
        tol_wave: Absolute tolerance for waveform comparison.

    Returns:
        One :class:`AmiTestConfigResult` per configuration block.
    """
    return [
        run_ami_test_config(
            ibis_file_dir, model, name,
            tol_ir=tol_ir, tol_wave=tol_wave)
        for name in model.test_configs
    ]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("ibis_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--model-name", "-m", default=None,
              help="Name of the [Model] to test.  Required when the .ibs file defines more than one model.")
@click.option("--config", "-c", default=None,
              help="Name of a single [AMI Test Configuration] to run.  Runs all configs when omitted.")
@click.option("--tol-ir",   default=1e-6, show_default=True,
              help="Absolute tolerance for impulse-response comparison.")
@click.option("--tol-wave", default=1e-6, show_default=True,
              help="Absolute tolerance for waveform comparison.")
def main(ibis_file, model_name, config, tol_ir, tol_wave):
    """Run [AMI Test Configuration] blocks embedded in an IBIS file (IBIS 8.0 §10.11).

    Parses IBIS_FILE, locates the target model, then calls AMI_Init() (and
    AMI_GetWave() for Time_domain configs) and compares the outputs against the
    golden data files referenced in each [AMI Test Configuration] block.

    Exits with status 1 if any configuration fails.
    """
    from ..ibis.parser import parse_ibis_file  # local import to avoid circular deps at module load

    ibis_path = Path(ibis_file).resolve()
    ibis_dir  = ibis_path.parent

    status, ibis_dict = parse_ibis_file(ibis_path.read_text(encoding="utf-8"))
    if status != "Success!":
        click.echo(f"ERROR: failed to parse {ibis_path}: {status}", err=True)
        sys.exit(1)

    models: dict = ibis_dict.get("models", {})
    if not models:
        click.echo("ERROR: no [Model] sections found in the IBIS file.", err=True)
        sys.exit(1)

    if model_name is None:
        if len(models) == 1:
            model_name = next(iter(models))
        else:
            click.echo(
                f"ERROR: the file contains multiple models ({', '.join(models)}); "
                "specify one with --model-name / -m.",
                err=True)
            sys.exit(1)

    if model_name not in models:
        click.echo(f"ERROR: model '{model_name}' not found (available: {', '.join(models)}).", err=True)
        sys.exit(1)

    model_obj = models[model_name]
    if not model_obj.test_configs:
        click.echo(f"No [AMI Test Configuration] blocks found in model '{model_name}'.")
        sys.exit(0)

    if config:
        results = [run_ami_test_config(ibis_dir, model_obj, config, tol_ir=tol_ir, tol_wave=tol_wave)]
    else:
        results = run_all_ami_test_configs(ibis_dir, model_obj, tol_ir=tol_ir, tol_wave=tol_wave)

    any_failed = False
    for result in results:
        click.echo(str(result))
        if not result.passed:
            any_failed = True

    if any_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
