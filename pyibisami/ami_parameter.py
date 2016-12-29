"""
*AMIParameter* class definition, plus some helpers.

Original author: David Banas <capn.freako@gmail.com>
Original date:   December 24, 2016

Copyright (c) 2016 David Banas; all rights reserved World wide.

"""

#####
# AMI parameter
#####

class AMIParamError(Exception):
    pass
        
class AMIParameter(object):
    """
    IBIS-AMI model parameter.

    This class encapsulates the attributes and behavior of a AMI
    parameter.

    """

    RESERVED_PARAM_NAMES = ['AMI_Version', 'GetWave_Exists', 'Init_Returns_Impulse', 'Ignore_Bits']

    # Properties.

    # Note: They are read-only, despite the presence of apparent setters.
    #       (The idea is that, once initialized, parameter definitions
    #        are immutable.)

    # Note that the setters, below, are only intended for use by
    # __init__(). They may raise an *AMIParamError* exception. This is
    # to ensure that a malformed instance never be created.

    ## name
    def _get_name(self):
        return self._name
    pname = property(_get_name, doc="Name of AMI parameter.")

    ## usage
    def _set_usage(self, values):
        'Process *Usage* tag.'

        val = values[0]
        if(val in ['In', 'Out', 'InOut', 'Info']):
            self._usage = val
        else:
            raise AMIParamError ("Unrecognized usage value: '{}'.".format(val))
    def _get_usage(self):
        return self._usage
    pusage = property(_get_usage, doc="Value of AMI parameter 'Usage' tag.")

    ## ptype
    def _set_type(self, values):
        'Process *Type* tag.'

        val = values[0]
        if(val in ['Float', 'Integer', 'String', 'Boolean', 'UI']):
            self._type = val
        else:
            raise AMIParamError ("Unrecognized type value: '{}'.".format(val))
    def _get_type(self):
        return self._type
    ptype = property(_get_type, doc="Value of AMI parameter 'Type' tag.")

    ## format
    def _set_format(self, values):
        'Process *Format* tag.'

        form = values[0]
        if(not form in ['Value', 'Range', 'List']):
            raise AMIParamError ("Unrecognized format value: '{}'.".format(form))
        if(len(values) < 2):
            raise AMIParamError ("No values provided for: '{}'.".format(form))
        self._format = form
        self._format_rem = values[1:]
    def _get_format(self):
        return self._format
    pformat = property(_get_format, doc="Value of AMI parameter 'Format' tag.")

    ## value
    def _get_value(self):
        return self._value
    pvalue = property(_get_value, doc="Value of AMI parameter.")

    ## min
    def _get_min(self):
        return self._min
    pmin = property(_get_min, doc="Minimum value of AMI parameter.")

    ## max
    def _get_max(self):
        return self._max
    pmax = property(_get_max, doc="Maximum value of AMI parameter.")

    ## default
    def _set_default(self, values):
        'Process *Default* tag.'
        self._default = values[0]

    ## description
    def _set_description(self, values):
        'Process *Description* tag.'
        self._description = values[0]
    def _get_description(self):
        return self._description
    pdescription = property(_get_description, doc="Description of AMI parameter.")

    ## list_tip
    def _set_list_tip(self, values):
        'Process *List_Tip* tag.'
        self._list_tip = map(lambda x: x.strip('"'), values)
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
        'Process *Value* tag.'

        return self._set_format(['Value'] + values)

    # range
    def _set_range(self, values):
        'Process *Range* tag.'

        return self._set_format(['Range'] + values)


    # usage
    def _set_list(self, values):
        'Process *List* tag.'

        return self._set_format(['List'] + values)


    # This dictionary defines both:
    #
    #  - the allowed parameter definition tag names, and
    #  - their processing functions.
    #
    # The idea is to allow this class to grow along with the IBIS
    # standard, without having to change any of its boilerplate.

    _param_def_tag_procs = {
        'Usage'             : _set_usage,
        'Type'              : _set_type,
        'Format'            : _set_format,
        'Value'             : _set_value,
        'Range'             : _set_range,
        'List'              : _set_list,
        'Default'           : _set_default,
        'Description'       : _set_description,
        'List_Tip'          : _set_list_tip,
    }

    # Initialization
    _usage              = None
    _type               = None
    _format             = None
    _value              = None
    _min                = None
    _max                = None
    _default            = None
    _description        = None
    _list_tip           = None

    def __init__(self, name, tags):
        """
        Inputs:

          - name    The name of the AMI parameter being created.

          - tags    A list of pairs, each containing:
                      - a parameter definition tag name
                        (Must be one of the keys from the
                         '_param_def_tag_procs' dictionary, above.)
                      - a list of values to be associated with that tag.

        """

        # Process all parameter definition tags.
        for tag in tags:
            tag_name = tag[0]
            if(not tag_name in self._param_def_tag_procs):
                raise AMIParamError("Unrecognized tag, '{}', found in definition of parameter, '{}'.".format(tag_name, name))
            else:
                try:
                    self._param_def_tag_procs[tag_name](self, tag[1])
                except AMIParamError as err:
                    raise AMIParamError("Problem initializing parameter, '{}':\n\t".format(name) + err.message)

        # Validate and complete the instance.
        ## Check for required tags.
        param_usage   = self._usage
        param_type    = self._type
        param_format  = self._format
        param_default = self._default
        if(param_usage is None):
            raise AMIParamError("Missing 'Usage' tag!")
        if(param_type is None):
            raise AMIParamError("Missing 'Type' tag!")
        if(param_format is None):
            if(param_default is None):
                raise AMIParamError("Missing both 'Format' and 'Default' tags!")
            else:
                self._value = param_default

        ## Check for mutual exclusivity of 'Format Value' and 'Default'.
        if( (param_format == 'Value') and (param_default is not None) ):
            raise AMIParamError("'Format Value' and 'Default' both found! (They are mutually exclusive.)")

        ## Check for 'Default' used with parameter type 'Out'.
        if( (param_type == 'Out') and (param_default is not None) ):
            raise AMIParamError("'Default' may not be used with parameter type 'Out'!")

        ## Complete the instance.
        vals = self._format_rem
        if(param_format == 'Value'):
            value_str = vals[0].strip()
            if(param_type == 'Float' or param_type == 'UI'):
                try:
                    self._value = float(value_str)
                except:
                    raise AMIParamError("Couldn't read float from '{}'.".format(value_str))
            elif(param_type == 'Integer'):
                try:
                    self._value = int(value_str)
                except:
                    raise AMIParamError("Couldn't read integer from '{}'.".format(value_str))
            elif(param_type == 'Boolean'):
                if(value_str == 'True'):
                    self._value = True
                elif(value_str == 'False'):
                    self._value = False
                else:
                    raise AMIParamError("Couldn't read Boolean from '{}'.".format(value_str))
            else:
                self._value = value_str.strip('"')
        elif(param_format == 'Range'):
            if(not ( param_type == 'Float' or param_type == 'Integer' or param_type == 'UI' )):
                raise AMIParamError("Illegal type, '{}', for use with Range.".format(param_type))
            if(len(vals) < 3):
                raise AMIParamError("Insufficient number of values, {}, provided for Range.".format(len(vals)))
            if(param_type == 'Float' or param_type == 'UI'):
                try:
                    temp_vals = map(float, vals[:3])
                except:
                    raise AMIParamError("Couldn't read floats from '{}'.".format(vals[:3]))
            else:
                try:
                    temp_vals = map(int, vals[:3])
                except:
                    raise AMIParamError("Couldn't read integers from '{}'.".format(vals[:3]))
            self._value = temp_vals[0]
            self._min   = temp_vals[1]
            self._max   = temp_vals[2]
        else:  # param_format == 'List'
            if(param_type == 'Float' or param_type == 'UI'):
                try:
                    temp_vals = map(float, vals)
                except:
                    raise AMIParamError("Couldn't read floats from '{}'.".format(vals))
            else:
                try:
                    temp_vals = map(int, vals)
                except:
                    raise AMIParamError("Couldn't read integers from '{}'.".format(vals))
            self._value = temp_vals

        self._name = name



