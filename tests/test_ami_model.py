from pathlib import Path
import sys

from pyibisami.ami_model import loadWave, AMIModelInitializer, AMIModel


def test_loadWave():
    """Simple test case to verify pytest and tox is up and working."""
    wave = loadWave(
        Path(__file__).parent.joinpath("examples", "runs", "impulse_response_8ma.txt")
    )
    assert len(wave[0]) == len(wave[1])
    assert len(wave[0]) == 1149


class Test_AMIModel(object):
    def test_init(self):
        """Verify that we can load in a .so file."""
        if sys.platform == "win32":
            example_so = Path(__file__).parent.joinpath("examples", "example_tx_x86_amd64.dll")
        else:
            example_so = Path(__file__).parent.joinpath("examples", "example_tx_x86_amd64.so")
        the_model = AMIModel(example_so)

        assert not the_model._ami_mem_handle
        # Verify that all three functions were bound.
        assert the_model._amiInit
        assert the_model._amiGetWave
        assert the_model._amiClose

        initializer = AMIModelInitializer(
            [("default", ({"root_name": "testAMI"}, {}))]
        )
        the_model.initialize(initializer)
        # assert the_model.msg == b''
        # assert the_model.ami_params_out == b''
        assert len(the_model.initOut) == 128
        assert the_model.sample_interval == 2.5e-11


class Test_AMIModelInitializer(object):
    def test_init(self):
        dut = AMIModelInitializer("")
        assert dut.ami_params == {"root_name": ""}
        data = ["channel_response", "row_size", "num_aggressors", "sample_interval", "bit_time"]
        assert all(name in dut._init_data for name in data)
