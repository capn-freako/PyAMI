from pyibisami.ami_parse import AMIParamConfigurator


class TestAMIParse():

    def test_AMIParamConfigurator(self):
        test_ami_config = r"""(example_tx

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
        param_test = AMIParamConfigurator(test_ami_config)
        assert param_test.ami_valid
        assert param_test.has_getwave