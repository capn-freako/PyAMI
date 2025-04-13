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
from time       import time
from typing     import Any, Optional

import click

NOTEBOOK = Path(__file__).parent.parent.joinpath("IBIS_AMI_Tester.ipynb")


def run_notebook(
    ibis_file: Path,
    notebook: Path,
    out_dir: Optional[Path] = None,
    notebook_params: Optional[dict[str, Any]] = None,
) -> None:
    """
    Run a Jupyter notebook on the target IBIS-AMI model.

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

    start_time = time()

    # Validate input.
    if not ibis_file.exists():
        raise RuntimeError(f"Can't find IBIS-AMI model file, {ibis_file}!")
    if not notebook.exists():
        raise RuntimeError(f"Can't find notebook file, {notebook}!")

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
    out_dir = out_dir or ibis_file.resolve().parent
    out_dir.mkdir(exist_ok=True)
    html_file = Path(out_dir.joinpath(ibis_file.name)).with_suffix(".html")

    # Run the notebook.
    print(f"Testing IBIS-AMI model: {ibis_file},")
    print(f"using notebook: {notebook},")
    print(f"sending HTML output to: {html_file}...")

    try:
        extra_args = []
        if notebook_params:
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
@click.option("--nbits", default=200, show_default=True, help="Number of bits to run in simulations.")
@click.option("--plot-t-max", default=0.5e-9, show_default=True, help="Maximum time value for plots (s).")
@click.option("--f-max",  default=40e9, show_default=True, help="Maximum frequency for transfer functions (Hz).")
@click.option("--f-step", default=10e6, show_default=True, help="Frequency step for transfer functions (Hz).")
@click.option("--fig-x", default=10, show_default=True, help="x-dimmension for plot figures (in).")
@click.option("--fig-y", default=3, show_default=True, help="y-dimmension for plot figures (in).")
@click.argument("ibis_file", type=click.Path(exists=True))
@click.argument("bit_rate", type=float)
@click.version_option(package_name="PyIBIS-AMI")
# pylint: disable=too-many-arguments,too-many-positional-arguments
def main(notebook, out_dir, params, ibis_file, bit_rate, debug, is_tx, nspui, nbits,
         plot_t_max, f_max, f_step, fig_x, fig_y):
    "Run a *Jupyter* notebook on an IBIS-AMI model file."
    run_notebook(
        Path(ibis_file).resolve(), Path(notebook).resolve(),
        out_dir=out_dir,
        notebook_params={
            'ibis_dir': ".",
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
            'params': params,
        })


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
