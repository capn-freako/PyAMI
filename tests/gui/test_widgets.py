"""Headless tests of the Qt widgets: widget edits reach the core object, and core changes reach the widgets."""

import json
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QLabel, QLineEdit, QWidget

from pyibisami.ami.configurator import AMIParamConfigurator
from pyibisami.gui import AmiParamEditor, IbisAmiBrowser, IbisBrowser, IbisSelector, IVPlot, VTPlot, ibis as gui_ibis
from pyibisami.gui.ami_config import RangeEditor, load_preset, save_preset
from pyibisami.gui.app import MainWindow
from pyibisami.gui.dialogs import edit_ami_params, select_ibis_model
from pyibisami.ibis.file import IBISModel

AMI = """(m
  (Reserved_Parameters
    (AMI_Version (Usage Info) (Type String) (Value "7.0"))
    (Init_Returns_Impulse (Usage Info) (Type Boolean) (Value True))
    (GetWave_Exists (Usage Info) (Type Boolean) (Value False)))
  (Model_Specific
    (gain (Usage In) (Type Float) (Range 0.5 0.0 1.0) (Description "Gain"))
    (taps (Usage In) (Type Integer) (Range 2 0 8))
    (mode (Usage In) (Type Integer) (List 0 1) (List_Tip "Off" "On"))
    (step (Usage In) (Type Float) (Increment 1.0 0.0 2.0 0.5))
    (en (Usage In) (Type Boolean) (Value True))
    (name (Usage In) (Type String) (Value "x"))
    (pvt (Usage In) (Type Float) (Corner 1.0 0.5 2.0))
    (dfe (-1 (Usage In) (Type Tap) (Range 0.0 -0.5 0.5)))
    (delay (Usage In) (Type Float) (Range 2e-12 1e-12 3e-12))))
"""


@pytest.fixture
def cfg():
    return AMIParamConfigurator(AMI)


@pytest.fixture
def editor(qtbot, cfg):
    widget = AmiParamEditor(cfg)
    qtbot.addWidget(widget)
    return widget


def test_one_editor_per_settable_parameter(editor, cfg):
    kinds = {path[-1]: type(editor.editor(path)) for path, _ in cfg.iter_settable()}
    assert kinds == {"gain": RangeEditor, "taps": RangeEditor, "mode": QComboBox, "step": QComboBox,
                     "en": QCheckBox, "name": QLineEdit, "-1": RangeEditor, "delay": RangeEditor}
    mode = editor.editor(("Model_Specific", "mode"))
    assert [mode.itemText(i) for i in range(mode.count())] == ["Off (0)", "On (1)"]


def test_widget_edit_sets_value(editor, cfg):
    mode = editor.editor(("Model_Specific", "mode"))
    mode.setCurrentIndex(1)
    mode.activated.emit(1)
    assert cfg.fetch_param_val(["Model_Specific", "mode"]) == 1
    editor.editor(("Model_Specific", "en")).setChecked(False)
    assert cfg.fetch_param_val(["Model_Specific", "en"]) is False


def test_tiny_float_range_edited_exactly(editor, cfg):
    """A Float Range in seconds (IBIS 8.0 p.269 example) is shown and set exactly; leaving it unchanged sets nothing."""
    path = ("Model_Specific", "delay")
    box = editor.editor(path).text
    assert box.text() == "2e-12"
    changes = []
    cfg.values_changed.connect(lambda *args: changes.append(args))
    box.editingFinished.emit()
    assert not changes
    box.setText("2.5e-12")
    box.editingFinished.emit()
    assert cfg.fetch_param_val(list(path)) == 2.5e-12


def test_range_editor_shows_bounds_and_slides(qtbot, editor, cfg):
    """As in 10.x: min, slider, max and text box; the tool tip stays the description. A drag is sent on release."""
    gain = editor.editor(("Model_Specific", "gain"))
    assert [label.text() for label in gain.findChildren(QLabel)] == ["0", "1"]
    assert gain.toolTip() == "Gain"
    assert gain.slider.value() == 5000 and gain.text.text() == "0.5"
    gain.slider.setSliderDown(True)
    gain.slider.setValue(7500)
    assert gain.text.text() == "0.75" and cfg.fetch_param_val(["Model_Specific", "gain"]) == 0.5  # Preview only.
    gain.slider.setSliderDown(False)  # Emits sliderReleased.
    assert cfg.fetch_param_val(["Model_Specific", "gain"]) == 0.75
    taps = editor.editor(("Model_Specific", "taps"))
    assert (taps.slider.minimum(), taps.slider.maximum()) == (0, 8)
    qtbot.keyClick(taps.slider, Qt.Key.Key_Right)  # A key moves it one value, sent at once.
    assert cfg.fetch_param_val(["Model_Specific", "taps"]) == 3


def test_illegal_value_reported_and_reverted(editor, cfg):
    editor._set(("Model_Specific", "gain"), 7.0)  # pylint: disable=protected-access  # As a stale widget could.
    assert "outside the Range" in editor.status.text()
    assert cfg.fetch_param_val(["Model_Specific", "gain"]) == 0.5


def test_core_change_shown(qtbot, editor, cfg):
    cfg.set_param_val(["Model_Specific", "taps"], 5)
    qtbot.waitUntil(lambda: editor.editor(("Model_Specific", "taps")).slider.value() == 5)


def test_change_from_another_thread_converges(qtbot, editor, cfg):
    """An optimizer thread's burst of changes is shown, coalesced, on the GUI thread."""
    def sweep():
        for taps in range(9):
            cfg.set_param_val(["Model_Specific", "taps"], taps)

    worker = threading.Thread(target=sweep)
    worker.start()
    worker.join()
    qtbot.waitUntil(lambda: editor.editor(("Model_Specific", "taps")).slider.value() == 8)


def test_corner_shown_read_only(qtbot, editor, cfg):
    cfg.sim_corner = "max"
    item = next(item for path, item in editor._fixed_items if path[-1] == "pvt")  # pylint: disable=protected-access
    qtbot.waitUntil(lambda: item.text(1) == "2.0")


def test_preset_round_trip(tmp_path, cfg):
    cfg.set_param_val(["Model_Specific", "taps"], 7)
    file = tmp_path / "preset.json"
    save_preset(cfg, file)
    assert json.loads(file.read_text())["values"]["Model_Specific/taps"] == 7
    other = AMIParamConfigurator(AMI)
    assert load_preset(other, file) == []
    assert other.fetch_param_val(["Model_Specific", "taps"]) == 7


def test_selector_follows_core_and_widget(qtbot, ibis_test_file):
    ibis = IBISModel(ibis_test_file)
    selector = IbisSelector(ibis)
    qtbot.addWidget(selector)
    selector.pin_box.activated.emit(2)
    assert ibis.pin_name == ibis.pin_choices[2]
    ibis.pin_name = ibis.pin_choices[4]
    qtbot.waitUntil(lambda: selector.pin_box.currentText() == ibis.pin_choices[4])


def test_selector_type_to_filter(qtbot, ibis_test_file):
    """Typing filters a box's choices (any part, any case); a complete name selects; a partial one is undone."""
    ibis = IBISModel(ibis_test_file)
    selector = IbisSelector(ibis)
    qtbot.addWidget(selector)
    completer = selector.pin_box.completer()
    completer.setCompletionPrefix("3P")
    assert completer.currentCompletion() == "3p(Tx_3_P)"
    completer.activated.emit("3p(Tx_3_P)")
    assert ibis.pin_name == "3p(Tx_3_P)"
    selector.pin_box.lineEdit().setText("3")
    selector.pin_box.lineEdit().editingFinished.emit()
    assert ibis.pin_name == "3p(Tx_3_P)" and selector.pin_box.currentText() == "3p(Tx_3_P)"


def test_browser_shows_pin_and_model(qtbot, ibis_test_file):
    ibis = IBISModel(ibis_test_file)
    browser = IbisBrowser(ibis)
    qtbot.addWidget(browser)
    assert browser.info.values["Model_type"].text() == "Output"
    assert browser.info.values["Signal"].text() == ibis.pin.signal
    ibis.pin_name = ibis.pin_choices[3]
    qtbot.waitUntil(lambda: browser.info.values["Signal"].text() == ibis.pin.signal)
    assert browser.visible_tabs() == ["Pulldown", "Pullup"]  # No V-T tables: their tabs are hidden.
    assert len(browser.pulldown_plot.shown_labels) == len(browser.pullup_plot.shown_labels) == 3


def test_ami_status_check(qtbot, ibis_test_file, tmp_path):
    """A check for an executable for this platform that's there; a warning sign if it's listed but missing."""
    import shutil  # pylint: disable=import-outside-toplevel
    import platform  # pylint: disable=import-outside-toplevel

    ibis = IBISModel(ibis_test_file)
    info = gui_ibis.ModelInfo()
    qtbot.addWidget(info)
    if not ibis.dll_file:
        pytest.skip(f"No example executable for {platform.system()}")
    info.set_model(ibis.model, ibis.pin, ibis.dll_path)
    assert "file not found" in info.ami_status.text()
    shutil.copy(ibis_test_file, tmp_path / ibis.dll_file)
    info.set_model(ibis.model, ibis.pin, tmp_path / ibis.dll_file)
    assert "&#10003;" in info.ami_status.text()
    assert ibis.dll_file in info.ami_status.toolTip()


WAVEFORMS = """
[Rising Waveform]
R_fixture = 50
V_fixture = 0.0
   0.0     0.0     NA      0.0
   1n      0.9     NA      1.0
[Falling Waveform]
R_fixture = 50
V_fixture = 1.8
   0.0     1.8     1.62    1.98
   1n      0.9     0.8     1.0
"""


def test_vt_tabs_and_corner_toggles(qtbot, ibis_test_file):
    text = ibis_test_file.read_text(encoding="utf-8").replace("[END]", WAVEFORMS + "\n[END]")
    browser = IbisBrowser(IBISModel.from_text(text))
    qtbot.addWidget(browser)
    assert browser.visible_tabs() == ["Pulldown", "Pullup", "Rising", "Falling"]
    rising, falling = browser.rising_plot, browser.falling_plot
    assert (len(rising.shown_labels), len(falling.shown_labels)) == (2, 3)  # The rising min is all NA.
    assert rising.shown_labels[0] == "50 Ohm to 0 V (typ)"
    falling.corner_boxes["typ"].setChecked(False)
    assert not any(label.endswith("(typ)") for label in falling.shown_labels)



def test_iv_plot_marks_rails(qtbot, ibis_test_file):
    """A Vcc line per shown corner, in its line style; none in the legend or ``shown_labels``."""
    iv = IBISModel(ibis_test_file).model.iv_data
    plot = IVPlot(iv, keyword="pullup")
    qtbot.addWidget(plot)
    vcc_lines = {str(line.get_label()): line for line in plot.axes.get_lines() if str(line.get_label()).startswith("_vcc")}
    assert {name: line.get_xdata()[0] for name, line in vcc_lines.items()} == pytest.approx(
        {"_vcc_typ": 1.8, "_vcc_min": 1.62, "_vcc_max": 1.98})
    assert plot.shown_labels == ["typ", "min", "max"]
    assert [t.get_text() for t in plot.axes.get_legend().get_texts()] == ["typ", "min", "max"]
    plot.corner_boxes["min"].setChecked(False)
    assert "_vcc_min" not in {str(line.get_label()) for line in plot.axes.get_lines()}


def test_iv_plot_without_data(qtbot):
    plot = IVPlot(None)
    qtbot.addWidget(plot)
    assert not plot.shown_labels and not plot.has_data


def test_show_alerts_pops_up_once(qtbot, ibis_test_file, monkeypatch):
    shown = []
    monkeypatch.setattr(gui_ibis.QMessageBox, "information", lambda parent, title, msg: shown.append(msg))
    ibis = IBISModel(ibis_test_file)
    gui_ibis.show_alerts(ibis)
    gui_ibis.show_alerts(ibis)
    ibis._announce_model()  # pylint: disable=protected-access
    assert not shown  # Queued: never inside the change that fired it.
    qtbot.waitUntil(lambda: len(shown) == 1)


def test_show_alerts_follows_the_latest_parent(qtbot, ibis_test_file, monkeypatch):
    """A repeat call moves the pop-ups to the new parent; a destroyed parent is forgotten, not used."""
    parents = []
    monkeypatch.setattr(gui_ibis.QMessageBox, "information", lambda parent, title, msg: parents.append(parent))
    ibis = IBISModel(ibis_test_file)
    first, second = QWidget(), QWidget()
    gui_ibis.show_alerts(ibis, first)
    gui_ibis.show_alerts(ibis, second)
    ibis._announce_model()  # pylint: disable=protected-access
    qtbot.waitUntil(lambda: parents == [second])
    second.deleteLater()
    qtbot.waitUntil(lambda: gui_ibis._POPUPS[ibis].parent_widget is None)  # pylint: disable=protected-access
    first.deleteLater()


def test_dialog_freed_after_closing(qtbot, monkeypatch, cfg):
    """A dialog with a parent is deleted after ``exec()``, so it stops listening to the configurator."""
    parent = QWidget()
    qtbot.addWidget(parent)
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    assert edit_ami_params(cfg, parent)
    qtbot.waitUntil(lambda: not parent.findChildren(QDialog))
    assert not len(cfg.values_changed)


def test_cancel_undoes_ami_edits(monkeypatch, cfg):
    """As in 10.x: Cancel puts back the values (and corner) the dialog opened with."""
    def edit_then_cancel(self):
        cfg.set_param_val(["Model_Specific", "taps"], 7)
        cfg.sim_corner = "max"
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", edit_then_cancel)
    assert not edit_ami_params(cfg)
    assert cfg.fetch_param_val(["Model_Specific", "taps"]) == 2 and cfg.sim_corner == "typ"


def test_cancel_undoes_ibis_selection(monkeypatch, ibis_test_file):
    ibis = IBISModel(ibis_test_file)
    before = (ibis.component_name, ibis.pin_name, ibis.model_name)

    def pick_then_cancel(self):
        ibis.pin_name = ibis.pin_choices[1]
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", pick_then_cancel)
    assert not select_ibis_model(ibis)
    assert (ibis.component_name, ibis.pin_name, ibis.model_name) == before


def test_model_info_shows_component(qtbot, ibis_test_file):
    """As in 10.x's component view: the component's Manufacturer and Package."""
    ibis = IBISModel(ibis_test_file)
    browser = IbisBrowser(ibis)
    qtbot.addWidget(browser)
    assert browser.info.values["Manufacturer"].text() == ibis.component.manufacturer
    assert browser.info.values["Package"].text().splitlines()[0] == "R_pkg: 0.1 / 0 / 0.5 Ω"


def test_load_preset_rejects_other_json(tmp_path, cfg):
    file = tmp_path / "not_a_preset.json"
    file.write_text(json.dumps({"values": [1, 2]}), encoding="utf-8")
    with pytest.raises(TypeError, match="Not an AMI preset"):
        load_preset(cfg, file)


CLAMPS = """
[GND Clamp]
  -1.8   -0.1   NA   NA
   0.0    0.0   NA   NA
[POWER Clamp]
  -1.8    0.1   NA   NA
   0.0    0.0   NA   NA
"""


def test_driver_clamp_tabs(qtbot, ibis_test_file):
    """A driver's clamp tables get their own tabs (they used to be shown only for receivers)."""
    text = ibis_test_file.read_text(encoding="utf-8").replace("[Ramp]", CLAMPS + "[Ramp]", 1)
    browser = IbisBrowser(IBISModel.from_text(text))
    qtbot.addWidget(browser)
    assert browser.visible_tabs() == ["Pulldown", "Pullup", "GND Clamp", "POWER Clamp"]
    assert browser.gnd_clamp_plot.shown_labels == ["typ"]


def test_app_opens_ibis_and_ami(qtbot, ibis_test_file, ami_test_file, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.open_file(ibis_test_file)
    assert window.browser.visible_tabs() == ["Pulldown", "Pullup", "AMI parameters", "Warnings"]
    assert [a.text() for a in window.menuBar().actions()] == ["&File", "&Tools"]
    assert window.ibis_path == ibis_test_file and window.open_ibis_action.isEnabled()
    assert not window.open_ami_action.isEnabled()  # Its .ami file isn't next to it.
    assert "Success!" in window.warnings.toPlainText()
    assert window.open_file(ami_test_file)
    assert isinstance(window.centralWidget().widget(0), AmiParamEditor)
    assert window.ami_path == ami_test_file and window.open_ami_action.isEnabled()
    opened = []
    monkeypatch.setattr("pyibisami.gui.app.open_in_text_editor", opened.append)
    window.open_ami_action.trigger()
    assert opened == [ami_test_file]
    monkeypatch.setattr("pyibisami.gui.app.QMessageBox.critical", lambda *args: None)
    bad = ibis_test_file.with_name("bad.ibs")
    bad.write_text("not IBIS", encoding="utf-8")
    assert not window.open_file(bad)
    assert isinstance(window.centralWidget().widget(0), AmiParamEditor)  # The previous file stays shown.


def test_ibis_ami_browser_embeds(qtbot, ibis_test_file, ami_test_file):
    """``IbisAmiBrowser`` is a plain widget: the selected model's AMI editor and warnings as tabs, and its
    ``configurator`` for the application (e.g. - PyBERT) to simulate with."""
    ibis = IBISModel(ibis_test_file)
    if ibis.ami_path is None:
        pytest.skip("No example executable for this platform")
    ibis.ami_path.write_text(ami_test_file.read_text(encoding="utf-8"), encoding="utf-8")
    host = QWidget()
    qtbot.addWidget(host)
    browser = IbisAmiBrowser(ibis, host)
    assert browser.visible_tabs() == ["Pulldown", "Pullup", "AMI parameters", "Warnings"]
    cfg = browser.configurator
    assert cfg is not None and cfg.root_name
    titles = [browser.tabs.tabText(i) for i in range(browser.tabs.count())]
    editor = browser.tabs.widget(titles.index("AMI parameters"))
    assert isinstance(editor, AmiParamEditor) and editor.configurator is cfg
    assert "Success!" in browser.warnings.toPlainText()
    with qtbot.assertNotEmitted(browser.amiChanged):
        ibis.pin_name = ibis.pin_choices[1]  # Same model: same configurator, editor kept.
        qtbot.waitUntil(lambda: browser.info.values["Signal"].text() == ibis.pin.signal)
    assert browser.configurator is cfg
