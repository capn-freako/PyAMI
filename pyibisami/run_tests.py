#! /usr/bin/env python

"""
Python tool for running several EmPy encoded tests on a IBIS-AMI model.

Original Author: David Banas
Original Date:   July 20, 2012

Copyright (c) 2012 David Banas; All rights reserved World wide.
"""

import em
import sys
import optparse
import os
import os.path as op
import shutil

from numpy import array, floor

import pyibisami.amimodel as ami

_plot_name_base = 'plot'
_plot_name_ext = 'png'
def plot_name(n=0):
    "Plot name generator keeps multiple tests from overwriting eachother's plots."
    while(True):
        n += 1
        yield _plot_name_base + '_' + str(n) + '.' + _plot_name_ext
plot_names = plot_name()

def hsv2rgb(hue=0, saturation=1.0, value=1.0):
    if(value < 0):
        value = 0.0
    elif(value > 1.0):
        value = 1.0
    if(saturation == 0):
        return(value, value, value)
    else:
        if(saturation < 0):
            saturation = 0
        elif(saturation > 1.0):
            saturation = 1.0
        hue = hue % 360
        H = float(hue)
        S = float(saturation)
        V = float(value)
        H_i =  floor (H / 60)
        f = ( H / 60 ) - H_i
        p = V * ( 1 - S )
        q = V * ( 1 - f * S )
        t = V * ( 1 - ( 1 - f ) * S )
        if(H_i == 0):
            R = V
            G = t
            B = p
        elif(H_i == 1):
            R = q
            G = V
            B = p
        elif(H_i == 2):
            R = p
            G = V
            B = t
        elif(H_i == 3):
            R = p
            G = q
            B = V
        elif(H_i == 4):
            R = t
            G = p
            B = V
        else:
            R = V
            G = p
            B = q
        return (R, G, B)

def color_picker(num_hues=3, first_hue=0):
    """
    Yields pairs of colors having the same hue, but different intensities.
    
    The first color is fully bright and saturated, and the second is
    half bright and half saturated. Originally, the intent was to have
    the second color used for the `reference` waveform in plots.
    """
    hue = first_hue
    while(True):
        yield (hsv2rgb(hue, 1.0, 1.0), hsv2rgb(hue, 0.75, 0.75))
        hue += 360 / num_hues

def main():
    """
    Run a series of tests on a AMI model DLL file.
    
    If no tests are specified on the command line, run all tests found
    in `test_dir'. (See `-t' option.)
    """

    __epilog__ = """
    Tests are written in the EmPy templating language, and produce XML
    output. (See the examples provided in the `tests' directory of the
    `pyibisami' Python package.)

    Test results should be viewed by loading the XML output file into
    a Web browser. By default, the XML output file refers to the supplied
    XSLT file, `test_results.xsl'. It is possible that you may need to
    copy this file from the pyibisami package directory to your local
    working directory, in order to avoid file loading errors in your
    Web browser.
    """

    __ver__ = 'run_tests.py v0.1 2012-07-21'
    __usage__ = 'usage: %prog [options] [test1 [test2 ...]]'

    # Configure and run the options parser.
    p = optparse.OptionParser(usage=__usage__, description=main.__doc__, epilog=__epilog__)
    p.add_option('--version', '-v', action='store_true',
                 help='Show program version info and exit.')
    p.add_option('--test_dir', '-t', default='tests',
                 help='Sets the name of the directory from which tests are taken. (Default: %default)')
    p.add_option('--model', '-m', default='libami.so',
                 help='Sets the AMI model DLL file name. (Default: %default)')
    p.add_option('--params', '-p', default='[("cfg_dflt", "default", [("default", ({"root_name":"testAMI"},{})),]),]',
                 help='List of lists of model configurations. Format: <filename> or [(name, [(label, ({AMI params., in "key:val" format},{Model params., in "key:val" format})), ...]), ...] (Default: %default)')
    p.add_option('--xml_file', '-x', default='test_results.xml',
                 help='Sets the name of the XML output file. You should load this file into your Web browser, after program completion. (Default: %default)')
    p.add_option('--ref_dir', '-r', default='refs',
                 help='Sets the name of the directory from which reference waveforms are taken. (Default: %default)')
    p.add_option('--out_dir', '-o', default='test_results',
                 help='Sets the name of the directory in which to place the results. (Default: %default)')
    options, arguments = p.parse_args()
    
    # Script identification.
    if(options.version):
        print __ver__
        return

    # Fetch options and cast into local independent variables.
    test_dir = str(options.test_dir)
    ref_dir = str(options.ref_dir)
    model = op.abspath(str(options.model))
    xml_filename = str(options.xml_file)
    out_dir = str(options.out_dir)
    xml_filename = op.join(out_dir, xml_filename)
    if not op.exists(out_dir):
        os.makedirs(out_dir)

    # Some browsers demand that the stylesheet be located in the same
    # folder as the *.XML file. Besides, this allows the model tester
    # to zip up her 'test_results' directory and send it off to
    # someone, whom may not have the PyIBIS-AMI package installed.
    shutil.copy(op.dirname(__file__) + '/test_results.xsl', out_dir)

    print "Testing model:", model
    print "Using tests in:", test_dir
    print "Sending XHTML output to:", xml_filename
    if(op.exists(options.params)):
        if(op.isfile(options.params)):
            cfg_dir = '.'
            cfg_files = [options.params,]
        else:
            cfg_dir = options.params
            cfg_files = filter(lambda s: s.endswith('.run'), \
                               filter(lambda f: op.isfile(cfg_dir + '/' + f), \
                                      os.listdir(cfg_dir)))
        params = []
        for cfg_filename in cfg_files:
            cfg_name = op.splitext(op.split(cfg_filename)[1])[0]
            param_list = []
            with open(cfg_dir + '/' + cfg_filename, 'rt') as cfg_file:
                description = cfg_file.readline()
                expr = ""
                for line in cfg_file:
                    toks = line.split()
                    if(not toks or toks[0].startswith('#')):
                        continue
                    expr += line
                    if(toks[-1] == '\\'): # Test for line continuation.
                        expr = expr.rstrip('\\\n')
                    else:
                        # param_list.append(eval(expr))
                        param_list.append(eval(compile(expr, cfg_filename, 'eval')))
                        expr = ""
            params.append((cfg_name, description, param_list))
    else:
        params = eval(options.params)

    # Run the tests.
    with open(xml_filename, 'wt') as xml_file:
        xml_file.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        xml_file.write('<?xml-stylesheet type="text/xsl" href="test_results.xsl"?>\n')
        xml_file.write('<tests>\n')
    if(arguments):
        tests = arguments
    else:
        tests = map(lambda x: x[0], map(op.splitext, \
                                        filter(lambda s: s.endswith('.em'), \
                                               filter(lambda f: op.isfile(test_dir + '/' + f), \
                                                      os.listdir(test_dir)))))
    test_dir = op.abspath(test_dir)
    ref_dir = op.abspath(ref_dir)
    for test in tests:
        print "Running test:", test, "..."
        theModel = ami.AMIModel(model)
        for cfg_item in params:
            cfg_name = cfg_item[0]
            print "\tRunning test configuration:", cfg_name, "..."
            description = cfg_item[1]
            param_list = cfg_item[2]
            colors = color_picker(num_hues=len(param_list))
            with open(xml_filename, 'at') as xml_file:
                interpreter = em.Interpreter(output = xml_file,
                                             globals = {'name'        : test + ' (' + cfg_name + ')',
                                                        'model'       : theModel,
                                                        'data'        : param_list,
                                                        'plot_names'  : plot_names,
                                                        'description' : description,
                                                        'plot_colors' : colors,
                                                        'ref_dir'     : ref_dir,
                                                       })
                try:
                    tmp_dir = os.getcwd()
                    os.chdir(out_dir)
                    interpreter.file(open(op.join(test_dir, test + '.em')))
                    os.chdir(tmp_dir)
                finally:
                    interpreter.shutdown()
        print "Test:", test, "complete."
    with open(xml_filename, 'at') as xml_file:
        xml_file.write('</tests>\n')

    print "Please, open file, `" + xml_filename + "' in a Web browser, in order to view the test results."

if __name__ == '__main__':
    main()

