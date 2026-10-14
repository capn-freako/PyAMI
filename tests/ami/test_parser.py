import pytest

import pyibisami.ami.model as ami_model
import pyibisami.ami.parser as ami_parser
from traits.api import TraitError


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
    underscore-joined hierarchical trait name that `make_param_traits()`
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
        paths = {tuple(path) for path, _ in ami.tunable_params}
        # Both the Boolean 'dbg_enable' and the Range 'dbg_level' are sweepable;
        # the 'description' key must not show up as a bogus third entry.
        assert paths == {
            ("Model_Specific", "debug", "dbg_enable"),
            ("Model_Specific", "debug", "dbg_level"),
        }


@pytest.fixture
def mode_selector_ami_config():
    """A real-world pattern (see the repo-bundled `example_rx.ami`'s
    `ctle_mode`): an Integer, List-format 'mode selector' that gates whether
    a sibling Range-format parameter has any effect at all. Also includes a
    non-contiguous List, which must NOT be treated as sweepable (there's no
    safe uniform step that stays within the legal value set)."""
    return r"""(example_tx

    (Reserved_Parameters
         (Init_Returns_Impulse (Usage Info) (Type Boolean) (Value True) (Description "x"))
         (GetWave_Exists (Usage Info) (Type Boolean) (Value False) (Description "x"))
    )
    (Model_Specific
         (eq_mode
             (Usage In )
             (Type Integer )
             (List 0 1 )
             (List_Tip "Off" "Manual" )
             (Description "EQ operating mode." )
         )
         (eq_mag
             (Usage In )
             (Type Float )
             (Range 0.0 0.0 12.0 )
             (Description "EQ peaking magnitude (dB)." )
         )
         (odd_steps
             (Usage In )
             (Type Integer )
             (List 6 12 18 )
             (Description "Non-contiguous discrete choices." )
         )
    )

)

"""


class TestModeSelectorParams:
    def test_contiguous_list_integer_is_sweepable(self, mode_selector_ami_config):
        ami = ami_parser.AMIParamConfigurator(mode_selector_ami_config)
        paths = {tuple(path) for path, _ in ami.tunable_params}
        assert ("Model_Specific", "eq_mode") in paths
        assert ("Model_Specific", "eq_mag") in paths

    def test_noncontiguous_list_integer_is_excluded(self, mode_selector_ami_config):
        ami = ami_parser.AMIParamConfigurator(mode_selector_ami_config)
        paths = {tuple(path) for path, _ in ami.tunable_params}
        assert ("Model_Specific", "odd_steps") not in paths

    def test_set_param_val_on_mode_selector_actually_gates_downstream_value(
        self, mode_selector_ami_config
    ):
        "Regression: sweeping a Boolean/List value must not corrupt AMIParameter.pvalue."
        ami = ami_parser.AMIParamConfigurator(mode_selector_ami_config)
        eq_mode_param = ami.ami_param_defs["Model_Specific"]["eq_mode"]
        assert eq_mode_param.pvalue == [0, 1]  # The legal-value list, untouched so far.

        ami.set_param_val(["Model_Specific", "eq_mode"], 1.0)  # As a sweep would pass it.
        assert ami.input_ami_params["eq_mode"] == 1
        # `pvalue` must still be the legal-value list, not clobbered with a scalar.
        assert eq_mode_param.pvalue == [0, 1]


@pytest.fixture
def grouped_ami_config():
    """Prefix-grouped parameters (``ctle_*``), a non-configurable ``Out`` parameter
    (which must get no Trait/GUI item), and a described nested group.
    (Ported from ``fix/95-decouple-gui``'s ``test_headless.py``.)"""
    return r"""(example_rx
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


@pytest.fixture
def tap_ami_config():
    "A tapped delay line, its taps named by tap number (IBIS 8.0 Section 10.3.4, p.240)."
    return _ami_file(r"""
         (tx_tap
             (Description "Tx FFE.")
             (-1 (Usage In) (Type Tap) (Range 0.0 -0.2 0.0) (Description "Pre-cursor."))
             (0 (Usage In) (Type Tap) (Range 1.0 0.6 1.0) (Description "Main."))
             (1 (Usage In) (Type Tap) (Range 0.0 -0.4 0.0) (Description "Post-cursor."))
         )""")


def _ami_file(model_specific, reserved='(AMI_Version (Usage Info) (Type String) (Value "7.0"))', ms_first=False):
    "A minimal ``.ami`` file with the given ``Model_Specific`` contents and extra reserved parameters."
    rsv = f"""(Reserved_Parameters
         {reserved}
         (Init_Returns_Impulse (Usage Info) (Type Boolean) (Value True))
         (GetWave_Exists (Usage Info) (Type Boolean) (Value False)))"""
    ms = f"(Model_Specific {model_specific})"
    return f"(my_model {ms} {rsv})" if ms_first else f"(my_model {rsv} {ms})"


class TestTapNames:
    def test_model_gets_tap_numbers(self, tap_ami_config):
        """Taps used to reach the model as ``pre1``/``post0``/``post1``, which it doesn't recognise."""
        ami = ami_parser.AMIParamConfigurator(tap_ami_config)
        assert ami.input_ami_params["tx_tap"] == {"-1": 0.0, "0": 1.0, "1": 0.0}
        ami.set_param_val(["Model_Specific", "tx_tap", "-1"], -0.1)
        assert ami.input_ami_params["tx_tap"]["-1"] == -0.1

    def test_tuners_keep_display_names(self, tap_ami_config):
        tuners = ami_parser.AMIParamConfigurator(tap_ami_config).mk_tap_tuners()
        assert [(t.name, t.branch_names) for t in tuners] == [
            ("tx_tap_pre1", ["Model_Specific", "tx_tap", "-1"]),
            ("tx_tap_post0", ["Model_Specific", "tx_tap", "0"]),
            ("tx_tap_post1", ["Model_Specific", "tx_tap", "1"]),
        ]

    def test_names_starting_with_a_digit(self):
        """Only a whole name is a tap number; ``2x`` used to be read as tap ``2`` (``post2``) plus an atom ``x``."""
        assert ami_parser.ami_parse("(r (2x (Usage In)) (-1 (Usage In)))") == (
            "r", [("2x", [("Usage", ["In"])]), ("-1", [("Usage", ["In"])])])


@pytest.mark.parametrize("param, expected", [
    ("(Type Integer) (List 0 1 2) (Default 2)", 2),  # Was the string "2", sent quoted to the model.
    ("(Type Float) (Range 0.5 0 1) (Default 0.7)", 0.7),  # Was 0.5: Default ignored.
    ('(Type Integer) (List 0 1 2) (List_Tip "a" "b" "c") (Default 2)', 2),  # Was 0: Default ignored.
    ("(Type Integer) (List 0 1 2) (Default 0)", 0),
])
def test_default_is_the_initial_value(param, expected):
    """``Default`` picks the value when the user doesn't (IBIS 8.0 Section 10.3.4, p.245)."""
    ami = ami_parser.AMIParamConfigurator(_ami_file(f"(x (Usage In) {param})"))
    value = ami.input_ami_params["x"]
    assert value == expected and type(value) is type(expected)
    assert not ami.ami_parsing_errors


@pytest.mark.parametrize("param, expected, warning", [
    ("(Type Float) (Range 0.5 0 1) (Default 1.5)", 0.5, "outside the Range"),
    ("(Type Integer) (List 0 1 2) (Default 3)", 0, "not a member of the List"),
    ("(Type Integer) (List 0 1 2) (Default high)", 0, "Couldn't read integer"),
])
def test_unusable_default_warns(param, expected, warning):
    """A Default of the wrong Type or outside the allowed values is ignored, with a warning; the file still loads."""
    ami = ami_parser.AMIParamConfigurator(_ami_file(f"(x (Usage In) {param})"))
    assert ami.input_ami_params["x"] == expected
    assert len(ami.ami_parsing_errors) == 1 and warning in ami.ami_parsing_errors[0]
    assert ami.ami_parsing_errors[0].startswith("Model_Specific.x: ")


def test_list_tip_count_must_match_list():
    """``zip()`` used to drop the extra List entries silently (IBIS 8.0 Section 10.3.4, p.241)."""
    ami = ami_parser.AMIParamConfigurator(_ami_file('(x (Usage In) (Type Integer) (List 0 1 2) (List_Tip "a" "b"))'))
    assert ami.ami_parsing_errors == ["Model_Specific.x: List_Tip has 2 entries, but List has 3; they must match."]


@pytest.mark.parametrize("reserved, warns", [
    ('(AMI_Version (Usage Info) (Type String) (Value "5.1"))', True),
    ("", False),  # No AMI_Version: a pre-5.1 model, for which the order is free.
])
def test_reserved_parameters_first_from_5_1(reserved, warns):
    """IBIS 8.0 Section 10.3.2, p.237."""
    ami = ami_parser.AMIParamConfigurator(_ami_file("(x (Usage In) (Type Integer) (Value 1))", reserved, ms_first=True))
    assert any("must come before Model_Specific" in w for w in ami.ami_parsing_errors) == warns


def test_newer_reserved_parameters_are_recognised():
    """Reserved parameters of AMI_Version 7.2 and 8.0 (IBIS 8.0 Table 41, p.338-339) used to warn."""
    names = ["Modulation_Levels", "PAM_Offsets", "PAM_Thresholds", "Tx_Impulse_Input",
             "Adaptation_Valid", "Rx_Port_Order", "Tx_Port_Order"]
    reserved = " ".join(f'({name} (Usage Info) (Type String) (Value "x"))' for name in names)
    ami = ami_parser.AMIParamConfigurator(_ami_file("(x (Usage In) (Type Integer) (Value 1))", reserved))
    assert not ami.ami_parsing_errors
    assert set(names) <= set(ami.info_ami_params)


@pytest.fixture
def formats_ami_config():
    "One parameter of each format that used to fail the whole file (IBIS 8.0 Section 10.3.4, p.239-244)."
    return _ami_file(r"""
         (gain (Usage In) (Type Float) (Increment 1.0 0.0 2.0 0.5))
         (vga (Usage In) (Type Integer) (Steps 4 0 8 4) (Default 6))
         (pvt (Usage In) (Type Float) (Corner 1.0 0.5 2.0))
         (poles (Usage InOut) (Type Integer Float Float)
             (Table (Labels "flag" "re" "im") (1 -5e8 0) (2 -9.4e8 8.3e8)))
         (fwd (Usage In) (Type Float) (Format Table ( -0.169324 1.40308 0.330246)))
         (rj (Usage In) (Type UI) (Gaussian 0 0.01))
         (dd (Usage In) (Type UI) (Dual-Dirac -0.1 0.1 0.01))
         (djrj (Usage In) (Type UI) (DjRj -0.1 0.1 0.01))
         (taps (Usage In) (Type Tap) (List 0.1 0.2))
         (big (Usage In) (Type Integer) (Range 1e3 0 2e3))
         (resolved (Usage Dep) (Type Float) (Value 1.0))""")


class TestFormats:
    """Each of these used to fail the whole ``.ami`` file."""

    def test_values_sent_to_model(self, formats_ami_config):
        ami = ami_parser.AMIParamConfigurator(formats_ami_config)
        assert not ami.ami_parsing_errors
        params = ami.input_ami_params
        assert params == {
            "root_name": "my_model",
            "gain": 1.0, "vga": 6, "pvt": 1.0,
            "poles": [1, -5e8, 0.0, 2, -9.4e8, 8.3e8],  # Rows flattened; Labels not sent (p.242-243).
            "fwd": [-0.169324, 1.40308, 0.330246],
            "rj": [0.0, 0.01], "dd": [-0.1, 0.1, 0.01], "djrj": [-0.1, 0.1, 0.01],
            "taps": 0.1, "big": 1000,
        }  # Dep is never sent (p.240).
        assert ami_model.ami_params_string({"root_name": "m", "poles": params["poles"], "s": "a b"}) == (
            '(m (poles 1 -500000000.0 0.0 2 -940000000.0 830000000.0)(s "a b"))')

    def test_increment_and_steps_allow_only_their_values(self, formats_ami_config):
        """``typ + N*delta`` within ``[min, max]`` (p.241); Steps' delta is ``(max - min) / steps``."""
        ami = ami_parser.AMIParamConfigurator(formats_ami_config)
        defs = ami.ami_param_defs["Model_Specific"]
        assert defs["gain"].pvalues == [0.0, 0.5, 1.0, 1.5, 2.0]
        assert defs["vga"].pvalues == [0, 2, 4, 6, 8]
        ami.gain = 1.5  # As the GUI sets it.
        assert ami.input_ami_params["gain"] == 1.5
        with pytest.raises(TraitError):
            ami.gain = 1.2

    @pytest.mark.parametrize("corner, expected", [("typ", 1.0), ("min", 0.5), ("max", 2.0)])
    def test_corner_follows_sim_corner(self, formats_ami_config, corner, expected):
        """The EDA tool picks typ/slow/fast by its simulation corner, not the user (p.246)."""
        ami = ami_parser.AMIParamConfigurator(formats_ami_config)
        ami.sim_corner = corner
        assert ami.input_ami_params["pvt"] == expected
        assert ami.fetch_param_val(["Model_Specific", "pvt"]) == expected
        assert "pvt" not in ami._param_trait_names
        assert all(path[-1] != "pvt" for path, _ in ami.tunable_params)

    def test_table_labels_and_column_types(self, formats_ami_config):
        poles = ami_parser.AMIParamConfigurator(formats_ami_config).ami_param_defs["Model_Specific"]["poles"]
        assert poles.plabels == ["flag", "re", "im"]
        assert poles.pvalue == [[1, -5e8, 0.0], [2, -9.4e8, 8.3e8]]
        assert [type(v) for v in poles.pvalue[0]] == [int, float, float]

    @pytest.mark.parametrize("param, reason", [
        ("(Usage In) (Type Tap) (Table (1 2))", "Illegal type, 'Tap', for use with Table"),  # p.242.
        ("(Usage In) (Type Integer) (Gaussian 0 1)", "Illegal type, 'Integer', for use with Gaussian"),  # p.245.
        ("(Usage In) (Type Float) (Table (1 2) (3))", "same number of entries"),
        ("(Usage Out) (Type Float) (Corner 1 2 3)", "Corner is not allowed with Usage Out"),
        ("(usage in) (Type Float) (Range 0.5 0 1)", "Missing 'Usage' tag"),  # Case sensitive (p.236).
        ("(usage In) (type Float) (Value 1)", "Missing 'Usage' and 'Type' tags"),  # Not an (empty) branch.
    ])
    def test_bad_parameter_is_skipped(self, param, reason):
        """Only the bad parameter is dropped, with a warning naming it; the rest of the file loads."""
        ami = ami_parser.AMIParamConfigurator(_ami_file(f"(grp (bad {param})) (good (Usage In) (Type Integer) (Value 1))"))
        assert ami.input_ami_params == {"root_name": "my_model", "grp": {}, "good": 1}
        assert len(ami.ami_parsing_errors) == 1
        assert ami.ami_parsing_errors[0].startswith("Skipped parameter Model_Specific.grp.bad: ")
        assert reason in ami.ami_parsing_errors[0]

    def test_skipped_required_parameter_still_fails(self):
        """A required Reserved Parameter that can't be read is reported missing, as before."""
        with pytest.raises(RuntimeError, match="'GetWave_Exists', not found"):
            ami_parser.AMIParamConfigurator(_ami_file("(x (Usage In) (Type Integer) (Value 1))").replace(
                "(GetWave_Exists (Usage Info) (Type Boolean) (Value False))",
                "(GetWave_Exists (Usage Info) (Type Boolean) (Value Maybe))"))

    def test_table_default_is_ignored_with_a_warning(self):
        ami = ami_parser.AMIParamConfigurator(_ami_file("(t (Usage In) (Type Float) (Table (1 2)) (Default 1))"))
        assert ami.input_ami_params["t"] == [1.0, 2.0]
        assert ami.ami_parsing_errors == ["Model_Specific.t: Default is not allowed with Table; ignoring it."]

    def test_subparameters_named_like_tags(self):
        """Names like ``Corner``/``Steps`` used for parameters don't turn their branch into one (bad) parameter."""
        ami = ami_parser.AMIParamConfigurator(_ami_file(
            '(Corner (Usage In) (Type String) (List "TT" "FF")) '
            "(ctle (Steps (Usage In) (Type Integer) (Value 3)) (gain (Usage In) (Type Float) (Value 0.5)))"))
        assert ami.ami_parsing_errors == []
        assert ami.input_ami_params == {"root_name": "my_model", "Corner": "TT", "ctle": {"Steps": 3, "gain": 0.5}}

    def test_empty_child_node_is_skipped_alone(self):
        """An empty node ``(x )`` is skipped on its own; it doesn't make its group look like one bad parameter."""
        ami = ami_parser.AMIParamConfigurator(_ami_file("(g (x )) (good (Usage In) (Type Integer) (Value 1))"))
        assert ami.input_ami_params == {"root_name": "my_model", "g": {}, "good": 1}
        assert ami.ami_parsing_errors == ["Skipped parameter Model_Specific.g.x: No tags or subparameters."]

    def test_boolean_table_rows(self):
        """Table rows may start with a Boolean column (Table 18)."""
        ami = ami_parser.AMIParamConfigurator(_ami_file("(t (Usage In) (Type Boolean Integer) (Table (True 1) (False 2)))"))
        assert ami.ami_parsing_errors == []
        assert ami.ami_param_defs["Model_Specific"]["t"].pvalue == [[True, 1], [False, 2]]


@pytest.mark.parametrize(
    "config", ["test_ami_config", "nested_ami_config", "described_group_ami_config", "grouped_ami_config",
               "tap_ami_config", "formats_ami_config"])
def test_gui_view_items_match_traits(config, request):
    """Every editable ``Item`` in the GUI view must name a registered parameter Trait."""
    pytest.importorskip("traitsui")
    from traitsui.api import Group, Item

    def item_names(content):
        for elem in content:
            if isinstance(elem, Group):
                yield from item_names(elem.content)
            elif isinstance(elem, Item) and elem.name:
                yield elem.name

    ami = ami_parser.AMIParamConfigurator(request.getfixturevalue(config))
    view = ami.default_traits_view()
    assert sorted(item_names(view.content.content)) == sorted(ami._param_trait_names)


def test_boolean_list_without_default_starts_at_first_value():
    """With no ``Default``, a List starts at its first value (IBIS 8.0 p.241); a Boolean List used to start at False."""
    ami = ami_parser.AMIParamConfigurator(_ami_file("(bl (Usage In) (Type Boolean) (List True False))"))
    assert ami.input_ami_params["bl"] is True


def test_pdefault_is_typed():
    """``pdefault`` is the typed Default when it is used, for every Format that takes one; ``None`` when unusable."""
    ami = ami_parser.AMIParamConfigurator(_ami_file(
        "(r (Usage In) (Type Float) (Range 0.5 0 1) (Default 0.7)) "
        "(bad (Usage In) (Type Float) (Range 0.5 0 1) (Default 2)) "
        "(d (Usage Info) (Type Boolean) (Default False)) "
        "(l (Usage In) (Type Integer) (List 0 1 2) (Default 2))"))
    params = ami.ami_param_defs["Model_Specific"]
    assert params["r"].pdefault == 0.7 and params["bad"].pdefault is None
    assert params["d"].pdefault is False and params["l"].pdefault == 2


def test_description_without_quotes():
    ami = ami_parser.AMIParamConfigurator(_ami_file('(x (Usage In) (Type Integer) (Value 1) (Description "Tap weight"))'))
    assert ami.ami_param_defs["Model_Specific"]["x"].pdescription == "Tap weight"
