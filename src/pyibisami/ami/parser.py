"""IBIS-AMI parameter parsing and configuration utilities.

Original author: David Banas <capn.freako@gmail.com>

Original date:   December 17, 2016

Copyright (c) 2019 David Banas; all rights reserved World wide.
"""

from ctypes         import c_double
import re
from typing         import Any, Callable, NewType, Optional, TypeAlias

import numpy as np
from numpy.typing import NDArray
from parsec import ParseError, generate, many, regex, string
from traits.api import Bool, Enum, HasTraits, Range, Trait, TraitType
from traitsui.api import Group, HGroup, Item, VGroup, View
from traitsui.menu import ModalButtons

from .model                     import AMIModelInitializer
from .parameter                 import AMIParamError, AMIParameter
from .reserved_parameter_names  import AmiReservedParameterName, RESERVED_PARAM_NAMES

# New types and aliases.
# Parameters  = NewType('Parameters',  dict[str, AMIParameter] | dict[str, 'Parameters'])
# ParamValues = NewType('ParamValues', dict[str, list[Any]]    | dict[str, 'ParamValues'])
# See: https://stackoverflow.com/questions/70894567/using-mypy-newtype-with-type-aliases-or-protocols
ParamName  = NewType("ParamName", str)
ParamValue:  TypeAlias = int | float | str | list["ParamValue"]
Parameters:  TypeAlias = dict[ParamName, "'AMIParameter' | 'Parameters'"]
ParamValues: TypeAlias = dict[ParamName, "'ParamValue'   | 'ParamValues'"]

AmiName = NewType("AmiName", str)
AmiAtom: TypeAlias = bool | int | float | str
AmiExpr: TypeAlias = "'AmiAtom' | 'AmiNode'"
AmiNode: TypeAlias = tuple[AmiName, list[AmiExpr]]
AmiNodeParser: TypeAlias = Callable[[str], AmiNode]
AmiParser:     TypeAlias = Callable[[str], tuple[AmiName, list[AmiNode]]]  # Atoms may not exist at the root level.

ParseErrMsg = NewType("ParseErrMsg", str)
AmiRootName = NewType("AmiRootName", str)
ReservedParamDict: TypeAlias = dict[AmiReservedParameterName, AMIParameter]
ModelSpecificDict: TypeAlias = dict[ParamName, "'AMIParameter' | 'ModelSpecificDict'"]

__all__ = [
    "ParamName", "ParamValue", "Parameters", "ParamValues",
    "AmiName", "AmiAtom", "AmiExpr", "AmiNode", "AmiNodeParser", "AmiParser",
    "ami_parse", "AMIParamConfigurator"]

#####
# AMI parameter configurator.
#####


class AMIParamConfigurator(HasTraits):
    """Customizable IBIS-AMI model parameter configurator.

    This class can be configured to present a customized GUI to the user
    for configuring a particular IBIS-AMI model.

    The intended use model is as follows:

     1. Instantiate this class only once per IBIS-AMI model invocation.
        When instantiating, provide the unprocessed contents of the AMI
        file, as a single string. This class will take care of getting
        that string parsed properly, and report any errors or warnings
        it encounters, in its ``ami_parsing_errors`` property.

     2. When you want to let the user change the AMI parameter
        configuration, call the ``open_gui`` member function.
        (Or, just call the instance as if it were a function.)
        The instance will then present a GUI to the user,
        allowing him to modify the values of any *In* or *InOut* parameters.
        The resultant AMI parameter dictionary, suitable for passing
        into the ``ami_params`` parameter of the ``AMIModelInitializer``
        constructor, can be accessed, via the instance's
        ``input_ami_params`` property. The latest user selections will be
        remembered, as long as the instance remains in scope.

    The entire AMI parameter definition dictionary, which should *not* be
    passed to the ``AMIModelInitializer`` constructor, is available in the
    instance's ``ami_param_defs`` property.

    Any errors or warnings encountered while parsing are available, in
    the ``ami_parsing_errors`` property.
    """

    def __init__(self, ami_file_contents_str: str) -> None:
        """
        Args:
            ami_file_contents_str: The unprocessed contents of the AMI file, as a single string.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super().__init__()

        # Parse the AMI file contents, storing any errors or warnings, and customize the view accordingly.
        (err_str,
         root_name,
         description,
         reserved_param_dict,
         model_specific_dict) = parse_ami_file_contents(ami_file_contents_str)
        if not reserved_param_dict:
            raise ValueError(
                "\n".join([
                    "No 'Reserved_Parameters' section found!",
                    err_str
                ]))
        if not model_specific_dict:
            raise ValueError(
                "\n".join([
                    "No 'Model_Specific' section found!",
                    err_str
                ]))
        gui_items, new_traits = make_gui(model_specific_dict)
        trait_names = []
        for trait in new_traits:
            self.add_trait(trait[0], trait[1])
            trait_names.append(trait[0])
        self._param_trait_names = trait_names
        self._root_name = root_name
        self._ami_parsing_errors = err_str
        self._content = gui_items
        self._reserved_param_dict = reserved_param_dict
        self._model_specific_dict = model_specific_dict
        self._description = description

    def __call__(self):
        self.open_gui()

    def open_gui(self):
        """Present a customized GUI to the user, for parameter
        customization."""
        # self.configure_traits(kind='modal')  # Waiting for Enthought/Traits PR1841 to be accepted.
        self.configure_traits()

    def default_traits_view(self):
        "Default Traits/UI view definition."
        view = View(
            resizable=False,
            buttons=ModalButtons,
            title=f"{self._root_name} AMI Parameter Configurator",
        )
        view.set_content(self._content)
        return view

    def fetch_param(self, branch_names):
        """Returns the parameter found by traversing 'branch_names' or None if
        not found.

        Note: 'branch_names' should *not* begin with 'root_name'.
        """
        param_dict = self.ami_param_defs
        while branch_names:
            branch_name = branch_names.pop(0)
            if branch_name in param_dict:
                param_dict = param_dict[branch_name]
            else:
                return None
        if isinstance(param_dict, AMIParameter):
            return param_dict
        return None

    def fetch_param_val(self, branch_names):
        """Returns the value of the parameter found by traversing
        'branch_names' or None if not found.

        Note: 'branch_names' should *not* begin with 'root_name'.
        """
        _param = self.fetch_param(branch_names)
        if _param:
            return _param.pvalue
        return None

    def set_param_val(self, branch_names, new_val):
        """Sets the value of the parameter found by traversing 'branch_names'
        or raises an exception if not found.

        Note: 'branch_names' should *not* begin with 'root_name'.
        Note: Be careful! There is no checking done here!
        """

        param_dict = self.ami_param_defs
        while branch_names:
            branch_name = branch_names.pop(0)
            if branch_name in param_dict:
                param_dict = param_dict[branch_name]
            else:
                raise ValueError(
                    f"Failed parameter tree search looking for: {branch_name}; available keys: {param_dict.keys()}"
                )
        if isinstance(param_dict, AMIParameter):
            param_dict.pvalue = new_val
            try:
                eval(f"self.set({branch_name}_={new_val})")  # pylint: disable=eval-used
            except Exception:  # pylint: disable=broad-exception-caught
                eval(f"self.set({branch_name}={new_val})")  # pylint: disable=eval-used
        else:
            raise TypeError(f"{param_dict} is not of type: AMIParameter!")

    @property
    def ami_parsing_errors(self):
        """Any errors or warnings encountered, while parsing the AMI parameter
        definition file contents."""
        return self._ami_parsing_errors

    @property
    def ami_param_defs(self) -> dict[str, ReservedParamDict | ModelSpecificDict]:
        """The entire AMI parameter definition dictionary.

        Should *not* be passed to ``AMIModelInitializer`` constructor!
        """
        return {"Reserved_Parameters": self._reserved_param_dict,
                "Model_Specific": self._model_specific_dict}

    @property
    def input_ami_params(self) -> ParamValues:
        """
        The dictionary of *Model Specific* AMI parameters of type 'In' or
        'InOut', along with their user selected values.

        Should be passed to ``AMIModelInitializer`` constructor.
        """

        res: ParamValues = {}
        res[ParamName("root_name")] = str(self._root_name)
        params = self._model_specific_dict
        for pname in params:
            res.update(self.input_ami_param(params, pname))
        return res

    def input_ami_param(
        self,
        params: Parameters,
        pname: ParamName,
        prefix: str = ""
    ) -> ParamValues:
        """
        Retrieve one AMI parameter value, or dictionary of subparameter values,
        from the given parameter definition dictionary.

        Args:
            params: The parameter definition dictionary.
            pname: The simple name of the parameter of interest, used by the IBIS-AMI model.

        Keyword Args:
            prefix: The current working parameter name prefix.

        Returns:
            A dictionary of parameter values indexed by non-prefixed parameter names.

        Notes:
            1. The "prefix" referred to above refers to a string encoding of the
            hierarchy above a particular trait. We need this hierarchy for the
            sake of the ``Traits/UI`` machinery, which addresses traits by name
            alone. However, the IBIS-AMI model is not expecting it. So, we have
            to strip it off, before sending the result here into ``AMI_Init()``.
        """

        res = {}
        tname = prefix + pname     # This is the fully hierarchical trait name, used by the Traits/UI machinery.
        param = params[pname]
        if isinstance(param, AMIParameter):
            if tname in self._param_trait_names:  # If model specific and of type In or InOut...
                # See the docs on the *HasTraits* class, if this is confusing.
                # Querry for a mapped trait, first, by trying to get '<trait_name>_'. (Note the underscore.)
                try:
                    res[pname] = self.trait_get(tname + "_")[tname + "_"]
                # If we get an exception, we have an ordinary (i.e. - not mapped) trait.
                except Exception:  # pylint: disable=broad-exception-caught
                    res[pname] = self.trait_get(tname)[tname]
        elif isinstance(param, dict):  # We received a dictionary of subparameters, in 'param'.
            subs: ParamValues = {}
            for sname in param:
                subs.update(self.input_ami_param(param, sname, prefix=pname + "_"))  # type: ignore
            res[pname] = subs
        return res

    @property
    def info_ami_params(self):
        "Dictionary of *Reserved* AMI parameter values."
        return self._reserved_param_dict

    def get_init(
        self,
        bit_time:         float,
        sample_interval:  float,
        channel_response: NDArray[np.longdouble],
        ami_params: Optional[dict[str, Any]] = None
    ) -> AMIModelInitializer:
        """
        Get a model initializer, configured by the user if necessary.
        """

        row_size = len(channel_response)
        if ami_params:
            initializer = AMIModelInitializer(
                ami_params,
                info_params=self.info_ami_params,
                bit_time=c_double(bit_time),
                row_size=row_size,
                sample_interval=c_double(sample_interval)
            )
        else:
            # This call will invoke a GUI applet for the user to interact with,
            # to configure the AMI parameter values.
            self()
            initializer = AMIModelInitializer(
                self.input_ami_params,
                info_params=self.info_ami_params,
                bit_time=c_double(bit_time),
                row_size=row_size,
                sample_interval=c_double(sample_interval)
            )

        # Don't try to pack this into the parentheses above!
        initializer.channel_response = channel_response
        return initializer


#####
# AMI file parser.
#####

# ignore cases.
whitespace = regex(r"\s+", re.MULTILINE)
comment = regex(r"\|.*")
ignore = many(whitespace | comment)


def lexeme(p):
    """Lexer for words."""
    return p << ignore  # skip all ignored characters.


def int2tap(x):
    """Convert integer to tap position."""
    x = x.strip()
    if x[0] == "-":
        res = "pre" + x[1:]
    else:
        res = "post" + x
    return res


lparen = lexeme(string("("))
rparen = lexeme(string(")"))
number = lexeme(regex(r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?"))
integ = lexeme(regex(r"[-+]?[0-9]+"))
nat = lexeme(regex(r"[0-9]+"))
tap_ix = (integ << whitespace).parsecmap(int2tap)
symbol = lexeme(regex(r"[0-9a-zA-Z_][^\s()]*"))
true = lexeme(string("True")).result(True)
false = lexeme(string("False")).result(False)
ami_string = lexeme(regex(r'"[^"]*"'))

atom = number | symbol | ami_string | (true | false)
node_name = tap_ix ^ symbol  # `tap_ix` is new and gives the tap position; negative positions are allowed.


@generate("AMI node")
def node():
    "Parse AMI node."
    yield lparen
    label  = yield node_name
    values = yield many(expr)
    yield rparen
    return (label, values)


@generate("AMI file")
def root():
    "Parse AMI file."
    yield lparen
    label  = yield node_name
    values = yield many(node)
    yield rparen
    return (label, values)


expr = atom | node
ami = ignore >> root
ami_parse: AmiParser = ami.parse


def proc_branch(branch):
    """Process a branch in a AMI parameter definition tree.

    That is, build a dictionary from a pair containing:
        - a parameter name, and
        - a list of either:
            - parameter definition tags, or
            - subparameters.

    We distinguish between the two possible kinds of payloads, by
    peaking at the names of the first two items in the list and noting
    whether they are keys of 'AMIParameter._param_def_tag_procs'.
    We have to do this twice, due to the dual use of the 'Description'
    tag and the fact that we have no guarantee of any particular
    ordering of subparameter branch items.

    Args:
        p (str, list): A pair, as described above.

    Returns:
        (str, dict): A pair containing:
            err_str: String containing any errors or warnings encountered,
                while building the parameter dictionary.
            param_dict: Resultant parameter dictionary.
    """
    results = ("", {})  # Empty Results
    if len(branch) != 2:
        if not branch:
            err_str = "ERROR: Empty branch provided to proc_branch()!\n"
        else:
            err_str = f"ERROR: Malformed item: {branch[0]}\n"
        results = (err_str, {})

    param_name = branch[0]
    param_tags = branch[1]

    if not param_tags:
        err_str = f"ERROR: No tags/subparameters provided for parameter, '{param_name}'\n"
        results = (err_str, {})

    try:
        if (
            (len(param_tags) > 1)
            and (  # noqa: W503
                param_tags[0][0] in AMIParameter._param_def_tag_procs  # pylint: disable=protected-access  # noqa: W503
            )
            and (  # noqa: W503
                param_tags[1][0] in AMIParameter._param_def_tag_procs  # pylint: disable=protected-access  # noqa: W503
            )
        ):
            try:
                results = ("", {param_name: AMIParameter(param_name, param_tags)})
            except AMIParamError as err:
                results = (str(err), {})
        elif param_name == "Description":
            results = ("", {"description": param_tags[0].strip('"')})
        else:
            err_str = ""
            param_dict = {}
            param_dict[param_name] = {}
            for param_tag in param_tags:
                temp_str, temp_dict = proc_branch(param_tag)
                param_dict[param_name].update(temp_dict)
                if temp_str:
                    err_str = (
                        f"Error returned by recursive call, while processing parameter, '{param_name}':\n{temp_str}"
                    )
                    results = (err_str, param_dict)

            results = (err_str, param_dict)
    except Exception:  # pylint: disable=broad-exception-caught
        print(f"Error processing branch:\n{param_tags}")
    return results


def parse_ami_file_contents(  # pylint: disable=too-many-locals,too-many-branches
    file_contents: str
) -> tuple[ParseErrMsg, AmiRootName, str, ReservedParamDict, ModelSpecificDict]:
    """
    Parse the contents of an IBIS-AMI *parameter definition* (i.e. - `*.ami`) file.

    Args:
        file_contents: The contents of the file, as a single string.

    Example:
        ::

            with open(<ami_file_name>) as ami_file:
                file_contents = ami_file.read()
                (err_str, root_name, reserved_param_dict, model_specific_param_dict) = parse_ami_file_contents(file_contents)

    Returns:
        A tuple containing

            1. Any error message generated by the parser. (empty on success)

            2. AMI file "root" name.

            3. *Reserved Parameters* dictionary. (empty on failure)

                - The keys of the *Reserved Parameters* dictionary are
                limited to those called out in the IBIS-AMI specification.

                - The values of the *Reserved Parameters* dictionary
                must be instances of class ``AMIParameter``.

            4. *Model Specific Parameters* dictionary. (empty on failure)

                - The keys of the *Model Specific Parameters* dictionary can be anything.

                - The values of the *Model Specific Parameters* dictionary
                may be either: an instance of class ``AMIParameter``, or a nested sub-dictionary.
    """
    try:
        res = ami_parse(file_contents)
    except ParseError as pe:
        err_str = ParseErrMsg(f"Expected {pe.expected} at {pe.loc()} in:\n{pe.text[pe.index:]}")
        return err_str, AmiRootName(""), "", {}, {}

    err_str, param_dict = proc_branch(res)
    if err_str:
        return (err_str, AmiRootName(""), "", {}, {})
    if len(param_dict.keys()) != 1:
        raise ValueError(f"Malformed AMI parameter S-exp has top-level keys: {param_dict.keys()}!")

    reserved_found = False
    init_returns_impulse_found = False
    getwave_exists_found = False
    model_spec_found = False
    root_name, params = list(param_dict.items())[0]
    description = ""
    reserved_params_dict = {}
    model_specific_dict = {}
    _err_str = ""
    for label in list(params.keys()):
        tmp_params = params[label]
        if label == "Reserved_Parameters":
            reserved_found = True
            for param_name in list(tmp_params.keys()):
                if param_name not in RESERVED_PARAM_NAMES:
                    _err_str += f"WARNING: Unrecognized reserved parameter name, '{param_name}', found in parameter definition string!\n"
                    continue
                param = tmp_params[param_name]
                if param.pname == "AMI_Version":
                    if param.pusage != "Info" or param.ptype != "String":
                        _err_str += "WARNING: Malformed 'AMI_Version' parameter.\n"
                elif param.pname == "Init_Returns_Impulse":
                    init_returns_impulse_found = True
                elif param.pname == "GetWave_Exists":
                    getwave_exists_found = True
            reserved_params_dict = tmp_params
        elif label == "Model_Specific":
            model_spec_found = True
            model_specific_dict = tmp_params
        elif label == "description":
            description = str(tmp_params)
        else:
            _err_str += f"WARNING: Unrecognized group with label, '{label}', found in parameter definition string!\n"

    if not reserved_found:
        _err_str += "ERROR: Reserved parameters section not found! It is required."

    if not init_returns_impulse_found:
        _err_str += "ERROR: Reserved parameter, 'Init_Returns_Impulse', not found! It is required."

    if not getwave_exists_found:
        _err_str += "ERROR: Reserved parameter, 'GetWave_Exists', not found! It is required."

    if not model_spec_found:
        _err_str += "WARNING: Model specific parameters section not found!"

    return (ParseErrMsg(_err_str), root_name, description, reserved_params_dict, model_specific_dict)


# Legacy client code support:
def parse_ami_param_defs(file_contents: str) -> tuple[ParseErrMsg, dict[str, Any]]:
    "The legacy version of ``parse_ami_file_contents()``."
    err_msg, root_name, description, reserved_params_dict, model_specific_dict = parse_ami_file_contents(file_contents)
    return (err_msg, {root_name: {"description":         description,
                                  "Reserved_Parameters": reserved_params_dict,
                                  "Model_Specific":      model_specific_dict}})


def make_gui(params: ModelSpecificDict) -> tuple[Group, list[TraitType]]:
    """
    Builds top-level ``Group`` and list of ``Trait`` s from AMI parameter dictionary.

    Args:
        params: Dictionary of AMI parameters to be configured.

    Returns:
        A pair consisting of:

            - the top-level ``Group`` for the ``View``, and
            - a list of new ``Trait`` s created.

    Notes:
        1. The dictionary passed through ``params`` may have sub-dictionaries.
        The window layout will reflect this nesting.
    """

    gui_items: list[Item | Group] = []
    new_traits: list[tuple[str, TraitType]] = []
    pnames = list(params.keys())
    pnames.sort()
    for pname in pnames:
        gui_item, new_trait = make_gui_items(pname, params[pname])
        gui_items.extend(gui_item)
        new_traits.extend(new_trait)

    return (HGroup(*gui_items), new_traits)


def make_gui_items(  # pylint: disable=too-many-locals,too-many-branches
    pname: str,
    param: AMIParameter | Parameters
) -> tuple[list[Item | Group], list[tuple[str, TraitType]]]:
    """
    Builds list of GUI items and list of traits from AMI parameter or dictionary.

    Args:
        pname: Parameter or sub-group name.
        param: AMI parameter or dictionary of AMI parameters to be configured.

    Returns:
        A pair consisting of:

            - the list of GUI items for the ``View``, and
            - the list of new ``Trait`` s created.

    Notes:
        1. A dictionary passed through ``param`` may have sub-dictionaries.
        These will be converted into sub- ``Group`` s in the returned list of GUI items.
    """

    if isinstance(param, AMIParameter):  # pylint: disable=no-else-return
        pusage = param.pusage
        if pusage not in ("In", "InOut"):
            return ([], [])

        if param.ptype == "Boolean":
            return ([Item(pname, tooltip=param.pdescription)], [(pname, Bool(param.pvalue))])

        pformat = param.pformat
        match pformat:
            case "Value":  # Value
                the_trait = Trait(param.pvalue)
            case "Range":
                the_trait = Range(param.pmin, param.pmax, param.pvalue)
            case "List":
                list_tips = param.plist_tip
                default = param.pdefault
                if list_tips:
                    tmp_dict: dict[str, Any] = {}
                    tmp_dict.update(list(zip(list_tips, param.pvalue)))
                    val = list(tmp_dict.keys())[0]
                    if default:
                        for tip in tmp_dict.items():
                            if tip[1] == default:
                                val = tip[0]
                                break
                    the_trait = Trait(val, tmp_dict)
                else:
                    val = default if default else param.pvalue[0]
                    the_trait = Enum([val] + param.pvalue)
            case _:
                raise ValueError(f"Unrecognized AMI parameter format: {pformat}, for parameter `{pname}` of type `{param.ptype}` and usage `{param.pusage}`!")
        if the_trait.metadata:
            the_trait.metadata.update({"transient": False})  # Required to support modal dialogs.
        else:
            the_trait.metadata = {"transient": False}
        return ([Item(name=pname, label=pname.split("_")[-1], tooltip=param.pdescription)], [(pname, the_trait)])

    else:  # subparameter branch
        gui_items: list[Item | Group] = []
        new_traits: list[tuple[str, TraitType]] = []
        subparam_names = list(param.keys())
        subparam_names.sort()
        group_desc = None

        # Build GUI items for this branch.
        for subparam_name in subparam_names:
            if subparam_name == "description":
                group_desc = param[subparam_name]
            else:
                tmp_items, tmp_traits = make_gui_items(pname + "_" + subparam_name, param[subparam_name])
                gui_items.extend(tmp_items)
                new_traits.extend(tmp_traits)

        if group_desc:
            gui_items = [Item(label=group_desc)] + gui_items

        return ([VGroup(*gui_items, label=pname.split("_")[-1], show_border=True)], new_traits)
