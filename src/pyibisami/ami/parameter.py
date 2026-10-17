"""``AMIParameter`` class definition, plus some helpers.

Original author: David Banas <capn.freako@gmail.com>

Original date:   December 24, 2016

Copyright (c) 2019 David Banas; all rights reserved World wide.
"""

import math
from collections.abc import Callable
from typing import Any, ClassVar, Optional

from traits.api import Bool, Float, HasTraits, List, Str

#####
# AMI parameter
#####

# Data formats (IBIS 8.0 Section 10.3.4, p.240-244).
FORMATS = ("Value", "Range", "List", "Corner", "Increment", "Steps", "Table", "Gaussian", "Dual-Dirac", "DjRj")
# Formats whose value the user doesn't choose: Corner is picked by the simulation corner; the others are sent as
# written. They get no trait, GUI item or tuner.
FIXED_FORMATS = ("Corner", "Table", "Gaussian", "Dual-Dirac", "DjRj")
# Types each format allows, where it restricts them (IBIS 8.0 Section 10.3.5, p.245; Table 18, p.247).
_NUMERIC_TYPES = ("Float", "UI", "Integer", "Tap")
_FORMAT_TYPES = {
    "Range": _NUMERIC_TYPES, "Increment": _NUMERIC_TYPES, "Steps": _NUMERIC_TYPES,
    "Table": ("Float", "UI", "Integer", "String", "Boolean"),
    "Gaussian": ("Float", "UI"), "Dual-Dirac": ("Float", "UI"), "DjRj": ("Float", "UI"),
}
_NO_DEFAULT_FORMATS = ("Table", "Gaussian", "Dual-Dirac", "DjRj")  # IBIS 8.0 p.245.
# Limit on the values an Increment or Steps parameter may expand to; a larger one is skipped, with a warning.
# Not a spec rule (the spec sets no limit): a guard against e.g. `(Increment 0 0 1 1e-12)`. 4096 covers a 12-bit
# code setting, far more than real models use (an 8-bit setting has 256 values).
MAX_DISCRETE_VALUES = 4096


class AMIParamError(Exception):
    """Base Exception for all AMI Parameter Errors."""


class AMIParameter:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """IBIS-AMI model parameter.

    This class encapsulates the attributes and behavior of a AMI
    parameter.
    """

    # Properties.

    # Note: They are read-only, despite the presence of apparent setters.
    #       (The idea is that, once initialized, parameter definitions
    #        are immutable.)
    #       The only exception to this is pvalue, which has been made
    #       writable, for scripted non-GUI use cases.
    #       Be very careful w/ this; there is NO CHECKING!

    # Note that the setters, below, are only intended for use by
    # __init__(). They may raise an *AMIParamError* exception. This is
    # to ensure that a malformed instance never be created.

    def _get_name(self):
        """pname."""
        return self._name

    pname = property(_get_name, doc="Name of AMI parameter.")

    # pusage
    def _set_usage(self, values):
        "Process *Usage* tag."

        val = values[0]
        if val in ("In", "Out", "InOut", "Info", "Dep"):  # Dep: set by AMI_Resolve (AMI_Version 6.1+); never sent.
            self._usage = val
        else:
            raise AMIParamError(f"Unrecognized usage value: '{val}'.")

    def _get_usage(self):
        return self._usage

    pusage = property(_get_usage, doc="Value of AMI parameter 'Usage' tag.")

    # ptype
    def _set_type(self, values):
        "Process *Type* tag."

        for val in values:
            if val not in ("Float", "Integer", "String", "Boolean", "UI", "Tap"):
                raise AMIParamError(f"Unrecognized type value: '{val}'.")
        self._type = values[0]
        self._types = list(values)  # Format Table may give one Type per column.

    def _get_type(self):
        return self._type

    ptype = property(_get_type, doc="Value of AMI parameter 'Type' tag (the first one, for a per-column Table).")

    @property
    def ptypes(self) -> list[str]:
        "All the values of the 'Type' tag: one, or one per column for Format Table."
        return self._types

    # pformat
    def _set_format(self, values):
        "Process *Format* tag."

        form = values[0]
        if form not in FORMATS:
            raise AMIParamError(f"Unrecognized format: '{form}'.")
        if len(values) < 2:
            raise AMIParamError(f"No values provided for: '{form}'.")
        self._format = form
        self._format_rem = values[1:]

    def _get_format(self):
        return self._format

    pformat = property(_get_format, doc="Value of AMI parameter 'Format' tag.")

    # pvalue
    def _get_value(self):
        return self._value

    def _set_val(self, new_val):
        self._value = new_val

    pvalue = property(_get_value, _set_val, doc="Value of AMI parameter.")

    # pmin
    def _get_min(self):
        return self._min

    pmin = property(_get_min, doc="Minimum value of AMI parameter.")

    # pmax
    def _get_max(self):
        return self._max

    pmax = property(_get_max, doc="Maximum value of AMI parameter.")

    # default
    def _set_default(self, values):
        """Process *Default* tag."""
        self._default = values[0]

    def _get_default(self):
        return self._default

    pdefault = property(_get_default, doc="Default value of AMI parameter.")

    # pdescription
    def _set_description(self, values):
        """Process *Description* tag."""
        self._description = values[0].strip('"')

    def _get_description(self):
        return self._description

    pdescription = property(_get_description, doc="Description of AMI parameter.")

    # plist_tip
    def _set_list_tip(self, values):
        """Process *List_Tip* tag."""
        self._list_tip = [x.strip('"') for x in values]

    def _get_list_tip(self):
        return self._list_tip

    plist_tip = property(_get_list_tip, doc="List tips of AMI parameter.")

    # Helpers.
    # These 3 just accomodate the awkwardness caused by the optional
    # nature of the 'Format' keyword, in *.AMI files. Since, a properly
    # formed instance of *AMIParameter* will always have a *format*
    # property, we don't need to make these properties of that class.

    # value
    def _set_value(self, values):
        """Process *Value* tag."""

        return self._set_format(["Value"] + values)

    # range
    def _set_range(self, values):
        """Process *Range* tag."""

        return self._set_format(["Range"] + values)

    # usage
    def _set_list(self, values):
        """Process *List* tag."""

        return self._set_format(["List"] + values)

    @property
    def pvalues(self) -> Optional[list]:
        "The legal values of an Increment or Steps parameter, in increasing order; ``None`` for other formats."
        return self._values

    @property
    def pcorners(self) -> Optional[dict[str, Any]]:
        """A Corner parameter's values, keyed by simulation corner: ``typ``, ``min`` (slow) and ``max`` (fast)
        (IBIS 8.0 Section 10.3.5, p.246); ``None`` for other formats."""
        return self._corners

    @property
    def plabels(self) -> Optional[list[str]]:
        "A Table's column ``Labels``; ``None`` if it has none (or isn't a Table). Never sent to the model."
        return self._labels

    # Holds any warnings encountered, during initialization.
    # (Any errors encountered will prevent initialization from completing.)
    _msg = ""

    def _get_msg(self):
        return self._msg

    msg = property(_get_msg, doc="Any warning messages encountered, during parameter initialization.")

    # This dictionary defines both:
    #
    #  - the allowed parameter definition tag names, and
    #  - their processing functions.
    #
    # The idea is to allow this class to grow along with the IBIS
    # standard, without having to change any of its boilerplate.

    _param_def_tag_procs: ClassVar[dict[str, Callable[..., Any]]] = {
        "Usage": _set_usage,
        "Type": _set_type,
        "Format": _set_format,
        "Value": _set_value,
        "Range": _set_range,
        "List": _set_list,
        **{form: (lambda self, values, form=form: self._set_format([form] + values))
           for form in ("Corner", "Increment", "Steps", "Table", "Gaussian", "Dual-Dirac", "DjRj")},
        "Default": _set_default,
        "Description": _set_description,
        "List_Tip": _set_list_tip,
        "Label": _set_list_tip,
        "Labels": _set_list_tip,
    }

    def __init__(self, name, tags):  # pylint: disable=too-many-branches,too-many-statements
        """
        Args:
            name (str): The name of the AMI parameter being created.
            tags ([(str, [a])]): A list of pairs, each containing

                - a parameter definition tag name
                    (Must be one of the keys from the '_param_def_tag_procs' dictionary.)

                - a list of values to be associated with that tag.
        """
        # Initialization
        self._usage = None
        self._type = None
        self._format = None
        self._value = None
        self._min = None
        self._max = None
        self._default = None
        self._description = ""
        self._list_tip = None
        self._types: list[str] = []
        self._values: Optional[list] = None
        self._corners: Optional[dict[str, Any]] = None
        self._labels: Optional[list[str]] = None

        # Holds any warnings encountered, during initialization.
        # (Any errors encountered will prevent initialization from completing.)
        self._msg = ""

        # Process all parameter definition tags.
        for tag in tags:
            tag_name = tag[0]
            if tag_name in self._param_def_tag_procs:
                try:
                    self._param_def_tag_procs[tag_name](self, tag[1])
                except AMIParamError as err:
                    raise AMIParamError(f"Problem initializing parameter, '{name}': {err}\n") from err
            else:
                self._msg += f"Ignoring unrecognized tag: {tag_name}.\n"

        # Validate and complete the instance.
        # Check for required tags.
        param_usage = self._usage
        param_type = self._type
        param_format = self._format
        param_default = self._default
        if param_usage is None:
            raise AMIParamError("Missing 'Usage' tag!\n")
        if param_type is None:
            raise AMIParamError("Missing 'Type' tag!\n")
        if param_format is None:
            if param_default is None:
                raise AMIParamError("Missing both 'Format' and 'Default' tags!\n")
            self._value = param_default
            param_format = "Value"
            self._format_rem = [param_default]
        # Check for mutual exclusivity of 'Format Value' and 'Default'.
        elif (param_format == "Value") and (param_default is not None):
            self._msg += "'Format Value' and 'Default' both found! (They are mutually exclusive.)\n"
        # Canonicalize Boolean if necessary.
        elif (param_format == "List") and (param_type == "Boolean"):
            if param_default:
                self._value = param_default
            elif self._format_rem:
                self._value = self._format_rem[0]  # No Default: the first List value (IBIS 8.0 p.241).
            else:
                raise AMIParamError("Missing List values.\n")
            param_format = "Value"
            self._format_rem = [self._value]
        self._format = param_format

        # Check for 'Default' used with parameter type 'Out'.
        if (param_usage == "Out") and (param_default is not None):
            raise AMIParamError("'Default' may not be used with parameter type 'Out'!\n")

        # Complete the instance.
        # Allowed Type/Format combinations: IBIS 8.0 Section 10.3.5, p.245, and Table 18, p.247.
        if len(self._types) > 1 and param_format != "Table":
            raise AMIParamError(f"Only Format Table may have more than one Type; got {self._types}.\n")
        allowed_types = _FORMAT_TYPES.get(param_format)
        if allowed_types and any(t not in allowed_types for t in self._types):
            raise AMIParamError(f"Illegal type, '{param_type}', for use with {param_format}.\n")
        if param_default is not None and param_format in _NO_DEFAULT_FORMATS:
            self._msg += f"Default is not allowed with {param_format}; ignoring it.\n"
            self._default = None
        vals = self._format_rem
        if param_format == "Value":
            self._value = _read_value(param_type, vals[0])
            if self._default is not None:
                self._default = self._typed_default(param_type)
        elif param_format in ("Range", "Increment", "Steps"):
            self._init_range(param_format, param_type, vals)
        elif param_format == "List":
            temp_vals = [_read_value(param_type, v) for v in vals]
            self._value = temp_vals
            # The current List selection lives on the trait ``make_param_traits()`` builds from ``pdefault``.
            default = self._typed_default(param_type)
            if default is not None and default not in temp_vals:
                self._msg += f"Default {default} is not a member of the List {temp_vals}; using {temp_vals[0]}.\n"
                default = None
            self._default = default
            if self._list_tip is not None and len(self._list_tip) != len(temp_vals):
                self._msg += (f"List_Tip has {len(self._list_tip)} entries, but List has {len(temp_vals)}; "
                              "they must match.\n")
        elif param_format == "Corner":
            if param_usage == "Out":
                raise AMIParamError("Corner is not allowed with Usage Out.\n")
            if len(vals) != 3:
                raise AMIParamError(f"Corner needs 3 values (typ, slow, fast); got {len(vals)}.\n")
            typ, slow, fast = (_read_value(param_type, v) for v in vals)
            self._value = typ
            self._corners = {"typ": typ, "min": slow, "max": fast}
            # The value follows the simulation corner (``AMIParamConfigurator.sim_corner``), so a Default
            # (allowed, IBIS 8.0 p.245) is checked but not used.
            default = self._typed_default(param_type)
            if default is not None and default not in (typ, slow, fast):
                self._msg += f"Default {default} is not one of the Corner values {[typ, slow, fast]}.\n"
            self._default = default
        elif param_format == "Table":
            self._init_table(vals)
        else:  # Gaussian, Dual-Dirac, DjRj
            nvals = 2 if param_format == "Gaussian" else 3
            if len(vals) != nvals:
                raise AMIParamError(f"{param_format} needs {nvals} values; got {len(vals)}.\n")
            self._value = [_read_value(param_type, v) for v in vals]

        self._name = name

    def _init_range(self, param_format: str, param_type: str, vals: list) -> None:
        """Complete a Range, Increment or Steps parameter.

        Increment ``<typ> <min> <max> <delta>`` allows ``typ + N*delta`` within ``[min, max]``; Steps
        ``<typ> <min> <max> <# steps>`` is Increment with ``delta = (max - min) / steps`` (IBIS 8.0 p.241).
        """
        nvals = 3 if param_format == "Range" else 4
        if len(vals) < nvals:
            raise AMIParamError(f"Insufficient number of values, {len(vals)}, provided for {param_format}.\n")
        typ, pmin, pmax = (_read_value(param_type, v) for v in vals[:3])
        if not pmin <= typ <= pmax:
            self._msg += f"{param_format} values must be min <= typ <= max; got {vals[:3]}.\n"
        self._value, self._min, self._max = typ, pmin, pmax
        if param_format != "Range":
            step = _read_value("Float", vals[3])
            delta = step if param_format == "Increment" else (pmax - pmin) / step if step else 0.0
            if delta <= 0:
                raise AMIParamError(f"{param_format} needs a positive step; got {vals[3]}.\n")
            if (pmax - pmin) / delta > MAX_DISCRETE_VALUES:
                raise AMIParamError(f"{param_format} has more than {MAX_DISCRETE_VALUES} values.\n")
            n_lo, n_hi = math.ceil((pmin - typ) / delta - 1e-9), math.floor((pmax - typ) / delta + 1e-9)
            values = [typ + n * delta for n in range(n_lo, n_hi + 1)]
            self._values = ([round(v) for v in values] if param_type == "Integer"
                            else [float(f"{v:.12g}") for v in values])  # Drop float noise (0.30000000000000004).
        default = self._typed_default(param_type)
        self._default = None  # Typed, and kept only when it is used (as for List).
        if default is None:
            return
        if self._values is not None and default not in self._values:
            self._msg += f"Default {default} is not one of the {param_format} values {self._values}; using {typ}.\n"
        elif not pmin <= default <= pmax:
            self._msg += f"Default {default} is outside the {param_format} [{pmin}, {pmax}]; using {typ}.\n"
        else:
            self._value = self._default = default

    def _init_table(self, items: list) -> None:
        """Complete a Table parameter: optional ``Labels``, then one or more rows of equal length (IBIS 8.0 p.242)."""
        if items and isinstance(items[0], tuple) and items[0][0] == "Labels":
            self._labels = [label.strip('"') for label in items[0][1]]
            items = items[1:]
        if not items or not all(isinstance(row, list) for row in items):
            raise AMIParamError(f"A Table needs one or more rows of values; got {items}.\n")
        ncols = len(items[0])
        if any(len(row) != ncols for row in items):
            raise AMIParamError("All Table rows must have the same number of entries.\n")
        types = self._types if len(self._types) > 1 else self._types * ncols
        if len(types) != ncols:
            raise AMIParamError(f"Table has {ncols} columns but {len(types)} Types.\n")
        self._value = [[_read_value(t, v) for t, v in zip(types, row)] for row in items]

    def _typed_default(self, param_type: str):
        """``Default``, read as ``param_type``; ``None`` if absent or unreadable (with a warning in ``msg``).

        Range and List use it, if present, as the initial value (IBIS 8.0 Section 10.3.4, p.245).
        """
        if self._default is None:
            return None
        try:
            return _read_value(param_type, self._default)
        except AMIParamError as err:
            self._msg += f"Ignoring Default: {err}"
            return None

    def __str__(self):
        return f"{self.pvalue}"


def _read_value(param_type: str, value_str: str):
    """One AMI value, as the given ``Type``.

    Raises:
        AMIParamError: ``value_str`` isn't a value of that type.
    """
    if not isinstance(value_str, str):
        raise AMIParamError(f"Expected a single {param_type} value; got {value_str}.\n")
    value_str = value_str.strip()
    if param_type in ("Float", "UI", "Tap"):
        try:
            return float(value_str)
        except (ValueError, TypeError) as exc:
            raise AMIParamError(f"Couldn't read float from '{value_str}'.\n") from exc
    if param_type == "Integer":
        try:
            as_float = float(value_str)  # Accommodates "1e5", for instance.
        except (ValueError, TypeError) as exc:
            raise AMIParamError(f"Couldn't read integer from '{value_str}'.\n") from exc
        if not as_float.is_integer():  # "if Type is Integer, <value> shall be an integer" (IBIS 8.0 p.245).
            raise AMIParamError(f"Couldn't read integer from '{value_str}'.\n")
        return int(as_float)
    if param_type == "Boolean":
        if value_str == "True":
            return True
        if value_str == "False":
            return False
        raise AMIParamError(f"Couldn't read Boolean from '{value_str}'.\n")
    return value_str.strip('"')  # `String`


#####
# AMI parameter tuner
#####


# pylint: disable=too-many-instance-attributes,too-few-public-methods
class AmiParamTuner(HasTraits):
    """Object used to populate the rows of a Tx/Rx AMI parameter tuning table.

    Represents one *Model_Specific* 'In'/'InOut' AMI parameter, of 'Range'
    format, offered to the user for inclusion in EQ optimization.
    """

    name = Str("(noname)")  # Display name (fully hierarchical, e.g. "tx_preset_coeffs_main").
    branch_names = List(Str)  # Hierarchical path for `fetch_param_val()`/`set_param_val()`.
    enabled = Bool(False)  # Will participate in EQ optimization when *True*.
    min_val = Float(0.0)  # Minimum allowed value during optimization.
    max_val = Float(0.0)  # Maximum allowed value during optimization.
    step = Float(0.0)  # Increment used during optimization.
    value = Float(0.0)  # Current value.
    is_int = Bool(False)  # Round swept values to the nearest integer when *True*.

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self, name: str = "(noname)", branch_names: "list[str] | None" = None, enabled: bool = False,
        min_val: float = 0.0, max_val: float = 0.0, step: float = 0.0, value: float = 0.0, is_int: bool = False
    ):
        """
        Allows user to define properties, at instantiation.

        Keyword Args:
            name: Parameter name/label.
                Default: "(noname)"
            branch_names: Hierarchical path to the parameter, rooted at "Model_Specific".
                Default: []
            enabled: Will participate in EQ optimization when *True*.
                Default: *False*
            min_val: Minimum allowed value during optimization.
                Default: 0.0
            max_val: Maximum allowed value during optimization.
                Default: 0.0
            step: Increment used during optimization.
                Default: 0.0
            value: Current value.
                Default: 0.0
            is_int: Round swept values to the nearest integer when *True*.
                Default: *False*
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super().__init__()

        self.name = name
        self.branch_names = branch_names or []
        self.enabled = enabled
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.value = value
        self.is_int = is_int
