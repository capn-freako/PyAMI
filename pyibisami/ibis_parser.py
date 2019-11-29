"""
Parse an IBIS model file.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

import re
from parsec import  regex, eof, many1, many, string, generate, sepBy1, \
                    one_of, skip, none_of, times, ParseError, count, \
                    separated, letter, digit, optional

from pyibisami.ibis_model import Component, Model

DBG = True

# Parser Definitions

# TODO: Consider shifting to an exclusively line-oriented parsing strategy.

whitespace = regex(r"\s+", re.MULTILINE)
# whitespace = regex(r"\s+")
comment    = regex(r"\|.*")
ignore     = many(whitespace | comment)

def lexeme(p):
    """Lexer for words."""
    return p << ignore  # Skip all ignored characters after word, including newlines.

def word(p):
    """Line limited word lexer."""
    return p << regex(r"\s*")  # Only skip space after words; don't skip comments or newlines.

@generate("remainder of line")
def rest_line():
    "Parse remainder of line."
    chars = yield (many(none_of("\n\r")) << ignore)  # So that we still function as a lexeme.
    return "".join(chars)

skip_line     = lexeme(rest_line).result('(Skipped.)')
name_only     = regex(r"[_a-zA-Z0-9/\.()#-]+")
name          = word(name_only)
symbol        = lexeme(regex(r"[a-zA-Z_][^\s()\[\]]*"))
true          = lexeme(string("True")).result(True)
false         = lexeme(string("False")).result(False)
quoted_string = lexeme(regex(r'"[^"]*"'))
fail          = one_of("")
skip_keyword  = (skip_line >> many(none_of("[") >> skip_line)).result('(Skipped.)')  # Skip over everything until the next keyword begins.

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
    s = yield word(regex(r"[-+]?[0-9]*\.?[0-9]+(([eE][-+]?[0-9]+)|([TknGmpMuf][a-zA-Z]*))?") << many(letter()))
    m = re.search(r'[^\d]+$', s)
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
na = word(string("NA") | string("na")).result(None)

@generate("typminmax")
def typminmax():
    "Parse Typ/Min/Max values."
    typ    = yield number
    if DBG:
        print(f"Typ.: {typ}")
    minmax = yield optional(count(number, 2) | count(na, 2).result([]), [])
    if DBG:
        print(f"Min./Max.: {minmax}")
    yield ignore  # So that `typminmax` behaves as a lexeme.
    res = [typ]
    res.extend(minmax)
    return res

vi_line = (number + typminmax) << ignore

@generate("ratio")
def ratio():
    [num, den] = yield (separated(number, string("/"), 2, maxt=2, end=False) | na.result([0, 0]))
    if den:
        return num / den
    else:
        return None

ramp_line = string("dV/dt_") >> ((string("r").result("rising") | string("f").result("falling")) << ignore) + times(ratio, 1, 3)
ex_line = word(string("Executable")) \
    >> ((((string("L") | string("l")) >> string("inux")).result("linux") | \
        ((string("W") | string("w")) >> string("indows")).result("windows")) \
    << string("_") << many(none_of("_")) << string("_")) \
    + lexeme(string("32") | string("64")) \
    + count(name, 2) << ignore

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
        yield regex(r"^\[", re.MULTILINE)
        wordlets = yield sepBy1(name_only, one_of(" _"))  # `name` gobbles up trailing space, which we don't want.
        yield string("]")
        yield ignore                # So that `keyword` functions as a lexeme.
        res = ("_".join(wordlets))  # Canonicalize to: "<wordlet1>_<wordlet2>_...".
        if kywrd:
            # assert res.lower() == kywrd.lower(), f"Expecting: {kywrd}; got: {res}."  # Does not work!
            if res.lower() == kywrd.lower():
                return res
            else:
                return fail.desc(f"Expecting: {kywrd}; got: {res}.")
        return res
    return fn

@generate("IBIS parameter")
def param():
    "Parse IBIS parameter."
    pname = yield regex(r"^[a-zA-Z]\w*", re.MULTILINE)  # Parameters must begin with a letter in column 1.
    if DBG:
        print(pname)
    res = yield (regex(r"\s*") >> ((word(string("=")) >> number) | typminmax | name | rest_line))
    yield ignore  # So that `param` functions as a lexeme.
    return (pname.lower(), res)

def node(valid_keywords, stop_keywords, debug=False):
    """Build a node-specific parser.

    Args:
        valid_keywords (dict): A dictionary with keys matching those
            keywords we want parsed. The values are the parsers for
            those keywords.
        stop_keywords: Any iterable with primary values (i.e. - those
            tested by the `in` function) matching those keywords we want
            to stop the parsing of this node and pop us back up the
            parsing stack.

    Returns:
        Parser: A parser for this node.

    Notes:
        1: Any keywords encountered that are _not_ found (via `in`) in
            either `valid_keywords` or `stop_keywords` are ignored.
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
            res = yield skip_keyword
        yield ignore                             # So that `kywrd` behaves as a lexeme.
        if debug:
            print("  ", nmL + ":", res)
        return (nmL, res)

    return (kywrd | param)

# Individual IBIS keyword (i.e. - "node") parsers:

# [End]
@generate("[End]")
def end():
    "Parse [End]."
    yield keyword("End")
    return eof

# [Model]
@generate("[Ramp]")
def ramp():
    "Parse [Ramp]."
    lines = yield count(ramp_line, 2)
    return dict(lines)

Model_keywords = {
    "pulldown": many1(vi_line),
    "pullup": many1(vi_line),
    "ramp": ramp,
    "algorithmic_model": many1(ex_line) << keyword('end_algorithmic_model'),
    "voltage_range": typminmax,
    "temperature_range": typminmax,
    "ground_clamp": many1(vi_line),
    "power_clamp": many1(vi_line),
}

@generate("[Model]")
def model():
    "Parse [Model]."
    nm = yield name
    if DBG:
        print("    ", nm)
    res = yield many1(node(Model_keywords, IBIS_keywords, debug=DBG))
    return {nm: Model(dict(res))}

# [Component]
rlc = lexeme(string("R_pin") | string("L_pin") | string("C_pin"))

@generate("[Package]")
def package():
    "Parse package RLC values."
    rlcs = yield many1(param)
    if DBG:
        print(f"rlcs: {rlcs}")
    return dict(rlcs)

def pin(rlcs):
    "Parse indiviual component pin."
    @generate("Component Pin")
    def fn():
        "Parse an individual component pin."
        [nm, sig] = yield count(name, 2)
        mod       = yield name_only
        rem_line  = yield rest_line
        rlc_vals  = optional(count(number, 3), []).parse(rem_line)
        rlc_dict  = {}
        if rlcs:
            rlc_dict.update(dict(zip(rlcs, rlc_vals)))
        return ((nm + "(" + sig + ")"), (mod, rlc_dict))
    return fn

@generate("[Component].[Pin]")
def pins():
    "Parse [Component].[Pin]."
    yield (lexeme(string("signal_name")) << lexeme(string("model_name")))
    rlcs = yield count(rlc, 3)
    prs  = yield many1(pin(rlcs))
    return dict(prs)

Component_keywords = {
    "manufacturer": rest_line,
    "package":      package,
    "pin":          pins,
    "diff_pin":     skip_keyword,
}

@generate("[Component]")
def comp():
    "Parse [Component]."
    nm = yield lexeme(name)
    res = yield many1(node(Component_keywords, IBIS_keywords, debug=DBG))
    return {nm: Component(dict(res))}

# [Model Selector]
@generate("[Model Selector]")
def modsel():
    "Parse [Model Selector]."
    nm = yield name
    res = yield many1(name + rest_line)
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

IBIS_kywrd_parsers = dict(zip(IBIS_keywords, [skip_keyword]*len(IBIS_keywords)))
IBIS_kywrd_parsers.update({
    "model":          model,
    "end":            end,
    "ibis_ver":       lexeme(number),
    "file_name":      lexeme(name),
    "file_rev":       lexeme(name),
    "date":           rest_line,
    "component":      comp,
    "model_selector": modsel,
    })

@generate("IBIS File")
def ibis_file():
    res = yield ignore >> many1True(node(IBIS_kywrd_parsers, {}, debug=DBG)) << end
    return res

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
        if DBG:
            print(nodes)
    except ParseError as pe:
        err_str = "Expected {} at {} in {}".format(pe.expected, pe.loc(), pe.text[pe.index])
        return err_str, {}

    kw_dict = {}
    components = {}
    models  = {}
    model_selectors = {}
    for (kw, val) in nodes:
        if kw == 'model':
            models.update(val)
        elif kw == 'component':
            components.update(val)
        elif kw == 'model_selector':
            model_selectors.update(val)
        else:
            kw_dict.update({kw: val})
    kw_dict.update({
        'components':      components,
        'models':          models,
        'model_selectors': model_selectors,
        })
    return "Success!", kw_dict
