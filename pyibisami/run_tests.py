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
import os.path

from numpy import array

import amimodel as ami

_plot_name_base = 'plot'
_plot_name_ext = 'png'
def plot_name(n=0):
    "Plot name generator keeps multiple tests from overwriting eachother's plots."
    while(True):
        n += 1
        yield _plot_name_base + '_' + str(n) + '.' + _plot_name_ext
plot_names = plot_name()

def loadWave(filename):
    """ Load a waveform file consisting of any number of lines, where each
        line contains, first, a time value and, second, a voltage value.
        Assume the first line is a header, and discard it.

        Specifically, this function may be used to load in waveform files
        saved from CosmosScope.

        Inputs:
        - filename: Name of waveform file to read in.

        Outputs:
        - t: vector of time values
        - v: vector of voltage values
    """
    with open(filename, mode='rU') as theFile:
        theFile.readline()              # Consume the header line.
        t = []
        v = []
        for line in theFile:
            tmp = map (float, line.split())
            t.append (tmp[0])
            v.append (tmp[1])
        return(t, v)

def getImpulse(filename, sample_per):
    """ Read in an impulse response from a file, and convert it to the
        given sample rate, using linear interpolation.

        Inputs:
        - filename:   Name of waveform file to read in.
        - sample_per: New sample interval

        Outputs:
        - res: resampled impulse response
    """
    impulse = loadWave(filename)
    ts = impulse[0]
    vs = impulse[1]
    tmax = ts[-1]
    # Build new impulse response, at new sampling period, using linear interpolation.
    res = []
    t = 0.0
    i = 0
    while(t < tmax):
        while(ts[i] <= t):
            i = i + 1
        res.append(vs[i - 1] + (vs[i] - vs[i - 1]) * (t - ts[i - 1]) / (ts[i] - ts[i - 1]))
        t = t + sample_per
    res = array(res)
    # Return normalized impulse response.
    return res / sum(res)

def main():
    """
    Run a series of tests on a AMI model DLL file. If no tests are
    specified on the command line, run all tests found in `test_dir'.
    (See `-t' option.)
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
    options, arguments = p.parse_args()
    
    # Script identification.
    if(options.version):
        print __ver__
        return

    # Fetch options and cast into local independent variables.
    test_dir = str(options.test_dir)
    model = str(options.model)
    xml_filename = str(options.xml_file)
    print "Testing model:", model
    print "Using tests in:", test_dir
    print "Sending XHTML output to:", xml_filename
    if(os.path.exists(options.params)):
        if(os.path.isfile(options.params)):
            cfg_dir = '.'
            cfg_files = [options.params,]
        else:
            cfg_dir = options.params
            cfg_files = filter(lambda s: s.endswith('.run'), \
                               filter(lambda f: os.path.isfile(cfg_dir + '/' + f), \
                                      os.listdir(cfg_dir)))
        params = []
        for cfg_filename in cfg_files:
            cfg_name = os.path.splitext(cfg_filename)[0]
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
                        new_item = eval(expr)
                        if('channel_response' in new_item[1][1]
                           and os.path.isfile(new_item[1][1]['channel_response'])):
                            if('sample_interval' in new_item[1][1]):
                                sample_interval = new_item[1][1]['sample_interval']
                            else:
#                                sample_interval = ami.AMIModelInitializer.sample_interval # the default value
                                sample_interval = 25.0e-12
                            new_item[1][1]['channel_response'] = getImpulse(new_item[1][1]['channel_response'], sample_interval)
                            new_item[1][1]['row_size'] = len(new_item[1][1]['channel_response'])
                        param_list.append(new_item)
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
        tests = map(lambda x: x[0], map(os.path.splitext, \
                                        filter(lambda s: s.endswith('.em'), \
                                               filter(lambda f: os.path.isfile(test_dir + '/' + f), \
                                                      os.listdir(test_dir)))))
    for test in tests:
        print "Running test:", test
        theModel = ami.AMIModel(model)
        for cfg_item in params:
            cfg_name = cfg_item[0]
            description = cfg_item[1]
            param_list = cfg_item[2]
            with open(xml_filename, 'at') as xml_file:
                interpreter = em.Interpreter(output = xml_file,
                                             globals = {'name'        : test + ' (' + cfg_name + ')',
                                                        'model'       : theModel,
                                                        'data'        : param_list,
                                                        'plot_names'  : plot_names,
                                                        'description' : description,
                                                       })
                try:
                    interpreter.file(open(test_dir + '/' + test + '.em'))
                finally:
                    interpreter.shutdown()
    with open(xml_filename, 'at') as xml_file:
        xml_file.write('</tests>\n')

    print "Please, open file, `" + xml_filename + "' in a Web browser, in order to view the test results."

if __name__ == '__main__':
    main()

