import logging
import platform

import pytest
from traits.api import TraitError

from pyibisami.ibis.file import RX_MODEL_TYPES, TX_MODEL_TYPES, IBISModel


def test_ibis_model_construction(ibis_test_file):
    """IBISModel should construct without error from a valid IBIS file.

    Regression test: construction previously crashed with an `AttributeError`
    (`datetime.timezone` doesn't exist on the `datetime.datetime` class)
    while time-stamping its own log messages.
    """
    model = IBISModel(ibis_test_file)
    assert model.file_name == "example_tx.ibs"


def test_alerts_are_logged_and_fired(ibis_test_file, caplog):
    """User-facing notices go to the logger and the ``alert`` event; no GUI involved."""
    with caplog.at_level(logging.INFO, logger="pyibisami.ibis.file"):
        model = IBISModel(ibis_test_file)
    assert [rec.levelno for rec in caplog.records if "Model `example_tx`" in rec.getMessage()] == [logging.INFO]

    fired = []
    model.observe(lambda event: fired.append(event.new), "alert")
    model._mod_changed(model.mod)  # pylint: disable=protected-access
    assert len(fired) == 1 and "Model `example_tx`" in fired[0]


def test_show_alerts_pops_up_once(ibis_test_file, monkeypatch):
    pytest.importorskip("traitsui")
    from pyibisami.gui import ibis as gui_ibis

    shown = []
    monkeypatch.setattr(gui_ibis, "message", lambda msg, title: shown.append(msg))
    model = IBISModel(ibis_test_file)
    gui_ibis.show_alerts(model)
    gui_ibis.show_alerts(model)
    model._mod_changed(model.mod)  # pylint: disable=protected-access
    assert len(shown) == 1


def test_component_pin_selection(ibis_test_file):
    """``Component.pin`` defaults to the first pin, and follows the selected pin."""
    comp = IBISModel(ibis_test_file).comp_
    first, last = list(comp.pins)[0], list(comp.pins)[-1]
    assert comp.pin == comp.pins[first]
    comp._pin = last  # pylint: disable=protected-access  # The trait the Component view edits.
    assert comp.pin == comp.pins[last]


MIXED_IBIS = r"""[IBIS Ver]   5.1
[File Name]  mixed.ibs
[File Rev]   v0.1

[Component]    Mixed
[Manufacturer] (n/a)

[Package]
R_pkg     0.10     0.00     0.50
L_pkg    10.00n    0.10n   50.00n
C_pkg     1.00p    0.01p    5.00p

[Pin]  signal_name        model_name
1      VDD                POWER
2      VSS                GND
3      Mystery            no_such_model
4      Tx_P               example_tx
5      Rx_P               example_rx
6      IO_P               example_io
7      Spare              NC
8      OE_P               example_3state
9      Term               example_term
10     Circ               CIRCUITCALL
11     Sel_P              sel_bad

[Model]   example_tx
Model_type   Output
Vmeas = 0.5

[Temperature_Range]     25.0      0.0    100.0
[Voltage_Range]         1.80     1.62     1.98

[Pulldown]
-1.80    -1.000e+01    -1.000e+01    -1.000e+01
0.00     0.000e+00     0.000e+00     0.000e+00
1.80     3.600e-02     4.000e-02     3.273e-02
3.60     1.000e+01     1.000e+01     1.000e+01

[Pullup]
-1.80    1.000e+01     1.000e+01     1.000e+01
0.00     -0.000e+00    -0.000e+00    -0.000e+00
1.80     -3.600e-02    -4.000e-02    -3.273e-02
3.60     -1.000e+01    -1.000e+01    -1.000e+01

[Ramp]
dV/dt_r    0.540/108.00p    0.512/511.58p    0.566/56.57p
dV/dt_f    0.540/108.00p    0.512/511.58p    0.566/56.57p

[Model]   example_rx
Model_type   Input
Vmeas = 0.5

[Temperature_Range]     25.0      0.0    100.0
[Voltage_Range]         1.80     1.62     1.98

[GND Clamp]
-1.80    -1.000e+01    -1.000e+01    -1.000e+01
0.00     0.000e+00     0.000e+00     0.000e+00
1.80     3.600e-02     4.000e-02     3.273e-02

[POWER Clamp]
-1.80    1.000e+01     1.000e+01     1.000e+01
0.00     -0.000e+00    -0.000e+00    -0.000e+00
1.80     -3.600e-02    -4.000e-02    -3.273e-02

[Model]   example_io
Model_type   I/O
Vmeas = 0.5

[Temperature_Range]     25.0      0.0    100.0
[Voltage_Range]         1.80     1.62     1.98

[Pulldown]
-1.80    -1.000e+01    -1.000e+01    -1.000e+01
0.00     0.000e+00     0.000e+00     0.000e+00
1.80     3.600e-02     4.000e-02     3.273e-02
3.60     1.000e+01     1.000e+01     1.000e+01

[Pullup]
-1.80    1.000e+01     1.000e+01     1.000e+01
0.00     -0.000e+00    -0.000e+00    -0.000e+00
1.80     -3.600e-02    -4.000e-02    -3.273e-02
3.60     -1.000e+01    -1.000e+01    -1.000e+01

[Ramp]
dV/dt_r    0.540/108.00p    0.512/511.58p    0.566/56.57p
dV/dt_f    0.540/108.00p    0.512/511.58p    0.566/56.57p

[Model]   example_3state
Model_type   3-state
Vmeas = 0.5

[Temperature_Range]     25.0      0.0    100.0
[Voltage_Range]         1.80     1.62     1.98

[Model]   example_term
Model_type   Terminator

[Temperature_Range]     25.0      0.0    100.0
[Voltage_Range]         1.80     1.62     1.98

[Model Selector] sel_bad
example_tx      Defined model
no_such_model   Undefined model

[END]
"""


def test_get_pins_qualified(ibis_test_file):
    """All 6 pins of the fixture use an ``Output`` model, so they're all Tx."""
    model = IBISModel(ibis_test_file)
    all_pins = model.get_pins()
    assert len(all_pins) == 6
    assert model.get_pins_qualified(True) == all_pins
    assert model.get_pins_qualified(False) == []
    assert model.get_pins_qualified(True, comp_name="Example_Tx") == all_pins
    with pytest.raises(ValueError, match="Example_Tx"):
        model.get_pins_qualified(True, comp_name="No_Such_Comp")


@pytest.fixture
def mixed_ibis_file(tmp_path):
    """An IBIS file whose component leads with ``POWER``/``GND`` pins and a pin naming an undefined model."""
    ibis_file = tmp_path / "mixed.ibs"
    ibis_file.write_text(MIXED_IBIS, encoding="utf-8")
    return str(ibis_file)


def test_pin_selection_skips_modelless_pins(mixed_ibis_file):
    """Pins without a model aren't selectable, so loading doesn't crash on a leading one.

    The parser drops ``POWER``/``GND``/``NC``/``CIRCUITCALL`` pins; a pin naming an undefined model used to raise
    ``IndexError``.
    """
    model = IBISModel(mixed_ibis_file)
    assert "10(Circ)" not in model.get_pins()
    assert model.pins == ["4(Tx_P)", "5(Rx_P)", "6(IO_P)", "8(OE_P)", "9(Term)", "11(Sel_P)"]
    assert model.pin == "4(Tx_P)" and model.mod == "example_tx"
    model.pin = "5(Rx_P)"
    assert model.mod == "example_rx"


def test_get_pins_qualified_mixed(mixed_ibis_file):
    """Tx/Rx pins follow IBIS Table 47: ``I/O`` is both, ``Terminator`` neither; pins without a model are skipped."""
    model = IBISModel(mixed_ibis_file)
    assert model.get_pins_qualified(True) == ["4(Tx_P)", "6(IO_P)", "8(OE_P)", "11(Sel_P)"]
    assert model.get_pins_qualified(False) == ["5(Rx_P)", "6(IO_P)"]


def test_model_selector_skips_undefined_models(mixed_ibis_file):
    """A model selector entry naming an undefined model is dropped, rather than crashing selection."""
    model = IBISModel(mixed_ibis_file)
    assert model.get_model_names("sel_bad") == ["example_tx"]
    model.pin = "11(Sel_P)"
    assert model.models == ["example_tx"]
    assert model.model.mtype.lower() == "output"


BROKEN_COMPONENT = r"""[Component]    Broken
[Manufacturer] (n/a)

[Package]
R_pkg     0.10     0.00     0.50
L_pkg    10.00n    0.10n   50.00n
C_pkg     1.00p    0.01p    5.00p

[Pin]  signal_name        model_name
1      Mystery            no_such_model

"""


def test_unusable_component_not_selectable(tmp_path, caplog):
    """A leading component with no usable pins is skipped for selection; the file still loads."""
    ibis_file = tmp_path / "broken_first.ibs"
    ibis_file.write_text(MIXED_IBIS.replace("[Component]    Mixed", BROKEN_COMPONENT + "[Component]    Mixed"),
                         encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="pyibisami.ibis.file"):
        model = IBISModel(str(ibis_file))
    assert "Broken" in caplog.text
    assert model.comp == "Mixed" and model.pin == "4(Tx_P)"
    with pytest.raises(TraitError):
        model.comp = "Broken"
    assert model.get_pins_qualified(True, comp_name="Broken") == []


def test_no_usable_component(tmp_path):
    """Loading fails only when no component has a pin with a defined model."""
    ibis_file = tmp_path / "all_broken.ibs"
    header = MIXED_IBIS[:MIXED_IBIS.index("[Component]")]
    models = MIXED_IBIS[MIXED_IBIS.index("[Model]"):]
    ibis_file.write_text(header + BROKEN_COMPONENT + models, encoding="utf-8")
    with pytest.raises(ValueError, match="No component"):
        IBISModel(str(ibis_file))


RX_ONLY_COMPONENT = BROKEN_COMPONENT.replace("Broken", "RxOnly").replace("Mystery            no_such_model",
                                                                          "Rx_Q               example_rx")


@pytest.mark.parametrize("model_types, pins", [
    (TX_MODEL_TYPES, ["4(Tx_P)", "6(IO_P)", "8(OE_P)", "11(Sel_P)"]),
    (RX_MODEL_TYPES, ["5(Rx_P)", "6(IO_P)", "11(Sel_P)"]),
    ({"Output", "I/O"}, ["4(Tx_P)", "6(IO_P)", "11(Sel_P)"]),  # Any case.
])
def test_model_types_restrict_pins_and_models(tmp_path, model_types, pins):
    """Only pins with a model of an allowed type are offered, and only those models (``sel_mixed``: Tx and Rx)."""
    ibis_file = tmp_path / "sel_mixed.ibs"
    ibis_file.write_text(MIXED_IBIS.replace("no_such_model   Undefined model", "example_rx      Rx model"),
                         encoding="utf-8")
    ibis = IBISModel(str(ibis_file), model_types=model_types)
    assert ibis.pins == pins
    allowed = {mtype.lower() for mtype in model_types}
    for pin in pins:
        ibis.pin = pin
        assert ibis.models and all(ibis.get_model(name).mtype.lower() in allowed for name in ibis.models)
        assert ibis.model.mtype.lower() in allowed


def test_model_types_skip_components(tmp_path, caplog):
    """A component with no pin of an allowed type isn't offered; loading fails only when none is."""
    ibis_file = tmp_path / "rx_only_first.ibs"
    ibis_file.write_text(MIXED_IBIS.replace("[Component]    Mixed", RX_ONLY_COMPONENT + "[Component]    Mixed"),
                         encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="pyibisami.ibis.file"):
        ibis = IBISModel(str(ibis_file), model_types=TX_MODEL_TYPES)
    assert "RxOnly" in caplog.text
    assert ibis.comps == ["Mixed"] and ibis.comp == "Mixed"
    with pytest.raises(TraitError):
        ibis.comp = "RxOnly"
    with pytest.raises(ValueError, match=r"Mixed.*Model_types found: \['3-state', 'I/O', 'Input', 'Output'"):
        IBISModel(str(ibis_file), model_types={"Series"})


def test_model_types_changed_after_loading(tmp_path):
    """Changing ``model_types`` keeps each selection that's still offered, moves the others, and never raises."""
    ibis_file = tmp_path / "rx_only_first.ibs"
    ibis_file.write_text(MIXED_IBIS.replace("[Component]    Mixed", RX_ONLY_COMPONENT + "[Component]    Mixed"),
                         encoding="utf-8")
    ibis = IBISModel(str(ibis_file))
    fired = []
    ibis.observe(lambda event: fired.append(event.new), "alert")
    ibis.comp = "Mixed"
    ibis.pin = "5(Rx_P)"

    ibis.model_types = TX_MODEL_TYPES  # Rx pin no longer offered: move to the first Tx one.
    assert ibis.comps == ["Mixed"] and ibis.pin == "4(Tx_P)" and ibis.mod == "example_tx"
    assert "example_tx" in fired[-1]

    ibis.pin = "6(IO_P)"
    ibis.model_types = RX_MODEL_TYPES  # I/O pin still offered: keep it.
    assert ibis.comps == ["RxOnly", "Mixed"] and ibis.comp == "Mixed" and ibis.pin == "6(IO_P)"

    ibis.model_types = {"Series"}  # Nothing to offer: undo the change, keep the selection, and say so.
    assert ibis.comps == ["RxOnly", "Mixed"] and ibis.pin == "6(IO_P)" and ibis.mod == "example_io"
    assert "No component" in fired[-1]
    assert ibis.model_types == RX_MODEL_TYPES
    ibis.pin = "5(Rx_P)"  # Later selections still work (they used to hit the empty filter).
    assert ibis.mod == "example_rx"
    ibis.comp = "RxOnly"
    assert ibis.pins == ["1(Rx_Q)"] and ibis.mod == "example_rx"

    ibis.model_types = None
    ibis.comp = "Mixed"
    assert ibis.pins == ["4(Tx_P)", "5(Rx_P)", "6(IO_P)", "8(OE_P)", "9(Term)", "11(Sel_P)"]


SAME_PIN_COMPONENT = BROKEN_COMPONENT.replace("Broken", "Second").replace("1      Mystery            no_such_model",
                                                                          "4      Tx_P               example_rx")


def test_component_change_with_same_pin_name(tmp_path):
    """A new component whose first pin has the current pin's name still gets its own model."""
    ibis_file = tmp_path / "same_pin.ibs"
    ibis_file.write_text(MIXED_IBIS.replace("[Model]   example_tx", SAME_PIN_COMPONENT + "[Model]   example_tx", 1),
                         encoding="utf-8")
    ibis = IBISModel(str(ibis_file))
    assert (ibis.comp, ibis.pin, ibis.mod) == ("Mixed", "4(Tx_P)", "example_tx")
    ibis.comp = "Second"
    assert (ibis.pin, ibis.models, ibis.mod) == ("4(Tx_P)", ["example_rx"], "example_rx")


@pytest.mark.parametrize("model_types", ["Output", 5])
def test_model_types_must_be_a_collection(ibis_test_file, model_types):
    """A single string would be read one character at a time; it's rejected, like a non-collection."""
    with pytest.raises(TraitError):
        IBISModel(ibis_test_file, model_types=model_types)


def test_model_types_from_a_generator(mixed_ibis_file):
    """``model_types`` is read once, so a generator works for every pin."""
    ibis = IBISModel(mixed_ibis_file, model_types=(t for t in ("Output", "I/O")))
    assert ibis.pins == ["4(Tx_P)", "6(IO_P)", "11(Sel_P)"]
    assert ibis.model_types == {"output", "i/o"}


def test_old_is_tx_argument_rejected(ibis_test_file):
    """The pre-10.0 positional ``is_tx`` isn't silently misread."""
    with pytest.raises(TypeError):
        IBISModel(ibis_test_file, True)  # pylint: disable=too-many-function-args


def test_views_are_application_neutral(ibis_test_file):
    pytest.importorskip("traitsui")
    pytest.importorskip("chaco")
    from pyibisami.gui import ibis as gui_ibis

    ibis = IBISModel(ibis_test_file)
    views = [gui_ibis.make_ibis_file_view(ibis), gui_ibis.make_component_view(ibis.comp_),
             gui_ibis.make_model_view(ibis.model)]
    assert not [view for view in views if "pybert" in f"{view.title} {view.id}".lower()]


def _set_platform(monkeypatch, system, bits):
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(platform, "architecture", lambda *args, **kwargs: (bits, ""))


@pytest.mark.parametrize("system, bits, files", [
    ("Windows", "64bit", ("example_tx_x86_amd64.dll", "example_tx.ami")),
    ("Windows", "32bit", ("example_tx_x86.dll", "example_tx.ami")),
    ("Linux", "64bit", ("example_tx_x86_amd64.so", "example_tx.ami")),
    ("Linux", "32bit", ("example_tx_x86.so", "example_tx.ami")),
])
def test_model_executable_for_platform(ibis_test_file, monkeypatch, system, bits, files):
    """``Model`` resolves its own executable for the running platform, without going through ``IBISModel.mod``."""
    model = IBISModel(ibis_test_file).model_dict["models"]["example_tx"]
    _set_platform(monkeypatch, system, bits)
    assert (model.dll_file, model.ami_file) == files


def test_model_without_algorithmic_model_has_no_executable(mixed_ibis_file):
    model = IBISModel(mixed_ibis_file).model_dict["models"]["example_rx"]
    assert (model.dll_file, model.ami_file) == ("", "")


TX_ALGO_MODEL = """Model_type   Output
[Algorithmic Model]
Executable linux_gcc4.1.2_64          example_tx_x86_amd64.so   example_tx.ami
[End Algorithmic Model]
"""


def test_ibis_model_executable_follows_selected_model(tmp_path, monkeypatch, caplog):
    """``IBISModel.dll_file``/``ami_file`` are the selected model's, and follow a change of ``mod``."""
    _set_platform(monkeypatch, "Linux", "64bit")
    ibis_file = tmp_path / "mixed_ami.ibs"
    ibis_file.write_text(MIXED_IBIS.replace("Model_type   Output\n", TX_ALGO_MODEL, 1), encoding="utf-8")
    caplog.set_level(logging.INFO, logger="pyibisami.ibis.file")  # For the whole test (notices follow selection).
    ibis = IBISModel(str(ibis_file))
    assert ibis.mod == "example_tx"
    assert (ibis.dll_file, ibis.ami_file) == ("example_tx_x86_amd64.so", "example_tx.ami")
    assert ibis.dll_path == tmp_path / "example_tx_x86_amd64.so" and ibis.ami_path == tmp_path / "example_tx.ami"
    assert "has an AMI executable for this platform: example_tx_x86_amd64.so" in caplog.text
    ibis.pin = "5(Rx_P)"
    assert ibis.mod == "example_rx"
    assert (ibis.dll_file, ibis.ami_file) == (ibis.model.dll_file, ibis.model.ami_file) == ("", "")
    assert ibis.dll_path is None and ibis.ami_path is None
    _set_platform(monkeypatch, "Windows", "64bit")
    ibis.pin = "4(Tx_P)"
    assert ibis.dll_file == ""
    assert "but no executable for this platform: Windows-64bit" in caplog.text


IO_BOTH_ALGO_MODEL = """Model_type   I/O
[Algorithmic Model]
Executable_Tx linux_gcc4.1.2_64        io_tx.so    io_tx.ami
Executable_Rx linux_gcc4.1.2_64        io_rx.so    io_rx.ami
Executable_Tx Windows_VisualStudio_64  io_tx.dll   io_tx.ami
[End Algorithmic Model]
"""


def _io_ibis_file(tmp_path, algo_model):
    "``MIXED_IBIS`` with ``algo_model`` (starting with its ``Model_type`` line) given to ``example_io``."
    ibis_file = tmp_path / "io_ami.ibs"
    ibis_file.write_text(MIXED_IBIS.replace("Model_type   I/O\n", algo_model, 1), encoding="utf-8")
    return str(ibis_file)


def test_io_model_with_both_directions(tmp_path, monkeypatch):
    """An ``I/O`` model's Tx and Rx files are both reachable; the direction is the caller's choice."""
    model = IBISModel(_io_ibis_file(tmp_path, IO_BOTH_ALGO_MODEL)).model_dict["models"]["example_io"]
    assert model.is_io
    assert [ex.direction for ex in model.ami_executables] == ["tx", "rx", "tx"]
    assert model.executables[1] == (("linux", "64"), ["io_rx.so", "io_rx.ami"])  # Shape used by Executable_index.
    assert "Executable_Rx" in str(model) and "io_rx.so" in str(model)

    _set_platform(monkeypatch, "Linux", "64bit")
    assert model.get_ami_files(is_tx=True) == ("io_tx.so", "io_tx.ami")
    assert model.get_ami_files(is_tx=False) == ("io_rx.so", "io_rx.ami")
    with pytest.raises(ValueError, match=r"get_ami_files\(is_tx\)"):
        model.get_ami_files()
    assert (model.dll_file, model.ami_file) == ("io_tx.so", "io_tx.ami")  # Direction-blind: first listed.

    _set_platform(monkeypatch, "Windows", "64bit")  # Only a Tx entry for this platform.
    assert model.get_ami_files() == model.get_ami_files(is_tx=True) == ("io_tx.dll", "io_tx.ami")
    assert model.get_ami_files(is_tx=False) == ("", "")


@pytest.mark.parametrize("keyword, tx_files, rx_files", [
    ("Executable_Rx", ("", ""), ("io.so", "io.ami")),
    ("Executable", ("io.so", "io.ami"), ("io.so", "io.ami")),  # Illegal for I/O, but tolerated for either direction.
])
def test_io_model_with_one_direction(tmp_path, monkeypatch, keyword, tx_files, rx_files):
    algo_model = ("Model_type   I/O\n[Algorithmic Model]\n"
                  f"{keyword} linux_gcc4.1.2_64  io.so  io.ami\n[End Algorithmic Model]\n")
    model = IBISModel(_io_ibis_file(tmp_path, algo_model)).model_dict["models"]["example_io"]
    _set_platform(monkeypatch, "Linux", "64bit")
    assert model.get_ami_files() == ("io.so", "io.ami")
    assert model.get_ami_files(is_tx=True) == tx_files
    assert model.get_ami_files(is_tx=False) == rx_files


@pytest.mark.parametrize("model_name, model_type, files_none, files_tx, files_rx", [
    ("example_tx", "Output", ("m.so", "m.ami"), ("m.so", "m.ami"), ("", "")),
    ("example_rx", "Input", ("m.so", "m.ami"), ("", ""), ("m.so", "m.ami")),
    ("example_term", "Terminator", ("m.so", "m.ami"), ("", ""), ("", "")),
])
def test_non_io_model_direction_follows_model_type(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    tmp_path, monkeypatch, model_name, model_type, files_none, files_tx, files_rx
):
    algo_model = (f"Model_type   {model_type}\n[Algorithmic Model]\n"
                  "Executable linux_gcc4.1.2_64  m.so  m.ami\n[End Algorithmic Model]\n")
    ibis_file = tmp_path / "non_io.ibs"
    ibis_file.write_text(MIXED_IBIS.replace(f"Model_type   {model_type}\n", algo_model, 1), encoding="utf-8")
    model = IBISModel(str(ibis_file)).model_dict["models"][model_name]
    _set_platform(monkeypatch, "Linux", "64bit")
    assert not model.is_io
    assert model.get_ami_files() == files_none
    assert model.get_ami_files(is_tx=True) == files_tx
    assert model.get_ami_files(is_tx=False) == files_rx


def test_ibis_model_ambiguous_io_direction_warns_once(tmp_path, monkeypatch, caplog):
    """``IBISModel`` stays Tx/Rx-unaware: first listed entry, plus one warning on selecting the model."""
    _set_platform(monkeypatch, "Linux", "64bit")
    ibis = IBISModel(_io_ibis_file(tmp_path, IO_BOTH_ALGO_MODEL))
    with caplog.at_level(logging.WARNING, logger="pyibisami.ibis.file"):
        ibis.pin = "6(IO_P)"
        assert ibis.mod == "example_io"
        assert (ibis.dll_file, ibis.ami_file) == ("io_tx.so", "io_tx.ami")
        assert ibis.dll_path == tmp_path / "io_tx.so"
    warnings = [rec for rec in caplog.records if "get_ami_files(is_tx)" in rec.getMessage()]
    assert [rec.levelno for rec in warnings] == [logging.WARNING]


def test_files_resolve_against_ibis_dir(ibis_test_file, tmp_path, monkeypatch):
    """Files named in the IBIS file resolve against its directory, not the working directory."""
    monkeypatch.chdir(tmp_path.parent)
    ibis = IBISModel(tmp_path.name + "/" + ibis_test_file.name)  # A relative IBIS file name.
    assert ibis.ibis_dir == tmp_path
    assert ibis.resolve_file("sub/model.ami") == tmp_path / "sub" / "model.ami"
    assert ibis.resolve_file("") is None
