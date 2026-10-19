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


def _model_text(ibis_dict):
    "The parsed ``example_tx`` model's values, for comparing an edited file with the original."
    model = ibis_dict["models"]["example_tx"]
    return str(model), model.zout, model.vrange


def test_comment_char(ibis_test_file):
    """``[Comment Char]`` (IBIS 8.0 Section 3.2, rule 5, p.19; p.32): ``#`` comments then parse like ``|`` ones."""
    _, original = _parse_edited(ibis_test_file)
    status, ibis_dict = _parse_edited(
        ibis_test_file,
        ("[IBIS Ver]   5.1\n", "[IBIS Ver]   5.1\n[Comment Char] #_char\n"),
        ("[File Rev]   v0.1", "[File Rev]   v0.1  #A comment"),
        ("[Pulldown]\n", "[Pulldown]\n# Voltage  I(typ)  I(min)  I(max)\n"),
        ("0.00     0.000e+00     0.000e+00     0.000e+00", "0.00     0.000e+00     0.000e+00     0.000e+00 #row"),
    )
    assert status == "Success!" and ibis_dict["warnings"] == []
    assert ibis_dict["file_rev"] == "v0.1"
    assert _model_text(ibis_dict) == _model_text(original)


def test_comment_char_changes(ibis_test_file):
    """Each ``[Comment Char]`` applies from the next line; a disallowed character is a warning (and ignored)."""
    status, ibis_dict = _parse_edited(
        ibis_test_file,
        ("[IBIS Ver]   5.1\n", "[IBIS Ver]   5.1\n[Comment Char] #_char\n[Comment Char] a_char\n"),
        ("[File Rev]   v0.1", "[File Rev]   v0.1  #A comment"),
        ("[Date]       2019-02-10", "[Comment Char] !_char\n[Date]       2019-02-10 # is text now ! a comment"),
    )
    assert status == "Success!"
    assert ibis_dict["file_rev"] == "v0.1"
    assert ibis_dict["date"].strip() == "2019-02-10 # is text now"
    assert len(ibis_dict["warnings"]) == 1 and "[Comment Char]" in ibis_dict["warnings"][0]


@pytest.mark.parametrize("old, new", [
    ("Vmeas = 0.5", "Vmeas= 0.5"),
    ("Cref  = 0", "Cref =0"),
    ("Rref  = 50", "Rref=50"),
])
def test_equals_without_spaces(ibis_test_file, old, new):
    """``name=value`` without spaces (e.g. - ``Vinl=0.4``) used to lose the rest of the ``[Model]``."""
    _, original = _parse_edited(ibis_test_file)
    status, ibis_dict = _parse_edited(ibis_test_file, (old, new))
    assert status == "Success!"
    assert _model_text(ibis_dict) == _model_text(original)


def test_pin_header_any_case(ibis_test_file):
    """``[Pin]`` sub-parameter names are reserved words, so any case (IBIS 8.0 Section 3.2, rule 1, p.18)."""
    status, ibis_dict = _parse_edited(
        ibis_test_file,
        ("[Pin]  signal_name        model_name            R_pin  L_pin  C_pin",
         "[Pin]  Signal_name        MODEL_NAME            r_pin  L_PIN  C_pin"),
        ("1p     Tx_1_P             example_tx", "1p     Tx_1_P             example_tx   0.1  1n  0.5p"),
    )
    assert status == "Success!"
    model, rlcs = ibis_dict["components"]["Example_Tx"].pins["1p(Tx_1_P)"]
    assert model == "example_tx"
    assert rlcs == pytest.approx({"R_pin": 0.1, "L_pin": 1e-9, "C_pin": 0.5e-12})


def test_bracket_inside_a_line(ibis_test_file):
    """A ``[`` after column 1 is text (IBIS 8.0 Section 3.2, rule 6, p.19), e.g. - in a selector description."""
    status, ibis_dict = _parse_edited(
        ibis_test_file,
        ("[Model]   example_tx", "[Model Selector] sel\nexample_tx   Drive [DRIVE2=0  DRIVE1=1] 2mA\n\n"
                                 "[Model]   example_tx"),
    )
    assert status == "Success!"
    [(mname, descr)] = ibis_dict["model_selectors"]["sel"]
    assert mname == "example_tx" and "[DRIVE2=0  DRIVE1=1] 2mA" in descr
    assert list(ibis_dict["models"]) == ["example_tx"]


def test_text_after_end(ibis_test_file):
    """Anything after ``[End]`` (e.g. - a stray control character) is ignored, with a warning."""
    status, ibis_dict = _parse_edited(ibis_test_file, ("[END]\n", "[END]\n\x13\n"))
    assert status == "Success!"
    assert len(ibis_dict["warnings"]) == 1 and "after [End]" in ibis_dict["warnings"][0]


def test_parse_failure_position_is_one_based(ibis_test_file):
    text = ibis_test_file.read_text(encoding="utf-8")
    line = text.splitlines().index("[File Rev]   v0.1") + 1
    status, ibis_dict = _parse_edited(ibis_test_file, ("[File Rev]   v0.1", "[File Rev]   v0.1 @bad"))
    assert ibis_dict == {}
    assert status.endswith(f"at line {line}, column {len('[File Rev]   v0.1 ') + 1}")


def test_trailing_comment_not_in_names(ibis_test_file):
    """A ``|`` comment after a ``[Component]`` name or ``[Date]`` isn't part of the value."""
    status, ibis_dict = _parse_edited(ibis_test_file,
                                      ("[Component]    Example_Tx", "[Component]    Example_Tx   | PECL input"),
                                      ("[Date]       2019-02-10", "[Date]       2019-02-10  | a note"))
    assert status == "Success!"
    assert list(ibis_dict["components"]) == ["Example_Tx"]
    assert ibis_dict["date"] == "2019-02-10"


def test_pin_rlc_na_column(ibis_test_file):
    """``NA`` in one ``R_pin``/``L_pin``/``C_pin`` column (IBIS 8.0 Section 5, p.36) keeps the other values."""
    status, ibis_dict = _parse_edited(ibis_test_file, ("1p     Tx_1_P             example_tx",
                                                       "1p     Tx_1_P             example_tx   55m  NA  0.2p"))
    assert status == "Success!"
    _, rlcs = ibis_dict["components"]["Example_Tx"].pins["1p(Tx_1_P)"]
    assert rlcs == pytest.approx({"R_pin": 0.055, "C_pin": 0.2e-12})  # ``L_pin`` falls back to ``[Package]``.


def test_file_ends_at_first_end(ibis_test_file):
    """``[End]`` ends the file (IBIS 8.0 Section 4, p.34): text and a second ``[End]`` after it are ignored."""
    status, ibis_dict = _parse_edited(ibis_test_file, ("[END]\n", "[END]\njunk\n[End]\n"))
    assert status == "Success!"
    assert len(ibis_dict["warnings"]) == 1 and "after [End]" in ibis_dict["warnings"][0]
