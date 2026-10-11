import pytest

from pyibisami.ibis.parser import parse_ibis_file


def test_parse_ibis_file_with_ideal_file(ibis_test_file):
    """Test that pyibisami can parse the template 5.1 ibis model file."""
    with open(ibis_test_file) as in_file:
        ibis_file_contents = in_file.read()
    status_string, ibis_dictionary = parse_ibis_file(ibis_file_contents)
    assert status_string == "Success!"
    assert ibis_dictionary["file_name"] == "example_tx.ibs"
    assert ibis_dictionary["file_rev"] == "v0.1"
    assert ibis_dictionary["ibis_ver"] == 5.1


def test_parse_ibis_file_with_ami_test_config(ibis_test_file_with_ami_test_config):
    """Test that [AMI Test Configuration] blocks are parsed correctly."""
    with open(ibis_test_file_with_ami_test_config) as in_file:
        ibis_file_contents = in_file.read()
    status_string, ibis_dictionary = parse_ibis_file(ibis_file_contents)
    assert status_string == "Success!"

    model = ibis_dictionary["models"]["example_tx"]
    test_configs = model.test_configs
    assert set(test_configs) == {"Typ_stat", "Typ_td"}

    stat = test_configs["Typ_stat"]
    assert stat["type"] == "Statistical"
    assert stat["direction"] == "Tx"
    assert stat["input_ir_file"] == "four_tap_input_IR.txt"
    assert stat["golden_ir_file"] == "four_tap_output_IR_typ.txt"
    assert stat["ami_input_parameters_file"] == "four_tap_tx_params_stat.txt"
    assert stat["ami_output_parameters_file"] == "four_tap_output_params_stat.txt"
    assert stat["executable_index"] == "1"

    td = test_configs["Typ_td"]
    assert td["type"] == "Time_domain"
    assert td["input_waveform_file"] == "four_tap_input_bits.txt"
    assert td["golden_waveform_file"] == "four_tap_output_wave_typ.txt"
    assert td["executable_index"] == "2"


def _parse_edited(ibis_test_file, *edits):
    "Parse the fixture after replacing each ``(old, new)`` (each ``old`` must occur)."
    text = ibis_test_file.read_text(encoding="utf-8")
    for old, new in edits:
        assert old in text, old
        text = text.replace(old, new)
    return parse_ibis_file(text)


def test_signal_names_with_punctuation(ibis_test_file):
    """Data-book signal names (IBIS 8.0 Section 5, p.36) like ``TX+`` and ``DQ<0>`` used to fail the whole file."""
    status, ibis_dict = _parse_edited(ibis_test_file, ("1p     Tx_1_P", "1p     TX+"), ("1n     Tx_1_N", "1n     DQ<0>"))
    assert status == "Success!"
    pins = ibis_dict["components"]["Example_Tx"].pins
    assert pins["1p(TX+)"][0] == pins["1n(DQ<0>)"][0] == "example_tx"


def test_model_names_with_punctuation(ibis_test_file):
    status, ibis_dict = _parse_edited(ibis_test_file, ("             example_tx", "             rx+lp"),  # [Pin]
                                      ("[Model]   example_tx", "[Model]   rx+lp"))
    assert status == "Success!"
    assert list(ibis_dict["models"]) == ["rx+lp"]
    assert {mod for (mod, _) in ibis_dict["components"]["Example_Tx"].pins.values()} == {"rx+lp"}


def test_comment_right_after_a_name(ibis_test_file):
    """A ``|`` ends a name (IBIS 8.0 Section 3.2, rule 5, p.19), even with no space before it."""
    status, ibis_dict = _parse_edited(ibis_test_file, ("             example_tx\n", "             example_tx|note\n"),
                                      ("[Model]   example_tx", "[Model]   example_tx|note"))
    assert status == "Success!"
    assert list(ibis_dict["models"]) == ["example_tx"]
    assert {mod for (mod, _) in ibis_dict["components"]["Example_Tx"].pins.values()} == {"example_tx"}


@pytest.mark.parametrize("values, expected", [
    ("1.80     NA       1.98", [1.8, 1.8, 1.98]),  # ``NA`` means the typical value (IBIS 8.0 Section 6.1, p.67).
    ("1.80     1.62     NA", [1.8, 1.62, 1.8]),
    ("1.80     NA       NA", [1.8]),  # Unchanged: just the typical value.
])
def test_na_for_min_or_max(ibis_test_file, values, expected):
    """``NA`` for only one of min/max used to fail the whole file."""
    status, ibis_dict = _parse_edited(ibis_test_file, ("[Voltage_Range]         1.80     1.62     1.98",
                                                       f"[Voltage_Range]         {values}"))
    assert status == "Success!"
    assert ibis_dict["models"]["example_tx"].vrange == pytest.approx(expected)
