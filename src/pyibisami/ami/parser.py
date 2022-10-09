"""IBIS-AMI parameter parsing and configuration utilities.

Original author: David Banas <capn.freako@gmail.com>

Original date:   December 17, 2016

Copyright (c) 2019 David Banas; all rights reserved World wide.
"""
import re

from parsec import ParseError, generate, many, many1, regex, string
from traits.api import Bool, Enum, HasTraits, Range, Trait
from traitsui.api import Group, Item, View
from traitsui.menu import ModalButtons

from pyibisami.ami.parameter import AMIParamError, AMIParameter

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
        (Or, just call the instance as if it were executable.)
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

    def __init__(self, ami_file_contents_str):
        """
        Args:
            ami_file_contents_str (str): The unprocessed contents of
                the AMI file, as a single string.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super().__init__()

        # Parse the AMI file contents, storing any errors or warnings,
        # and customize the view accordingly.
        err_str, param_dict = parse_ami_param_defs(ami_file_contents_str)
        if not param_dict:
            print("Empty dictionary returned by parse_ami_param_defs()!")
            print(f"Error message:\n{err_str}")
            raise KeyError("Failed to parse AMI file; see console for more detail.")
        top_branch = list(param_dict.items())[0]
        param_dict = top_branch[1]
        if "Reserved_Parameters" not in param_dict:
            print(f"Error: {err_str}\nParameters: {param_dict}")
            raise KeyError("Unable to get 'Reserved_Parameters' from the parameter set.")
        if "Model_Specific" not in param_dict:
            print(f"Error: {err_str}\nParameters: {param_dict}")
            raise KeyError("Unable to get 'Model_Specific' from the parameter set.")
        pdict = param_dict["Reserved_Parameters"]
        pdict.update(param_dict["Model_Specific"])
        gui_items, new_traits = make_gui_items("Model In/InOut Parameters", pdict, first_call=True)
        trait_names = []
        for trait in new_traits:
            self.add_trait(trait[0], trait[1])
            trait_names.append(trait[0])
        self._content = gui_items
        self._param_trait_names = trait_names
        self._root_name = top_branch[0]
        self._ami_parsing_errors = err_str
        self._content = gui_items
        self._param_dict = param_dict

    def __call__(self):
        self.open_gui()

    def open_gui(self):
        """Present a customized GUI to the user, for parameter
        customization."""
        # self.edit_traits()
        self.configure_traits()

    def default_traits_view(self):
        view = View(
            resizable=False,
            buttons=ModalButtons,
            title="PyBERT AMI Parameter Configurator",
            id="pybert.pybert_ami.param_config",
        )
        view.set_content(self._content)
        return view

    def fetch_param_val(self, branch_names):
        """Returns the value of the parameter found by traversing
        'branch_names' or None if not found.

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
            return param_dict.pvalue
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
                eval(f"self.set({branch_name}_={new_val})")  # mapped trait; see below
            except:
                eval(f"self.set({branch_name}={new_val})")
        else:
            raise TypeError(f"{param_dict} is not of type: AMIParameter!")

    @property
    def ami_parsing_errors(self):
        """Any errors or warnings encountered, while parsing the AMI parameter
        definition file contents."""
        return self._ami_parsing_errors

    @property
    def ami_param_defs(self):
        """The entire AMI parameter definition dictionary.

        Should *not* be passed to ``AMIModelInitializer`` constructor!
        """
        return self._param_dict

    @property
    def input_ami_params(self):
        """The dictionary of *Model Specific* AMI parameters of type 'In' or
        'InOut', along with their user selected values.

        Should be passed to ``AMIModelInitializer`` constructor.
        """
        res = {}
        res["root_name"] = self._root_name
        params = self.ami_param_defs["Model_Specific"]
        for pname in params:
            res.update(self.input_ami_param(params, pname))
        return res

    def input_ami_param(self, params, pname):
        """Retrieve one AMI parameter, or dictionary of subparameters."""
        res = {}
        param = params[pname]
        if isinstance(param, AMIParameter):
            if pname in self._param_trait_names:  # If model specific and In or InOut...
                # See the docs on the *HasTraits* class, if this is confusing.
                try:  # Querry for a mapped trait, first, by trying to get '<trait_name>_'. (Note the underscore.)
                    res[pname] = self.get(pname + "_")[pname + "_"]
                except:  # If we get an exception, we have an ordinary (i.e. - not mapped) trait.
                    res[pname] = self.get(pname)[pname]
        elif isinstance(param, dict):  # We received a dictionary of subparameters, in 'param'.
            subs = {}
            for sname in param.keys():
                subs.update(self.input_ami_param(param, sname))
            res[pname] = subs
        return res


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
    label = yield node_name
    values = yield many1(expr)
    yield rparen
    return (label, values)


expr = atom | node
ami_defs = ignore >> node


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

            err_str:
                String containing any errors or warnings encountered,
                while building the parameter dictionary.
            param_dict:
                Resultant parameter dictionary.
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
            and (param_tags[0][0] in AMIParameter._param_def_tag_procs)
            and (param_tags[1][0] in AMIParameter._param_def_tag_procs)
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
    except:
        print(f"Error processing branch:\n{param_tags}")
    return results


def parse_ami_param_defs(param_str):
    """Parse the contents of a IBIS-AMI parameter definition file.

    Args:
        param_str (str): The contents of the file, as a single string.

    Example:
        ::

            with open(<ami_file_name>) as ami_file:
                param_str = ami_file.read()
                (err_str, param_dict) = parse_ami_param_defs(param_str)

    Returns:
        (str, dict): A pair containing:

            err_str:
                - None, if parser succeeds.
                - Helpful message, if it fails.
            param_dict:
                Dictionary containing parameter definitions.
                (Empty, on failure.)
                It has a single key, at the top level, which is the
                model root name. This key indexes the actual
                parameter dictionary, which has the following
                structure::

                    {
                        'description'           :   <optional model description string>
                        'Reserved_Parameters'   :   <dictionary of reserved parameter defintions>
                        'Model_Specific'        :   <dictionary of model specific parameter definitions>
                    }

                The keys of the 'Reserved_Parameters' dictionary are
                limited to those called out in the IBIS-AMI
                specification.

                The keys of the 'Model_Specific' dictionary can be
                anything.

                The values of both are either:
                    - instances of class *AMIParameter*, or
                    - sub-dictionaries following the same pattern.
    """
    try:
        res = ami_defs.parse(param_str)
    except ParseError as pe:
        err_str = f"Expected {pe.expected} at {pe.loc()} in:\n{pe.text[pe.index:]}"
        return err_str, {}

    err_str, param_dict = proc_branch(res)
    if err_str:
        return (err_str, {"res": res, "dict": param_dict})

    reserved_found = False
    init_returns_impulse_found = False
    getwave_exists_found = False
    model_spec_found = False
    params = list(param_dict.items())[0][1]
    for label in list(params.keys()):
        if label == "Reserved_Parameters":
            reserved_found = True
            tmp_params = params[label]
            for param_name in list(tmp_params.keys()):
                if param_name not in AMIParameter.RESERVED_PARAM_NAMES:
                    err_str += f"WARNING: Unrecognized reserved parameter name, '{param_name}', found in parameter definition string!\n"
                    continue
                param = tmp_params[param_name]
                if param.pname == "AMI_Version":
                    if param.pusage != "Info" or param.ptype != "String":
                        err_str += "WARNING: Malformed 'AMI_Version' parameter.\n"
                elif param.pname == "Init_Returns_Impulse":
                    init_returns_impulse_found = True
                elif param.pname == "GetWave_Exists":
                    getwave_exists_found = True
        elif label == "Model_Specific":
            model_spec_found = True
        elif label == "description":
            pass
        else:
            err_str += f"WARNING: Unrecognized group with label, '{label}', found in parameter definition string!\n"

    if not reserved_found:
        err_str += "ERROR: Reserved parameters section not found! It is required."

    if not init_returns_impulse_found:
        err_str += "ERROR: Reserved parameter, 'Init_Returns_Impulse', not found! It is required."

    if not getwave_exists_found:
        err_str += "ERROR: Reserved parameter, 'GetWave_Exists', not found! It is required."

    if not model_spec_found:
        err_str += "WARNING: Model specific parameters section not found!"

    return (err_str, param_dict)


def make_gui_items(pname, param, first_call=False):
    """Builds list of GUI items from AMI parameter dictionary."""

    gui_items = []
    new_traits = []
    if isinstance(param, AMIParameter):
        pusage = param.pusage
        if pusage in ("In", "InOut"):
            if param.ptype == "Boolean":
                new_traits.append((pname, Bool(param.pvalue)))
                gui_items.append(Item(pname, tooltip=param.pdescription))
            else:
                pformat = param.pformat
                if pformat == "Range":
                    new_traits.append((pname, Range(param.pmin, param.pmax, param.pvalue)))
                    gui_items.append(Item(pname, tooltip=param.pdescription))
                elif pformat == "List":
                    list_tips = param.plist_tip
                    default = param.pdefault
                    if list_tips:
                        tmp_dict = {}
                        tmp_dict.update(list(zip(list_tips, param.pvalue)))
                        val = list(tmp_dict.keys())[0]
                        if default:
                            for tip in tmp_dict.items():
                                if tip == default:
                                    val = tip
                                    break
                        new_traits.append((pname, Trait(val, tmp_dict)))
                    else:
                        val = param.pvalue[0]
                        if default:
                            val = default
                        new_traits.append((pname, Enum([val] + param.pvalue)))
                    gui_items.append(Item(pname, tooltip=param.pdescription))
                else:  # Value
                    new_traits.append((pname, param.pvalue))
                    gui_items.append(Item(pname, tooltip=param.pdescription))
    else:  # subparameter branch
        subparam_names = list(param.keys())
        subparam_names.sort()
        sub_items = []
        group_desc = ""

        # Build GUI items for this branch.
        for subparam_name in subparam_names:
            if subparam_name == "description":
                group_desc = param[subparam_name]
            else:
                tmp_items, tmp_traits = make_gui_items(subparam_name, param[subparam_name])
                sub_items.extend(tmp_items)
                new_traits.extend(tmp_traits)

        # Put all top-level ungrouped parameters in a single VGroup.
        top_lvl_params = []
        sub_params = []
        for item in sub_items:
            if isinstance(item, Item):
                top_lvl_params.append(item)
            else:
                sub_params.append(item)
        sub_items = [Group(top_lvl_params)] + sub_params

        # Make the top-level group an HGroup; all others VGroups (default).
        if first_call:
            gui_items.append(
                Group([Item(label=group_desc)] + sub_items, label=pname, show_border=True, orientation="horizontal")
            )
        else:
            gui_items.append(Group([Item(label=group_desc)] + sub_items, label=pname, show_border=True))

    return gui_items, new_traits
