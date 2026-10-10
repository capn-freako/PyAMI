#! /usr/bin/env python

"""Python tool for running several EmPy encoded tests on a IBIS-AMI model.

Original Author: David Banas
Original Date:   July 20, 2012

Copyright (c) 2012 David Banas; All rights reserved World wide.
"""

import logging
import shutil
from os import chdir
from pathlib import Path
from typing import Optional

import click
import em

from pyibisami.ami.model    import AMIModel
from pyibisami.cli_logging  import setup_cli_logging
from pyibisami.common       import TestSweep
from pyibisami.report.plot  import plot_name, color_picker

logger = logging.getLogger(__name__)


def expand_params(input_parameters: str) -> list[TestSweep]:
    """
    Take the command line input and convert it into usable parameter sweeps.

    We can pass in a file, directory, or raw string here.
    Handle all three cases.
    """
    if Path(input_parameters).exists():
        if Path(input_parameters).is_file():
            cfg_files = [Path(input_parameters)]
        else:
            cfg_files = list(Path(input_parameters).glob("*.run"))
        param_sweeps = []
        for cfg_filename in cfg_files:
            cfg_name = cfg_filename.stem
            param_list = []
            with open(cfg_filename, "rt", encoding="utf-8") as cfg_file:
                description = cfg_file.readline()
                expr = ""
                for line in cfg_file:
                    toks = line.split()
                    if not toks or toks[0].startswith("#"):
                        continue
                    expr += line
                    if toks[-1] == "\\":  # Test for line continuation.
                        expr = expr.rstrip("\\\n")
                    else:
                        param_list.append(eval(compile(expr, cfg_filename, "eval")))  # pylint: disable=eval-used
                        expr = ""
            param_sweeps.append((cfg_name, description, param_list))
    else:
        try:
            param_sweeps = eval(input_parameters)  # pylint: disable=eval-used
        except Exception as err:
            raise ValueError(f"input_parameters: {input_parameters}") from err
    return param_sweeps


def run_tests(**kwargs) -> Path:  # pylint: disable=too-many-locals
    """Provide a thin wrapper around the click interface so that we can test
    the operation.

    Returns:
        The XML test results file.
    """

    # Fetch options and cast into local independent variables.
    test_dir = Path(kwargs["test_dir"]).resolve()
    ref_path = Path(kwargs["ref_dir"]).resolve()
    ref_dir: Optional[Path] = ref_path if ref_path.exists() else None
    model = Path(kwargs["model"]).resolve()
    out_dir = Path(kwargs["out_dir"]).resolve()
    out_dir.mkdir(exist_ok=True)
    xml_filename = out_dir.joinpath(kwargs["xml_file"])

    # Some browsers demand that the stylesheet be located in the same
    # folder as the *.XML file. Besides, this allows the model tester
    # to zip up her 'test_results' directory and send it off to
    # someone, whom may not have the PyIBIS-AMI package installed.
    #
    # Note: To avoid this issue entirely, incorporate `xsltproc` into your build flow.
    shutil.copy(str(Path(__file__).parent.joinpath("test_results.xsl")), str(out_dir))

    logger.info("Testing model: %s", model)
    logger.info("Using tests in: %s", test_dir)
    params = expand_params(kwargs["params"])

    # Run the tests.
    logger.info("Sending XHTML output to: %s", xml_filename)
    with open(xml_filename, "w", encoding="utf-8") as xml_file:
        xml_file.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        xml_file.write('<?xml-stylesheet type="text/xsl" href="test_results.xsl"?>\n')
        xml_file.write("<tests>\n")
    if kwargs["tests"]:
        tests = kwargs["tests"]
    else:
        tests = list(test_dir.glob("*.em"))
    for test in tests:
        test_ = test.stem
        logger.info("Running test: %s ...", test_)
        theModel = AMIModel(str(model))
        plot_names = plot_name(test_)
        for cfg_item in params:
            cfg_name = cfg_item[0]
            logger.info("Running test configuration: %s ...", cfg_name)
            description = cfg_item[1]
            param_list = cfg_item[2]
            colors = color_picker(num_hues=len(param_list))
            with open(xml_filename, "a", encoding="utf-8") as xml_file:
                interpreter = em.Interpreter(
                    output=xml_file,
                    globals={
                        "name": f"{test_} ({cfg_name})",
                        "model": theModel,
                        "data": param_list,
                        "plot_names": plot_names,
                        "description": description,
                        "plot_colors": colors,
                        "ref_dir": ref_dir,
                    },
                )
                cwd = Path().cwd()
                try:
                    chdir(out_dir)  # So that the images are saved in the output directory.
                    with open(Path(test_dir, test), encoding="utf-8") as test_file:
                        interpreter.file(test_file)
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Test `%s` failed for configuration `%s`.", test_, cfg_name)
                finally:
                    chdir(cwd)
                    interpreter.shutdown()
        logger.info("Test: %s complete.", test_)
    with open(xml_filename, "a", encoding="utf-8") as xml_file:
        xml_file.write("</tests>\n")

    return xml_filename


@click.command(context_settings={"ignore_unknown_options": True, "help_option_names": ["-h", "--help"]})
@click.option(
    "--model", "-m", default="libami.so", type=click.Path(exists=True), help="Sets the AMI model DLL file name."
)
@click.option(
    "--test_dir",
    "-t",
    default="tests",
    type=click.Path(),
    help="Sets the name of the directory from which tests are taken.",
)
@click.option(
    "--params",
    "-p",
    default='[("cfg_dflt", "default", [("default", ({"root_name":"testAMI"},{})),]),]',
    help='List of lists of model configurations. Format: <filename> or [(name, [(label, ({AMI params., in "key:val" format},{Model params., in "key:val" format})), ...]), ...]',
)
@click.option(
    "--xml_file",
    "-x",
    default="test_results.xml",
    help="Sets the name of the XML output file. You should load this file into your Web browser after the program completion.",
)
@click.option(
    "--ref_dir",
    "-r",
    default="refs",
    type=click.Path(),
    help="Sets the name of the directory from which reference waveforms are taken.",
)
@click.option(
    "--out_dir",
    "-o",
    default="test_results",
    type=click.Path(),
    help="Sets the name of the directory in which to place the results.",
)
@click.option("--debug", "-d", is_flag=True, help="Provide extra debugging information.")
@click.argument("tests", nargs=-1, type=click.UNPROCESSED)
@click.version_option()
def main(debug, **kwargs):
    """Run a series of tests on a AMI model DLL file.

    If no tests are specified on the command line, run all tests found
    in `test_dir'. (See `-t' option.)

    usage: %prog [options] [test1 [test2 ...]]

    Tests are written in the EmPy templating language, and produce XML
    output. (See the examples provided in the `examples' directory of the
    `pyibisami' Python package.)

    Test results should be viewed by loading the XML output file into
    a Web browser. By default, the XML output file refers to the supplied
    XSLT file, `test_results.xsl'. It is possible that you may need to
    copy this file from the pyibisami package directory to your local
    working directory, in order to avoid file loading errors in your
    Web browser.

    If your browser's security settings disallow the use of an XSLT style
    sheet when processing XML then use the `xsltproc` utility to convert
    the XML/XSLT to HTML before viewing in your browser.
    """
    setup_cli_logging(debug)
    xml_filename = run_tests(**kwargs)
    click.echo(f"Test results: {xml_filename}\nOpen this file in a Web browser, to view them.")


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
