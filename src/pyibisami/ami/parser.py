"""IBIS-AMI parameter parsing and configuration utilities.

Original author: David Banas <capn.freako@gmail.com>

Original date:   December 17, 2016

Copyright (c) 2019 David Banas; all rights reserved World wide.
"""

from __future__     import annotations
from ctypes         import c_double
from dataclasses    import dataclass
import logging
import re
from typing         import Any, NewType, Optional, TypeAlias, cast
from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray
from parsec import ParseError, generate, many, regex, string
from traits.api import Bool, Enum, HasTraits, Range, Trait, TraitType

from .model                     import AMIModelInitializer
from .parameter                 import FIXED_FORMATS, AmiParamTuner, AMIParamError, AMIParameter
from .reserved_parameter_names  import AmiReservedParameterName, RESERVED_PARAM_NAMES

logger = logging.getLogger(__name__)

# New types and aliases.
# Parameters  = NewType('Parameters',  dict[str, AMIParameter] | dict[str, 'Parameters'])
# ParamValues = NewType('ParamValues', dict[str, list[Any]]    | dict[str, 'ParamValues'])
# See: https://stackoverflow.com/questions/70894567/using-mypy-newtype-with-type-aliases-or-protocols
ParamName  = NewType("ParamName", str)
Parameters:  TypeAlias = dict[ParamName, "'AMIParameter' | 'Parameters'"]
ParamValue:  TypeAlias = int | float | str | list["ParamValue"]
ParamValues: TypeAlias = dict[ParamName, "'ParamValue'   | 'ParamValues'"]

# AMI parameter tree structure.
AmiName = NewType("AmiName", str)
AmiAtom: TypeAlias = bool | int | float | str


@dataclass(frozen=True)
class AmiLeaf:
    name: AmiName
    values: list[AmiAtom]


@dataclass(frozen=True)
class AmiBranch:
    name: AmiName
    children: list[AmiNode]


AmiNode:       TypeAlias = AmiLeaf | AmiBranch
AmiNodeParser: TypeAlias = Callable[[str], AmiNode]
AmiParser:     TypeAlias = Callable[[str], tuple[AmiName, list[AmiNode]]]  # Atoms may not exist at the root level.

# Local definitions.
ParseErrMsg = NewType("ParseErrMsg", str)
AmiRootName = NewType("AmiRootName", str)
ReservedParamDict: TypeAlias = dict[AmiReservedParameterName, AMIParameter]
ModelSpecificDict: TypeAlias = dict[ParamName, "'AMIParameter' | 'ModelSpecificDict'"]

__all__ = [  # ruff: ignore=RUF022
    "ParamName", "ParamValue", "Parameters", "ParamValues",
    "AmiName", "AmiAtom", "AmiNode", "AmiNodeParser", "AmiParser",
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

    Parameters of Format Corner aren't user-selectable: their value follows ``sim_corner``
    (``"typ"``, ``"min"`` (slow) or ``"max"`` (fast); IBIS 8.0 Section 10.3.5, p.246), the same
    corner the application uses for the IBIS model data.
    """

    sim_corner = Enum("typ", "min", "max")  # Simulation corner; selects each Corner parameter's value.

    def __init__(self, ami_file_contents_str: str) -> None:
        """
        Args:
            ami_file_contents_str: The unprocessed contents of the AMI file, as a single string.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super().__init__()

        # Parse the AMI file contents, storing any errors or warnings, and customize the view accordingly.
        (errors,
         warnings,
         root_name,
         description,
         reserved_param_dict,
         model_specific_dict) = parse_ami_file_contents(ami_file_contents_str)
        if errors:
            err_msgs = ["AMI parsing errors:"]
            err_msgs.extend(errors)
            raise RuntimeError("\n\t".join(err_msgs))
        if not reserved_param_dict:
            raise ValueError("No 'Reserved_Parameters' section found!")
        trait_names = []
        for pname, param in model_specific_dict.items():
            for trait_name, trait in make_param_traits(trait_name_part(pname), param):
                self.add_trait(trait_name, trait)
                trait_names.append(trait_name)
        self._param_trait_names = trait_names
        self._root_name = root_name
        self._ami_parsing_errors = errors + warnings
        self._reserved_param_dict = reserved_param_dict
        self._model_specific_dict = model_specific_dict
        self._description = description

    def __call__(self):
        self.open_gui()

    def open_gui(self):
        """Present a customized GUI to the user, for parameter
        customization.

        Requires the ``gui`` extra: ``pip install 'pyibis-ami[gui]'``.
        """
        from .. import gui  # noqa: F401  # pylint: disable=import-outside-toplevel,unused-import
        # self.configure_traits(kind='modal')  # Waiting for Enthought/Traits PR1841 to be accepted.
        self.configure_traits()

    def default_traits_view(self):
        "Default Traits/UI view definition."
        from ..gui.ami_config import make_view  # pylint: disable=import-outside-toplevel
        return make_view(self)

    @property
    def root_name(self) -> str:
        "The AMI model root name."
        return self._root_name

    @property
    def model_specific_dict(self) -> ModelSpecificDict:
        "The parsed ``Model_Specific`` parameter definitions."
        return self._model_specific_dict

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
            return self._fixed_value(_param) if _param.pformat == "Corner" else _param.pvalue
        return None

    def _fixed_value(self, param: AMIParameter) -> Any:
        """The value sent for a parameter of one of the ``FIXED_FORMATS``: a Corner's value for ``sim_corner``,
        a Table's rows flattened (IBIS 8.0 p.242), or a Gaussian/Dual-Dirac/DjRj's numbers."""
        if param.pformat == "Corner":
            return param.pcorners[self.sim_corner]  # type: ignore[index]
        if param.pformat == "Table":
            return [value for row in param.pvalue for value in row]
        return param.pvalue

    def set_param_val(
        self: AMIParamConfigurator,
        branch_names: list[str],
        new_val: Any
    ) -> None:
        """
        Sets the value of the parameter found by traversing 'branch_names'
        or raises an exception if not found.

        Args:
            branch_names: A sequence of node names, used to traverse the parameter tree.
            new_val: The value to assign to the target parameter.

        Notes:
            1. ``branch_names`` should *not* begin with <root_name>.
            2. Be careful! There is no checking done here!
        """

        param_dict = self.ami_param_defs
        tname_parts: list[str] = []  # Fully hierarchical trait name, minus the root key.
        root_key: Optional[str] = None
        while branch_names:
            branch_name = branch_names.pop(0)
            if root_key is None:
                root_key = branch_name  # "Reserved_Parameters" or "Model_Specific"; not part of the trait name.
            else:
                tname_parts.append(trait_name_part(branch_name))
            if branch_name in param_dict:
                param_dict = param_dict[branch_name]  # type: ignore
            else:
                raise ValueError(
                    f"Failed parameter tree search looking for: {branch_name}; available keys: {param_dict.keys()}"
                )
        if isinstance(param_dict, AMIParameter):
            if param_dict.pformat == "Corner":
                raise ValueError(f"A Corner parameter's value follows `sim_corner`; it can't be set: {branch_names}")
            if param_dict.pformat in FIXED_FORMATS:  # Table, Gaussian, ...: stored as given, no trait.
                param_dict.pvalue = new_val
                return
            # Coerce to the parameter's declared type. Notably: a `Bool` trait rejects a
            # float outright, and a vendor's AMI_Init() parser may choke on "1.0" where an
            # Integer-typed value (e.g. a List-format mode selector) is expected.
            if param_dict.ptype == "Boolean":
                if not isinstance(new_val, bool):
                    if isinstance(new_val, str):
                        match new_val:
                            case "FALSE" | "False" | "false":
                                new_val = False
                            case _:
                                new_val = bool(new_val)
                    else:
                        new_val = bool(new_val)
            elif param_dict.ptype == "Integer":
                new_val = int(new_val)
            elif param_dict.ptype in ("Float", "UI", "Tap"):  # A Tap is a (float) tap weight.
                new_val = float(new_val)
            # `pvalue`, for 'List' format, holds the list of *legal* values, not the
            # current one (that lives on the Trait) -- leave it alone, to avoid corrupting it.
            if param_dict.pformat != "List":
                param_dict.pvalue = new_val
            tname = "_".join(tname_parts)
            if tname:
                try:
                    self.trait_set(**{f"{tname}_": new_val})
                except Exception:  # pylint: disable=broad-exception-caught
                    self.trait_set(**{tname: new_val})
        else:
            raise TypeError(f"{param_dict} is not of type: AMIParameter!")

    @property
    def tunable_params(self) -> list[tuple[list[str], AMIParameter]]:
        """Every *Model Specific* parameter of type 'In' or 'InOut' that is a
        candidate for automated sweeping/optimization, paired with its fully
        hierarchical branch name path. This includes:

            - numeric 'Range'-format parameters (real min/max bounds),
            - 'Boolean' parameters (True/False), and
            - 'List'-format 'Integer' parameters whose legal values form a
              contiguous range (e.g. a mode selector like `(List 0 1)`) --
              this is deliberately conservative: a non-contiguous legal set
              (e.g. `(List 6 12 18)`) can't be swept with a uniform step
              without risking illegal intermediate values, so it's excluded.

        The returned branch name paths are ready to pass directly into
        ``fetch_param_val()``/``set_param_val()`` (i.e. - they are rooted at
        ``"Model_Specific"``).
        """
        return _walk_tunable_params(self._model_specific_dict, ["Model_Specific"])

    def mk_tap_tuners(self) -> list[AmiParamTuner]:
        """Build a fresh list of `AmiParamTuner`s from this AMI model's tunable
        Model_Specific parameters (see `tunable_params` for exactly which ones
        qualify: Range-format, Boolean, and contiguous Integer/List "mode
        selector" parameters)."""
        tuners = []
        for branch_names, param in self.tunable_params:
            tname = "_".join(map(trait_name_part, branch_names[1:]))  # Drop the "Model_Specific" root.
            if param.pformat == "Range":
                pmin, pmax = float(param.pmin), float(param.pmax)
                step = (pmax - pmin) / 10 or 1.0
                is_int = param.ptype == "Integer"
                value = float(param.pvalue)
            elif param.pformat == "Value" and param.ptype == "Boolean":
                pmin, pmax, step, is_int = 0.0, 1.0, 1.0, True
                value = float(param.pvalue)
            else:  # List-format Integer "mode selector" (contiguous legal values).
                vals = [float(v) for v in param.pvalue]
                pmin, pmax, step, is_int = min(vals), max(vals), 1.0, True
                # `pvalue`, for 'List' format, is the list of *legal* values, not the
                # current one -- that lives on the Trait `make_param_traits()` registered.
                try:
                    value = float(self.trait_get(tname + "_")[tname + "_"])
                except Exception:  # pylint: disable=broad-exception-caught
                    value = float(self.trait_get(tname)[tname])
            tuners.append(AmiParamTuner(
                name=tname,
                branch_names=branch_names,
                enabled=False,
                min_val=pmin,
                max_val=pmax,
                step=step,
                value=value,
                is_int=is_int,
            ))
        return tuners

    @property
    def ami_parsing_errors(self) -> list[str]:
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
        tname = prefix + trait_name_part(pname)  # The fully hierarchical trait name, used by the Traits/UI machinery.
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
            elif param.pusage in ("In", "InOut") and param.pformat in FIXED_FORMATS:  # Sent, but has no trait.
                res[pname] = self._fixed_value(param)
        elif isinstance(param, dict):  # We received a dictionary of subparameters, in 'param'.
            subs: ParamValues = {}
            for sname in param:
                subs.update(self.input_ami_param(param, sname, prefix=tname + "_"))  # type: ignore
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


def _is_sweepable(param: AMIParameter) -> bool:
    "See `AMIParamConfigurator.tunable_params` for the exact criteria."
    if param.pusage not in ("In", "InOut"):
        return False
    if param.pformat == "Range":
        return True
    if param.pformat == "Value" and param.ptype == "Boolean":
        return True
    if param.pformat == "List" and param.ptype == "Integer":
        vals = sorted(int(v) for v in param.pvalue)
        return vals == list(range(vals[0], vals[-1] + 1))  # Contiguous?
    return False


def _walk_tunable_params(
    params: Parameters, prefix: list[str]
) -> list[tuple[list[str], AMIParameter]]:
    """Recursively collect every sweepable (see `_is_sweepable`) leaf of a
    *Model Specific* parameter (sub)tree.

    Args:
        params: The (sub)dictionary of AMI parameters to walk.
        prefix: The branch name path leading to ``params``.

    Returns:
        A list of (branch name path, parameter) pairs, one per sweepable leaf.
    """

    results: list[tuple[list[str], AMIParameter]] = []
    for pname, param in params.items():
        if pname == "description":  # A branch's optional descriptive text, not a subparameter.
            continue
        path = prefix + [pname]
        if isinstance(param, AMIParameter):
            if _is_sweepable(param):
                results.append((path, param))
        else:  # Subparameter branch.
            results.extend(_walk_tunable_params(param, path))
    return results


def _walk_params(params: Parameters, prefix: list[str]) -> list[tuple[list[str], AMIParameter]]:
    "Every leaf parameter of a (sub)tree, with its branch name path."
    results: list[tuple[list[str], AMIParameter]] = []
    for pname, param in params.items():
        if isinstance(param, AMIParameter):
            results.append((prefix + [pname], param))
        elif isinstance(param, dict):  # Subparameter branch; skips a branch's "description" text.
            results.extend(_walk_params(param, prefix + [pname]))
    return results


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
    match x[0]:
        case "-":
            res = "pre" + x[1:]
        case "+":
            res = "post" + x[1:]
        case _:
            res = "post" + x
    return res


def trait_name_part(name: str) -> str:
    """The trait/display form of one AMI parameter name.

    Tap weights are named by tap number (``-1``, ``0``, ``1``; IBIS 8.0 Section 10.3.4, p.240), which isn't a valid
    trait name, so they're shown as ``pre1``, ``post0``, ``post1`` (see ``int2tap()``). Everything sent to the
    model (``input_ami_params``, ``fetch_param_val()``/``set_param_val()`` paths) keeps the ``.ami`` names.
    """
    return int2tap(name) if re.fullmatch(r"[-+]?[0-9]+", name) else name


lparen = lexeme(string("("))
rparen = lexeme(string(")"))
number = lexeme(regex(r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?"))
integ = lexeme(regex(r"[-+]?[0-9]+"))
nat = lexeme(regex(r"[0-9]+"))
# A tap number, as written; the lookahead stops it matching the start of a number (e.g. ``-0.5`` in a Table row).
tap_ix = lexeme(regex(r"[-+]?[0-9]+(?=[\s()|])"))
symbol = lexeme(regex(r"[0-9a-zA-Z_][^\s()]*"))
true = lexeme(string("True")).result(True)
false = lexeme(string("False")).result(False)
ami_string = lexeme(regex(r'"[^"]*"'))

atom = number | symbol | ami_string | (true | false)
node_name = tap_ix ^ symbol  # `tap_ix` is new and gives the tap position; negative positions are allowed.
number_re = re.compile(r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?")
# First entry of a Table row that isn't also a name: a signed/decimal number (e.g. ``-0.169``) or a quoted string.
row_head = lexeme(regex(number_re.pattern + r"(?=[\s()|])")) | ami_string


@generate("AMI node")
def node():
    """Parse AMI node: ``(name values...)`` gives ``(name, values)``.

    A Table row (IBIS 8.0 p.242), i.e. - a number or quoted string followed only by atoms, gives a plain list instead:
    ``(1 -0.5 2)`` gives ``["1", "-0.5", "2"]``. (A tap, e.g. ``(-1 (Usage In) ...)``, contains nodes.)
    """
    yield lparen
    label  = yield node_name ^ row_head
    values = yield many(expr)
    yield rparen
    if (number_re.fullmatch(label) or label.startswith('"')) and all(isinstance(v, str) for v in values):
        return [label] + values
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


def proc_branch(  # pylint: disable=too-many-return-statements
    branch, skipped: Optional[list[str]] = None, path: Optional[tuple[str, ...]] = None
) -> tuple[str, dict[str, Any]]:
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

    A parameter that can't be built (or a malformed item) is skipped: it's left out of the result, and a
    ``"Skipped parameter <path>: <reason>"`` message is logged and added to ``skipped``. The rest of the tree loads.

    Args:
        branch (str, list): A pair, as described above.

    Keyword Args:
        skipped: Collects the messages for skipped parameters.
            Default: None (only logged)
        path: The names of the enclosing branches, below the root; ``None`` for the root itself.
            Default: None

    Returns:
        (str, dict): A pair containing:
            err_str: Always empty (kept for compatibility); see ``skipped``.
            param_dict: Resultant parameter dictionary.
    """
    def skip(name: str, reason: str) -> tuple[str, dict[str, Any]]:
        msg = f"Skipped parameter {'.'.join((path or ()) + (name,))}: {reason.strip()}"
        logger.warning(msg)
        if skipped is not None:
            skipped.append(msg)
        return ("", {})

    results: tuple[str, dict[str, Any]] = ("", {})  # Empty Results
    if not isinstance(branch, tuple) or len(branch) != 2:
        return skip("<item>", f"Malformed item: {branch}")
    param_name, param_tags = branch
    if not param_tags:
        return skip(param_name, "No tags or subparameters.")
    child_path = () if path is None else path + (param_name,)

    tag_names = AMIParameter._param_def_tag_procs  # pylint: disable=protected-access
    try:
        # A parameter has at least one tag other than Description (which a branch of subparameters may also have).
        if any(isinstance(tag, tuple) and tag[0] in tag_names and tag[0] != "Description" for tag in param_tags):
            try:
                results = ("", {param_name: AMIParameter(param_name, param_tags)})
            except AMIParamError as err:
                return skip(param_name, str(err))
        elif param_name == "Description":
            results = ("", {"description": param_tags[0].strip('"')})
        elif not all(isinstance(tag, tuple) for tag in param_tags):
            return skip(param_name, f"Expected parameter tags or subparameters; got {param_tags}")
        else:
            param_dict: dict[str, Any] = {}
            param_dict[param_name] = {}
            for param_tag in param_tags:
                _, temp_dict = proc_branch(param_tag, skipped, child_path)
                param_dict[param_name].update(temp_dict)
            results = ("", param_dict)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Error processing branch:\n%s", param_tags)
    return results


def parse_ami_file_contents(  # pylint: disable=too-many-locals,too-many-branches
    file_contents: str
) -> tuple[list[str], list[str], AmiRootName, str, ReservedParamDict, ModelSpecificDict]:
    """
    Parse the contents of an IBIS-AMI *parameter definition* (i.e. - `*.ami`) file.

    Args:
        file_contents: The contents of the file, as a single string.

    Example:
        ::

            with open(<ami_file_name>) as ami_file:
                file_contents = ami_file.read()
                (errors,
                 warnings,
                 root_name,
                 description,
                 reserved_param_dict,
                 model_specific_param_dict
                ) = parse_ami_file_contents(file_contents)

    Returns:
        A tuple containing

            1. Any error messages generated by the parser and/or this function. (empty on success)

            2. Any warning messages generated by this function upon inspecting the parsed results.

            3. AMI file "root" name.

            4. The value of the *Description* leaf.

            5. *Reserved Parameters* dictionary. (empty on failure)

                - The keys of the *Reserved Parameters* dictionary are
                limited to those called out in the IBIS-AMI specification.

                - The values of the *Reserved Parameters* dictionary
                must be instances of class ``AMIParameter``.

            6. *Model Specific Parameters* dictionary. (optional)

                - The keys of the *Model Specific Parameters* dictionary can be anything.

                - The values of the *Model Specific Parameters* dictionary
                may be either: an instance of class ``AMIParameter``, or a nested sub-dictionary.

    Raises:
        RuntimeError: If ``ami_parse()`` function fails or returns a malformed S-expression.
    """

    try:
        res = ami_parse(file_contents)
    except ParseError as pe:
        raise RuntimeError(
            f"Expected {pe.expected} at {pe.loc()} in: {pe.text[pe.index: pe.index + 20]}"
        ) from pe

    skipped: list[str] = []
    _, param_dict = proc_branch(res, skipped)
    if len(param_dict.keys()) != 1:
        raise RuntimeError(
            f"Malformed AMI parameter S-exp has top-level keys: {param_dict.keys()}!"
        )

    errors: list[str] = []
    warnings: list[str] = list(skipped)  # A bad parameter is left out; a required one is then reported missing.

    def log_error(msg: str) -> None:
        errors.append(msg)

    def log_warning(msg: str) -> None:
        warnings.append(msg)

    reserved_found = False
    init_returns_impulse_found = False
    getwave_exists_found = False
    model_spec_found = False
    root_name, params = next(iter(param_dict.items()))
    description = ""
    reserved_params_dict: dict[AmiReservedParameterName, AMIParameter] = {}
    model_specific_dict: ModelSpecificDict = {}

    for label in list(params.keys()):
        tmp_params = params[label]
        if label == "Reserved_Parameters":
            reserved_found = True
            for param_name in list(tmp_params.keys()):
                if param_name not in RESERVED_PARAM_NAMES:
                    log_warning(f"Unrecognized reserved parameter name, '{param_name}', found in parameter definition string!")
                    continue
                param = tmp_params[param_name]
                if param.pname == "AMI_Version":
                    if param.pusage != "Info" or param.ptype != "String":
                        log_warning("Malformed 'AMI_Version' parameter.")
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
            log_warning(f"Unrecognized group with label, '{label}', found in parameter definition string! "
                        "Only Reserved_Parameters, Model_Specific and Description may be at the top level "
                        "(IBIS 8.0 Section 10.3.2, p.236).")

    leaves = (_walk_params(cast(Parameters, reserved_params_dict), ["Reserved_Parameters"])
              + _walk_params(model_specific_dict, ["Model_Specific"]))  # noqa: W503
    for path, param in leaves:
        if param.msg:  # Problems that don't stop the parameter loading (e.g. - an unusable Default).
            log_warning(f"{'.'.join(path)}: {param.msg.strip()}")

    version = reserved_params_dict.get("AMI_Version")  # type: ignore[call-overload]
    version_match = re.match(r"\s*(\d+)\.(\d+)", str(version.pvalue)) if version else None
    is_5_1_or_later = version_match is not None and (int(version_match[1]), int(version_match[2])) >= (5, 1)
    labels = list(params.keys())
    if is_5_1_or_later and model_spec_found and labels.index("Model_Specific") < labels.index("Reserved_Parameters"):
        log_warning("For AMI_Version 5.1 and later, Reserved_Parameters must come before Model_Specific "
                    "(IBIS 8.0 Section 10.3.2, p.237).")

    if not reserved_found:
        log_error("Reserved parameters section not found! It is required.")

    if not init_returns_impulse_found:
        log_error("Reserved parameter, 'Init_Returns_Impulse', not found! It is required.")

    if not getwave_exists_found:
        log_error("Reserved parameter, 'GetWave_Exists', not found! It is required.")

    if not model_spec_found:
        log_warning("Model specific parameters section not found!")

    return (errors, warnings, AmiRootName(root_name), description, reserved_params_dict, model_specific_dict)


# Legacy client code support:
def parse_ami_param_defs(file_contents: str) -> tuple[ParseErrMsg, dict[str, Any]]:
    "The legacy version of ``parse_ami_file_contents()``."
    errors, _warnings, root_name, description, reserved_params_dict, model_specific_dict = parse_ami_file_contents(file_contents)
    if errors:
        err_msg = errors[0]
    else:
        err_msg = ""
    return (
        ParseErrMsg(err_msg),
        {root_name: {"description":         description,
                     "Reserved_Parameters": reserved_params_dict,
                     "Model_Specific":      model_specific_dict
                     }
         }
    )


def make_param_traits(
    pname: str,
    param: AMIParameter | Parameters
) -> list[tuple[str, TraitType]]:
    """
    Builds list of ``Trait`` s from AMI parameter or dictionary.

    Args:
        pname: Parameter or sub-group name.
        param: AMI parameter or dictionary of AMI parameters to be configured.

    Returns:
        The list of new (name, ``Trait``) pairs created, one per *In* or *InOut* leaf parameter.

    Notes:
        1. Sub-parameter trait names are the underscore-joined hierarchical parameter names.
    """

    if isinstance(param, AMIParameter):  # pylint: disable=no-else-return
        if param.pusage not in ("In", "InOut") or param.pformat in FIXED_FORMATS:  # Not user-selectable.
            return []

        if param.ptype == "Boolean":
            return [(pname, Bool(param.pvalue))]

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
                    val = next(iter(tmp_dict.keys()))
                    if default is not None:  # Already checked to be a List member, of the List's type.
                        for tip in tmp_dict.items():
                            if tip[1] == default:
                                val = tip[0]
                                break
                    the_trait = Trait(val, tmp_dict)
                else:
                    val = default if default is not None else param.pvalue[0]
                    the_trait = Enum([val] + param.pvalue)
            case "Increment" | "Steps":  # Only the discrete values typ + N*delta are legal (IBIS 8.0 p.241).
                the_trait = Enum([param.pvalue] + param.pvalues)  # type: ignore[operator]
            case _:
                raise ValueError(f"Unrecognized AMI parameter format: {pformat}, for parameter `{pname}` of type `{param.ptype}` and usage `{param.pusage}`!")
        if the_trait.metadata:
            the_trait.metadata.update({"transient": False})  # Required to support modal dialogs.
        else:
            the_trait.metadata = {"transient": False}
        return [(pname, the_trait)]

    else:  # subparameter branch
        new_traits: list[tuple[str, TraitType]] = []
        for subparam_name in sorted(param.keys()):
            if subparam_name != "description":
                new_traits.extend(make_param_traits(pname + "_" + trait_name_part(subparam_name), param[subparam_name]))
        return new_traits
