#! /usr/bin/env python

"""
Python tool for testing IBIS-AMI models

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

def main():
    """ami_test v0.1
    """

    # Script identification.
    print main.__doc__

    # Configure and run the options parser.
    p = optparse.OptionParser()
    p.add_option('--sample_interval', '-s', default="25.0e-12")
    p.add_option('--bit_time', '-b', default="200.0e-12")
    p.add_option('--num_samples', '-n', default="128")
    p.add_option('--magnitude', '-m', default="0.1")
    p.add_option('--dll_file', '-f', default="libami.so")
    p.add_option('--ami_params', '-p', default=" \
        (testAMI \
            (Mode 1) \
            (Dcgain 0) \
            (BW 0) \
            (Process 0) \
        )")
    options, arguments = p.parse_args()
    
    # Fetch options and cast into local independent variables.
    n               = int(options.num_samples)
    sample_interval = float(options.sample_interval)
    bit_time        = float(options.bit_time)
    magnitude       = float(options.magnitude)
    dll_file        = str(options.dll_file)
    ami_params      = str(options.ami_params)

    # Calculate any local dependent variable values.
    stop_time = sample_interval * n
    num_bits  = int(stop_time / bit_time)

    # Initialize the model.
    print "Initializing AMI model..."
    Vector = c_double * n
    init_data = ami.AMIModelInitializer(
        channel_response=Vector(0.0, magnitude, 0.0, ),
        row_size=n,
        num_aggressors=0,
        ami_params_in=ami_params
    )
    theModel = ami.AMIModel(dll_file)
    theModel.initialize(init_data)
    print theModel._msg.value
    print theModel._ami_params_out.value

    # Call `GetWave'.
    print "Calling GetWave..."
    wave_in = [0.0, magnitude] + [0.0 for i in range(n - 2)]
    wave_out = theModel.getWave(wave_in)
    print theModel._msg.value
    print theModel._ami_params_out.value
    print wave_out

if __name__ == '__main__':
    main()

