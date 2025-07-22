"""``AMIParameter`` class definition, plus some helpers.

Original author: David Banas <capn.freako@gmail.com>

Original date:   December 24, 2016

Copyright (c) 2019 David Banas; all rights reserved World wide.
"""

#####
# AMI parameter
#####


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
        if val in ("In", "Out", "InOut", "Info"):
            self._usage = val
        else:
            raise AMIParamError(f"Unrecognized usage value: '{val}'.")

    def _get_usage(self):
        return self._usage

    pusage = property(_get_usage, doc="Value of AMI parameter 'Usage' tag.")

    # ptype
    def _set_type(self, values):
        "Process *Type* tag."

        val = values[0]
        if val in ("Float", "Integer", "String", "Boolean", "UI", "Tap"):
            self._type = val
        else:
            raise AMIParamError(f"Unrecognized type value: '{val}'.")

    def _get_type(self):
        return self._type

    ptype = property(_get_type, doc="Value of AMI parameter 'Type' tag.")

    # pformat
    def _set_format(self, values):
        "Process *Format* tag."

        form = values[0]
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
        self._description = values[0]

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

    _param_def_tag_procs = {
        "Usage": _set_usage,
        "Type": _set_type,
        "Format": _set_format,
        "Value": _set_value,
        "Range": _set_range,
        "List": _set_list,
        "Corner": _set_list,
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
            else:
                self._value = "False"
            param_format = "Value"
            self._format_rem = [self._value]
        self._format = param_format

        # Check for 'Default' used with parameter type 'Out'.
        if (param_usage == "Out") and (param_default is not None):
            raise AMIParamError("'Default' may not be used with parameter type 'Out'!\n")

        # Complete the instance.
        vals = self._format_rem
        if param_format == "Value":
            value_str = vals[0].strip()
            if param_type in ("Float", "UI"):
                try:
                    self._value = float(value_str)
                except (ValueError, TypeError) as exc:
                    raise AMIParamError(f"Couldn't read float from '{value_str}'.\n") from exc
            elif param_type == "Integer":
                try:
                    self._value = int(float(value_str))  # Hack to accommodate: "1e5", for instance.
                except (ValueError, TypeError) as exc:
                    raise AMIParamError(f"Couldn't read integer from '{value_str}'.\n") from exc
            elif param_type == "Boolean":
                if value_str == "True":
                    self._value = True
                elif value_str == "False":
                    self._value = False
                else:
                    raise AMIParamError(f"Couldn't read Boolean from '{value_str}'.\n")
            else:  # `String`
                self._value = value_str.strip('"')
        elif param_format == "Range":
            if param_type not in ("Float", "Integer", "UI", "Tap"):
                raise AMIParamError(f"Illegal type, '{param_type}', for use with Range.\n")
            if len(vals) < 3:
                raise AMIParamError(f"Insufficient number of values, {len(vals)}, provided for Range.\n")
            if param_type in ("Float", "UI", "Tap"):
                try:
                    temp_vals = list(map(float, vals[:3]))
                except (ValueError, TypeError) as exc:
                    raise AMIParamError(f"Couldn't read floats from '{vals[:3]}'.\n") from exc
            else:
                try:
                    temp_vals = list(map(int, vals[:3]))
                except (ValueError, TypeError) as exc:
                    raise AMIParamError(f"Couldn't read integers from '{vals[:3]}'.\n") from exc
            self._value = temp_vals[0]
            self._min = temp_vals[1]
            self._max = temp_vals[2]
        else:  # param_format == 'List'
            if param_type in ("Float", "UI"):
                try:
                    temp_vals = list(map(float, vals))
                except (ValueError, TypeError) as exc:
                    raise AMIParamError(f"Couldn't read floats from '{vals}'.\n") from exc
            elif param_type in ("Integer", "Tap"):
                try:
                    temp_vals = list(map(int, vals))
                except (ValueError, TypeError) as exc:
                    raise AMIParamError(f"Couldn't read integers from '{vals}'.\n") from exc
            else:  # 'param_type' == 'String'
                try:
                    temp_vals = list(map(str, vals))
                    temp_vals = [x.strip('"') for x in temp_vals]
                except (ValueError, TypeError) as exc:
                    raise AMIParamError(f"Couldn't read strings from '{vals}'.\n") from exc
            self._value = temp_vals

        self._name = name
