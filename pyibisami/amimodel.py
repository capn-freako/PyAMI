"""
Class definitions for working with IBIS-AMI models

Original Author: David Banas
Original Date:   July 3, 2012

Copyright (c) 2012 David Banas; All rights reserved World wide.
"""

from ctypes import *
import numpy as np
import copy as cp
import os

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
        return(np.array(t), np.array(v))

def interpFile(filename, sample_per):
    """ Read in a waveform from a file, and convert it to the
        given sample rate, using linear interpolation.

        Inputs:
        - filename:   Name of waveform file to read in.
        - sample_per: New sample interval

        Outputs:
        - res: resampled waveform
    """
    impulse = loadWave(filename)
    ts = impulse[0]
    ts = ts - ts[0]
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
    res = np.array(res)
    return res

# dbanas-2016_11_25: I'm not sure how this function came to be. It
# offers nothing above and beyond interpFile(), above, which it calls.
# And its name is very misleading.
#
# I'm deprecating it, leaving it here in commented form for a while,
# as an aid to anyone, whos code I break. My apologies for any trouble.
#
# If you have code that breaks, due to the removal of this function,
# the proper corrective action is to change any and all calls to the
# getImpulse() function to calls to interpFile(), instead.
#
# def getImpulse(filename, sample_per):
#     # Return impulse response.
#     res = interpFile(filename, sample_per)
#     return res

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

    ami_params = {
        'root_name' : "",
    }

    _init_data = {
        'channel_response' : (c_double * 128)(0.0, 1.0, 0.0),
        'row_size'         : 128,
        'num_aggressors'   : 0,
        'sample_interval'  : c_double(25.0e-12),
        'bit_time'         : c_double(0.1e-9)
    }

    def __init__(self, ami_params, **optional_args):
        """ Constructor accepts a mandatory dictionary containing the
            AMI parameters, as well as optional initialization
            data overrides and validates them, before using them to
            update the local initialization data structures.

            Valid names of optional initialization data overrides:

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
        """

        self.ami_params = {
            'root_name' : "",
        }
        self.ami_params.update(ami_params)

        # Need to reverse sort, in order to catch `sample_interval` and `row_size`,
        # before `channel_response`, since `channel_response` depends upon `sample_interval`,
        # when `h` is a file name, and overwrites `row_size`, in any case.
        keys = optional_args.keys()
        keys.sort(reverse=True)
        if(keys):
            for key in keys:
                if(key in self._init_data):
                    self._init_data[key] = optional_args[key]

    def _getChannelResponse(self):
        return map(float, self._init_data['channel_response'])
    def _setChannelResponse(self, h):
        if(isinstance(h, str) and os.path.isfile(h)):
            h = interpFile(h, self.sample_interval)
        Vector = c_double * len(h)
        self._init_data['channel_response'] = Vector(*h)
        self.row_size = len(h)
    channel_response = property(_getChannelResponse, _setChannelResponse, \
        doc='Channel impulse response to be passed to AMI_Init(). May be a file name.')

    def _getRowSize(self):
        return self._init_data['row_size']
    def _setRowSize(self, n):
        self._init_data['row_size'] = n
    row_size = property(_getRowSize, _setRowSize, \
        doc='Number of elements in channel response vector(s).')

    def _getNumAggressors(self):
        return self._init_data['num_aggressors']
    def _setNumAggressors(self, n):
        self._init_data['num_aggressors'] = n
    num_aggressors = property(_getNumAggressors, _setNumAggressors, \
        doc="Number of vectors in `channel_response', minus one.")

    def _getSampleInterval(self):
        return float(self._init_data['sample_interval'].value)
    def _setSampleInterval(self, T):
        self._init_data['sample_interval'] = c_double(T)
    sample_interval = property(_getSampleInterval, _setSampleInterval, \
        doc='Time interval between adjacent elements in channel response vector(s).')

    def _getBitTime(self):
        return float(self._init_data['bit_time'].value)
    def _setBitTime(self, T):
        self._init_data['bit_time'] = c_double(T)
    bit_time = property(_getBitTime, _setBitTime, \
        doc='Link unit interval.')

class AMIModel(object):
    """ Class defining the structure and behavior of a AMI Model.
        
        Public Methods: (See individual docs.)
          initialize()
          getWave()
        
        Properties: (See individual docs.)
          initOut
          channel_response
          clock
          row_size
          num_aggressors
          sample_interval
          bit_time
          ami_params_in
          ami_params_out
          ami_mem_handle
          msg

        Additional Features:

          - Makes the calling of AMI_Close() automagic, by calling it
            from the destructor.
    """

    def __init__(self, filename):
        " Load the dll and bind the 3 AMI functions."

        self._ami_mem_handle = None
        my_dll = CDLL(filename)
        self._amiInit = my_dll.AMI_Init
        try:
            self._amiGetWave = my_dll.AMI_GetWave
        except:
            self._amiGetWave = None
        self._amiClose = my_dll.AMI_Close

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

        # Free any memory allocated by the previous initialization.
        if(self._ami_mem_handle):
            self._amiClose(self._ami_mem_handle)
            self._ami_mem_handle = c_char_p(None)

        # Set up the AMI_Init() arguments.
        self._channel_response = init_object._init_data['channel_response']
        self._clock            = cp.copy(self._channel_response)
        self._initOut          = cp.copy(self._channel_response)
        self._row_size         = init_object._init_data['row_size']
        self._num_aggressors   = init_object._init_data['num_aggressors']
        self._sample_interval  = init_object._init_data['sample_interval']
        self._bit_time         = init_object._init_data['bit_time']

        # Construct the AMI parameters string.
        self._ami_params_in = "(" + init_object.ami_params['root_name'] + " "
        for item in init_object.ami_params.items():
            if(not item[0] == 'root_name'):
                self._ami_params_in = self._ami_params_in + \
                    "(" + str(item[0]) + " " + str(item[1]) + ")"
        self._ami_params_in = self._ami_params_in + ")"

        # Set handle types.
        self._ami_params_out   = c_char_p("")
        self._ami_mem_handle   = c_char_p(None)
        self._msg              = c_char_p("")

        # Call AMI_Init(), via our Python wrapper.
        try:
            self._amiInit(
                byref(self._initOut),
                self._row_size,
                self._num_aggressors,
                self._sample_interval,
                self._bit_time,
                self._ami_params_in,
                byref(self._ami_params_out),
                byref(self._ami_mem_handle),
                byref(self._msg)
            )
        except:
            raise

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

    def _getInitOut(self):
        return map(float, self._initOut)
    initOut = property(_getInitOut, doc='Channel response convolved with model impulse response.')

    def _getChannelResponse(self):
        return map(float, self._channel_response)
    channel_response = property(_getChannelResponse, doc='Channel response passed to initialize().')

    def _getRowSize(self):
        return self._row_size
    row_size = property(_getRowSize, doc='Length of vector(s) passed to initialize().')

    def _getNumAggressors(self):
        return self._num_aggressors
    num_aggressors = property(_getNumAggressors, \
        doc='Number of rows in matrix passed to initialize(), minus one.')

    def _getSampleInterval(self):
        return float(self._sample_interval.value)
    sample_interval = property(_getSampleInterval, \
        doc='Time interval between adjacent elements of the vector(s) passed to initialize().')

    def _getBitTime(self):
        return float(self._bit_time.value)
    bit_time = property(_getBitTime, doc='Link unit interval, as passed to initialize().')

    def _getAmiParamsIn(self):
        return self._ami_params_in
    ami_params_in = property(_getAmiParamsIn, \
        doc='The AMI parameter string passed to AMI_Init() by initialize().')

    def _getAmiParamsOut(self):
        return self._ami_params_out.value
    ami_params_out = property(_getAmiParamsOut, doc='The AMI parameter string returned by AMI_Init().')

    def _getMsg(self):
        return self._msg.value
    msg = property(_getMsg, doc='Message returned by most recent call to AMI_Init() or AMI_GetWave().')

