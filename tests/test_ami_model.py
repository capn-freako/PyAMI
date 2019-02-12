from pathlib import Path


class TestAMIModel(object):

    def test_loadWave(self):
        """Simple test case to verify pytest and tox is up and working."""
        from pyibisami.ami_model import loadWave
        wave = loadWave(
            Path(__file__).parent.joinpath("examples", "runs", "impulse_response_8ma.txt")
        )
        assert len(wave[0]) == len(wave[1])
        assert len(wave[0]) == 1149
