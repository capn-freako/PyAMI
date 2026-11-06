"""IBIS-AMI model parameter configurator: the user's choice of AMI parameter values.

Original author: David Banas <capn.freako@gmail.com>

Original date:   December 17, 2016

Copyright (c) 2019 David Banas; all rights reserved World wide.
"""

from __future__     import annotations
from ctypes         import c_double
import re
from collections.abc import Callable, Iterator, Mapping
from typing         import Any, Optional

import numpy as np
from numpy.typing import NDArray

from ..events                   import InvalidValueError, Signal
from .model                     import AMIModelInitializer
from .parameter                 import FIXED_FORMATS, AmiParamTuner, AMIParameter
from .parser                    import (ModelSpecificDict, ParamName, Parameters, ParamValues, ReservedParamDict,
                                        parse_ami_file_contents)

__all__ = ["AMIParamConfigurator", "ParamPath", "SIM_CORNERS", "display_name", "display_name_part"]

ParamPath = tuple[str, ...]  # A parameter's path in the ``.ami`` file, rooted at "Model_Specific" (no root name).
SIM_CORNERS = ("typ", "min", "max")

#####
# AMI parameter configurator.
#####


class AMIParamConfigurator:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """The user's choice of values for an IBIS-AMI model's parameters.

    The intended use model is as follows:

     1. Instantiate this class once per IBIS-AMI model, giving the unprocessed contents of its ``.ami`` file.
        Any warnings found while parsing are in ``ami_parsing_errors``.

     2. Set parameter values with ``set_param_val()`` (or let the user do it, in the ``gui`` extra's
        ``AmiParamEditor``, or ``open_gui()``). Every *Model Specific* parameter of Usage *In* or *InOut*
        (except the ``FIXED_FORMATS``) has a current value, starting at its ``AMIParameter.initial_value``.

     3. Pass ``input_ami_params`` (or use ``get_init()``) to ``AMIModelInitializer``.

    Each change of a value is announced through ``values_changed`` (``(path, old, new)``), and each change of
    ``sim_corner`` through ``sim_corner_changed`` (``(old, new)``).

    Parameters of Format Corner aren't user-selectable: their value follows ``sim_corner``
    (``"typ"``, ``"min"`` (slow) or ``"max"`` (fast); IBIS 8.0 Section 10.3.5, p.246), the same
    corner the application uses for the IBIS model data.
    """

    def __init__(self, ami_file_contents_str: str) -> None:
        """
        Args:
            ami_file_contents_str: The unprocessed contents of the AMI file, as a single string.

        Raises:
            RuntimeError: The file couldn't be parsed.
            ValueError: It has no ``Reserved_Parameters`` section.
        """
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
        self._root_name = root_name
        self._ami_parsing_errors = errors + warnings
        self._reserved_param_dict = reserved_param_dict
        self._model_specific_dict = model_specific_dict
        self._description = description
        self._sim_corner = "typ"
        self._settable: dict[ParamPath, AMIParameter] = dict(
            _walk_leaves(model_specific_dict, ("Model_Specific",), lambda param: param.is_settable))
        self._values: dict[ParamPath, Any] = {path: param.initial_value for path, param in self._settable.items()}
        self.values_changed = Signal()  # (path, old, new)
        self.sim_corner_changed = Signal()  # (old, new)

    def open_gui(self) -> bool:
        """Let the user set the parameter values, in a modal dialog.

        Requires the ``gui`` extra: ``pip install 'pyibis-ami[gui]'``.

        Returns:
            ``True`` if the user accepted the dialog. Changes apply as they're made; Cancel undoes them.
        """
        from ..gui.dialogs import edit_ami_params  # pylint: disable=import-outside-toplevel
        return edit_ami_params(self)

    @property
    def sim_corner(self) -> str:
        "The simulation corner (``typ``, ``min`` or ``max``); selects each Corner parameter's value."
        return self._sim_corner

    @sim_corner.setter
    def sim_corner(self, corner: str) -> None:
        if corner not in SIM_CORNERS:
            raise InvalidValueError(f"sim_corner must be one of {SIM_CORNERS}; got {corner!r}.")
        old, self._sim_corner = self._sim_corner, corner
        if old != corner:
            self.sim_corner_changed.emit(old, corner)

    @property
    def description(self) -> str:
        "The model's description, from the ``.ami`` file."
        return self._description

    @property
    def root_name(self) -> str:
        "The AMI model root name."
        return self._root_name

    @property
    def model_specific_dict(self) -> ModelSpecificDict:
        "The parsed ``Model_Specific`` parameter definitions (read-only: values are set with ``set_param_val()``)."
        return self._model_specific_dict

    def fetch_param(self, branch_names) -> Optional[AMIParameter]:
        """Returns the parameter found by traversing 'branch_names' or None if
        not found.

        Note: 'branch_names' should *not* begin with 'root_name'.
        """
        try:
            node = self._lookup(branch_names)
        except ValueError:
            return None
        return node if isinstance(node, AMIParameter) else None

    def _lookup(self, branch_names) -> Any:
        """The node (parameter or group) at ``branch_names`` in ``ami_param_defs``.

        Raises:
            ValueError: There's none; the message lists the keys available where the search failed.
        """
        node: Any = self.ami_param_defs
        for branch_name in branch_names:
            if not isinstance(node, dict) or branch_name not in node:
                keys = node.keys() if isinstance(node, dict) else []
                raise ValueError(f"Failed parameter tree search looking for: {branch_name}; available keys: {keys}")
            node = node[branch_name]
        return node

    def fetch_param_val(self, branch_names):
        """Returns the value of the parameter found by traversing
        'branch_names' or None if not found.

        A settable *Model Specific* parameter (Usage In/InOut) gives its current value (e.g. - the selected
        List value), as sent to the model; a Corner gives its value for ``sim_corner``.

        Note: 'branch_names' should *not* begin with 'root_name'.
        """
        _param = self.fetch_param(branch_names)
        if not _param:
            return None
        path = tuple(branch_names)
        if path in self._values:
            return self._values[path]
        return self._fixed_value(_param) if _param.pformat == "Corner" else _param.pvalue

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
        branch_names: list[str] | ParamPath,
        new_val: Any
    ) -> None:
        """
        Sets the value of the parameter found by traversing 'branch_names'
        or raises an exception if not found.

        Args:
            branch_names: A sequence of node names, used to traverse the parameter tree.
            new_val: The value to assign to the target parameter.

        Raises:
            ValueError: No parameter at ``branch_names``, or a Corner parameter.
            TypeError: ``branch_names`` names a group, not a parameter.
            InvalidValueError: The value isn't legal for the parameter (see ``AMIParameter.validate()``).

        Notes:
            1. ``branch_names`` should *not* begin with <root_name>.
            2. A settable *Model Specific* parameter (Usage In/InOut) is checked, and its current value set
               (announced through ``values_changed``); ``pvalue`` keeps the ``.ami`` file's value. Other parameters
               (e.g. - Reserved ones) set ``pvalue``, unchecked.
        """

        param_dict = self._lookup(branch_names)
        if not isinstance(param_dict, AMIParameter):
            raise TypeError(f"{param_dict} is not of type: AMIParameter!")
        if param_dict.pformat == "Corner":
            raise ValueError(f"A Corner parameter's value follows `sim_corner`; it can't be set: {branch_names}")
        path = tuple(branch_names)
        if path in self._values:
            new_val = param_dict.validate(new_val)
            old = self._values[path]
            self._values[path] = new_val
            if old != new_val:
                self.values_changed.emit(path, old, new_val)
        # `pvalue`, for 'List' format, holds the list of *legal* values, not the current one -- leave it alone.
        elif param_dict.pformat != "List":
            param_dict.pvalue = new_val

    def iter_settable(self) -> Iterator[tuple[ParamPath, AMIParameter]]:
        "Each settable parameter (``AMIParameter.is_settable``) and its path, in ``.ami`` file order."
        yield from self._settable.items()

    def current_values(self) -> dict[ParamPath, Any]:
        "A snapshot of every settable parameter's current value, keyed by path."
        return dict(self._values)

    def apply_values(self, values: Mapping[ParamPath, Any] | Mapping[str, Any], *, strict: bool = False) -> list[str]:
        """Set several values (e.g. - a saved ``current_values()``), keyed by path (a tuple, or ``/``-joined).

        Keyword Args:
            strict: Raise on the first unknown path or illegal value, instead of skipping it.
                Default: ``False``

        Returns:
            One message per skipped entry.
        """
        skipped = []
        for key, value in values.items():
            path = tuple(key.split("/")) if isinstance(key, str) else tuple(key)
            if path not in self._values:
                if strict:
                    raise ValueError(f"No settable parameter at {path}.")
                skipped.append(f"No settable parameter at {'/'.join(path)}; skipped.")
                continue
            try:
                self.set_param_val(path, value)
            except InvalidValueError as err:
                if strict:
                    raise
                skipped.append(f"{'/'.join(path)}: {err} Skipped.")
        return skipped

    def reset_to_defaults(self) -> None:
        "Set every settable parameter back to its ``AMIParameter.initial_value``."
        for path, param in self._settable.items():
            self.set_param_val(path, param.initial_value)

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
        return [(list(path), param)
                for path, param in _walk_leaves(self._model_specific_dict, ("Model_Specific",), _is_sweepable)]

    def mk_tap_tuners(self) -> list[AmiParamTuner]:
        """Build a fresh list of `AmiParamTuner`s from this AMI model's tunable
        Model_Specific parameters (see `tunable_params` for exactly which ones
        qualify: Range-format, Boolean, and contiguous Integer/List "mode
        selector" parameters).

        Each tuner's ``value`` is the parameter's current value, as sent to the model."""
        tuners = []
        for branch_names, param in self.tunable_params:
            tname = display_name(branch_names)
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
            value = float(self._values[tuple(branch_names)])
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
            res.update(self.input_ami_param(params, pname, prefix=("Model_Specific",)))
        return res

    def input_ami_param(
        self,
        params: Parameters,
        pname: ParamName,
        prefix: ParamPath = ("Model_Specific",)
    ) -> ParamValues:
        """
        Retrieve one AMI parameter value, or dictionary of subparameter values,
        from the given parameter definition dictionary.

        Args:
            params: The parameter definition dictionary.
            pname: The simple name of the parameter of interest, used by the IBIS-AMI model.

        Keyword Args:
            prefix: The path of ``params``.
                Default: ``("Model_Specific",)``

        Returns:
            A dictionary of parameter values indexed by (unprefixed) parameter names.
        """

        res = {}
        path = (*prefix, pname)
        param = params[pname]
        if isinstance(param, AMIParameter):
            if path in self._values:  # If settable (model specific and of type In or InOut)...
                res[pname] = self._values[path]
            elif param.pusage in ("In", "InOut") and param.pformat in FIXED_FORMATS:  # Sent, but not settable.
                res[pname] = self._fixed_value(param)
        elif isinstance(param, dict):  # We received a dictionary of subparameters, in 'param'.
            subs: ParamValues = {}
            for sname in param:
                subs.update(self.input_ami_param(param, sname, prefix=path))  # type: ignore
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
        Get a model initializer.

        Keyword Args:
            ami_params: The AMI parameters to send; ``input_ami_params`` (the current values) when ``None``.
                Default: ``None``
        """

        initializer = AMIModelInitializer(
            ami_params if ami_params is not None else self.input_ami_params,
            info_params=self.info_ami_params,
            bit_time=c_double(bit_time),
            row_size=len(channel_response),
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


def _walk_leaves(
    params: Parameters, prefix: ParamPath, keep: Callable[[AMIParameter], bool]
) -> Iterator[tuple[ParamPath, AMIParameter]]:
    "Each leaf of a parameter (sub)tree for which ``keep`` is true, with its path, in file order."
    for pname, param in params.items():
        if pname == "description":  # A branch's optional descriptive text, not a subparameter.
            continue
        path = (*prefix, pname)
        if isinstance(param, AMIParameter):
            if keep(param):
                yield path, param
        else:  # Subparameter branch.
            yield from _walk_leaves(param, path, keep)


def display_name_part(name: str) -> str:
    """The display form of one AMI parameter name.

    Tap weights are named by tap number (``-1``, ``0``, ``1``; IBIS 8.0 Section 10.3.4, p.240), shown as ``pre1``,
    ``post0``, ``post1``. Everything sent to the model (``input_ami_params``, ``fetch_param_val()``/
    ``set_param_val()`` paths) keeps the ``.ami`` names.
    """
    m = re.fullmatch(r"([-+]?)([0-9]+)", name)
    if not m:
        return name
    return ("pre" if m[1] == "-" else "post") + m[2]


def display_name(path: list[str] | ParamPath) -> str:
    "A parameter's flat display name: its path (less the ``Model_Specific`` root) as ``display_name_part`` s, ``_``-joined."
    parts = path[1:] if path and path[0] == "Model_Specific" else path
    return "_".join(map(display_name_part, parts))
