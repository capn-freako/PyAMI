"""IBIS-AMI model parameter configurator: the user's choice of AMI parameter values.

Original author: David Banas <capn.freako@gmail.com>

Original date:   December 17, 2016

Copyright (c) 2019 David Banas; all rights reserved World wide.
"""

from __future__     import annotations
from ctypes         import c_double
import re
from typing         import Any, Optional

import numpy as np
from numpy.typing import NDArray
from traits.api import Bool, Enum, HasTraits, Range, Trait, TraitType

from .model                     import AMIModelInitializer
from .parameter                 import FIXED_FORMATS, AmiParamTuner, AMIParameter
from .parser                    import (ModelSpecificDict, ParamName, Parameters, ParamValues, ReservedParamDict,
                                        parse_ami_file_contents)

__all__ = ["AMIParamConfigurator", "make_param_traits", "trait_name_part"]

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

        A *Model Specific* parameter with a trait (Usage In/InOut) gives its current value (e.g. - the selected
        List value), as sent to the model; a Corner gives its value for ``sim_corner``.

        Note: 'branch_names' should *not* begin with 'root_name'.
        """
        _param = self.fetch_param(list(branch_names))
        if not _param:
            return None
        tname = self._param_trait_name(branch_names)
        if tname:
            return self._trait_value(tname)
        return self._fixed_value(_param) if _param.pformat == "Corner" else _param.pvalue

    def _param_trait_name(self, branch_names: list[str]) -> Optional[str]:
        "The trait holding the value of the parameter at ``branch_names``; ``None`` if it has none."
        if branch_names[:1] != ["Model_Specific"]:
            return None
        tname = "_".join(trait_name_part(name) for name in branch_names[1:])
        return tname if tname in self._param_trait_names else None

    def _trait_value(self, tname: str) -> Any:
        "A parameter trait's value, as sent to the model (a mapped trait's (List_Tip's) value, not its label)."
        trait = self.trait(tname)
        return getattr(self, f"{tname}_" if trait.is_mapped else tname)

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

        Raises:
            ValueError: No parameter at ``branch_names``; a Corner parameter; an Integer parameter given a
                non-integer value; or a value that isn't one of a List_Tip parameter's values.
            TypeError: ``branch_names`` names a group, not a parameter.
            TraitError: The value isn't legal for the parameter (e.g. - outside its Range).

        Notes:
            1. ``branch_names`` should *not* begin with <root_name>.
            2. A *Model Specific* parameter with a trait (Usage In/InOut) is set on its trait, which checks the
               value; ``pvalue`` keeps the ``.ami`` file's value. Other parameters (e.g. - Reserved ones) set
               ``pvalue``, unchecked.
        """

        param_dict = self.ami_param_defs
        for branch_name in branch_names:
            if branch_name not in param_dict:
                raise ValueError(
                    f"Failed parameter tree search looking for: {branch_name}; available keys: {param_dict.keys()}"
                )
            param_dict = param_dict[branch_name]  # type: ignore
        if not isinstance(param_dict, AMIParameter):
            raise TypeError(f"{param_dict} is not of type: AMIParameter!")
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
            as_float = float(new_val)
            if not as_float.is_integer():
                raise ValueError(f"Integer parameter {branch_names} can't be set to {new_val!r}.")
            new_val = int(as_float)
        elif param_dict.ptype in ("Float", "UI", "Tap"):  # A Tap is a (float) tap weight.
            new_val = float(new_val)
        tname = self._param_trait_name(branch_names)
        if tname:
            trait = self.trait(tname)
            if trait.is_mapped:  # List_Tip: the trait holds the tip; ``<tname>_`` follows it (read-only).
                tips = [tip for tip, value in trait.handler.map.items() if value == new_val]
                if not tips:
                    raise ValueError(f"{new_val!r} isn't one of the values of {branch_names}: "
                                     f"{list(trait.handler.map.values())}")
                new_val = tips[0]
            self.trait_set(**{tname: new_val})
        # `pvalue`, for 'List' format, holds the list of *legal* values, not the
        # current one (that lives on the Trait) -- leave it alone, to avoid corrupting it.
        elif param_dict.pformat != "List":
            param_dict.pvalue = new_val

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
        selector" parameters).

        Each tuner's ``value`` is the parameter's current value (its trait's), as sent to the model."""
        tuners = []
        for branch_names, param in self.tunable_params:
            tname = "_".join(map(trait_name_part, branch_names[1:]))  # Drop the "Model_Specific" root.
            if param.pformat == "Range":
                pmin, pmax = float(param.pmin), float(param.pmax)
                step = (pmax - pmin) / 10 or 1.0
                is_int = param.ptype == "Integer"
            elif param.pformat == "Value" and param.ptype == "Boolean":
                pmin, pmax, step, is_int = 0.0, 1.0, 1.0, True
            else:  # List-format Integer "mode selector" (contiguous legal values).
                # `pvalue`, for 'List' format, is the list of *legal* values, not the current one.
                vals = [float(v) for v in param.pvalue]
                pmin, pmax, step, is_int = min(vals), max(vals), 1.0, True
            # `pvalue` keeps the `.ami` file's value; the current one lives on the trait.
            value = float(self._trait_value(tname))
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
                res[pname] = self._trait_value(tname)
            elif param.pusage in ("In", "InOut") and param.pformat in FIXED_FORMATS:  # Sent, but has no trait.
                res[pname] = self._fixed_value(param)
        elif isinstance(param, dict):  # We received a dictionary of subparameters, in 'param'.
            subs: ParamValues = {}
            for sname in param:
                subs.update(self.input_ami_param(param, sname, prefix=tname + "_"))  # type: ignore
            if subs:  # A group with nothing to send is left out (IBIS 8.0 Section 10.3.6, p.246).
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


def trait_name_part(name: str) -> str:
    """The trait/display form of one AMI parameter name.

    Tap weights are named by tap number (``-1``, ``0``, ``1``; IBIS 8.0 Section 10.3.4, p.240), which isn't a valid
    trait name, so they're shown as ``pre1``, ``post0``, ``post1``. Everything sent to the
    model (``input_ami_params``, ``fetch_param_val()``/``set_param_val()`` paths) keeps the ``.ami`` names.
    """
    m = re.fullmatch(r"([-+]?)([0-9]+)", name)
    if not m:
        return name
    return ("pre" if m[1] == "-" else "post") + m[2]


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
