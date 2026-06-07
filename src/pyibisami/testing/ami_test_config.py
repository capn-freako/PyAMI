"""
Runner for [AMI Test Configuration] blocks (IBIS 8.0, section 10.11).

Each [AMI Test Configuration] block in a model's [Algorithmic Model] section
embeds golden input/output data so any EDA tool can verify the model produces
the same output the model-maker intended.  This module drives that verification.
"""

import re
from ctypes    import c_double
from dataclasses import dataclass, field
from pathlib   import Path
from typing    import Optional

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
        # Booleans are already handled by the parser (True/False atoms), but guard anyway.
        if v == "True":
            return True
        if v == "False":
            return False
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

    cfg_type = config.get("type", "").strip()
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
        initializer.channel_response = input_ir.flatten().tolist()
        ami_model.initialize(initializer)
    except Exception as exc:
        return AmiTestConfigResult(
            config_name=config_name, passed=False,
            message=f"AMI_Init() failed: {exc}")

    # ======================================================= Statistical path
    if cfg_type == "Statistical":
        return _check_statistical(
            config_name, config, ibis_file_dir, ami_model, tol_ir)

    # ======================================================= Time_domain path
    if cfg_type == "Time_domain":
        return _check_time_domain(
            config_name, config, ibis_file_dir, ami_model,
            initializer, sim_params, num_rows, tol_ir, tol_wave)

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

    # --- IR comparison ---
    try:
        golden_ir  = _load_numeric_file(ibis_dir / config["golden_ir_file"])
        init_out   = np.array(ami_model.initOut)
        n          = min(len(init_out), len(golden_ir.flatten()))
        diff       = init_out[:n] - golden_ir.flatten()[:n]
        ir_max     = float(np.max(np.abs(diff)))
        ir_rms     = float(np.sqrt(np.mean(diff ** 2)))
        if ir_max > tol_ir:
            passed = False
            messages.append(
                f"IR max|err|={ir_max:.3e} exceeds tolerance {tol_ir:.3e}")
    except Exception as exc:
        passed = False
        messages.append(f"IR comparison failed: {exc}")

    # --- params_out comparison ---
    try:
        golden_path = ibis_dir / config["ami_output_parameters_file"]
        with open(golden_path, encoding="utf-8") as fh:
            golden_str = fh.read()
        params_out_match = (
            _normalize_params_str(ami_model.ami_params_out)
            == _normalize_params_str(golden_str)
        )
        if not params_out_match:
            passed = False
            messages.append(
                f"params_out mismatch.\n"
                f"  Got:      {_normalize_params_str(ami_model.ami_params_out)}\n"
                f"  Expected: {_normalize_params_str(golden_str)}")
    except Exception as exc:
        passed = False
        messages.append(f"params_out comparison failed: {exc}")

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
    initializer: AMIModelInitializer,
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
        try:
            golden_ir = _load_numeric_file(ibis_dir / config["golden_ir_file"])
            init_out  = np.array(ami_model.initOut)
            n         = min(len(init_out), len(golden_ir.flatten()))
            diff      = init_out[:n] - golden_ir.flatten()[:n]
            ir_max    = float(np.max(np.abs(diff)))
            ir_rms    = float(np.sqrt(np.mean(diff ** 2)))
            if ir_max > tol_ir:
                passed = False
                messages.append(
                    f"IR max|err|={ir_max:.3e} exceeds tolerance {tol_ir:.3e}")
        except Exception as exc:
            passed = False
            messages.append(f"IR comparison failed: {exc}")

    # --- Waveform comparison via AMI_GetWave() ---
    if not ami_model.has_getwave:
        messages.append("Model has no AMI_GetWave(); waveform comparison skipped.")
    else:
        try:
            input_wave  = _load_numeric_file(ibis_dir / config["input_waveform_file"])
            golden_wave = _load_numeric_file(ibis_dir / config["golden_waveform_file"])
        except Exception as exc:
            return AmiTestConfigResult(
                config_name=config_name, passed=False,
                message=f"Failed to load waveform file: {exc}")

        # Compute bits_per_call from wave_size (fixed samples per AMI_GetWave call).
        samps_per_bit = max(1, round(initializer.bit_time / initializer.sample_interval))
        wave_size     = int(sim_params.get("wave_size", str(num_rows)))
        bits_per_call = max(1, wave_size // samps_per_bit)

        try:
            wave_out, _clocks, _params_list = ami_model.getWave(
                input_wave, bits_per_call=bits_per_call)
            n        = min(len(wave_out), len(golden_wave))
            diff     = wave_out[:n] - golden_wave[:n]
            wave_max = float(np.max(np.abs(diff)))
            wave_rms = float(np.sqrt(np.mean(diff ** 2)))
            if wave_max > tol_wave:
                passed = False
                messages.append(
                    f"Waveform max|err|={wave_max:.3e} exceeds tolerance {tol_wave:.3e}")
        except Exception as exc:
            passed = False
            messages.append(f"GetWave comparison failed: {exc}")

        # --- params_out: compare last block against golden file ---
        try:
            golden_path = ibis_dir / config["ami_output_parameters_file"]
            with open(golden_path, encoding="utf-8") as fh:
                golden_str = fh.read()
            # For Time_domain the golden file contains accumulated blocks; we
            # compare only the final ami_params_out string (last GetWave call).
            actual_norm  = _normalize_params_str(ami_model.ami_params_out)
            golden_norm  = _normalize_params_str(golden_str)
            params_out_match = (actual_norm in golden_norm)  # substring: last block must appear
            if not params_out_match:
                passed = False
                messages.append(
                    f"Last params_out block not found in golden params_out file.\n"
                    f"  Got: {actual_norm}")
        except Exception as exc:
            passed = False
            messages.append(f"params_out comparison failed: {exc}")

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
