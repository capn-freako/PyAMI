"""
Class definitions for working with IBIS-AMI models

Original Author: David Banas
Original Date:   July 3, 2012

Copyright (c) 2012 David Banas; All rights reserved World wide.
"""

from ctypes import *
import numpy as np
import copy as cp

class AMIModelInitializer(object):
    """ Class containing the initialization data for an instance of `AMIModel'.

        Created primarily to facilitate use of the PyAMI package at the
        pylab command prompt, this class can be used by the pylab user,
        in order to store all the data required to initialize an instance
        of class `AMIModel'. In this way, the pylab user may assemble
        the AMIModel initialization data just once, and modify it
        incrementally, as she experiments with different initialization
        settings. In this way, she can avoid having to type a lot of
        redundant constants every time she invokes the AMIModel constructor.
    """

    _initValues = {
        'channel_response' : (c_double * 128)(0.0, 1.0, 0.0),
        'row_size'         : 128,
        'num_aggressors'   : 0,
        'sample_interval'  : c_double(25.0e-12),
        'bit_time'         : c_double(0.1e-9),
        'ami_params_in'    : ""
    }

    def __init__(self, **optional_args):
        """ Constructor accepts a dictionary of optional initialization
            data overrides and validates them, before using them to
            update the local initialization data structure.

            Valid dictionary keys:

            - channel_response
                a matrix of `c_double's where the first row represents the
                impulse response of the analog channel, and the rest represent
                the impulse responses of several aggressor-to-victim far end
                crosstalk (FEXT) channels.

                Default) a single 128 element vector containing an ideal impulse

            - row_size
                integer giving the size of the rows in `channel_response'.

                Default) 128

            - num_aggressors
                integer giving the number or rows in `channel_response', minus
                one.

                Default) 0

            - sample_interval
                c_double giving the time interval, in seconds, between
                successive elements in any row of `channel_response'.

                Default) 25e-12 (40 GHz sampling rate)

            - bit_time
                c_double giving the bit period (i.e. - unit interval) of the
                link, in seconds.

                Default) 100e-12 (10 Gbits/s)

            - ami_params_in
                string containing the AMI input parameters

                Default) empty string
        """
        for item in optional_args.items():
            theKey = item[0]
            if(not theKey in self._initValues):
                del optional_args[theKey]
        self._initValues.update(optional_args)

class AMIModel(object):
    """ Class defining the structure and behavior of a AMI Model.
        
        Public Methods:
          initialize()
          getWave()
        
        Additional Features:

          - Makes the calling of AMI_Close() automagic, by calling it
            from the destructor.
    """

    def __init__(self, filename):
        " Load the dll and bind the 3 AMI functions."

        my_dll = CDLL(filename)
        self._amiInit = my_dll.AMI_Init
        self._amiGetWave = my_dll.AMI_GetWave
        self._amiClose = my_dll.AMI_Close
        self._ami_mem_handle = None

    def __del__(self):
        """ Destructor - Calls AMI_Close with handle to AMI model memory.
        
            This obviates the need for the user to call the AMI_Close
            function explicitly, and guards against memory leaks, during
            PyLab command prompt operation, by ensuring that AMI_Close
            gets called automagically when the model goes out of scope.
        """
        if(self._ami_mem_handle):
            self._amiClose(self._ami_mem_handle)

    def initialize(self, init_object):
        """ Wraps the `AMI_Init' function.
            
            Takes an instance of `AMIModelInitializer' as its only argument.
            This allows model initialization data to be constructed once,
            and modified incrementally in between multiple calls of
            `initialize'. This is useful for PyLab command prompt testing.
        """

        if(self._ami_mem_handle):
            self._amiClose(self._ami_mem_handle)
        self._channel_response = init_object._initValues['channel_response']
        self._clock            = cp.copy(self._channel_response)
        self._wave             = cp.copy(self._channel_response)
        self._row_size         = init_object._initValues['row_size']
        self._num_aggressors   = init_object._initValues['num_aggressors']
        self._sample_interval  = init_object._initValues['sample_interval']
        self._bit_time         = init_object._initValues['bit_time']
        self._ami_params_in    = init_object._initValues['ami_params_in']
        self._ami_params_out   = c_char_p("")
        self._ami_mem_handle   = c_char_p("")
        self._msg              = c_char_p("")
        self._amiInit(
            byref(self._wave),
            self._row_size,
            self._num_aggressors,
            self._sample_interval,
            self._bit_time,
            self._ami_params_in,
            byref(self._ami_params_out),
            byref(self._ami_mem_handle),
            byref(self._msg)
        )

    def getWave(self, wave, row_size=0):
        """ Wraps the `AMI_GetWave' function.
            
            Takes an input waveform, as a standard Python type, and,
            optionally, a new processing block size, and calls
            AMI_GetWave(), returning the processed waveform as a NumPy array.
        """

        if(row_size):
            self._row_size = row_size
        Vector = c_double * len(wave)
        _wave = Vector(*wave)
        self._amiGetWave(
            byref(_wave),
            self._row_size,
            byref(self._clock),
            byref(self._ami_params_out),
            self._ami_mem_handle
        )
        return np.array(_wave)

