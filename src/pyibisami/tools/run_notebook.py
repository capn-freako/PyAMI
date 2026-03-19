#! /usr/bin/env python

"""
Run an IBIS-AMI model through a Jupyter notebook, generating an HTML report.

Original Author: David Banas

Original Date:   January 31, 2025

Copyright (c) 2025 David Banas; all rights reserved World wide.
"""

import os
from pathlib    import Path
import subprocess
import sys
import shlex
from time       import time
from typing     import Any, Optional

import click

from ..ami.parser import AMIParamConfigurator, ParamName
from ..ibis.file  import IBISModel

NOTEBOOK = Path(__file__).parent.parent.joinpath("IBIS_AMI_Tester.ipynb")


def mk_dummy_run_file(ibis_file: Path, is_tx: bool, debug: bool) -> Path:
    """
    Create a parameter sweep specification template file for an IBIS-AMI model.

    Args:
        ibis_file: The ``*.ibs`` file defining the IBIS-AMI model of interest.
        is_tx: True for Tx model.
        debug: True for debugging mode.

    Returns:
        The path to the created parameter sweep specification template file.
    """

    # Import the `*.ibs` file.
    try:
        ibis = IBISModel(ibis_file, is_tx, debug=debug, gui=False)
        dName = ibis_file.parent
        assert ibis.ami_file, RuntimeError(
            "Missing AMI file definition in IBIS file!"
        )
        ami_file = dName / ibis.ami_file
    except Exception as err:
        raise RuntimeError(f"Failed to open/import IBIS file: {ibis_file}!") from err

    # Import the `*.ami` file.
    try:
        with open(ami_file, mode="r", encoding="utf-8") as pfile:
            pcfg = AMIParamConfigurator(pfile.read())
    except Exception as err:
        raise RuntimeError(f"Failed to open/import AMI file: {ami_file}!") from err
    if pcfg.ami_parsing_errors:
        print(f"Non-fatal parsing errors:\n{pcfg.ami_parsing_errors}")

    # Write parameter sweep specification template file.
    root_name = str(pcfg.input_ami_params[ParamName("root_name")])
    run_file_path = (Path("test_runs") / Path(root_name) / Path("defaults").with_suffix(".run")).resolve()
    run_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(run_file_path, mode="wt", encoding="utf-8") as run_file:
        run_file.write(f"Template for specifying `{root_name}` parameter sweeps.\n")
        run_file.write("\n('Defaults', \\\n")
        run_file.write(
            ", \\\n   ".join(
                [f"  ({{'root_name' : '{root_name}'"] +
                [f" '{ami_param_name}': {pcfg.input_ami_params[ami_param_name]}"
                    for ami_param_name in pcfg.input_ami_params
                    if ami_param_name != "root_name"
                ] +
                ["}, {} \\\n"]
                ))
        run_file.write("  ) \\\n")
        run_file.write(")\n")

    return run_file_path


def run_notebook(
    ibis_file: Path,
    notebook: Path,
    notebook_params: dict[str, Any],
    out_dir: Path
) -> None:
    """
    Run a Jupyter notebook on the target IBIS-AMI model.

    Args:
        ibis_file: The ``*.ibs`` file to test.
            (Presumably, an IBIS-AMI model.)
        notebook: The *Jupyter* notebook to use for testing the model.
        notebook_params: A dictionary of parameter overrides for the notebook.
        out_dir: The directory into which to place the resultant HTML file.
    """

    start_time = time()

    # Validate input.
    if not ibis_file.exists():
        raise RuntimeError(f"Can't find IBIS-AMI model file, {ibis_file}!")
    if not notebook.exists():
        raise RuntimeError(f"Can't find notebook file, {notebook}!")
    if not out_dir.exists():
        raise RuntimeError(f"Can't find output directory, {out_dir}!")
    if "params" not in notebook_params or notebook_params["params"] == "":
        dummy_run_file_name = mk_dummy_run_file(
            ibis_file, notebook_params["is_tx"], notebook_params["debug"])
        notebook_params["params"] = dummy_run_file_name
        print("\nNOTE: Since you provided no parameter sweep information,")
        print(f'a "dummy" sweep file has been created: {dummy_run_file_name}.')
        print("You may use this file as a template for creating parameter sweep specifications.")
        print("")

    # Define temp. (i.e. - parameterized) notebook and output file locations.
    tmp_dir = (
        os.environ.get("TMP") or os.environ.get("TEMP") or  # noqa: W504
        (Path(os.environ.get("HOME")).joinpath("tmp")  # type: ignore
            if os.environ.get("HOME")
            else "/tmp")
    )
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(exist_ok=True)
    tmp_notebook = tmp_dir.joinpath(notebook.stem + "_papermill").with_suffix(".ipynb")
    html_file = Path(out_dir.joinpath(ibis_file.name)).with_suffix(".html")

    # Run the notebook.
    print(f"Testing IBIS-AMI model: {ibis_file},")
    print(f"\tusing notebook: {notebook},")
    print(f"\twith parameter sweeps: {notebook_params['params']},")
    print(f"\tsending HTML output to: {html_file}...")

    try:
        # This unconventional syntax avoids the need for flattening a list of lists.
        extra_args = [tok for item in notebook_params.items()
                          for tok  in ['-p', f'{item[0]}', f'{item[1]}']]  # noqa: E127
        subprocess.run(['papermill', str(notebook), str(tmp_notebook)] + extra_args, check=True)
    except Exception:
        print(f"notebook: {notebook}")
        print(f"tmp_notebook: {tmp_notebook}")
        raise

    subprocess.run(
        ['jupyter', 'nbconvert', '--to', 'html', '--no-input', '--output', html_file, tmp_notebook],
        check=True)

    run_time = int(time() - start_time)  # integer seconds
    hours, rem_secs  = divmod(run_time, 3600)
    minutes, seconds = divmod(rem_secs, 60)
    print(f"Done after {hours} hrs., {minutes} min., {seconds} sec.")


@click.command(context_settings={"ignore_unknown_options": False,
                                 "help_option_names": ["-h", "--help"]})
@click.option(
    "--notebook", "-n", default=NOTEBOOK, type=click.Path(exists=True),
    help="Override the default notebook file name."
)
@click.option(
    "--out-dir", "-o", default=None, type=click.Path(),
    help="Override the name of the directory in which to place the results."
)
@click.option(
    "--params", "-p",
    default='',
    help='Directory (or, file) containing configuration sweeps.',
)
@click.option("--debug", is_flag=True, help="Provide extra debugging information.")
@click.option("--is_tx", is_flag=True, help="Flags a Tx model.")
@click.option("--nspui", default=32, show_default=True, help="Number of samples per unit interval.")
@click.option("--no-nspui-swp", is_flag=True, help="Skip samples per UI sweep.")
@click.option("--nbits", default=200, show_default=True, help="Number of bits to run in simulations.")
@click.option("--plot-t-max", default=0.5e-9, show_default=True, help="Maximum time value for plots (s).")
@click.option("--f-max",  default=40e9, show_default=True, help="Maximum frequency for transfer functions (Hz).")
@click.option("--f-step", default=10e6, show_default=True, help="Frequency step for transfer functions (Hz).")
@click.option("--fig-x", default=10, show_default=True, help="x-dimension for plot figures (in).")
@click.option("--fig-y", default=3, show_default=True, help="y-dimension for plot figures (in).")
@click.argument("ibis_file", type=click.Path(exists=True))
@click.argument("bit_rate", type=float)
@click.version_option(package_name="PyIBIS-AMI")
# pylint: disable=too-many-arguments,too-many-positional-arguments
def main(notebook, out_dir, params, ibis_file, bit_rate,  # pylint: disable=too-many-locals
         debug, is_tx, nspui, no_nspui_swp, nbits,
         plot_t_max, f_max, f_step, fig_x, fig_y):
    "Run a *Jupyter* notebook on an IBIS-AMI model file."
    arguments_list = sys.argv
    full_command_line = "run-notebook " + " ".join(shlex.quote(arg) for arg in arguments_list[1:])
    if out_dir:
        out_dir = Path(out_dir).resolve()
    else:
        out_dir = Path(ibis_file).resolve().parent
    out_dir.mkdir(exist_ok=True)
    run_notebook(
        Path(ibis_file).resolve(), Path(notebook).resolve(),
        out_dir=out_dir,
        notebook_params={
            'ibis_dir': ".",
            'ibis_file': ibis_file,
            'debug': debug,
            'is_tx': is_tx,
            'nspui': nspui,
            'no_nspui_swp': no_nspui_swp,
            'nbits': nbits,
            'plot_t_max': plot_t_max,
            'f_max': f_max,
            'f_step': f_step,
            'fig_x': fig_x,
            'fig_y': fig_y,
            'bit_rate': bit_rate,
            'params': params,
            'full_command_line': full_command_line,
        })


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
