#! /usr/bin/env python

"""
Python tool for running several EmPy encoded tests on a IBIS-AMI model.

Original Author: David Banas
Original Date:   July 20, 2012

Copyright (c) 2012 David Banas; All rights reserved World wide.
"""

import shutil
from os import chdir
from pathlib import Path

import click
import em
from numpy import floor

from pyibisami.ami.model import AMIModel

def plot_name(tst_name, n=0):
    """Plot name generator keeps multiple tests from overwriting each other's plots."""
    while True:
        n += 1
        yield f"{tst_name}_plot_{n}.png"

def hsv2rgb(hue=0, saturation=1.0, value=1.0):
    """Convert a HSV number to and RGB one."""
    if value < 0:
        value = 0.0
    elif value > 1.0:
        value = 1.0
    if saturation == 0:
        return (value, value, value)
    if saturation < 0:
        saturation = 0
    elif saturation > 1.0:
        saturation = 1.0
    hue = hue % 360
    H = float(hue)
    S = float(saturation)
    V = float(value)
    H_i = floor(H / 60.)
    f = (H / 60.) - H_i
    p = V * (1. - S)
    q = V * (1. - f * S)
    t = V * (1. - (1. - f) * S)
    if H_i == 0:
        R = V
        G = t
        B = p
    elif H_i == 1:
        R = q
        G = V
        B = p
    elif H_i == 2:
        R = p
        G = V
        B = t
    elif H_i == 3:
        R = p
        G = q
        B = V
    elif H_i == 4:
        R = t
        G = p
        B = V
    else:
        R = V
        G = p
        B = q
    # return (int(R), int(G), int(B))
    return (R, G, B)


def color_picker(num_hues=3, first_hue=0):
    """
    Yields pairs of colors having the same hue, but different intensities.

    The first color is fully bright and saturated, and the second is
    half bright and half saturated. Originally, the intent was to have
    the second color used for the `reference` waveform in plots.
    """
    hue = first_hue
    while True:
        yield (hsv2rgb(hue, 1.0, 1.0), hsv2rgb(hue, 0.75, 0.75))
        hue += 360 // num_hues


def expand_params(input_parameters):
    """Take the command line input and convert it into usable parameters.

    We can pass in a file, directory or raw string here. Handle all three cases.
    """
    if Path(input_parameters).exists():
        if Path(input_parameters).is_file():
            cfg_files = [Path(input_parameters)]
        else:
            cfg_files = list(Path(input_parameters).glob("*.run"))
        params = []
        for cfg_filename in cfg_files:
            cfg_name = cfg_filename.stem
            param_list = []
            with open(cfg_filename, "rt") as cfg_file:
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
                        param_list.append(eval(compile(expr, cfg_filename, "eval")))
                        expr = ""
            params.append((cfg_name, description, param_list))
    else:
        # params = eval(compile(input_parameters, "cmd_line", "eval"))
        params = eval(input_parameters)
    return params


def run_tests(**kwargs):
    """Provide a thin wrapper around the click interface so that we can test the operation."""

    # Fetch options and cast into local independent variables.
    test_dir = Path(kwargs["test_dir"]).resolve()
    ref_dir = Path(kwargs["ref_dir"])
    if not ref_dir.exists():
        ref_dir = None
    model = Path(kwargs["model"]).resolve()
    out_dir = Path(kwargs["out_dir"])
    out_dir.mkdir(exist_ok=True)
    xml_filename = out_dir.joinpath(kwargs["xml_file"])

    # Some browsers demand that the stylesheet be located in the same
    # folder as the *.XML file. Besides, this allows the model tester
    # to zip up her 'test_results' directory and send it off to
    # someone, whom may not have the PyIBIS-AMI package installed.
    shutil.copy(str(Path(__file__).parent.joinpath("test_results.xsl")), str(out_dir))

    print("Testing model: {}".format(model))
    print("Using tests in: {}".format(test_dir))
    params = expand_params(kwargs["params"])

    # Run the tests.
    print("Sending XHTML output to: {}".format(xml_filename))
    with open(xml_filename, "w") as xml_file:
        xml_file.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        xml_file.write('<?xml-stylesheet type="text/xsl" href="test_results.xsl"?>\n')
        xml_file.write("<tests>\n")
    if kwargs["tests"]:
        tests = kwargs["tests"]
    else:
        tests = list(test_dir.glob("*.em"))
    for test in tests:
        # print("Running test: {} ...".format(test.stem))
        print("Running test: {} ...".format(test))
        theModel   = AMIModel(model.__str__())
        plot_names = plot_name(xml_filename.stem)
        for cfg_item in params:
            cfg_name = cfg_item[0]
            print("\tRunning test configuration: {} ...".format(cfg_name))
            description = cfg_item[1]
            param_list = cfg_item[2]
            colors = color_picker(num_hues=len(param_list))
            with open(xml_filename, "a") as xml_file:
                interpreter = em.Interpreter(
                    output=xml_file,
                    globals={
                        "name": "{} ({})".format(test, cfg_name),
                        "model": theModel,
                        "data": param_list,
                        # "plot_names": plot_name(xml_filename.stem),
                        "plot_names": plot_names,
                        "description": description,
                        "plot_colors": colors,
                        "ref_dir": ref_dir,
                    },
                )
                try:
                    cwd = Path().cwd()
                    chdir(out_dir)  # So that the images are saved in the output directory.
                    interpreter.file(open(Path(test_dir, test)))
                    chdir(cwd)
                except:
                    print("Something went wrong.")
                finally:
                    interpreter.shutdown()
        print("Test:", test, "complete.")
    with open(xml_filename, "a") as xml_file:
        xml_file.write("</tests>\n")

    print("Please, open file, `{}` in a Web browser, in order to view the test results.".format(xml_filename))


@click.command(context_settings=dict(ignore_unknown_options=True, help_option_names=["-h", "--help"]))
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
@click.argument("tests", nargs=-1, type=click.UNPROCESSED)
@click.version_option()
def main(**kwargs):
    """
    Run a series of tests on a AMI model DLL file.

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
    """
    # print(kwargs)
    run_tests(**kwargs)

if __name__ == "__main__":
    main()
