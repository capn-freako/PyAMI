#! /usr/bin/env python

"""
Run an IBIS-AMI model through a Jupyter notebook, generating an HTML report.

Original Author: David Banas

Original Date:   January 31, 2025

Copyright (c) 2025 David Banas; all rights reserved World wide.
"""

import shutil
from os import chdir
from pathlib import Path
import subprocess
from typing import Any, Optional

import click
import em
import numpy as np
from papermill import execute_notebook

from pyibisami.ami.model import AMIModel

NOTEBOOK = Path(__file__).parent.parent.joinpath("IBIS_AMI_Checker.ipynb")


def run_notebook(
    ibis_file: Path,
    notebook: Path,
    out_dir: Optional[Path] = None,
    notebook_params: Optional[dict[str, Any]] = None,
):
    """
    Run the Jupyter notebook on the target IBIS-AMI model.

    Args:
        ibis_file: The ``*.ibs`` file to test.
            (Presumably, an IBIS-AMI model.)
        notebook: The *Jupyter* notebook to use for testing the model.

    Keyword Args:
        out_dir: The directory into which to place the resultant HTML file.
            Default: None (Use the directory containing the ``*.ibs`` file.)
        notebook_params: An optional dictionary of parameter overrides for the notebook.
            Default: None
    """

    # Fetch options and cast into local independent variables.
    assert ibis_file.exists(), RuntimeError(
        f"Can't find IBIS-AMI model file, {ibis_file}!")
    assert notebook.exists(), RuntimeError(
        f"Can't find notebook file, {notebook}!")
    tmp_notebook = notebook.with_stem(notebook.stem + "_papermill")
    out_dir = out_dir or ibis_file.resolve().parent
    out_dir.mkdir(exist_ok=True)
    html_file = Path(out_dir.joinpath(ibis_file.name)).with_suffix(".html")

    # Run the notebook.
    print(f"Testing IBIS-AMI model: {ibis_file},")
    print(f"using notebook: {notebook},")
    print(f"sending HTML output to: {html_file}...")
    execute_notebook(notebook, tmp_notebook, parameters=notebook_params)
    # subprocess.run([
    #     'jupyter', 'nbconvert', '--to', 'notebook', '--execute', '--inplace', notebook],
    #     check=True)
    subprocess.run(
        ['jupyter', 'nbconvert', '--to', 'html', '--no-input', '--output', html_file, tmp_notebook],
        check=True)
    print("Done.")


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
@click.option("--debug", is_flag=True, help="Provide extra debugging information.")
@click.option("--is_tx", is_flag=True, help="Flags a Tx model.")
@click.option("--nspui", default=32, show_default=True, help="Number of samples per unit interval.")
@click.option("--nbits", default=200, show_default=True, help="Number of bits to run in simulations.")
@click.option("--plot-t-max", default=0.5e-9, show_default=True, help="Maximum time value for plots (s).")
@click.option("--f-max",  default=40e9, show_default=True, help="Maximum frequency for transfer functions (Hz).")
@click.option("--f-step", default=10e6, show_default=True, help="Frequency step for transfer functions (Hz).")
@click.option("--fig-x", default=7, show_default=True, help="x-dimmension for plot figures (in).")
@click.option("--fig-y", default=2, show_default=True, help="y-dimmension for plot figures (in).")
@click.argument("ibis_file", type=click.Path(exists=True))
@click.argument("bit_rate", type=float)
@click.version_option(package_name="PyIBIS-AMI")
def main(notebook, out_dir, ibis_file, bit_rate, debug, is_tx, nspui, nbits, plot_t_max, f_max, f_step, fig_x, fig_y):
    "Run a *Jupyter* notebook on an IBIS-AMI model file."
    run_notebook(Path(ibis_file), Path(notebook), out_dir=out_dir,
        notebook_params={
            'ibis_file': ibis_file,
            'debug': debug,
            'is_tx': is_tx,
            'nspui': nspui,
            'nbits': nbits,
            'plot_t_max': plot_t_max,
            'f_max': f_max,
            'f_step': f_step,
            'fig_x': fig_x,
            'fig_y': fig_y,
            'bit_rate': bit_rate,
        })


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
