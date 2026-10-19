"""The core package must work without any optional extra (``gui``, ``report``, ``notebook``) installed.

Each test runs in a fresh interpreter in which the extras' packages are made unimportable,
so it also passes, unchanged, in a core-only install (``make test-core``).
"""

import subprocess
import sys
import textwrap

BLOCKER = textwrap.dedent("""
    import importlib.abc, sys

    BLOCKED = {
        "chaco", "enable", "kiwisolver", "pyface", "traitsui",  # gui
        "PyQt5", "PyQt6", "PySide6",                            # Qt bindings
        "matplotlib", "reportlab", "scipy",                     # report
        "jupyter", "nbformat", "papermill",                     # notebook
    }

    class Blocker(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name.split(".")[0] in BLOCKED:
                raise ModuleNotFoundError(f"No module named {name!r} (blocked)", name=name)

    sys.meta_path.insert(0, Blocker())

    def assert_no_extras_loaded():
        loaded = BLOCKED & {name.split(".")[0] for name in sys.modules}
        assert not loaded, loaded
""")


def run_without_extras(code: str, *args: str) -> None:
    "Run ``code`` in a fresh interpreter, with the optional extras blocked."
    script = BLOCKER + textwrap.dedent(code) + "\nassert_no_extras_loaded()\n"
    result = subprocess.run([sys.executable, "-c", script, *args], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_core_modules_import():
    run_without_extras("""
        import pyibisami.ami.config
        import pyibisami.ami.model
        import pyibisami.ami.parameter
        import pyibisami.ami.configurator
        import pyibisami.ami.parser
        import pyibisami.common
        import pyibisami.ibis.file
        import pyibisami.ibis.iv
        import pyibisami.ibis.model
        import pyibisami.ibis.parser
        import pyibisami.testing.ami_test_config
        import pyibisami.testing.test_defs
        import pyibisami.testing.util
        import pyibisami.util.ami
        import pyibisami.util.misc
        import pyibisami.tools.run_notebook
    """)


def test_ibis_model_headless(ibis_test_file):
    """Alerts must only be logged and fired, never touch the GUI."""
    run_without_extras("""
        import sys
        from pyibisami.ibis.file import IBISModel

        ibis = IBISModel(sys.argv[1])
        model = ibis.model
        assert abs(model.zout - 50.0) < 1e-9, model.zout
        assert set(model.iv_data.curves) == {"pulldown", "pullup"}
        assert ibis.comp_.pins
        try:
            model.plot_iv
        except ImportError as err:
            assert "pyibis-ami[gui]" in str(err), err
        else:
            raise AssertionError("`plot_iv` should need the `gui` extra.")
    """, str(ibis_test_file))


def test_ami_configurator_headless(ami_test_file):
    run_without_extras("""
        import sys
        from pyibisami.ami.configurator import AMIParamConfigurator

        with open(sys.argv[1], encoding="utf-8") as ami_file:
            cfg = AMIParamConfigurator(ami_file.read())
        assert cfg.input_ami_params
        try:
            cfg.open_gui()
        except ImportError as err:
            assert "pyibis-ami[gui]" in str(err), err
        else:
            raise AssertionError("`open_gui()` should need the `gui` extra.")
    """, str(ami_test_file))


def test_report_clis_need_report_extra():
    run_without_extras("""
        for module in ("pyibisami.report", "pyibisami.report.test_models", "pyibisami.tools.run_tests"):
            try:
                __import__(module)
            except ImportError as err:
                assert "pyibis-ami[report]" in str(err), err
            else:
                raise AssertionError(f"`{module}` should need the `report` extra.")
    """)
