from pathlib import Path

from pyibisami.run_tests import color_picker, plot_name, hsv2rgb, run_tests


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

    def test_run_tests(self):
        model = Path(__file__).parent.joinpath("examples", "example_tx_x86_amd64.so")
        test_dir = Path(__file__).parent.joinpath("examples", "tests")
        params = Path(__file__).parent.joinpath("examples", "runs")
        out_dir = Path(__file__).parent.joinpath("examples", "out")
        run_tests(
            model=model,
            test_dir=test_dir,
            params=params,
            out_dir=out_dir,
            ref_dir="",
            xml_file="test.xml",
        )
