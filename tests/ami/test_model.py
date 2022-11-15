import sys
from pathlib import Path

import pytest

from pyibisami.ami.model import AMIModel, AMIModelInitializer, loadWave


def test_loadWave(tmp_path):
    """Simple test case to verify pytest and tox is up and working."""
    waveform = tmp_path.joinpath("waveform.txt")
    with open(waveform, "w") as test_file:
        test_file.write("Time Voltage\n")
        test_file.write("0.00 .000\n")
        test_file.write("0.01 .001\n")
        test_file.write("0.02 .002\n")
        test_file.write("0.03 .003\n")
        test_file.write("0.04 .004\n")

    wave = loadWave(waveform)
    assert len(wave[0]) == len(wave[1])
    assert len(wave[0]) == 5


class Test_AMIModel(object):
    def test_init(self):
        """Verify that we can load in a .so file.

        This example and compiled object files come from ibisami a related module that this
        command is used with.
        """
        if sys.platform == "win32":
            example_so = str(Path(__file__).parents[1].joinpath("examples", "example_tx_x86_amd64.dll"))
        elif sys.platform.startswith("linux"):
            example_so = str(Path(__file__).parents[1].joinpath("examples", "example_tx_x86_amd64.so"))
        else:  # darwin aka OS X
            example_so = str(Path(__file__).parents[1].joinpath("examples", "example_tx_x86_amd64_osx.so"))

        the_model = AMIModel(example_so)

        initializer = AMIModelInitializer({"root_name": "exampleTx"})

        the_model.initialize(initializer)
        assert the_model.msg == b"Initializing Tx...\n\n"
        assert the_model.ami_params_out == (
            "(example_tx (tx_tap_units 27) (taps[0] 0) (taps[1] 27) (taps[2] 0) "
            "(taps[3] 0) (tap_weights_[0] -0) (tap_weights_[1] 1.0989) (tap_weights_[2] -0) "
            "(tap_weights_[3] -0)\n"
        ).encode("utf-8")


class Test_AMIModelInitializer(object):
    def test_init(self):
        dut = AMIModelInitializer("")
        assert dut.ami_params == {"root_name": ""}
        data = ["channel_response", "row_size", "num_aggressors", "sample_interval", "bit_time"]
        assert all(name in dut._init_data for name in data)
