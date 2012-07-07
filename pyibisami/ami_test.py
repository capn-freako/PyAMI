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

import amimodel

kUseHaskellModel = False

# Constant definitions.
if(kUseHaskellModel):
    kAmiFileName = "libami.so"
    kAmiInitParams = """
        (testAMI
            (Mode 1)
            (Dcgain 0)
            (BW 0)
            (Process 0)
        )
    """
else:
    kAmiFileName = "arria5_rx.linux.so"
    kAmiInitParams = """
        (Arria_V_Rx
            (Mode 1)
            (Dcgain 0)
            (BW 0)
            (Process 0)
        )
    """

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
    options, arguments = p.parse_args()
    
    # Fetch options and cast into local independent variables.
    n               = int(options.num_samples)
    sample_interval = float(options.sample_interval)
    bit_time        = float(options.bit_time)
    magnitude       = float(options.magnitude)

    # Calculate any local dependent variable values.
    stop_time = sample_interval * n
    num_bits  = int(stop_time / bit_time)

    # Initialize the model.
    print "Initializing AMI model..."
    Vector = c_double * n
    init_data = AMIModelInitializer(
        channel_response=Vector(0.0, magnitude, 0.0, ),
        row_size=n,
        num_aggressors=0,
        ami_params_in=kAmiInitParams
    )
    theModel = AMIModel(kAmiFileName)
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

