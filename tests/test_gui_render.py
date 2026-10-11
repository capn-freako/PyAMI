"""The optional GUI must actually render, not just build its views.

Building a ``View`` doesn't evaluate its items' editors (e.g. - a ``format_str`` applied to a
non-numeric trait only fails at display time), so this opens every viewer, offscreen.
Needs the ``gui`` extra *and* a Qt binding (which that extra doesn't install).
(Ported from ``fix/95-decouple-gui``'s ``test_headless.py``.)
"""

import os
import subprocess
import sys
import textwrap
from importlib.util import find_spec

import pytest

pytestmark = [
    pytest.mark.skipif(find_spec("traitsui") is None or find_spec("chaco") is None, reason="needs the `gui` extra"),
    pytest.mark.skipif(not any(find_spec(qt) for qt in ("PySide6", "PyQt6", "PyQt5")), reason="needs a Qt binding"),
]

AMI_CONTENTS = r"""(example_rx
    (Reserved_Parameters
         (Init_Returns_Impulse (Usage Info) (Type Boolean) (Value True) (Description "x"))
         (GetWave_Exists (Usage Info) (Type Boolean) (Value False) (Description "x"))
    )
    (Model_Specific
         (enable (Usage In) (Type Boolean) (Value True) (Description "Top-level flag."))
         (ctle_mode (Usage In) (Type Integer) (List 0 1 2) (Description "Prefix-grouped list."))
         (ctle_level (Usage InOut) (Type Float) (Range 0.5 0.0 1.0) (Description "Prefix-grouped range."))
         (dfe_out (Usage Out) (Type Float) (Value 0.0) (Description "Not configurable."))
         (tx_preset
             (Description "A described group.")
             (coeffs
                 (main (Usage In) (Type Float) (Range 0.5 0.0 1.0) (Description "Nested."))
             )
         )
    )
)
"""


def test_views_render(ibis_test_file):
    """Every viewer renders (offscreen), for Output and Input models, and the AMI configurator."""
    script = textwrap.dedent(f"""
        from pyibisami.ami.parser import AMIParamConfigurator
        from pyibisami.ibis.file import IBISModel
        from pyibisami.ibis.model import Model

        iv = [(0.0, (0.0, 0.0, 0.0)), (0.5, (0.01, 0.008, 0.012)), (1.0, (0.02, 0.016, 0.024))]
        input_model = Model({{"model_type": "Input", "voltage_range": [1.0, 0.9, 1.1],
                             "gnd_clamp": iv, "power_clamp": iv}})
        ibis = IBISModel({str(ibis_test_file)!r})
        for obj in [ibis, ibis.comp_, ibis.model, input_model, AMIParamConfigurator({AMI_CONTENTS!r})]:
            obj.edit_traits(kind="live").dispose()
        print("rendered")
    """)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    rslt = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, check=False)
    assert rslt.returncode == 0, rslt.stderr
    assert "rendered" in rslt.stdout
    assert "Traceback" not in rslt.stderr, rslt.stderr
