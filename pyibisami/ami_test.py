#! /usr/bin/env python

"""
Python tool for testing IBIS-AMI models in batch mode.

Original Author: David Banas
Original Date:   July 3, 2012

Copyright (c) 2012 David Banas; All rights reserved World wide.
"""

"""
ToDo:
- Add test for proper response to bogus init parameters.
- Add test for proper init params out format.

"""

import sys
import random
import optparse
from ctypes import *
import numpy as np

import amimodel as ami

# Making the model and its initialization data global.
_theModel = None
_theModelInitializer = None

def doCmd(cmd_str):
    """ Processes a single command line, typically, taken from a file
        containing several such lines.

        Available commands: (Commands may be abbreviated to uniqueness.)

        - load <filename>
            Loads a new AMI DLL from <filename>.

        - initialize
            Calls the `initialize' method of the model with the parameters
            created and/or adjusted by the `parameters' command.
            (See, below.)

        - getwave
            (Not yet implemented.)

        - parameters {['<ami_param>':<new_value>],...} {['<init_data>:<new_value>'],...}
            Creates or modifies the model initialization parameters.

            Note) Both bracketed expressions MUST be present (although, they may be empty),
                  and neither may contain spaces! Furthermore, if `<new_value>' is a
                  string, it MUST be quoted.
    """
    global _theModel, _theModelInitializer

    toks = cmd_str.split()
    cmd = toks[0]

    if(cmd.startswith('l')):
        _filename = toks[1]
        _theModel = ami.AMIModel(_filename)

    elif(cmd.startswith('i')):
        _theModel.initialize(_theModelInitializer)

    elif(cmd.startswith('g')):
        return

    elif(cmd.startswith('p')):
        _ami_params = eval(toks[1])
        _init_data = eval(toks[2])
        if(_theModelInitializer):
            _theModelInitializer.ami_params.update(_ami_params)
            for item in _init_data.items():
                _the_prop = item[0]
                _the_val = item[1]
                eval('_theModelInitializer.' + _the_prop + ' = ' + _the_val)
        else:
            _theModelInitializer = ami.AMIModelInitializer(_ami_params)
            for item in _init_data.items():
                _the_prop = item[0]
                _the_val = item[1]
                eval('_theModelInitializer.' + _the_prop + ' = ' + _the_val)

def main():
    """ami_test v0.4 - PyIBIS-AMI batch command processor
    """

    # Script identification.
    print main.__doc__

    # Configure and run the options parser.
    p = optparse.OptionParser()
#    p.add_option('--command_file', '-c', default=None)
    options, arguments = p.parse_args()
    
    # Fetch options and cast into local independent variables.
#    n               = int(options.command_file)

    # Open command file (or STDIN).
    if(not arguments):
        cmd_file = sys.stdin
        print "Reading commands from <STDIN>"
    else:
        cmd_file = open(arguments[0])
        print "Reading commands from ", arguments[0]

    # Read and process commands.
    i = 0
    try:
        for line in cmd_file:
            toks = line.split()
            if(not toks or toks[0].startswith('#')):
                continue
            print "[%4d]> "%i, line,
            i = i + 1
            doCmd(line)
    finally:
        if(arguments):
            cmd_file.close()

if __name__ == '__main__':
    main()

