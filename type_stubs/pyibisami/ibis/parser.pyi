from collections.abc import Generator

from _typeshed import Incomplete

from pyibisami.ibis.model import Component as Component
from pyibisami.ibis.model import Model as Model

DBG: bool
whitespace: Incomplete
comment: Incomplete
ignore: Incomplete

def logf(p, preStr: str = ...): ...
def lexeme(p): ...
def word(p): ...
def rest_line() -> Generator[Incomplete, Incomplete, Incomplete]: ...

skip_line: Incomplete
name_only: Incomplete
name: Incomplete
symbol: Incomplete
true: Incomplete
false: Incomplete
quoted_string: Incomplete
skip_keyword: Incomplete
IBIS_num_suf: Incomplete

def number() -> Generator[Incomplete, Incomplete, Incomplete]: ...

na: Incomplete

def typminmax() -> Generator[Incomplete, Incomplete, Incomplete]: ...

vi_line: Incomplete

def ratio() -> Generator[Incomplete, Incomplete, Incomplete]: ...

ramp_line: Incomplete
ex_line: Incomplete

def manyTrue(p): ...
def many1True(p): ...
def keyword(kywrd: str = ...): ...
def param() -> Generator[Incomplete, Incomplete, Incomplete]: ...
def node(valid_keywords, stop_keywords, debug: bool = ...): ...
def end() -> Generator[Incomplete, None, Incomplete]: ...
def ramp() -> Generator[Incomplete, Incomplete, Incomplete]: ...

Model_keywords: Incomplete

def model() -> Generator[Incomplete, Incomplete, Incomplete]: ...

rlc: Incomplete

def package() -> Generator[Incomplete, Incomplete, Incomplete]: ...
def pin(rlcs): ...
def pins() -> Generator[Incomplete, Incomplete, Incomplete]: ...

Component_keywords: Incomplete

def comp() -> Generator[Incomplete, Incomplete, Incomplete]: ...
def modsel() -> Generator[Incomplete, Incomplete, Incomplete]: ...

IBIS_keywords: Incomplete
IBIS_kywrd_parsers: Incomplete

def ibis_file() -> Generator[Incomplete, Incomplete, Incomplete]: ...
def parse_ibis_file(ibis_file_contents_str, debug: bool = ...): ...