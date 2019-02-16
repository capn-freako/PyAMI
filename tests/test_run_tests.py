from pyibisami.run_tests import color_picker, plot_name, hsv2rgb, expand_params


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
        image_filename = plot_name()
        assert next(image_filename) == "plot_1.png"

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
