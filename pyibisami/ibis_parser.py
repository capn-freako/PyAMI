"""
Parse an IBIS model file.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

import re
import numpy      as np
import platform

from parsec       import regex, eof, many1, many, string, generate, sepBy1, \
                         one_of, skip, none_of, times, ParseError, count, separated
from traits.api   import HasTraits, Trait, String, Float, List
from traitsui.api import Item, View, ModalButtons, Group, spring
from chaco.api    import ArrayPlotData, Plot
from enable.component_editor import ComponentEditor

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
        if 'models' in model_dict:
            models = model_dict['models']
            self.add_trait('_model',    Trait(list(models)[0], models))
            self.add_trait('ibis_ver',  Float(model_dict['ibis_ver']))
            self.add_trait('file_name', String(model_dict['file_name']))
            self.add_trait('file_rev',  String(model_dict['file_rev']))
            self.add_trait('date',      String(model_dict['date']))
            self._content = [
                Group(
                    Group(
                        Item('file_name', label='File name', style='readonly'),
                        spring,
                        Item('file_rev', label='rev', style='readonly'),
                        orientation="horizontal",
                    ),
                    Group(
                        Item('ibis_ver', label='IBIS ver', style='readonly'),
                        spring,
                        Item('date', label='Date', style='readonly'),
                        orientation="horizontal",
                    ),
                    label='Info', show_border=True,
                ),
                Item('_model'),
                ]

        self._ibis_parsing_errors = err_str
        self._model_dict = model_dict

    def __str__(self):
        res = ""
        for k in ['ibis_ver', 'file_name', 'file_rev']:
            res += k + ':\t' + str(self._model_dict[k]) + '\n'
        res += 'date' + ':\t\t' + str(self._model_dict['date']) + '\n'
        res += "Models:\n"
        for m in list(self._model_dict['models']):
            res += "\n" + m + ":\n" + "===\n" + str(self._model_dict['models'][m])
        return res

    def __call__(self):
        """Present a customized GUI to the user, for model selection, etc."""
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
        "Dictionary of all model keywords."
        return self._model_dict

    @property
    def model(self):
        """The model selected most recently by the user.

        Returns the first model parsed, if the user hasn't made a selection yet.
        """
        return self._model_

class Model(HasTraits):
    """Encapsulation of a particular I/O model from an IBIS model file.
    """

    def __init__(self, subDict):
        """
        Args:
            subDict (dict): Dictionary of sub-keywords/params.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super(Model, self).__init__()

        # Stash the sub-keywords/parameters.
        self._subDict = subDict

        # Fetch available keyword/parameter definitions.
        def maybe(name):
            return subDict[name] if name in subDict else None
        self._mtype  = maybe('model_type')
        self._ccomp  = maybe('c_comp')
        self._cref   = maybe('cref')
        self._vref   = maybe('vref')
        self._vmeas  = maybe('vmeas')
        self._rref   = maybe('rref')
        self._trange = maybe('temperature_range')
        self._vrange = maybe('voltage_range')
        self._ramp   = maybe('ramp')

        # Check for the required keywords.
        if not self._mtype:
            raise LookupError("Missing Model_type!")
        if not self._vrange:
            raise LookupError("Missing [Voltage Range]!")
        
        # Infer impedance and rise/fall time for output models.
        if self._mtype == 'Output':
            if 'pulldown' not in subDict or 'pullup' not in subDict:
                raise LookupError("Missing I-V curves!")
            plotdata = ArrayPlotData()
            def proc_iv(xs):
                if len(xs) < 2:
                    raise ValueError("Insufficient number of I-V data points!")
                vs, iss = zip(*(xs))  # Idiomatic Python for `unzip`.
                ityps, imins, imaxs = zip(*iss)
                vmeas = self._vmeas
                def calcZ(x):
                    (vs, ivals) = x
                    if vmeas:
                        ix = np.where(np.array(vs) >= vmeas)[0][0]
                    else:
                        ix = np.where(np.array(vs) >= max(vs)/2)[0][0]
                    return abs((vs[ix] - vs[ix-1])/(ivals[ix] - ivals[ix-1]))
                zs = map(calcZ, zip([vs, vs, vs], [ityps, imins, imaxs]))
                return vs, ityps, imins, imaxs, zs
            pd_vs, pd_ityps, pd_imins, pd_imaxs, pd_zs = proc_iv(subDict['pulldown'])
            pu_vs, pu_ityps, pu_imins, pu_imaxs, pu_zs = proc_iv(subDict['pullup'])
            pu_vs = self._vrange[0] - np.array(pu_vs)  # Correct for Vdd-relative pull-up voltages.
            pu_ityps = -np.array(pu_ityps)             # Correct for current sense, for nicer plot.
            pu_imins = -np.array(pu_imins)
            pu_imaxs = -np.array(pu_imaxs)
            self._zout = (list(pd_zs)[0] + list(pu_zs)[0])/2
            plotdata.set_data("pd_vs",    pd_vs)
            plotdata.set_data("pd_ityps", pd_ityps)
            plotdata.set_data("pd_imins", pd_imins)
            plotdata.set_data("pd_imaxs", pd_imaxs)
            plotdata.set_data("pu_vs",    pu_vs)
            plotdata.set_data("pu_ityps", pu_ityps)
            plotdata.set_data("pu_imins", pu_imins)
            plotdata.set_data("pu_imaxs", pu_imaxs)
            plot_iv = Plot(plotdata)  # , padding_left=75)
            # The 'line_style' trait of a LinePlot instance must be 'dash' or 'dot dash' or 'dot' or 'long dash' or 'solid'.
            plot_iv.plot(("pd_vs", "pd_ityps"), type="line", color="blue", line_style="solid", name="PD-Typ")
            plot_iv.plot(("pd_vs", "pd_imins"), type="line", color="blue", line_style="dot",   name="PD-Min")
            plot_iv.plot(("pd_vs", "pd_imaxs"), type="line", color="blue", line_style="dash",  name="PD-Max")
            plot_iv.plot(("pu_vs", "pu_ityps"), type="line", color="red",  line_style="solid", name="PU-Typ")
            plot_iv.plot(("pu_vs", "pu_imins"), type="line", color="red",  line_style="dot",   name="PU-Min")
            plot_iv.plot(("pu_vs", "pu_imaxs"), type="line", color="red",  line_style="dash",  name="PU-Max")
            plot_iv.title = "Pull-Up/Down I-V Curves"
            plot_iv.index_axis.title = "Vout (V)"
            plot_iv.value_axis.title = "Iout (A)"
            plot_iv.index_range.low_setting  = 0
            plot_iv.index_range.high_setting = self._vrange[0]
            plot_iv.value_range.low_setting  = 0
            plot_iv.value_range.high_setting = 0.1
            plot_iv.legend.visible = True
            plot_iv.legend.align = "ul"
            self.plot_iv = plot_iv

            if not self._ramp:
                raise LookupError("Missing [Ramp]!")
            ramp = subDict['ramp']
            self._slew = (ramp['rising'][0] + ramp['falling'][0])/2e9  # (V/ns)

        # Separate AMI executables by OS.
        def is64(x):
            ((_, b), _) = x
            return int(b) == 64

        def isWin(x):
            ((os, _), _) = x
            return os == 'Windows'

        def showExec(x):
            ((os, b), fs) = x
            return os + str(b) + ': ' + str(fs)

        def partition(p, xs):
            ts, fs = [], []
            for x in xs:
                ts.append(x) if p(x) else fs.append(x)
            return ts, fs

        def getFiles(x):
            ((_, _), fs) = x
            return fs

        if 'algorithmic_model' in subDict:
            execs = subDict['algorithmic_model']
            exec64s, exec32s = partition(is64, execs)
            self._exec32Wins, self._exec32Lins = list(map(lambda x: list(map(getFiles, x))[0], partition(isWin, exec32s)))
            self._exec64Wins, self._exec64Lins = list(map(lambda x: list(map(getFiles, x))[0], partition(isWin, exec64s)))

        # Set up the GUI.
        self.add_trait('model_type', String(self._mtype))
        self.add_trait('c_comp', String(self._ccomp))
        self.add_trait('cref',   String(self._cref))
        self.add_trait('vref',   String(self._vref))
        self.add_trait('vmeas',  String(self._vmeas))
        self.add_trait('rref',   String(self._rref))
        self.add_trait('trange', String(self._trange))
        self.add_trait('vrange', String(self._vrange))
        if self._mtype == 'Output':
            self.add_trait('zout',   String(self._zout))
            self.add_trait('slew',   String(self._slew))
        self._content = [
            Group(
                Item('model_type', label='Model type',            style='readonly'),
                Item('c_comp',     label='Ccomp',                 style='readonly'),
                Item('trange',     label='Temperature Range',     style='readonly'),
                Item('vrange',     label='Voltage Range',         style='readonly'),
                Group(
                    Item('cref', label='Cref', style='readonly'),
                    Item('vref', label='Vref', style='readonly'),
                    Item('vmeas', label='Vmeas', style='readonly'),
                    Item('rref', label='Rref', style='readonly'),
                    orientation="horizontal",
                ),
                label='Model', show_border=True,
            ),
        ]
        if self._mtype == 'Output':
            self._content.append(Item('zout',       label='Impedance (Ohms)',      style='readonly', format_str='%4.1f'))
            self._content.append(Item('slew',       label='Slew Rate (V/ns)',      style='readonly', format_str='%4.1f'))
            self._content.append(Item('plot_iv', editor=ComponentEditor(), show_label=False))

    def __str__(self):
        res = "Model Type:\t" + self._mtype + '\n'
        res += "C_comp:    \t" + str(self._ccomp) + '\n'
        res += "Cref:      \t" + str(self._cref)  + '\n'
        res += "Vref:      \t" + str(self._vref)  + '\n'
        res += "Vmeas:     \t" + str(self._vmeas) + '\n'
        res += "Rref:      \t" + str(self._rref)  + '\n'
        res += "Temperature Range:\t" + str(self._trange) + '\n'
        res += "Voltage Range:    \t" + str(self._vrange) + '\n'
        res += "Algorithmic Model:\n" \
               + "\t32-bit:\n" \
               + "\t\tLinux: "   + str(self._exec32Lins) + '\n' \
               + "\t\tWindows: " + str(self._exec32Wins) + '\n' \
               + "\t64-bit:\n" \
               + "\t\tLinux: "   + str(self._exec64Lins) + '\n' \
               + "\t\tWindows: " + str(self._exec64Wins) + '\n' \
        # res += "\n" + str(self._subDict)
        return res

    def __call__(self):
        self.edit_traits()

    def default_traits_view(self):
        view = View(
            resizable=False,
            buttons=ModalButtons,
            title="PyBERT IBIS Model Viewer",
            id="pyibisami.ibis_parser.Model",
        )
        view.set_content(self._content)
        return view

    @property
    def zout(self):
        "The driver impedance."
        return self._zout

    @property
    def slew(self):
        "The driver impedance."
        return self._slew
        
    @property
    def ccomp(self):
        "The driver impedance."
        return self._ccomp
        
# Parser Definitions

whitespace = regex(r"\s+", re.MULTILINE)
comment = regex(r"\|.*")
ignore = many((whitespace | comment))

def lexeme(p):
    """Lexer for words."""
    return p << ignore  # Skip all ignored characters after word.

name = lexeme(regex(r"[_a-zA-Z0-9/\.-]+"))
symbol = lexeme(regex(r"[a-zA-Z_][^\s()\[\]]*"))
true = lexeme(string("True")).result(True)
false = lexeme(string("False")).result(False)
quoted_string = lexeme(regex(r'"[^"]*"'))
fail = one_of("")
skip_keyword = (many(none_of("[")) >> ignore).result('(Skipped.)')  # Skip over everything until the next keyword begins.
skip_line = (many(none_of("\n\r")) >> ignore).result('(Skipped.)')

IBIS_num_suf = {
    'T': 'e12',
    'k': 'e3',
    'n': 'e-9',
    'G': 'e9',
    'm': 'e-3',
    'p': 'e-12',
    'M': 'e6',
    'u': 'e-6',
    'f': 'e-15',
}
@generate("number")
def number():
    "Parse an IBIS numerical value."
    s = yield lexeme(regex(r"[-+]?[0-9]*\.?[0-9]+(([eE][-+]?[0-9]+)|([TknGmpMuf][a-zA-Z]*))?"))
    m = re.search('[^\d]+$', s)
    if m:
        ix = m.start()
        c = s[ix]
        if c in IBIS_num_suf:
            res = float(s[:ix] + IBIS_num_suf[c])
        else:
            raise ParseError("IBIS numerical suffix", s[ix:], ix)
    else:
        res = float(s)
    return res

# Note: This doesn't catch the error of providing exactly 2 numbers!
typminmax = times(number, 1, 3)
vi_line   = number + typminmax

@generate("ratio")
def ratio():
    [num, den] = yield separated(number, string("/"), 2, maxt=2, end=False)
    return num/den

ramp_line = string("dV/dt_") >> ((string("r").result("rising") | string("f").result("falling")) << ignore) + times(ratio, 1, 3)
ex_line = lexeme(string("Executable")) \
          >> ((string("linux") | string("Windows")) << string("_") << many(none_of("_")) << string("_")) \
          + lexeme(string("32") | string("64")) \
          + count(name, 2)

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

def node(valid_keywords, stop_keywords, valid_parameters, debug=False):
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
        if debug:
            print(nmL)
        if nmL in valid_keywords:
            if nmL == "end":  # Because `ibis_file` expects this to be the last thing it sees,
                return fail   # we can't consume it here.
            else:
                res = yield valid_keywords[nmL]  # Parse the sub-keyword.
        elif nmL in stop_keywords:
            return fail                          # Stop parsing.
        else:
            res = yield (typminmax ^ skip_keyword)
        return (nmL, res)

    @generate("lbl")
    def lbl():
        "Parse non-keyword syntax."
        nm = yield name
        nmL = nm.lower()
        if nmL in valid_parameters:
            res = yield valid_parameters[nmL]  # Parse the sub-parameter.
            return (nmL, res)
        else:  # Note: Doesn't handle "<param_name>\n" lines properly!
            res = yield (many(lexeme(string('='))) >> (typminmax ^ skip_line))
            return (nmL, res)

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
    res = yield many1(node(Model_keywords, IBIS_keywords, Model_params))
    return {nm: Model(dict(res))}

@generate("[Ramp]")
def ramp():
    "Parse [Ramp]."
    lines = yield count(ramp_line, 2)
    return dict(lines)

Model_keywords = {
    "pulldown": many1(vi_line),
    "pullup": many1(vi_line),
    "ramp": ramp,
    "algorithmic_model": many1(ex_line) << keyword('end_algorithmic_model')
}

Model_params = {
    "model_type": name,
    "c_comp": times(number, 1, 3),
}

# Note: The following dictionary MUST have a complete set of keys,
#       in order for the parsing logic to work correctly!
IBIS_keywords = {
    "model": model,
    "end": end,
    "ibis_ver": number,
    "comment_char": skip_keyword,
    "file_name": name,
    "file_rev": name,
    "date": name,
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
        nodes = ibis_file.parse(ibis_file_contents_str)
    except ParseError as pe:
        err_str = "Expected {} at {} in {}".format(pe.expected, pe.loc(), pe.text[pe.index :])
        return err_str, {}

    kw_dict = {}
    models  = {}    
    for (kw, val) in nodes:
        if kw == 'model':
            models.update(val)
        else:
            kw_dict.update({kw: val})
    kw_dict.update({'models': models})
    return "Success!", kw_dict

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
