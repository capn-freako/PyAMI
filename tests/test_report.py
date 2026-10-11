"""Tests for the ``pyibisami.report`` package (needs the ``report`` extra)."""

import pytest

pytest.importorskip("reportlab")

from click.testing import CliRunner  # noqa: E402

from pyibisami.report import test_models  # noqa: E402


def test_test_model_cli_fails_with_nonzero_exit(ibis_test_file, monkeypatch, tmp_path):
    """A testing failure must be reported as a CLI error (exit status 1), not just printed."""
    def fail(*args, **kwargs):
        raise RuntimeError("There were no AMI models found in this IBIS file.")

    monkeypatch.setattr(test_models, "test_ibis_ami_models", fail)
    result = CliRunner().invoke(test_models.main, [str(ibis_test_file), "-p", str(tmp_path)])
    assert result.exit_code == 1
    assert "Error: There were no AMI models found" in result.output


def test_test_model_cli_echoes_pdf_report(ibis_test_file, monkeypatch, tmp_path):
    monkeypatch.setattr(test_models, "test_ibis_ami_models", lambda *args, **kwargs: tmp_path / "x_test_results.pdf")
    result = CliRunner().invoke(test_models.main, [str(ibis_test_file), "-p", str(tmp_path)])
    assert result.exit_code == 0
    assert result.stdout == f"PDF report: {tmp_path / 'x_test_results.pdf'}\n"


def test_sweep_template_exists():
    """The default test sweep template must be where ``test_ami_model()`` looks for it.

    Regression test: moving ``ami_tests`` into ``pyibisami.report`` left this lookup pointing at the wrong package.
    """
    from pyibisami.report.ami_tests import SWEEP_TEMPLATE

    assert SWEEP_TEMPLATE.is_file(), SWEEP_TEMPLATE
