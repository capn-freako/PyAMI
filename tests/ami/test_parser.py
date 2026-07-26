import pytest

import pyibisami.ami.parser as ami_parser


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
         (corner_test
             (Usage In )
             (Type Integer )
             (Format Corner 1 0 2 )
             (Description "Dummy parameter, using `Corner` formatting." )
         )
    )

)

"""


@pytest.mark.usefixtures("test_ami_config")
class TestAMIParse:
    def test_parse_ami_param_defs(self, test_ami_config):
        error_string, param_defs = ami_parser.parse_ami_param_defs(test_ami_config)
        assert error_string == ""
        assert param_defs["example_tx"]["description"] == "Example Tx model from ibisami package."

    def test_parse_ami_file_contents(self, test_ami_config):
        (errors,
         warnings,
         root_name,
         description,
         reserved_params_dict,
         model_specific_dict) = ami_parser.parse_ami_file_contents(test_ami_config)
        assert not errors
        assert root_name == "example_tx"
        assert description == "Example Tx model from ibisami package."

    def test_AMIParamConfigurator_without_GUI(self, test_ami_config):
        ami = ami_parser.AMIParamConfigurator(test_ami_config)
        assert ami._root_name == "example_tx"
        assert not ami._ami_parsing_errors
        test_keys = ("tx_tap_units", "tx_tap_np1", "tx_tap_nm1", "tx_tap_nm2", "corner_test")
        assert all(key in ami.ami_param_defs["Model_Specific"] for key in test_keys)
        assert ami.ami_param_defs["Model_Specific"]["tx_tap_units"].pvalue == 27
        assert ami.ami_param_defs["Reserved_Parameters"]["AMI_Version"].pvalue == "5.1"

    def test_fetch_param_val(self, test_ami_config):
        ami = ami_parser.AMIParamConfigurator(test_ami_config)
        assert ami.fetch_param_val(["Reserved_Parameters", "Init_Returns_Impulse"])
        assert not ami.fetch_param_val(["Reserved_Parameters", "Bad Name"])

    def test_set_param_val_top_level(self, test_ami_config):
        ami = ami_parser.AMIParamConfigurator(test_ami_config)
        ami.set_param_val(["Model_Specific", "tx_tap_np1"], 5)
        assert ami.fetch_param_val(["Model_Specific", "tx_tap_np1"]) == 5
        assert ami.input_ami_params["tx_tap_np1"] == 5

    def test_tunable_params(self, test_ami_config):
        ami = ami_parser.AMIParamConfigurator(test_ami_config)
        names = {"_".join(path) for path, _ in ami.tunable_params}
        assert names == {
            "Model_Specific_tx_tap_units",
            "Model_Specific_tx_tap_np1",
            "Model_Specific_tx_tap_nm1",
            "Model_Specific_tx_tap_nm2",
        }
        # 'corner_test' uses 'Corner' format, not 'Range', so it must be excluded.


@pytest.fixture
def nested_ami_config():
    return r"""(example_tx

    (Reserved_Parameters
         (Init_Returns_Impulse (Usage Info) (Type Boolean) (Value True) (Description "x"))
         (GetWave_Exists (Usage Info) (Type Boolean) (Value False) (Description "x"))
    )
    (Model_Specific
         (tx_preset
             (coeffs
                 (main
                     (Usage In )
                     (Type Float )
                     (Range 0.5 0.0 1.0 )
                     (Description "Main tap coefficient." )
                 )
             )
         )
    )

)

"""


class TestNestedModelSpecificParams:
    """Regression coverage for nested (grouped) `Model_Specific` parameters,
    which exercise a hierarchical-trait-name path that `set_param_val()`
    previously got wrong (it synced only the leaf name, not the full,
    underscore-joined hierarchical trait name that `make_gui_items()`
    actually registers)."""

    def test_tunable_params_nested(self, nested_ami_config):
        ami = ami_parser.AMIParamConfigurator(nested_ami_config)
        assert ami.tunable_params == [
            (["Model_Specific", "tx_preset", "coeffs", "main"],
             ami.ami_param_defs["Model_Specific"]["tx_preset"]["coeffs"]["main"])
        ]

    def test_set_param_val_nested(self, nested_ami_config):
        ami = ami_parser.AMIParamConfigurator(nested_ami_config)
        ami.set_param_val(["Model_Specific", "tx_preset", "coeffs", "main"], 0.75)
        assert ami.fetch_param_val(["Model_Specific", "tx_preset", "coeffs", "main"]) == 0.75
        # The value actually consumed by `AMI_Init()` comes from the Trait, via
        # `input_ami_params`, not from `AMIParameter.pvalue` -- this is what was broken.
        assert ami.input_ami_params["tx_preset"]["coeffs"]["main"] == 0.75


@pytest.fixture
def described_group_ami_config():
    """A branch with an explicit `(Description ...)` tag alongside sibling
    subparameters -- `proc_branch()` folds that description in as a plain
    string under a `"description"` key at the *same* dict level as the real
    subparameters (see e.g. the real, repo-bundled `example_rx.ami`'s
    `debug` group), which `tunable_params()`'s tree-walk must not choke on."""
    return r"""(example_rx

    (Reserved_Parameters
         (Init_Returns_Impulse (Usage Info) (Type Boolean) (Value True) (Description "x"))
         (GetWave_Exists (Usage Info) (Type Boolean) (Value False) (Description "x"))
    )
    (Model_Specific
         (debug
             (dbg_enable
                 (Usage In )
                 (Type Boolean )
                 (Value False )
                 (Description "Master debug enable." )
             )
             (dbg_level
                 (Usage In )
                 (Type Integer )
                 (Range 1 0 3 )
                 (Description "Debug verbosity." )
             )
             (Description "Debugging options.")
         )
    )

)

"""


class TestDescribedGroupParams:
    def test_tunable_params_skips_description_key(self, described_group_ami_config):
        ami = ami_parser.AMIParamConfigurator(described_group_ami_config)
        paths = [path for path, _ in ami.tunable_params]
        assert paths == [["Model_Specific", "debug", "dbg_level"]]
