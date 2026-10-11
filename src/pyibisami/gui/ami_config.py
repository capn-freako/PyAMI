"""
Traits/UI view for ``AMIParamConfigurator``.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   December 17, 2016

Copyright (c) 2019 David Banas; all rights reserved World wide.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from traitsui.api import Group, HGroup, Item, VGroup, View
from traitsui.menu import ModalButtons

from ..ami.parameter import AMIParameter
from ..ami.parser import trait_name_part

if TYPE_CHECKING:
    from ..ami.parser import AMIParamConfigurator, ModelSpecificDict, Parameters

MAX_ITEMS_PER_ROW = 8


def make_view(cfg: AMIParamConfigurator) -> View:
    """
    Builds the parameter configuration ``View`` for an ``AMIParamConfigurator``.

    Args:
        cfg: The configurator whose *In* and *InOut* parameters are to be presented.

    Returns:
        The Traits/UI ``View``.
    """
    view = View(
        resizable=False,
        buttons=ModalButtons,
        title=f"{cfg.root_name} AMI Parameter Configurator",
    )
    view.set_content([make_gui(cfg.model_specific_dict)])
    return view


def make_gui(params: ModelSpecificDict) -> Group:
    """
    Builds top-level ``Group`` from AMI parameter dictionary.

    Args:
        params: Dictionary of AMI parameters to be configured.

    Returns:
        The top-level ``Group`` for the ``View``.
    """

    gui_items: list[Item | Group] = []

    # Place parameters with a common prefix in their names,
    # but no pre-existing enclosing group, in a ``VGroup``.
    # - Generate grouped parameter names and list of unique group names.
    pnames = list(params.keys())
    pnames_split = [n.split('_') for n in pnames]
    group_names = [xs[0] for xs in pnames_split]
    grouped_pnames = list(zip(pnames, group_names))
    # The following doesn't preserve the parameter ordering of the AMI file!
    # for group_name in set(group_names):  # Iterate over unique group names.
    unique_group_names = []
    for group_name in group_names:
        if group_name not in unique_group_names:
            unique_group_names.append(group_name)
    # - Process all parameters, trapping those from a non-explicit group for special processing.
    for group_name in unique_group_names:
        pnames_in_group = [pname for pname, grp_name in grouped_pnames if grp_name == group_name]
        if len(pnames_in_group) > 1:
            _gui_items: list[Item | Group] = []
            for pname in pnames_in_group:
                _gui_items.extend(make_gui_items(trait_name_part(pname), params[pname]))
            gui_items.append(VGroup(*_gui_items, label=group_name, show_border=True))
        else:
            pname = pnames_in_group[0]
            gui_items.extend(make_gui_items(trait_name_part(pname), params[pname]))

    # Finally, split into two rows if necessary.
    if len(gui_items) > MAX_ITEMS_PER_ROW:
        return VGroup(
            HGroup(*(gui_items[:MAX_ITEMS_PER_ROW])),
            HGroup(*(gui_items[MAX_ITEMS_PER_ROW:])))
    return HGroup(*gui_items)


def make_gui_items(pname: str, param: AMIParameter | Parameters) -> list[Item | Group]:
    """
    Builds list of GUI items from AMI parameter or dictionary.

    Args:
        pname: Parameter or sub-group name.
        param: AMI parameter or dictionary of AMI parameters to be configured.

    Returns:
        The list of GUI items for the ``View``.

    Notes:
        1. Item names must match the trait names registered by ``make_param_traits()``.
        2. A dictionary passed through ``param`` may have sub-dictionaries.
           These will be converted into sub- ``Group`` s in the returned list of GUI items.
    """

    if isinstance(param, AMIParameter):
        if param.pusage not in ("In", "InOut"):
            return []
        if param.ptype == "Boolean":
            return [Item(pname, tooltip=param.pdescription)]
        return [Item(name=pname, label=pname.split("_")[-1], tooltip=param.pdescription)]

    # subparameter branch
    gui_items: list[Item | Group] = []
    group_desc = None
    for subparam_name in sorted(param.keys()):
        if subparam_name == "description":
            group_desc = param[subparam_name]
        else:
            gui_items.extend(make_gui_items(pname + "_" + trait_name_part(subparam_name), param[subparam_name]))
    if group_desc:
        gui_items = [Item(label=group_desc)] + gui_items
    return [VGroup(*gui_items, label=pname.split("_")[-1], show_border=True)]
