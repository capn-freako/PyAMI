"""
Parse an IBIS model file.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

import re
from parsec     import regex, eof, many1, many, string, generate, sepBy1, one_of, skip, none_of, times, ParseError
from traits.api import HasTraits

class IBISModel(HasTraits):
    """
    HasTraits subclass for wrapping and interacting with an IBIS model.

    This class can be configured to present a customized GUI to the user
    for interacting with a particular IBIS model (i.e. - selecting models, etc.).

    The intended use model is as follows:

     1. Instantiate this class only once per IBIS model file.
        When instantiating, provide the unprocessed contents of the IBIS
        file, as a single string. This class will take care of getting
        that string parsed properly, and report any errors or warnings
        it encounters, in its 'ibis_parsing_errors' property.

     2. When you want to let the user select a particular model,
        call the *open_gui* member function.
        The instance will then present a GUI to the user,
        allowing him to select a particular model, which may then
        be retrieved, via the *model* property.
        The latest user selections will be remembered,
        as long as the instance remains in scope.

    Any errors or warnings encountered while parsing are available, in
    the *ibis_parsing_errors* property.

    The complete dictionary containing all parsed models may be retrieved,
    via the *model_dict* property.
    """

    def __init__(self, ibis_file_contents_str):
        """
        Args:
            ibis_file_contents_str (str): The unprocessed contents of
                the IBIS file, as a single string.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super(IBISModel, self).__init__()

        # Parse the IBIS file contents, storing any errors or warnings,
        # and customize the view accordingly.
        err_str, model_dict = parse_ibis_file(ibis_file_contents_str)
        if False:
            gui_items, new_traits = make_gui_items(
                "Models", model_dict, first_call=True
            )
            trait_names = []
            for trait in new_traits:
                self.add_trait(trait[0], trait[1])
                trait_names.append(trait[0])
                self._content = gui_items
                self._param_trait_names = trait_names
        # self._root_name = top_branch[0]
        self._ibis_parsing_errors = err_str
        # self._content = gui_items
        self._model_dict = model_dict

    def open_gui(self):
        """Present a customized GUI to the user, for parameter customization."""
        self.edit_traits()

    def default_traits_view(self):
        view = View(
            resizable=False,
            buttons=ModalButtons,
            title="PyBERT IBIS Model Selector",
            id="pybert.pybert_ami.model_selector",
        )
        view.set_content(self._content)
        return view

    @property
    def ibis_parsing_errors(self):
        """Any errors or warnings encountered, while parsing the IBIS file contents."""
        return self._ibis_parsing_errors

    @property
    def model_dict(self):
        """The entire AMI parameter definition dictionary.

        Should NOT be passed to AMIModelInitializer constructor!
        """
        return self._model_dict

    @property
    def model(self):
        """The model selected most recently by the user.

        Returns the first model parsed, if the user hasn't made a selection yet.
        """
        return self._model_dict[self.selectedModelName]

whitespace = regex(r"\s+", re.MULTILINE)
comment = regex(r"\|.*")
ignore = many((whitespace | comment))

def lexeme(p):
    """Lexer for words."""
    return p << ignore  # Skip all ignored characters after word.

number = lexeme(regex(r"[-+]?[0-9]*\.?[0-9]+([TknGmpMuf][a-zA-Z]*)?"))
name = lexeme(regex(r"[_a-zA-Z0-9]+"))
symbol = lexeme(regex(r"[a-zA-Z_][^\s()\[\]]*"))
true = lexeme(string("True")).result(True)
false = lexeme(string("False")).result(False)
quoted_string = lexeme(regex(r'"[^"]*"'))
fail = one_of("")
skip_keyword = many(none_of("[")) >> ignore  # Skip over everything until the next keyword begins.
skip_line = many(none_of("\n")) >> many1(string("\n")) >> ignore

def manyTrue(p):
    "Run a parser multiple times, filtering `False` results."
    @generate("manyTrue")
    def fn():
        "many(p) >> filter(True)"
        nodes = yield many(p)
        res = list(filter(None, nodes))
        return res
    return fn

def many1True(p):
    "Run a parser at least once, filtering `False` results."
    @generate("many1True")
    def fn():
        "many1(p) >> filter(True)"
        nodes = yield many1(p)
        res = list(filter(None, nodes))
        return res
    return fn

# IBIS file parser:

def keyword(kywrd=""):
    """Parse an IBIS keyword.

    Keyword Args:
        kywrd (str): The particular keyword to match; null for any keyword.
            If provided, _must_ be in canonicalized form (i.e. - underscores,
            no spaces)!

    Returns:
        Parser: A keyword parser.
    """
    @generate("IBIS keyword")
    def fn():
        "Parse IBIS keyword."
        yield string("[")
        wordlets = yield sepBy1(regex(r"[a-zA-Z]+"), one_of(" _"))  # `name` gobbles up trailing space.
        yield string("]")
        yield ignore  # So that `keyword` functions as a lexeme.
        res = ("_".join(wordlets))  # Canonicalize to: "<wordlet1>_<wordlet2>_...".
        if kywrd:
            # assert res.lower() == kywrd.lower(), f"Expecting: {kywrd}; got: {res}."  # Does not work!
            if res.lower() == kywrd.lower():
                return res
            else:
                return fail.desc(f"Expecting: {kywrd}; got: {res}.")
        return res
    return fn

def node(valid_keywords, stop_keywords, valid_parameters):
    """Build a node-specific parser.

    Args:
        valid_keywords (dict): A dictionary with keys matching those
            keywords we want parsed. The values are the parsers for
            those keywords.
        stop_keywords: Any iterable with primary values (i.e. - those
            tested by the `in` function) matching those keywords we want
            to stop the parsing of this node and pop us back up the
            parsing stack.
        valid_parameters (dict): A dictionary with keys matching those
            parameters we want parsed. The values are the parsers for
            those keywords.

    Returns:
        Parser: A parser for this node.

    Notes:
        1: Any keywords encountered that are _not_ found (via `in`) in
            either `valid_keywords` or `stop_keywords` are ignored.
        2: Any parameters encountered that are _not_ found in `valid_parameters`
            are ignored.
    """
    @generate("kywrd")
    def kywrd():
        "Parse keyword syntax."
        nm = yield keyword()
        nmL = nm.lower()
        if nmL in valid_keywords:
            if nmL == "end":  # Because `ibis_file` expects this to be the last thing it sees,
                return fail   # we can't consume it here.
            else:
                #print(nm)  # TEMP DEBUG
                res = yield valid_keywords[nmL]  # Parse the sub-keyword.
                return (nmL, res)
        elif nmL in stop_keywords:
            return fail                          # Stop parsing.
        else:
            return skip_keyword

    @generate("lbl")
    def lbl():
        "Parse non-keyword syntax."
        nm = yield name
        nmL = nm.lower()
        if nmL in valid_parameters:
            res = yield valid_parameters[nmL]  # Parse the sub-parameter.
            return (nmL, res)
        else:
            return skip_line

    @generate("IBIS node")
    def fn():
        "Parse IBIS node."
        res = yield (kywrd ^ lbl)  # `return kywrd ^ lbl` gives strange error: "`Parser` has no attribute `send`."
        return res
        
    return fn

# Individual IBIS keyword (i.e. - "node") parsers:

# [End]
@generate("[End]")
def end():
    "Parse [End]."
    yield keyword("End")
    return eof

# [Model]
@generate("[Model]")
def model():
    "Parse [Model]."
    nm = yield name
    res = yield many1True(node(Model_keywords, IBIS_keywords, Model_params))
    return {nm: dict(res)}

@generate("[Pulldown]")
def model_pulldown():
    yield skip_keyword
    return

@generate("[Pullup]")
def model_pullup():
    yield skip_keyword
    return
    
@generate("[Ramp]")
def model_ramp():
    yield skip_keyword
    return
    
Model_keywords = {
    "pulldown": model_pulldown,
    "pullup": model_pullup,
    "ramp": model_ramp,
}

Model_params = {
    "model_type": name,
    "c_comp": times(number, 1, 3),
    #"c_comp": many1(number),
}

# Note: The following dictionary MUST have a complete set of keys,
#       in order for the parsing logic to work correctly!
IBIS_keywords = {
    "model": model,
    "end": end,
    "ibis_ver": skip_keyword,
    "comment_char": skip_keyword,
    "file_name": skip_keyword,
    "file_rev": skip_keyword,
    "date": skip_keyword,
    "source": skip_keyword,
    "notes": skip_keyword,
    "disclaimer": skip_keyword,
    "copyright": skip_keyword,
    "component": skip_keyword,
    "model_selector": skip_keyword,
    "Submodel": skip_keyword,
    "external_circuit": skip_keyword,
    "test_data": skip_keyword,
    "test_load": skip_keyword,
    "define_package_model": skip_keyword,
    "interconnect_model_set": skip_keyword,
}

@generate("IBIS File")
def ibis_file():
    res = yield ignore >> many1True(node(IBIS_keywords, {}, {})) << end
    return res

# Utility functions

def proc_branch(branch):
    """
    Process a branch in a AMI parameter definition tree.

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
            err_str = "ERROR: Malformed item: {}\n".format(branch[0])
        results = (err_str, {})

    param_name = branch[0]
    param_tags = branch[1]

    if not param_tags:
        err_str = "ERROR: No tags/subparameters provided for parameter, '{}'\n".format(param_name)
        results = (err_str, {})

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
                err_str = "Error returned by recursive call, while processing parameter, '{}':\n{}".format(
                    param_name, temp_str
                )
                results = (err_str, param_dict)

        results = (err_str, param_dict)
    return results


def parse_ibis_file(ibis_file_contents_str):
    """
    Parse the contents of an IBIS file.

    Args:
        ibis_file_contents_str (str): The contents of the IBIS file, as a single string.

    Example:
        ::

            with open(<ibis_file_name>) as ibis_file:
                ibis_file_contents_str = ibis_file.read()
                (err_str, model_dict)  = parse_ibis_file(ibis_file_contents_str)

    Returns:
        (str, dict): A pair containing:

            err_str:
                A message describing the nature of any parse failure that occured.
            model_dict:
                Dictionary containing keyword definitions (empty upon failure).
    """
    try:
        res = ibis_file.parse(ibis_file_contents_str)
    except ParseError as pe:
        err_str = "Expected {} at {} in {}".format(pe.expected, pe.loc(), pe.text[pe.index :])
        return err_str, {}
    return "Success!", res

    # err_str, param_dict = proc_branch(res)
    # if err_str:
    #     return (err_str, {"res": res, "dict": param_dict})

    # reserved_found = False
    # init_returns_impulse_found = False
    # getwave_exists_found = False
    # model_spec_found = False
    # params = list(param_dict.items())[0][1]
    # for label in list(params.keys()):
    #     if label == "Reserved_Parameters":
    #         reserved_found = True
    #         tmp_params = params[label]
    #         for param_name in list(tmp_params.keys()):
    #             if param_name not in AMIParameter.RESERVED_PARAM_NAMES:
    #                 err_str += "WARNING: Unrecognized reserved parameter name, '{}', found in parameter definition string!\n".format(
    #                     param_name
    #                 )
    #                 continue
    #             param = tmp_params[param_name]
    #             if param.pname == "AMI_Version":
    #                 if param.pusage != "Info" or param.ptype != "String":
    #                     err_str += "WARNING: Malformed 'AMI_Version' parameter.\n"
    #             elif param.pname == "Init_Returns_Impulse":
    #                 init_returns_impulse_found = True
    #             elif param.pname == "GetWave_Exists":
    #                 getwave_exists_found = True
    #     elif label == "Model_Specific":
    #         model_spec_found = True
    #     elif label == "description":
    #         pass
    #     else:
    #         err_str += "WARNING: Unrecognized group with label, '{}', found in parameter definition string!\n".format(
    #             label
    #         )

    # if not reserved_found:
    #     err_str += "ERROR: Reserved parameters section not found! It is required."

    # if not init_returns_impulse_found:
    #     err_str += "ERROR: Reserved parameter, 'Init_Returns_Impulse', not found! It is required."

    # if not getwave_exists_found:
    #     err_str += "ERROR: Reserved parameter, 'GetWave_Exists', not found! It is required."

    # if not model_spec_found:
    #     err_str += "WARNING: Model specific parameters section not found!"

    # return (err_str, param_dict)


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
                            for tip in tmp_dict:
                                if tmp_dict[tip] == default:
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
                    gui_items.append(Item(pname, style="readonly", tooltip=param.pdescription))
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
