"""Parse an IBIS model file.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

import logging
import re

from functools import reduce
from typing import Any, Optional, TypeAlias, TypeVar
from collections.abc import Generator, Iterable

from parsec import (
    ParseError,
    Parser,
    count,
    eof,
    fail_with,
    generate,
    letter,
    many,
    many1,
    none_of,
    one_of,
    optional,
    regex,
    separated,
    sepBy1,
    string,
    times,
    try_choice,
)

from pyibisami.ibis.model import Component, Model

logger = logging.getLogger(__name__)

T = TypeVar('T')
GenParser: TypeAlias = Generator[Parser, Any, T]

# Parser Definitions

whitespace = regex(r"\s+", re.MULTILINE)
comment    = regex(r"\|.*")                 # To end of line only.
ignore     = many(whitespace | comment)     # None is okay; so, can be used completely safely.


def logf(p: Parser, preStr: str = "") -> Parser:
    """
    Returns parser ``p`` wrapped in a thin shell, which logs any failure at the point of occurence.

    Args:
        p: The original parser.

    Keyword Args:
        preStr: A prefix string to use in failure message.
            (Default = <empty string>)

    Returns:
        p': The original parser wrapped in a thin failure location shell.
    """

    @Parser
    def fn(txt, ix):
        res = p(txt, ix)
        if not res.status:
            logger.debug(
                "%s: Expected `%s` in `%s` at %s.",
                preStr, res.expected, txt[res.index: res.index + 5], ParseError.loc_info(txt, res.index),
            )
        return res

    return fn


def lexeme(p: Parser) -> Parser:
    """Lexer for words.

    Skips all ignored characters after word, including newlines.
    """
    return p << ignore


def word(p: Parser) -> Parser:
    """Line limited word lexer.

    Only skips space after words; dosen't skip comments or newlines.
    Requires, at least, one white space character after word.
    """
    return p << regex(r"\s+")


@generate("remainder of line")
def rest_line() -> GenParser[str]:  # type: ignore
    "Parse remainder of line."
    chars = yield many(none_of("[\n\r")) << ignore  # So that we still function as a lexeme.
    rslt = "".join(chars)
    return rslt


skip_line: Parser = lexeme(rest_line).result("(Skipped.)")
name_only: Parser = regex(r"[_a-zA-Z0-9/\.()#-]+")
name: Parser = word(name_only)
# Parameters must begin with a letter in column 1.
param_name: Parser = word(regex(r"^[a-zA-Z]\w*", re.MULTILINE))
symbol: Parser = lexeme(regex(r"[a-zA-Z_][^\s()\[\]]*"))
true: Parser = lexeme(string("True")).result(True)
false: Parser = lexeme(string("False")).result(False)
quoted_string: Parser = lexeme(regex(r'"[^"]*"'))
skip_keyword: Parser = (skip_line >> many(none_of("[") >> skip_line)).result(
    "(Skipped.)"
)  # Skip over everything until the next keyword begins.

IBIS_num_suf: dict[str, str] = {
    "T": "e12",
    "k": "e3",
    "n": "e-9",
    "G": "e9",
    "m": "e-3",
    "p": "e-12",
    "M": "e6",
    "u": "e-6",
    "f": "e-15",
}


@generate("number")
def number() -> GenParser[float]:
    "Parse an IBIS numerical value."
    s = yield (regex(r"[-+]?[0-9]*\.?[0-9]+(([eE][-+]?[0-9]+)|([TknGmpMuf][a-zA-Z]*))?") << many(letter()) << ignore)
    m = re.search(r"[^\d]+$", s)
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


na: Parser = word(string("NA") | string("na")).result(None)


@generate("typminmax")
def typminmax() -> GenParser[list[float]]:
    "Parse Typ/Min/Max values."
    typ = yield number
    minmax = yield optional(count(number, 2) | count(na, 2).result([]), [])
    yield ignore  # So that ``typminmax`` behaves as a lexeme.
    res = [typ]
    res.extend(minmax)
    return res


vi_line: Parser = (number + typminmax) << ignore


@generate("ratio")
def ratio() -> GenParser[Optional[float]]:
    "Parse ratio."
    [num, den] = yield (separated(number, string("/"), 2, maxt=2, end=False) | na.result([0, 0]))
    if den:
        return num / den
    return None


def _platform_os(chars: list[str]) -> str:
    """The OS field of an ``Executable`` line's ``Platform_Compiler_Bits``, lower-cased.

    Any OS name, with an optional version, is accepted (IBIS 8.0 Section 10.1, p.213); ``Linux...``/``Windows...``
    become exactly ``"linux"``/``"windows"``, the only platforms executables are selected for.
    """
    token = "".join(chars).lower()
    for os_name in ("linux", "windows"):
        if token.startswith(os_name):
            return os_name
    return token


# ``(direction, ((os, bits), [dll, ami]))``; ``direction`` is ``"tx"``, ``"rx"``, or ``None`` for plain ``Executable``.
ex_line: Parser = (
    word(
        string("Executable_Tx").result("tx")
        ^ string("Executable_Rx").result("rx")  # noqa: W503
        ^ string("Executable").result(None)  # noqa: W503
    )
    + (  # noqa: W503
        (
            many1(none_of("_ \t\r\n")).parsecmap(_platform_os)
            << string("_")  # noqa: W503
            << many(none_of("_"))  # noqa: W503
            << string("_")  # noqa: W503
        )
        + lexeme(string("32") | string("64"))  # noqa: W503
        + count(name, 2)  # noqa: W503
    )
    << ignore  # noqa: W503
)


@generate("[AMI Test Configuration] subparam")
def ami_tc_param() -> GenParser[tuple[str, str]]:
    "Parse a single [AMI Test Configuration] subparameter line."
    pname = yield param_name
    pval = yield rest_line
    return (pname.lower(), pval.strip())


@generate("[AMI Test Configuration]")
def ami_test_config() -> GenParser[tuple[str, dict[str, str]]]:
    "Parse [AMI Test Configuration] block (name + subparameters)."
    cfg_name = yield rest_line
    params = yield many(ami_tc_param)
    return (cfg_name.strip(), dict(params))


@generate("[Algorithmic Model]")
def algo_model() -> GenParser[dict]:
    """Parse [Algorithmic Model]: Executable lines then optional [AMI Test Configuration] blocks.

    Each ``executables`` entry is ``(direction, ((os, bits), [dll, ami]))``; see ``ex_line``.
    """
    execs = yield many1(ex_line)
    cfg_pairs = yield many(keyword("ami_test_configuration") >> ami_test_config)
    yield keyword("end_algorithmic_model")
    return {"executables": execs, "test_configs": dict(cfg_pairs)}


def manyTrue(p: Parser) -> Parser:
    "Run a parser multiple times, filtering ``False`` results."

    @generate("manyTrue")
    def fn() -> GenParser[list[T]]:
        "many(p) >> filter(True)"
        nodes = yield many(p)
        res = list(filter(None, nodes))
        return res

    return fn


def many1True(p: Parser) -> Parser:
    "Run a parser at least once, filtering ``False`` results."

    @generate("many1True")
    def fn() -> GenParser[list[T]]:
        "many1(p) >> filter(True)"
        nodes = yield many1(p)
        res = list(filter(None, nodes))
        return res

    return fn


# IBIS file parser:


def keyword(kywrd="") -> Parser:
    """Parse an IBIS keyword.

    Keyword Args:
        kywrd (str): The particular keyword to match; null for any keyword.
            If provided, *must* be in canonicalized form (i.e. - underscores,
            no spaces)!

    Returns:
        Parser: A keyword parser.
    """

    @generate("IBIS keyword")
    def fn() -> GenParser[str]:
        "Parse IBIS keyword."
        yield regex(r"^\[", re.MULTILINE)
        wordlets = yield sepBy1(name_only, one_of(" _"))  # ``name`` gobbles up trailing space, which we don't want.
        yield string("]")
        yield ignore  # So that ``keyword`` functions as a lexeme.
        res = "_".join(wordlets)  # Canonicalize to: "<wordlet1>_<wordlet2>_...".
        if kywrd:
            if res.lower() == kywrd.lower():
                return res
            return fail_with(f"Expecting: {kywrd}; got: {res}.")  # type: ignore
        return res

    return fn


allowed_model_types: list[str] = [
    "Input",
    "Output",
    "I/O",
    "3-state",
    "Open_drain",
    "I/O_open_drain",
    "Open_sink",
    "I/O_open_sink",
    "Open_source",
    "I/O_open_source",
    "Input_ECL",
    "Output_ECL",
    "I/O_ECL",
    "3-state_ECL",
    "Terminator",
    "Series",
    "Series_switch",
]
model_type_parsers = [word(string(mt)) for mt in allowed_model_types]
model_type = reduce(try_choice, model_type_parsers)


@generate("IBIS parameter")
def param() -> GenParser[tuple[str, Any]]:
    "Parse IBIS parameter."
    pname = yield param_name
    logger.debug("Parsing parameter %s...", pname)
    match pname:  # Handle special cases.
        case "Model_type":
            res = yield model_type
        case _:
            res = yield ((word(string("=")) >> (number | rest_line)) | typminmax | name | rest_line)
    logger.debug("%s", res)
    yield ignore  # So that ``param`` functions as a lexeme.
    return (pname.lower(), res)


def node(
    valid_keywords: dict[str, Parser],
    stop_keywords: Iterable[str],
) -> Parser:
    """
    Build a node-specific parser.

    Args:
        valid_keywords: A dictionary with keys matching those keywords we want parsed.
            The values are the parsers for those keywords.
        stop_keywords: Any iterable with primary values (i.e. - those
            tested by the ``in`` function) matching those keywords we want
            to stop the parsing of this node and pop us back up the
            parsing stack.

    Returns:
        Parser: A parser for this node.

    Notes:
        1: Any keywords encountered that are _not_ found (via ``in``) in
            either ``valid_keywords`` or ``stop_keywords`` are ignored.
    """

    @generate("kywrd")
    def kywrd():
        "Parse keyword syntax."
        nm = yield keyword()
        nmL = nm.lower()
        logger.debug("Parsing keyword: [%s]...", nm)
        if nmL in valid_keywords:
            if nmL == "end":  # Because ``ibis_file`` expects this to be the last thing it sees,
                return fail_with("")  # we can't consume it here.
            res = yield logf(valid_keywords[nmL], f"[{nm}]")  # Parse the sub-keyword.
        elif nmL in stop_keywords:
            return fail_with("")  # Stop parsing.
        else:
            res = yield skip_keyword
        yield ignore  # So that ``kywrd`` behaves as a lexeme.
        logger.debug("Finished parsing keyword: [%s].", nm)
        return (nmL, res)

    return kywrd | param


# Individual IBIS keyword (i.e. - "node") parsers:


# [End]
@generate("[End]")
def end() -> GenParser[Any]:
    "Parse [End]."
    yield keyword("End")
    return eof


# [Model]
load_line: Parser = string("R_load") >> many(string(" ")) >> string("=") >> many(string(" ")) >> number << ignore

ramp_line: Parser = (
    string("dV/dt_") >> (
        (string("r").result("rising") | string("f").result("falling")) << ignore
    ) + times(ratio, 1, 3)
)


@generate("[Ramp]")
def ramp() -> GenParser[dict[str, Any]]:
    "Parse [Ramp]."
    load1 = yield optional(load_line, 50)
    lines = yield count(ramp_line, 2).desc("Two ramp_lines")
    load2 = yield optional(load_line, 50)
    rslt = dict(lines)
    rslt.update({"load": load2 if load1 == 50 else load1})
    return rslt


# ToDo: Implement: rising_waveform, falling_waveform, and composite_current.
Model_keywords: dict[str, Parser] = {
    "pulldown": many1(vi_line),
    "pullup": many1(vi_line),
    "ramp": ramp,
    "algorithmic_model": algo_model,
    "voltage_range": typminmax,
    "temperature_range": typminmax,
    "gnd_clamp": many1(vi_line),
    "power_clamp": many1(vi_line),
    "rising_waveform": skip_keyword,
    "falling_waveform": skip_keyword,
    "composite_current": skip_keyword,
}


@generate("[Model]")
def model():
    "Parse [Model]."
    nm = yield name << ignore
    logger.debug("Parsing model: %s...", nm)
    res = yield many1(node(Model_keywords, IBIS_keywords))
    logger.debug("[Model] %s contains: %s", nm, dict(res).keys())
    try:
        theModel = Model(dict(res), name=nm)
    except LookupError as le:
        return fail_with(f"[Model] {nm}: {le!s}")
    return {nm: theModel}


# [Component]
rlc = lexeme(string("R_pin") | string("L_pin") | string("C_pin"))


@generate("[Manufacturer]")
def manufacturer():
    "Parse manufacturer."
    rslt = yield rest_line
    if not rslt:
        rslt = "(n/a)"
    logger.debug("Manufacturer: %s", rslt)
    return rslt


@generate("[Package]")
def package():
    "Parse package RLC values."
    rlcs = yield many1(param)
    logger.debug("rlcs: %s", rlcs)
    return dict(rlcs)


def pin(rlcs):
    "Parse indiviual component pin."

    @generate("Component Pin")
    def fn():
        "Parse an individual component pin."
        [nm, sig] = yield count(name, 2)
        mod = yield name_only
        rem_line = yield rest_line
        rlc_vals = optional(count(number, 3), []).parse(rem_line)
        rlc_dict = {}
        if rlcs:
            rlc_dict.update(dict(zip(rlcs, rlc_vals)))
        return ((nm + "(" + sig + ")"), (mod, rlc_dict))

    return fn


@generate("[Component].[Pin]")
def pins():
    "Parse [Component].[Pin]."

    def filt(x):
        (_, (mod, _)) = x
        m = mod.upper()
        return m not in ("POWER", "GND", "NC", "CIRCUITCALL")

    # Parse the section header.
    yield (lexeme(string("signal_name")) << lexeme(string("model_name")))
    rlcs = yield optional(count(rlc, 3), [])
    prs = yield many1(pin(rlcs))
    prs_filt = list(filter(filt, prs))
    return dict(prs_filt)


Component_keywords = {
    "manufacturer": manufacturer,
    "package": package,
    "pin": pins,
    "diff_pin": skip_keyword,
    "pin_mapping": skip_keyword,
}


@generate("[Component]")
def comp():
    "Parse [Component]."
    nm = yield rest_line
    logger.debug("Parsing component: %s", nm)
    res = yield many1(node(Component_keywords, IBIS_keywords))
    try:
        Component(dict(res))
    except LookupError as le:
        return fail_with(f"[Component] {nm}: {le!s}")
    except Exception as err:  # pylint: disable=broad-exception-caught
        return fail_with(f"[Component] {nm}: {err!s}")
    return {nm: Component(dict(res))}


@generate("[Model Selector]")
def modsel():
    "Parse [Model Selector]."
    nm = yield name
    res = yield ignore >> many1(name + rest_line)
    return {nm: res}


# Note: The following list MUST have a complete set of keys,
#       in order for the parsing logic to work correctly!
IBIS_keywords = [
    "model",
    "end",
    "ibis_ver",
    "comment_char",
    "file_name",
    "file_rev",
    "date",
    "source",
    "notes",
    "disclaimer",
    "copyright",
    "component",
    "model_selector",
    "submodel",
    "external_circuit",
    "test_data",
    "test_load",
    "define_package_model",
    "interconnect_model_set",
]

IBIS_kywrd_parsers = dict(zip(IBIS_keywords, [skip_keyword] * len(IBIS_keywords)))
IBIS_kywrd_parsers.update(
    {
        "model": model,
        "end": end,
        "ibis_ver": lexeme(number),
        "file_name": lexeme(name),
        "file_rev": lexeme(name),
        "date": rest_line,
        "component": comp,
        "model_selector": modsel,
    }
)


@generate("IBIS File")
def ibis_file() -> GenParser[Any]:
    "Parse IBIS file."
    res = yield ignore >> many1True(node(IBIS_kywrd_parsers, {})) << end
    return res


def parse_ibis_file(
    ibis_file_contents_str: str,
) -> tuple[str, dict[str, Any]]:
    """
    Parse the contents of an IBIS file.

    Args:
        ibis_file_contents_str: The contents of the IBIS file, as a single string.

    Example:
        ::

            with open(<ibis_file_name>) as ibis_file:
                ibis_file_contents_str = ibis_file.read()
                (err_str, model_dict)  = parse_ibis_file(ibis_file_contents_str)

    Returns:
        A pair containing

        - A message describing the nature of any parse failure that occured (``"Success!"`` otherwise).
        - A dictionary containing keyword definitions (empty upon failure). Its ``"warnings"`` entry lists the
          IBIS spec rules broken that didn't stop the file loading (see ``Model.spec_warnings``); each is also
          logged at ``WARNING``.
    """

    try:
        nodes = ibis_file.parse_strict(ibis_file_contents_str)  # Parse must consume the entire file.
        logger.debug("Parsed nodes:\n%s", nodes)
    except ParseError as pe:
        return str(pe), {}

    kw_dict = {}
    components = {}
    models = {}
    model_selectors = {}
    warnings = []
    for kw, val in nodes:
        if kw == "model":
            models.update(val)
        elif kw == "component":
            components.update(val)
        elif kw == "model_selector":
            model_selectors.update(val)
        elif kw == "algorithmic_model":  # Not inside a [Model]; e.g. - under [Submodel], where it's skipped.
            warnings.append("[Algorithmic Model] found outside a [Model] (e.g. - under [Submodel]), where it is not "
                            "permitted; ignored (IBIS 8.0 Section 10.1, p.213).")
        else:
            kw_dict.update({kw: val})
    for mdl in models.values():
        warnings.extend(mdl.spec_warnings)
    for warning in warnings:
        logger.warning("%s", warning)
    kw_dict.update(
        {
            "components": components,
            "models": models,
            "model_selectors": model_selectors,
            "warnings": warnings,
        }
    )
    return "Success!", kw_dict
