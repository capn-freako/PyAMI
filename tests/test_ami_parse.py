import pytest
import pyibisami.ami_parse as ami_parse

@pytest.fixture
def test_ami_config():
    return r"""(example_tx

    (Description "Example Tx model from ibisami package.")

    (Reserved_Parameters
         (AMI_Version
             (Usage Info )
             (Type String )
             (Value "5.1" )
             (Description "Version of IBIS standard we comply with." )
         )
         (Init_Returns_Impulse
             (Usage Info )
             (Type Boolean )
             (Value True )
             (Description "In fact, this model is, currently, Init-only." )
         )
         (GetWave_Exists
             (Usage Info )
             (Type Boolean )
             (Value True )
             (Description "This model is dual-mode, with GetWave() mimicking Init()." )
         )
    )
    (Model_Specific
         (tx_tap_units
             (Usage In )
             (Type Integer )
             (Range 27 6 27 )
             (Description "Total current available to FIR filter." )
         )
         (tx_tap_np1
             (Usage In )
             (Type Integer )
             (Range 0 0 10 )
             (Description "First (and only) pre-tap." )
         )
         (tx_tap_nm1
             (Usage In )
             (Type Integer )
             (Range 0 0 10 )
             (Description "First post-tap." )
         )
         (tx_tap_nm2
             (Usage In )
             (Type Integer )
             (Range 0 0 10 )
             (Description "Second post-tap." )
         )
    )

)

"""

@pytest.mark.usefixtures("test_ami_config")
class TestAMIParse():

    def test_parse_ami_param_defs(self, test_ami_config):
        error_string, param_defs = ami_parse.parse_ami_param_defs(test_ami_config)
        assert error_string == ""
        assert param_defs["example_tx"]["description"] == "Example Tx model from ibisami package."

    def test_AMIParamConfigurator_without_GUI(self, test_ami_config):
        ami = ami_parse.AMIParamConfigurator(test_ami_config)
        assert ami._root_name == "example_tx"
        assert ami._ami_parsing_errors == ""
        test_keys = ("tx_tap_units", "tx_tap_np1", "tx_tap_nm1", "tx_tap_nm2")
        assert all(key in ami._param_dict["Model_Specific"] for key in test_keys)
        assert ami._param_dict["Model_Specific"]["tx_tap_units"].pvalue == 27
        assert ami._param_dict["Reserved_Parameters"]["AMI_Version"].pvalue == "5.1"

    def test_no_model_specific_key(self, test_ami_config):
        edited = test_ami_config.replace("Model_Specific", "whoops")
        with pytest.raises(KeyError):
            ami_parse.AMIParamConfigurator(edited)

    def test_fetch_param_val(self, test_ami_config):
        ami = ami_parse.AMIParamConfigurator(test_ami_config)
        assert ami.fetch_param_val(["Reserved_Parameters", "Init_Returns_Impulse"])
        assert not ami.fetch_param_val(["Reserved_Parameters", "Bad Name"])
