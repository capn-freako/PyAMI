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
