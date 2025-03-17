#! /usr/bin/env python

"""IBIS-AMI model source code, AMI file, and IBIS file configuration utility.

Original author: David Banas

Original date:   February 26, 2016

Copyright (c) 2016 David Banas; all rights reserved World wide.

**Note:** The following use model has been deprecated!
The preferred approach is to make *executable* model configurators,
which draw what they need from this module.

This script gets called from a makefile, when any of the following need rebuilding:

* a C++ source code file
* a ``*.AMI`` file
* a ``*.IBS`` file
* a ``*.TST`` file (a dummy place-holder indicating that the test run config. files have been made)

All files will be rebuilt.
(We rebuild all files, because it doesn't take very long, and we can
ensure consistency this way.)

This gets triggered by one of two things:

#. The common model configuration information has changed, or
#. One of the EmPy template files was updated.

The idea here is that the ``*.IBS`` file, the ``*.AMI`` file, the C++ source file,
and the test run configuration files should be configured from a common model
configuration file, so as to ensure consistency between them all.
"""

import importlib.util
from datetime import date
from pathlib import Path
from typing import Any, NewType

import click
import em

ParamDict      = NewType("ParamDict",      dict[str, Any])
NamedParamDict = NewType("NamedParamDict", tuple[str, ParamDict])
TestDefinition = NewType("TestDefinition", tuple[str, NamedParamDict, NamedParamDict, str])

param_types = {
    "INT": {"c_type": "int", "ami_type": "Integer", "getter": "get_param_int"},
    "FLOAT": {"c_type": "double", "ami_type": "Float", "getter": "get_param_float"},
    "TAP": {"c_type": "double", "ami_type": "Tap", "getter": "get_param_float"},
    "BOOL": {"c_type": "bool", "ami_type": "Boolean", "getter": "get_param_bool"},
    "STRING": {"c_type": "char *", "ami_type": "String", "getter": "get_param_str"},
}


def print_param(indent, name, param):  # pylint: disable=too-many-branches
    """Print AMI parameter specification. Handle nested parameters, via
    recursion.

    Args:
        indent (str): String containing some number of spaces.
        name (str): Parameter name.
        param (dict): Dictionary containing parameter definition fields.
    """

    print(indent, f"({name}")
    if "subs" in param:
        for key in param["subs"]:
            print_param(indent + "    ", key, param["subs"][key])
        if "description" in param:
            print(indent + "    ", f"(Description {param['description']})")
    else:
        for fld_name, fld_key in [
            ("Usage", "usage"),
            ("Type", "type"),
            ("Format", "format"),
            ("Default", "default"),
            ("Description", "description"),
        ]:
            # Trap the special cases.
            if fld_name == "Type":
                print(indent, "    (Type", param_types[param["type"]]["ami_type"], ")")
            elif fld_name == "Default":
                if param["format"] == "Value":
                    pass
            elif fld_name == "Format":
                if param["format"] == "Value":
                    print(indent, "    (Value", param["default"], ")")
                elif param["format"] == "List":
                    print(indent, "    (List", end=" ")
                    for item in param["values"]:
                        print(item, end=" ")
                    print(")")
                    print(indent, "    (List_Tip", end=" ")
                    for item in param["labels"]:
                        print(item, end=" ")
                    print(")")
                else:
                    print(indent, f"    ({param['format']}", param["default"], param["min"], param["max"], ")")
            # Execute the default action.
            else:
                print(indent, f"    ({fld_name}", param[fld_key], ")")
    print(indent, ")")


def print_code(pname, param):
    """Print C++ code needed to query AMI parameter tree for a particular leaf.

    Args:
        pname (str): Parameter name.
        param (dict): Dictionary containing parameter definition fields.
    """

    print("       ", f'node_names.push_back("{pname}");')
    if "subs" in param:
        for key in param["subs"]:
            print_code(key, param["subs"][key])
    else:
        if param["usage"] == "In" or param["usage"] == "InOut":
            ptype = param["type"]
            print(f"        {param_types[ptype]['c_type']} {pname};")
            if ptype == "BOOL":
                print(f"        {pname} = {param_types[ptype]['getter']}(node_names, {param['default'].lower()});")
            else:
                print(f"        {pname} = {param_types[ptype]['getter']}(node_names, {param['default']});")
    print("       ", "node_names.pop_back();")


def mk_model(
    ibis_params: ParamDict,
    ami_params: ParamDict,
    model_name: str,
    description: str,
    out_dir: str = "."
) -> None:
    """
    Generate ibis, ami, and cpp files, by merging the
    device specific parameterization with the templates.

    Args:
        ibis_params: Dictionary of IBIS model parameter definitions.
        ami_params: Dictionary of AMI parameter definitions.
        model_name: Name given to IBIS model.
        description: Model description.

    Keyword Args:
        out_dir: Directory in which to place created files.
            Default: "."
    """

    py_file = (Path(out_dir).resolve() / model_name).with_suffix(".py")
    # Configure the model files.
    for ext in ["cpp", "ami", "ibs"]:
        out_file = py_file.with_suffix(f".{ext}")
        if ext == "ami":
            em_file = Path(__file__).parent.joinpath("generic.ami.em")
        elif ext == "ibs":
            em_file = Path(__file__).parent.joinpath("generic.ibs.em")
        else:
            em_file = out_file.with_suffix(".cpp.em")

        print(f"Building '{out_file}' from '{em_file}'...")
        with open(out_file, "w", encoding="utf-8") as o_file:
            interpreter = em.Interpreter(
                output=o_file,
                globals={
                    "ami_params": ami_params,
                    "ibis_params": ibis_params,
                    "param_types": param_types,
                    "model_name": model_name,
                    "description": description,
                    "date": str(date.today()),
                },
            )
            try:
                with open(em_file, "rt", encoding="utf-8") as in_file:
                    interpreter.file(in_file)
            finally:
                interpreter.shutdown()


def ami_config(py_file):
    """
    Read in ``py_file`` and cpp.em files, then generate: ibis, ami, and cpp files.

    Args:
        py_file: name of model configuration file (<stem>.py)

    Notes:
        1. This function is deprecated! Instead, make your model configurator executable
        and import what you need from this module. This is much cleaner.
    """

    file_base_name = Path(py_file).stem

    # Read model configuration information.
    print(f"Reading model configuration information from file: {py_file}.")
    spec = importlib.util.spec_from_file_location(file_base_name, py_file)
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)

    mk_model(cfg.ibis_params, cfg.ami_params, cfg.kFileBaseName, cfg.kDescription, out_dir=Path(py_file).parent)


def mk_combs(dict_items: list[tuple[str, Any]]) -> list[list[tuple[str, Any]]]:
    """
    Make all combinations possible from a list of dictionary items.

    Args:
        dict_items: List of dictionary key/value pairs.
            The values are lists.

    Return:
        List of all possible combinations of key values.
    """
    if not dict_items:
        return [
            [],
        ]
    head, *tail = dict_items
    k, vs = head
    kvals = [(k, v) for v in vs]
    return [[kval] + rest for kval in kvals for rest in mk_combs(tail)]


def mk_tests(  # pylint: disable=too-many-locals
    test_defs: dict[str, TestDefinition],
    file_base_name: str,
    test_dir: str = "test_runs"
) -> None:
    """
    Make the test run configuration files.

    Args:
        test_defs: Dictionary of test sweep definitions.
        file_base_name: Stem name for test run definition files.

    Keyword Args:
        test_dir: Directory in which to place the created test run definition files.
            Default: "test_runs/"
    """

    pname = Path(test_dir).resolve()
    pname.mkdir(exist_ok=True)
    pname = (pname / file_base_name).resolve()
    pname.mkdir(exist_ok=True)
    for fname in test_defs.keys():
        desc, ami_defs, sim_defs, ref_fstr = test_defs[fname]
        ami_str, ami_dict = ami_defs
        sim_str, sim_dict = sim_defs
        with open((pname / fname).with_suffix(".run"), "w", encoding="utf-8") as f:
            f.write(desc + "\n")
            for ami_comb in mk_combs(list(ami_dict.items())):
                for sim_comb in mk_combs(list(sim_dict.items())):
                    pdict = dict(ami_comb)
                    pdict.update(dict(sim_comb))
                    f.write(f"\n('{ami_str.format(pdict=pdict)}_{sim_str.format(pdict=pdict)}', \\\n")
                    f.write(f"  ({{'root_name': '{file_base_name}', \\\n")
                    for k, v in ami_comb:
                        f.write(f"    '{k}': {v}, \\\n")
                    f.write("   }, \\\n")
                    if sim_comb:
                        head, *tail = sim_comb
                        k, v = head
                        f.write(f"   {{'{k}': {v}, \\\n")
                        for k, v in tail:
                            f.write(f"    '{k}': {v}, \\\n")
                        f.write("   } \\\n")
                    f.write("  ), \\\n")
                    if ref_fstr:
                        f.write(f"  '{ref_fstr.format(pdict=pdict)}', \\\n")
                    f.write(")\n")


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("py_file", type=click.Path(exists=True, resolve_path=True))
@click.version_option()
def main(py_file):
    """
    Configure IBIS-AMI model C++ source code, IBIS model, and AMI file.
    This command generates three files based off the input config file.
    It expects a .cpp.em file to be located in the same directory so that it can
    generate a cpp file from the config file and template file.

    Args:
       py_file: name of model configuration file (*.py)

    Notes:
        1. This command is deprecated! Instead, make your model configurator executable
        and import what you need from this module. This is much cleaner.
    """
    ami_config(py_file)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
