"""
Tests for pyibisami.testing.ami_test_config — the [AMI Test Configuration] runner.

Strategy: use the compiled example_tx model (already in tests/examples/) to
generate golden data on the fly, then verify the runner detects matches and
mismatches correctly.
"""

import platform
from ctypes    import c_double
from pathlib   import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from pyibisami.ami.model import AMIModel, AMIModelInitializer
from pyibisami.testing.ami_test_config import (
    AmiTestConfigResult,
    _parse_ami_input_params_file,
    run_ami_test_config,
    run_all_ami_test_configs,
)


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

def _dll_name() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "example_tx_x86_amd64.dll"
    if system == "darwin":
        return "example_tx_x86_amd64_osx.so"
    return "example_tx_x86_amd64.so"


EXAMPLES_DIR = Path(__file__).parent / "examples"
DLL_PATH     = EXAMPLES_DIR / _dll_name()

needs_dll = pytest.mark.skipif(
    not DLL_PATH.exists(),
    reason=f"AMI DLL not found: {DLL_PATH}",
)

# ---------------------------------------------------------------------------
# Model constants (must match the DLL's defaults)
# ---------------------------------------------------------------------------

BIT_RATE        = 10e9
OSF             = 32
SAMPLE_INTERVAL = 1.0 / (BIT_RATE * OSF)  # 3.125 ps
SYMBOL_TIME     = 1.0 / BIT_RATE           # 100 ps
NUM_ROWS        = 128
WAVE_SIZE       = NUM_ROWS                  # samples per AMI_GetWave call

AMI_PARAMS      = {
    "root_name":    "example_tx",
    "tx_tap_units": 27,
    "tx_tap_np1":   0,
    "tx_tap_nm1":   0,
    "tx_tap_nm2":   0,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_initializer(channel_response: list[float]) -> AMIModelInitializer:
    init = AMIModelInitializer(
        AMI_PARAMS,
        bit_time=c_double(SYMBOL_TIME),
        row_size=NUM_ROWS,
        sample_interval=c_double(SAMPLE_INTERVAL),
    )
    init.channel_response = channel_response
    return init


def _write_ami_params_file(path: Path, *, wave_size: int | None = None) -> None:
    """Write an AMI_input_parameters_file for the example_tx model."""
    if wave_size is None:
        # Statistical format
        sim = (
            f"(Simulator_parameters\n"
            f"(Sample_interval {SAMPLE_INTERVAL})\n"
            f"(Symbol_time {SYMBOL_TIME})\n"
            f"(Number_of_rows {NUM_ROWS})\n"
            f"(Aggressors 0)\n"
            f")\n"
        )
    else:
        # Time_domain format
        sim = (
            f"(Simulator_parameters\n"
            f"(Sample_interval {SAMPLE_INTERVAL})\n"
            f"(Symbol_time {SYMBOL_TIME})\n"
            f"(Wave_size {wave_size})\n"
            f")\n"
        )
    model_sec = (
        f"(Model_parameters\n"
        f"(example_tx\n"
        f"(tx_tap_units 27)\n"
        f"(tx_tap_np1 0)\n"
        f"(tx_tap_nm1 0)\n"
        f"(tx_tap_nm2 0)\n"
        f")\n"
        f")\n"
    )
    path.write_text(sim + model_sec, encoding="utf-8")


def _mock_model(tmp_path: Path, configs: dict) -> MagicMock:
    """Return a MagicMock Model whose executables point to the real DLL."""
    m = MagicMock()
    m.test_configs = configs
    # Use the absolute DLL path so ibis_file_dir / dll_name resolves correctly.
    m.executables = [(("linux", "64"), [str(DLL_PATH.resolve()), "example_tx.ami"])]
    return m


# ---------------------------------------------------------------------------
# _parse_ami_input_params_file (no DLL required)
# ---------------------------------------------------------------------------

class TestParseAmiInputParamsFile:
    "Unit tests for the internal params-file parser."

    STAT_CONTENT = """\
(Simulator_parameters
(Sample_interval 3.125e-12)
(Symbol_time 1e-10)
(Number_of_rows 128)
(Aggressors 0)
)
(Model_parameters
(my_tx
(tx_tap_units 27)
(tx_tap_np1 2)
)
)
"""

    TD_CONTENT = """\
(Simulator_parameters
(Sample_interval 3.125e-12)
(Symbol_time 1e-10)
(Wave_size 128)
)
(Model_parameters
(my_tx
(tx_tap_nm1 3)
)
)
"""

    def test_statistical_sim_params(self):
        sim, _, _ = _parse_ami_input_params_file(self.STAT_CONTENT)
        assert float(sim["sample_interval"]) == pytest.approx(3.125e-12)
        assert float(sim["symbol_time"])     == pytest.approx(1e-10)
        assert int(sim["number_of_rows"])    == 128
        assert int(sim["aggressors"])        == 0

    def test_time_domain_sim_params(self):
        sim, _, _ = _parse_ami_input_params_file(self.TD_CONTENT)
        assert int(sim["wave_size"]) == 128
        assert "number_of_rows" not in sim

    def test_model_params_and_root_name(self):
        _, model_params, root_name = _parse_ami_input_params_file(self.STAT_CONTENT)
        assert root_name == "my_tx"
        assert model_params["tx_tap_units"] == "27"
        assert model_params["tx_tap_np1"]   == "2"

    def test_model_params_time_domain(self):
        _, model_params, root_name = _parse_ami_input_params_file(self.TD_CONTENT)
        assert root_name == "my_tx"
        assert model_params["tx_tap_nm1"] == "3"


# ---------------------------------------------------------------------------
# Fixture: generates golden data by running the real model
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def golden_workspace(tmp_path_factory):
    """
    Run example_tx once to produce golden data files.  Shared across the module
    so the (relatively slow) DLL calls happen only once.
    """
    tmp = tmp_path_factory.mktemp("ami_tc")

    # ----- perfect channel (Dirac at index 1, same as AMIModelInitializer default) -----
    input_ir = np.zeros(NUM_ROWS)
    input_ir[1] = 1.0

    # ----- Statistical golden data -----
    ami_model = AMIModel(str(DLL_PATH))
    init = _make_initializer(input_ir.tolist())
    ami_model.initialize(init)

    golden_ir          = np.array(ami_model.initOut)
    golden_params_stat = ami_model.ami_params_out

    # ----- Time_domain golden data -----
    bits_per_call = WAVE_SIZE // OSF               # 4 bits per GetWave call
    nbits         = bits_per_call * 10             # 40 bits total
    bits          = np.tile([0, 1], nbits // 2)
    input_wave    = (bits.repeat(OSF) - 0.5).astype(float)

    wave_out, _, _ = ami_model.getWave(input_wave, bits_per_call=bits_per_call)
    golden_wave        = wave_out
    golden_params_td   = ami_model.ami_params_out

    # ----- Write files -----
    np.savetxt(str(tmp / "input_ir.txt"),         input_ir)
    np.savetxt(str(tmp / "golden_ir.txt"),         golden_ir)
    np.savetxt(str(tmp / "input_wave.txt"),        input_wave)
    np.savetxt(str(tmp / "golden_wave.txt"),       golden_wave)

    _write_ami_params_file(tmp / "ami_params_stat.txt")
    _write_ami_params_file(tmp / "ami_params_td.txt", wave_size=WAVE_SIZE)

    (tmp / "golden_params_stat.txt").write_text(golden_params_stat, encoding="utf-8")
    (tmp / "golden_params_td.txt").write_text(golden_params_td,   encoding="utf-8")

    return tmp


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------

@needs_dll
class TestStatistical:
    "Tests for Type Statistical [AMI Test Configuration] blocks."

    def _stat_config(self) -> dict:
        return {
            "type":                        "statistical",
            "direction":                   "Tx",
            "input_ir_file":               "input_ir.txt",
            "ami_input_parameters_file":   "ami_params_stat.txt",
            "golden_ir_file":              "golden_ir.txt",
            "ami_output_parameters_file":  "golden_params_stat.txt",
            "executable_index":            "1",
        }

    def test_pass_with_exact_golden_data(self, golden_workspace):
        model = _mock_model(golden_workspace, {"stat": self._stat_config()})
        result = run_ami_test_config(golden_workspace, model, "stat")
        assert isinstance(result, AmiTestConfigResult)
        assert result.passed, f"Expected PASS; got: {result.message}"
        assert result.ir_max_abs_error == pytest.approx(0.0, abs=1e-30)
        assert result.params_out_match

    def test_fail_with_wrong_golden_ir(self, golden_workspace, tmp_path):
        # Write a wrong golden IR (scaled by 2)
        real_ir = np.loadtxt(str(golden_workspace / "golden_ir.txt"))
        wrong_ir_path = tmp_path / "wrong_golden_ir.txt"
        np.savetxt(str(wrong_ir_path), real_ir * 2.0)

        cfg = self._stat_config()
        cfg["golden_ir_file"] = str(wrong_ir_path)  # absolute path overrides ibis_file_dir /
        model = _mock_model(golden_workspace, {"stat": cfg})
        result = run_ami_test_config(golden_workspace, model, "stat")
        assert not result.passed
        assert result.ir_max_abs_error is not None
        assert result.ir_max_abs_error > 1e-6

    def test_fail_for_missing_config_name(self, golden_workspace):
        model = _mock_model(golden_workspace, {})
        result = run_ami_test_config(golden_workspace, model, "nonexistent")
        assert not result.passed
        assert "nonexistent" in result.message

    def test_result_str_contains_config_name(self, golden_workspace):
        model = _mock_model(golden_workspace, {"stat": self._stat_config()})
        result = run_ami_test_config(golden_workspace, model, "stat")
        assert "stat" in str(result)


# ---------------------------------------------------------------------------
# Time_domain tests
# ---------------------------------------------------------------------------

@needs_dll
class TestTimeDomain:
    "Tests for Type Time_domain [AMI Test Configuration] blocks."

    def _td_config(self) -> dict:
        return {
            "type":                        "time_domain",
            "direction":                   "Tx",
            "input_ir_file":               "input_ir.txt",
            "ami_input_parameters_file":   "ami_params_td.txt",
            "input_waveform_file":         "input_wave.txt",
            "golden_waveform_file":        "golden_wave.txt",
            "ami_output_parameters_file":  "golden_params_td.txt",
            "executable_index":            "1",
        }

    def test_pass_with_exact_golden_waveform(self, golden_workspace):
        model = _mock_model(golden_workspace, {"td": self._td_config()})
        result = run_ami_test_config(golden_workspace, model, "td")
        assert result.passed, f"Expected PASS; got: {result.message}"
        assert result.wave_max_abs_error == pytest.approx(0.0, abs=1e-30)

    def test_fail_with_wrong_golden_waveform(self, golden_workspace, tmp_path):
        real_wave = np.loadtxt(str(golden_workspace / "golden_wave.txt"))
        wrong_wave_path = tmp_path / "wrong_golden_wave.txt"
        np.savetxt(str(wrong_wave_path), real_wave + 0.5)  # offset by 0.5 V

        cfg = self._td_config()
        cfg["golden_waveform_file"] = str(wrong_wave_path)
        model = _mock_model(golden_workspace, {"td": cfg})
        result = run_ami_test_config(golden_workspace, model, "td")
        assert not result.passed
        assert result.wave_max_abs_error is not None
        assert result.wave_max_abs_error > 1e-6

    def test_optional_golden_ir_checked_when_present(self, golden_workspace):
        cfg = self._td_config()
        cfg["golden_ir_file"] = "golden_ir.txt"   # add optional IR file
        model = _mock_model(golden_workspace, {"td": cfg})
        result = run_ami_test_config(golden_workspace, model, "td")
        assert result.passed, f"Expected PASS; got: {result.message}"
        assert result.ir_max_abs_error is not None  # IR was checked
        assert result.ir_max_abs_error == pytest.approx(0.0, abs=1e-30)


# ---------------------------------------------------------------------------
# run_all_ami_test_configs
# ---------------------------------------------------------------------------

@needs_dll
class TestRunAll:
    "Tests for the convenience wrapper that runs every config in a model."

    def test_runs_all_configs(self, golden_workspace):
        configs = {
            "stat": {
                "type":                       "statistical",
                "direction":                  "Tx",
                "input_ir_file":              "input_ir.txt",
                "ami_input_parameters_file":  "ami_params_stat.txt",
                "golden_ir_file":             "golden_ir.txt",
                "ami_output_parameters_file": "golden_params_stat.txt",
                "executable_index":           "1",
            },
            "td": {
                "type":                       "time_domain",
                "direction":                  "Tx",
                "input_ir_file":              "input_ir.txt",
                "ami_input_parameters_file":  "ami_params_td.txt",
                "input_waveform_file":        "input_wave.txt",
                "golden_waveform_file":       "golden_wave.txt",
                "ami_output_parameters_file": "golden_params_td.txt",
                "executable_index":           "1",
            },
        }
        model   = _mock_model(golden_workspace, configs)
        results = run_all_ami_test_configs(golden_workspace, model)
        assert len(results) == 2
        names = {r.config_name for r in results}
        assert names == {"stat", "td"}
        assert all(r.passed for r in results), \
            "\n".join(str(r) for r in results if not r.passed)
