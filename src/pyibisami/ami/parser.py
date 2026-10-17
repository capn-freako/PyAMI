"""IBIS-AMI parameter definition (``.ami``) file parser.

The parameter configurator, ``AMIParamConfigurator``, is in ``pyibisami.ami.configurator``
(and still importable from here).

Original author: David Banas <capn.freako@gmail.com>

Original date:   December 17, 2016

Copyright (c) 2019 David Banas; all rights reserved World wide.
"""

from __future__     import annotations
from dataclasses    import dataclass
import logging
import re
from typing         import TYPE_CHECKING, Any, NewType, Optional, TypeAlias, cast
from collections.abc import Callable

from parsec import ParseError, generate, many, regex, string

from .parameter                 import AMIParamError, AMIParameter
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
    "ami_parse", "AMIParamConfigurator", "make_param_traits", "trait_name_part"]


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

    A Table row (IBIS 8.0 p.242), i.e. - a number, quoted string or Boolean followed only by atoms, gives a plain list:
    ``(1 -0.5 2)`` gives ``["1", "-0.5", "2"]``. (A tap, e.g. ``(-1 (Usage In) ...)``, contains nodes.)
    """
    yield lparen
    label  = yield node_name ^ row_head
    values = yield many(expr)
    yield rparen
    is_row_head = number_re.fullmatch(label) or label.startswith('"') or label in ("True", "False")
    if is_row_head and all(isinstance(v, str) for v in values):
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

    A parameter has a 'Usage' or 'Type' tag, i.e. - an item of that name whose values are all atoms.
    (Those names are reserved, so no subparameter has them; IBIS 8.0 Section 10.3.4, p.239.)
    Other tag names (e.g. - 'Corner', 'Steps', 'Labels') may also name subparameters, so they don't decide it.

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

    try:
        if any(isinstance(tag, tuple) and tag[0] in ("Usage", "Type") and all(isinstance(v, str) for v in tag[1])
               for tag in param_tags):
            try:
                results = ("", {param_name: AMIParameter(param_name, param_tags)})
            except AMIParamError as err:
                return skip(param_name, str(err))
        elif param_name == "Description":
            results = ("", {"description": param_tags[0].strip('"')})
        elif not all(isinstance(tag, tuple) for tag in param_tags):
            return skip(param_name, f"Expected parameter tags or subparameters; got {param_tags}")
        elif (items := [tag for tag in param_tags if tag[0] != "Description"]) and all(
                tag[1] and all(isinstance(v, str) for v in tag[1]) for tag in items):
            # Every item is tag-like (one or more values, no nodes; an empty ``(x )`` is an empty node, skipped
            # on its own below): a parameter missing its ``Usage`` and ``Type`` tags
            # (e.g. - written in lower case; tags are case sensitive), not a branch of subparameters.
            return skip(param_name, "Missing 'Usage' and 'Type' tags (tag names are case sensitive).")
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
                        "Only Reserved_Parameters, Model_Specific and Description may be at the top level.")

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
        log_warning("For AMI_Version 5.1 and later, Reserved_Parameters must come before Model_Specific.")

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


# Moved to ``.configurator``, which imports this module; still importable from here (e.g. - PyBERT's
# ``from pyibisami.ami.parser import AMIParamConfigurator``), loaded on first use.
_MOVED = ("AMIParamConfigurator", "make_param_traits", "trait_name_part")

if TYPE_CHECKING:
    from .configurator import AMIParamConfigurator, make_param_traits, trait_name_part


def __getattr__(name: str) -> Any:
    if name in _MOVED:
        from . import configurator  # pylint: disable=import-outside-toplevel,cyclic-import
        return getattr(configurator, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
