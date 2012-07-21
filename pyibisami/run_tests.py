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

import amimodel as ami

def main():
    """run_tests.py v0.1
    """

    # Script identification.
    print main.__doc__

    # Configure and run the options parser.
    p = optparse.OptionParser()
    p.add_option('--test_dir', '-t', default='tests')
    p.add_option('--model', '-m', default='libami.so')
    p.add_option('--params', '-p', default='{"root_name":"Stratix4_Tx"}')
#    p.add_option('--out_dir', '-o', default='test_results')
    p.add_option('--xml_file', '-x', default='test_results.xml')
    options, arguments = p.parse_args()
    
    # Fetch options and cast into local independent variables.
    test_dir = str(options.test_dir)
    model = str(options.model)
    params = eval(options.params)
#    out_dir = str(options.out_dir)
    xml_filename = str(options.xml_file)

    # Run the tests.
    with open(xml_filename, 'wt') as xml_file:
        xml_file.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        xml_file.write('<?xml-stylesheet type="text/xsl" href="test_results.xsl"?>\n')
    if(arguments):
        for test in arguments:
            print "Running test:", test
            theModel = ami.AMIModel(model)
            theModelInitializer = ami.AMIModelInitializer(params)
#            filename = os.path.normcase(out_dir + '/' + test + '.xml')
            with open(xml_filename, 'at') as xml_file:
                interpreter = em.Interpreter(output = xml_file, globals = {'name' : test, 'model' : theModel, 'data' : theModelInitializer})
                try:
                    interpreter.file(open(test_dir + '/' + test + '.em'))
                finally:
                    interpreter.shutdown()
    else:
        return

if __name__ == '__main__':
    main()

