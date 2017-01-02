"""
IBIS-AMI parameter parsing and configuration utilities.

Original author: David Banas <capn.freako@gmail.com>
Original date:   December 17, 2016

Copyright (c) 2016 David Banas; all rights reserved World wide.
"""

from __future__ import generators

import re

from parsec import *

from traits.api      import HasTraits, Array, Range, Float, Int, Property, Trait, String, Enum, Bool, List
from traitsui.api    import View, Item, Group, Include
from traitsui.menu   import ModalButtons

from ami_parameter   import AMIParameter, AMIParamError


#####
# AMI parameter configurator.
#####

class AMIParamConfigurator(HasTraits):
    """
    Customizable IBIS-AMI model parameter configurator.

    This class can be configured to present a customized GUI to the user
    for configuring a particular IBIS-AMI model.

    The intended use model is as follows:

     1. Instantiate this class only once per IBIS-AMI model invocation.
        When instantiating, provide the unprocessed contents of the AMI
        file, as a single string. This class will take care of getting
        that string parsed properly, and report any errors or warnings
        it encounters, in its 'ami_parsing_errors' property.

     2. When you want to let the user change the AMI parameter
        configuration, call the instance created, above, as if it were
        a function. The instance will then present a GUI to the user,
        allowing him to modify the values of any In or InOut parameters.
        The resultant AMI parameter dictionary, suitable for passing
        into the 'ami_params' parameter of the AMIModelInitializer
        constructor, can be accessed, via the instance's
        'input_ami_params' property. The latest user selections will be
        remembered, as long as the instance remains in scope.

    The entire AMI parameter definition dictionary, which should NOT be
    passed to the AMIModelInitializer constructor, is available in the
    instance's 'ami_param_defs' property.

    Any errors or warnings encountered while parsing are available, in
    the 'ami_parsing_errors' property.

    """

    def __init__(self, ami_file_contents_str):
        """
        Inputs:

          - ami_file_contents_str   The unprocessed contents of the AMI
                                    file, as a single string.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super(AMIParamConfigurator, self).__init__()

        def make_gui_items(pname, param):
            'Builds list of GUI items from AMI parameter dictionary.'

            gui_items = []
            new_traits = []
            if(isinstance(param, AMIParameter)):
                pusage = param.pusage
                if(pusage == 'In' or pusage == 'InOut'):
                    if(param.ptype == 'Boolean'):
                        new_traits.append((pname, Bool(param.pvalue)))
                        gui_items.append(Item(pname, tooltip=param.pdescription ))
                    else:
                        pformat = param.pformat
                        if(pformat == 'Range'):
                            new_traits.append((pname, Range(param.pmin, param.pmax, param.pvalue)))
                            gui_items.append(Item(pname, tooltip=param.pdescription ))
                        elif(pformat == 'List'):
                            list_tips = param.plist_tip
                            default = param.pdefault
                            if(list_tips):
                                # The attempt, below, doesn't work.
                                # Prevent alphabetic sorting of list tips by Traits/UI machinery.
                                # i = 0
                                # tmp_tips = []
                                # for list_tip in list_tips:
                                #     i += 1
                                #     tmp_tips.append("{:02d}:{}".format(i, list_tip))
                                tmp_dict = {}
                                # tmp_dict.update(zip(tmp_tips, param.pvalue))
                                tmp_dict.update(zip(list_tips, param.pvalue))
                                val = tmp_dict.keys()[0]
                                if(default):
                                    for tip in tmp_dict:
                                        if(tmp_dict[tip] == default):
                                            val = tip
                                            break
                                new_traits.append((pname, Trait(val, tmp_dict)))
                            else:
                                val = param.pvalue[0]
                                if(default):
                                    val = default
                                new_traits.append((pname, Enum([val] + param.pvalue)))
                            gui_items.append(Item(pname, tooltip=param.pdescription ))
                        else:  # Value
                            new_traits.append((pname, param.pvalue))
                            gui_items.append(Item(pname, style='readonly', tooltip=param.pdescription ))
            else:  # subparameter branch
                subparam_names = param.keys()
                subparam_names.sort()
                sub_items = []
                group_desc = ''
                for subparam_name in subparam_names:
                    if(subparam_name == 'description'):
                        group_desc = param[subparam_name]
                    else:
                        tmp_items, tmp_traits = make_gui_items(subparam_name, param[subparam_name])
                        sub_items.append(tmp_items)
                        new_traits.extend(tmp_traits)
                sub_items = sum(sub_items, [])  # Using sum to concatenate.
                gui_items.append(Group([Item(label=group_desc)] + sub_items, label=pname, show_border=True))

            return gui_items, new_traits


        # Parse the AMI file contents, storing any errors or warnings,
        # and customize the view accordingly.
        err_str, param_dict = parse_ami_param_defs(ami_file_contents_str)
        top_branch = param_dict.items()[0]
        param_dict = top_branch[1]
        params = param_dict['Model_Specific']
        gui_items, new_traits = make_gui_items('Model Specific In/InOut Parameters', params)
        trait_names = []
        for trait in new_traits:
            self.add_trait(trait[0], trait[1])
            trait_names.append(trait[0])

        self._root_name = top_branch[0]
        self._ami_parsing_errors = err_str
        self._content = gui_items
        self._param_trait_names = trait_names
        self._param_dict = param_dict


    def __call__(self):
        """
        Present a customized GUI to the user, for parameter
        customization.
        """

        self.edit_traits()


    def default_traits_view(self):
        view = View(
            resizable = False,
            buttons = ModalButtons,
            title='PyBERT AMI Parameter Configurator',
            id='pybert.pybert_ami.param_config',
        )
        view.set_content(self._content)
        return view


    def fetch_param_val(self, branch_names):
        "Returns the value of the parameter found by traversing 'branch_names', or None if not found."

        param_dict = self.ami_param_defs
        while branch_names:
            branch_name = branch_names.pop(0)
            if(branch_name in param_dict):
                param_dict = param_dict[branch_name]
            else:
                return None
        if(isinstance(param_dict, AMIParameter)):
            return param_dict.pvalue
        else:
            return None


    # Properties

    ## ami_parsing_errors
    def _get_ami_parsing_errors(self):
        return self._ami_parsing_errors
    ami_parsing_errors = property(_get_ami_parsing_errors,
            doc='Any errors or warnings encountered, while parsing the AMI parameter definition file contents.')


    ## ami_param_defs
    def _get_ami_param_defs(self):
        return self._param_dict
    ami_param_defs = property(_get_ami_param_defs,
            doc='The entire AMI parameter definition dictionary. Should NOT be passed to AMIModelInitializer constructor!')


    ## input_ami_params
    def _get_input_ami_params(self):
        res = {}
        res['root_name'] = self._root_name 
        for pname in self._param_trait_names:
            # See the docs on the *HasTraits* class, if this is confusing.
            try:  # Querry for a mapped trait, first, by trying to get '<trait_naem>_'. (Note the underscore.)
                res[pname] = self.get(pname + '_')[pname + '_']
            except:  # If we get an exception, we have an ordinary (i.e. - not mapped) trait.
                res[pname] = self.get(pname)[pname]
        return res
    input_ami_params = property(_get_input_ami_params,
            doc='The dictionary of AMI parameters of type In or InOut, along with their user selected values. Should be passed to AMIModelInitializer constructor.')


#####
# AMI file parser.
#####

# ignore cases.
whitespace = regex(r'\s+', re.MULTILINE)
comment = regex(r'\|.*')
ignore = many((whitespace | comment))

# lexer for words.
lexeme = lambda p: p << ignore  # skip all ignored characters.

lparen = lexeme(string('('))
rparen = lexeme(string(')'))
number = lexeme(regex(r'[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?'))
# symbol = lexeme(regex(r'[\d\w_-\[\]]+'))
symbol = lexeme(regex(r'[a-zA-Z_][^\s()]*'))
true = lexeme(string('True')).result(True)
false = lexeme(string('False')).result(False)
ami_string = lexeme(regex(r'"[^"]*"'))

atom = number | symbol | ami_string | (true | false)

@generate('AMI node')
def node():
    'Parse AMI node.'
    yield lparen
    label = yield symbol
    values = yield many1(expr)
    yield rparen
    err = StopIteration()
    err.value = (label, values)
    raise err

expr = atom | node
ami_defs = ignore >> node


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

    Inputs:

        - Pair, as described above.

    Outputs:

        - err_str     String containing any errors or warnings
                      encountered, while building the parameter
                      dictionary.

        - param_dict  Resultant parameter dictionary.

    """

    if(len(branch) != 2):
        if(len(branch) < 1):
            err_str = "ERROR: Empty branch provided to proc_branch()!\n"
        else:
            err_str = "ERROR: Malformed item: {}\n".format(branch[0])
        return (err_str, {})

    param_name = branch[0]
    param_tags = branch[1]

    if(len(param_tags) == 0):
        err_str = "ERROR: No tags/subparameters provided for parameter, '{}'\n".format(param_name)
        return (err_str, {})

    if( (len(param_tags) > 1) and (param_tags[0][0] in AMIParameter._param_def_tag_procs) and (param_tags[1][0] in AMIParameter._param_def_tag_procs) ):
        try:
            return ('', {param_name : AMIParameter(param_name, param_tags)})
        except AMIParamError as err:
            return (err.message, {})
    elif(param_name == 'Description'):
        return ('', {'description' : param_tags[0].strip('"')})
    else:
        err_str = ""
        param_dict = {}
        param_dict[param_name] = {}
        for param_tag in param_tags:
            temp_str, temp_dict = proc_branch(param_tag)
            param_dict[param_name].update(temp_dict)
            if(temp_str):
                err_str = "Error returned by recursive call, while processing parameter, '{}':\n{}".format(param_name, temp_str)
                return (err_str, param_dict)

        return (err_str, param_dict)


def parse_ami_param_defs(param_str):
    """
    Parse the contents of a IBIS-AMI parameter definition file.

    Inputs:

      - param_str   The contents of the file, as a single string.
                    For example:

                        with open(<ami_file_name>) as ami_file:
                            param_str = ami_file.read()
                            parse_ami_param_defs(param_str)

    Outputs:

      - err_str     None, if parser succeeds;
                    Helpful message, if it fails.

      - param_dict  Dictionary containing parameter definitions.
                    (Empty, on failure.)
                    It has a single key, at the top level, which is the
                    model root name. This key indexes the actual
                    parameter dictionary, which has the following
                    structure:

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
        err_str = "Expected {} at {} in {}".format(pe.expected, pe.loc(), pe.text[pe.index:])
        return err_str, {}

    err_str, param_dict = proc_branch(res)
    if(err_str):
        return (err_str, {  'res'  : res,
                            'dict' : param_dict})

    reserved_found               = False
    init_returns_impulse_found   = False
    getwave_exists_found         = False
    model_spec_found             = False
    params = param_dict.items()[0][1]
    for label in params.keys():
        if (label == 'Reserved_Parameters'):
            reserved_found = True
            tmp_params = params[label]
            for param_name in tmp_params.keys():
                if(not param_name in AMIParameter.RESERVED_PARAM_NAMES):
                    err_str += "WARNING: Unrecognized reserved parameter name, '{}', found in parameter definition string!\n".format(param_name)
                    continue
                param = tmp_params[param_name]
                if(param.pname == 'AMI_Version'):
                    if(param.pusage != 'Info' or param.ptype != 'String'):
                        err_str += "WARNING: Malformed 'AMI_Version' parameter.\n"
                elif(param.pname == 'Init_Returns_Impulse'):
                    init_returns_impulse_found = True
                elif(param.pname == 'GetWave_Exists'):
                    getwave_exists_found = True
        elif (label == 'Model_Specific'):
            model_spec_found = True
        elif (label == 'description'):
            pass
        else:
            err_str += "WARNING: Unrecognized group with label, '{}', found in parameter definition string!\n".format(label)

    if(not reserved_found):
        err_str += "ERROR: Reserved parameters section not found! It is required."

    if(not init_returns_impulse_found):
        err_str += "ERROR: Reserved parameter, 'Init_Returns_Impulse', not found! It is required."

    if(not getwave_exists_found):
        err_str += "ERROR: Reserved parameter, 'GetWave_Exists', not found! It is required."

    if(not model_spec_found):
        err_str += "WARNING: Model specific parameters section not found!"

    return (err_str, param_dict)

