#! /usr/bin/env python

"""IBIS-AMI model source code, AMI file, and IBIS file configuration utility.

Original author: David Banas

Original date:   February 26, 2016

Copyright (c) 2016 David Banas; all rights reserved World wide.

This script gets called from a makefile, when any of the following need rebuilding:

* a C++ source code file
* a ``*.AMI`` file
* a ``*.IBS`` file
* a ``*.TST`` file (a dummy place-holder indicating that the test run config. files have been made)

All files will be rebuilt.
(We rebuild all files, because it doesn't take very long, and we can
insure consistency this way.)

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

import click
import em

param_types = {
    "INT": {"c_type": "int", "ami_type": "Integer", "getter": "get_param_int"},
    "FLOAT": {"c_type": "float", "ami_type": "Float", "getter": "get_param_float"},
    "TAP": {"c_type": "float", "ami_type": "Tap", "getter": "get_param_float"},
    "BOOL": {"c_type": "bool", "ami_type": "Boolean", "getter": "get_param_bool"},
    "STRING": {"c_type": "char *", "ami_type": "String", "getter": "get_param_str"},
}


def print_param(indent, name, param):
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


def ami_config(py_file, test_dir="test_runs"):
    """
    Read in the ``py_file`` and cpp.em file then generate a ibis, ami,
    cpp, and test run configuration files.
    """

    file_base_name = Path(py_file).stem

    # Read model configuration information.
    print(f"Reading model configuration information from file: {py_file}.")
    spec = importlib.util.spec_from_file_location(file_base_name, py_file)
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)

    # Configure the model files.
    for ext in ["cpp", "ami", "ibs"]:
        out_file = Path(py_file).with_suffix(f".{ext}")
        if ext == "ami":
            em_file = Path(__file__).parent.joinpath("generic.ami.em")
        elif ext == "ibs":
            em_file = Path(__file__).parent.joinpath("generic.ibs.em")
        else:
            em_file = out_file.with_suffix(".cpp.em")

        print(f"Building '{out_file}' from '{em_file}'...")
        with open(out_file, "w", encoding="utf-8") as out_file:
            interpreter = em.Interpreter(
                output=out_file,
                globals={
                    "ami_params": cfg.ami_params,
                    "ibis_params": cfg.ibis_params,
                    "param_types": param_types,
                    "model_name": cfg.kFileBaseName,
                    "description": cfg.kDescription,
                    "date": str(date.today()),
                },
            )
            try:
                interpreter.file(open(em_file))
            finally:
                interpreter.shutdown()

    # Generate the test run files.
    def mk_combs(dict_items):
        """Make all combinations possible from a list of dictionary items.

        Args:
            dict_items([(str, [T])]): List of dictionary key/value pairs.
                The values are lists.

        Return:
            [[(str, T)]]: List of all possible combinations of key values.
        """
        if not dict_items:
            return [[],]
        head, *tail = dict_items
        k, vs = head
        kvals = [(k,v) for v in vs]
        return [ [kval] + l
                 for kval in kvals
                 for l in mk_combs(tail)
               ]

    pname = Path(test_dir).resolve()
    pname.mkdir(exist_ok=True)
    pname = (pname / file_base_name).resolve()
    pname.mkdir(exist_ok=True)
    for fname in cfg.test_defs.keys():
        desc, ami_defs, sim_defs, ref_fstr = cfg.test_defs[fname]
        ami_str, ami_dict = ami_defs
        sim_str, sim_dict = sim_defs
        with open((pname / fname).with_suffix(".run"), "w", encoding="utf-8") as f:
            f.write(desc + "\n")
            for ami_comb in mk_combs(ami_dict.items()):
                for sim_comb in mk_combs(sim_dict.items()):
                    try:
                        pdict = dict(ami_comb)
                        pdict.update(dict(sim_comb))
                        f.write(f"\n('{ami_str.format(pdict=pdict)}_{sim_str.format(pdict=pdict)}', \\\n")
                    except:
                        print(f"ami_str: {ami_str}")
                        print(f"sim_str: {sim_str}")
                        print(f"pdict: {pdict}")
                        raise
                    f.write(f"  ({{'root_name': '{file_base_name}', \\\n")
                    for (k,v) in ami_comb:
                        f.write(f"    '{k}': {v}, \\\n")
                    f.write("   }, \\\n")
                    if sim_comb:
                        head, *tail = sim_comb
                        k, v = head
                        f.write(f"   {{'{k}': {v}, \\\n")
                        for (k,v) in tail:
                            f.write(f"    '{k}': {v}, \\\n")
                        f.write("   } \\\n")
                    f.write("  ), \\\n")
                    if ref_fstr:
                        f.write(f"  '{ref_fstr.format(pdict=pdict)}', \\\n")
                    f.write(")\n")


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.argument("py_file", type=click.Path(exists=True, resolve_path=True))
@click.option("-d", "--test_dir", show_default=True, default="test_runs", help="Output directory for test run generation.")
@click.version_option()
def main(py_file, **kwd_args):
    """Configure IBIS-AMI model C++ source code, IBIS model, and AMI file.

    This command generates three files based off the input config file.
    It expects a .cpp.em file to be located in the same directory so that it can
    generate a cpp file from the config file and template file.

       py_file: name of model configuration file (*.py)
    """
    ami_config(py_file)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
