from pathlib import Path

import pytest

from pyibisami.tools.run_tests import (
    color_picker,
    expand_params,
    hsv2rgb,
    plot_name,
    run_tests,
)


class TestRunTests(object):
    def test_hsv2rgb(self):
        """Convert an HSV number to a RGB one. Everything is normalized to 1."""
        # Black
        assert hsv2rgb(0, 0, 0) == (0.0, 0.0, 0.0)
        # Cyan
        assert hsv2rgb(180, 1, 1) == (0.0, 1.0, 1.0)
        # Red
        assert hsv2rgb(0, 1, 1) == (1.0, 0.0, 0.0)
        # Lime
        assert hsv2rgb(120, 1, 1) == (0.0, 1.0, 0.0)
        # Blue
        assert hsv2rgb(240, 1, 1) == (0.0, 0.0, 1.0)

    def test_plot_name(self):
        image_filename = plot_name("pytest")
        assert next(image_filename) == "pytest_plot_1.png"

    def test_color_picker(self):
        color = color_picker()
        assert next(color) == (hsv2rgb(0, 1.0, 1.0), hsv2rgb(0, 0.75, 0.75))

    def test_expand_params(self):
        input_params = '[("cfg_dflt", "default", [("default", ({"root_name":"testAMI"},{})),]),]'
        params = expand_params(input_params)
        assert params == [("cfg_dflt", "default", [("default", ({"root_name": "testAMI"}, {}))])]

    def test_expand_params_file(self, tmp_path):
        run_file = tmp_path.joinpath("test.run")
        with open(run_file, "w") as test_file:
            test_file.write(
                """Sweep of Tx pre-emphasis filter posttap1 values.

('Posttap1 = 0', \
  ({'root_name'        : 'example_tx', \
    'tx_tap_np1'       : 0, \
    'tx_tap_nm1'       : 0, \
    'tx_tap_nm2'       : 0, \
   }, \
   {'channel_response' : [2.0e11] + [0.], \
    'sample_interval'  : 5.0e-12, \
   }, \
  ), \
)"""
            )
        params = expand_params(run_file)
        assert params == [
            (
                "test",
                "Sweep of Tx pre-emphasis filter posttap1 values.\n",
                [
                    (
                        "Posttap1 = 0",
                        (
                            {
                                "root_name": "example_tx",
                                "tx_tap_nm1": 0,
                                "tx_tap_nm2": 0,
                                "tx_tap_np1": 0,
                            },
                            {"channel_response": [200000000000.0, 0.0], "sample_interval": 5e-12},
                        ),
                    )
                ],
            )
        ]

    def test_expand_params_directory(self, tmp_path):
        runs_dir = tmp_path.joinpath("runs")
        runs_dir.mkdir()
        run_file = runs_dir.joinpath("test.run")
        with open(run_file, "w") as test_file:
            test_file.write(
                """Sweep of Tx pre-emphasis filter posttap1 values.

('Posttap1 = 0', \
  ({'root_name'        : 'example_tx', \
    'tx_tap_np1'       : 0, \
    'tx_tap_nm1'       : 0, \
    'tx_tap_nm2'       : 0, \
   }, \
   {'channel_response' : [2.0e11] + [0.], \
    'sample_interval'  : 5.0e-12, \
   }, \
  ), \
)"""
            )
        params = expand_params(runs_dir)
        assert params == [
            (
                "test",
                "Sweep of Tx pre-emphasis filter posttap1 values.\n",
                [
                    (
                        "Posttap1 = 0",
                        (
                            {
                                "root_name": "example_tx",
                                "tx_tap_nm1": 0,
                                "tx_tap_nm2": 0,
                                "tx_tap_np1": 0,
                            },
                            {"channel_response": [200000000000.0, 0.0], "sample_interval": 5e-12},
                        ),
                    )
                ],
            )
        ]

    @pytest.mark.xfail(reason="EMPY looses its stdout proxy.")
    def test_run_tests(self):
        model = Path(__file__).parents[1].joinpath("examples", "example_tx_x86_amd64.so")
        test_dir = Path(__file__).parents[1].joinpath("examples", "tests")
        params = Path(__file__).parents[1].joinpath("examples", "runs")
        xml_file = "test_results.xml"
        ref_dir = Path().cwd()
        out_dir = Path(__file__).parents[1].joinpath("examples", "test_results")
        run_tests(
            model=model,
            test_dir=test_dir,
            params=params,
            xml_file=xml_file,
            ref_dir=ref_dir,
            out_dir=out_dir,
            tests=(),
        )
