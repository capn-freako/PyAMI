"""
Class definitions for working with IBIS-AMI models

Original Author: David Banas

Original Date:   July 3, 2012

Copyright (c) 2019 David Banas; All rights reserved World wide.
"""
from pathlib import Path
from typing import Dict

import copy as cp
import unicodedata
from ctypes import CDLL, byref, c_char_p, c_double
import numpy as np


def loadWave(filename):
    """
    Load a waveform file.

    The file should consist of any number of lines, where each line
    contains, first, a time value and, second, a voltage value.
    Assume the first line is a header, and discard it.

    Specifically, this function may be used to load in waveform files
    saved from *CosmosScope*.

    Args:
        filename (str): Name of waveform file to read in.

    Returns:
        ([float], [float]): A pair of *NumPy* arrays containing the time
            and voltage values, respectively.
    """

    with open(filename, "r") as theFile:
        theFile.readline()  # Consume the header line.
        time = []
        voltage = []
        for line in theFile:
            tmp = list(map(float, line.split()))
            time.append(tmp[0])
            voltage.append(tmp[1])
        return (np.array(time), np.array(voltage))


def interpFile(filename, sample_per):
    """
    Read in a waveform from a file, and convert it to the given sample
    rate, using linear interpolation.

    Args:
        filename (str): Name of waveform file to read in.
        sample_per (float): New sample interval, in seconds.

    Returns:
        [float]: A *NumPy* array containing the resampled waveform.
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
    while t < tmax:
        while ts[i] <= t:
            i = i + 1
        res.append(vs[i - 1] + (vs[i] - vs[i - 1]) * (t - ts[i - 1]) / (ts[i] - ts[i - 1]))
        t = t + sample_per
    return np.array(res)


class AMIModelInitializer:
    """ Class containing the initialization data for an instance of ``AMIModel``.

        Created primarily to facilitate use of the PyAMI package at the
        pylab command prompt, this class can be used by the pylab user,
        in order to store all the data required to initialize an instance
        of class ``AMIModel``. In this way, the pylab user may assemble
        the AMIModel initialization data just once, and modify it
        incrementally, as she experiments with different initialization
        settings. In this way, she can avoid having to type a lot of
        redundant constants every time she invokes the AMIModel constructor.
    """

    ami_params = {"root_name": ""}

    _init_data = {
        "channel_response": (c_double * 128)(0.0, 1.0, 0.0),
        "row_size": 128,
        "num_aggressors": 0,
        "sample_interval": c_double(25.0e-12),
        "bit_time": c_double(0.1e-9),
    }

    def __init__(self, ami_params: Dict, **optional_args):
        """ Constructor accepts a mandatory dictionary containing the
            AMI parameters, as well as optional initialization
            data overrides and validates them, before using them to
            update the local initialization data structures.

            Valid names of optional initialization data overrides:

            - channel_response
                a matrix of ``c_double's`` where the first row represents the
                impulse response of the analog channel, and the rest represent
                the impulse responses of several aggressor-to-victim far end
                crosstalk (FEXT) channels.

                Default) a single 128 element vector containing an ideal impulse

            - row_size
                integer giving the size of the rows in ``channel_response``.

                Default) 128

            - num_aggressors
                integer giving the number or rows in ``channel_response``, minus
                one.

                Default) 0

            - sample_interval
                c_double giving the time interval, in seconds, between
                successive elements in any row of ``channel_response``.

                Default) 25e-12 (40 GHz sampling rate)

            - bit_time
                c_double giving the bit period (i.e. - unit interval) of the
                link, in seconds.

                Default) 100e-12 (10 Gbits/s)
        """

        self.ami_params = {"root_name": ""}
        self.ami_params.update(ami_params)

        # Need to reverse sort, in order to catch ``sample_interval`` and ``row_size``,
        # before ``channel_response``, since ``channel_response`` depends upon ``sample_interval``,
        # when ``h`` is a file name, and overwrites ``row_size``, in any case.
        keys = list(optional_args.keys())
        keys.sort(reverse=True)
        if keys:
            for key in keys:
                if key in self._init_data:
                    self._init_data[key] = optional_args[key]

        # Perform some sanity checks.
        # if((self.bit_time / self.sample_interval) != int(self.bit_time / self.sample_interval)):
        # raise ValueError("bit_time must be an integral multiple of sample_interval.")

    def _getChannelResponse(self):
        return list(map(float, self._init_data["channel_response"]))

    def _setChannelResponse(self, h):
        if isinstance(h, str) and Path(h).is_file():
            h = interpFile(h, self.sample_interval)
        Vector = c_double * len(h)
        self._init_data["channel_response"] = Vector(*h)
        self.row_size = len(h)

    channel_response = property(
        _getChannelResponse,
        _setChannelResponse,
        doc="Channel impulse response to be passed to AMI_Init(). May be a file name.",
    )

    def _getRowSize(self):
        return self._init_data["row_size"]

    def _setRowSize(self, n):
        self._init_data["row_size"] = n

    row_size = property(_getRowSize, _setRowSize, doc="Number of elements in channel response vector(s).")

    def _getNumAggressors(self):
        return self._init_data["num_aggressors"]

    def _setNumAggressors(self, n):
        self._init_data["num_aggressors"] = n

    num_aggressors = property(
        _getNumAggressors, _setNumAggressors, doc="Number of vectors in ``channel_response``, minus one."
    )

    def _getSampleInterval(self):
        return float(self._init_data["sample_interval"].value)

    def _setSampleInterval(self, T):
        self._init_data["sample_interval"] = c_double(T)

    sample_interval = property(
        _getSampleInterval,
        _setSampleInterval,
        doc="Time interval between adjacent elements in channel response vector(s).",
    )

    def _getBitTime(self):
        return float(self._init_data["bit_time"].value)

    def _setBitTime(self, T):
        self._init_data["bit_time"] = c_double(T)

    bit_time = property(_getBitTime, _setBitTime, doc="Link unit interval.")


class AMIModel:
    """ Class defining the structure and behavior of a AMI Model.

        Notes:
            * Makes the calling of ``AMI_Close()`` automagic,
              by calling it from the destructor.
    """

    def __init__(self, filename):
        """ Load the dll and bind the 3 AMI functions."""

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
        if self._ami_mem_handle:
            self._amiClose(self._ami_mem_handle)

    def initialize(self, init_object):
        """ Wraps the ``AMI_Init`` function.

        Args:
            init_object(AMIModelInitializer): The model initialization data.

        Notes:
            * Takes an instance of ``AMIModelInitializer`` as its only argument.
              This allows model initialization data to be constructed once,
              and modified incrementally in between multiple calls of
              ``initialize``. This is useful for *PyLab* command prompt testing.
        """

        # Free any memory allocated by the previous initialization.
        if self._ami_mem_handle:
            self._amiClose(self._ami_mem_handle)
            self._ami_mem_handle = c_char_p(None)

        # Set up the AMI_Init() arguments.
        self._channel_response = init_object._init_data["channel_response"]
        # self._clock_times      = cp.copy(self._channel_response)
        self._initOut = cp.copy(self._channel_response)
        self._row_size = init_object._init_data["row_size"]
        self._num_aggressors = init_object._init_data["num_aggressors"]
        self._sample_interval = init_object._init_data["sample_interval"]
        self._bit_time = init_object._init_data["bit_time"]

        # Construct the AMI parameters string.
        ami_params_in = "({} ".format(init_object.ami_params["root_name"])
        for item in list(init_object.ami_params.items()):
            if not item[0] == "root_name":
                ami_params_in += "({} {})".format(str(item[0]), str(item[1]))
        ami_params_in += ")"
        self._ami_params_in = ami_params_in.encode("utf-8")

        # Set handle types.
        self._ami_params_out = c_char_p(b"")
        self._ami_mem_handle = c_char_p(None)
        self._msg = c_char_p(b"")

        # Call AMI_Init(), via our Python wrapper.
        try:
            self._amiInit(
                byref(self._initOut),
                self._row_size,
                self._num_aggressors,
                self._sample_interval,
                self._bit_time,
                self._ami_params_in,  # Prevents model from mucking up our input parameter string.
                byref(self._ami_params_out),
                byref(self._ami_mem_handle),
                byref(self._msg),
            )
        except OSError as error:
            raise error

        # Initialize attributes used by getWave().
        bit_time = self._bit_time.value
        sample_interval = self._sample_interval.value
        # ToDo: Fix this.
        # if(bit_time % sample_interval):
        # raise ValueError("bit_time ({:6.3G}) must be an integral multiple of sample_interval ({:6.3G}).".format(self._bit_time.value, self._sample_interval.value))
        self._samps_per_bit = int(bit_time / sample_interval)
        self._bits_per_call = self._row_size / self._samps_per_bit

    def getWave(self, wave, bits_per_call=0):
        """
        Performs time domain processing of input waveform, using the ``AMI_GetWave`` function.

        Args:
            wave(array-like): Waveform to be processed.
            bits_per_call(Integer): Number of bits to use, per call to AMI_GetWave().
                (Optional; default = existing value.)

        Returns:
            NumPy 1D array, NumPy 1D array: (The processed waveform, The recovered slicer sampling instants).
        """

        if bits_per_call:
            self._bits_per_call = bits_per_call
        bits_per_call = self._bits_per_call
        samps_per_call = self._samps_per_bit * bits_per_call

        # Create the required C types.
        Signal = c_double * samps_per_call
        Clocks = c_double * bits_per_call

        idx = 0  # Holds the starting index of the next processing chunk.
        _clock_times = Clocks(0.0)
        wave_out = []
        clock_times = []
        input_len = len(wave)
        while idx < input_len:
            remaining_samps = input_len - idx
            if remaining_samps < samps_per_call:
                Signal = c_double * remaining_samps
                tmp_wave = wave[idx:]
            else:
                tmp_wave = wave[idx : idx + samps_per_call]
            _wave = Signal(*tmp_wave)
            self._amiGetWave(
                byref(_wave), len(_wave), byref(_clock_times), byref(self._ami_params_out), self._ami_mem_handle
            )
            wave_out.extend(_wave)
            clock_times.extend(_clock_times)
            idx += len(_wave)

        return np.array(wave_out), np.array(clock_times[: len(wave_out) // self._samps_per_bit])

    def _getInitOut(self):
        return list(map(float, self._initOut))

    initOut = property(_getInitOut, doc="Channel response convolved with model impulse response.")

    def _getChannelResponse(self):
        return list(map(float, self._channel_response))

    channel_response = property(_getChannelResponse, doc="Channel response passed to initialize().")

    def _getRowSize(self):
        return self._row_size

    row_size = property(_getRowSize, doc="Length of vector(s) passed to initialize().")

    def _getNumAggressors(self):
        return self._num_aggressors

    num_aggressors = property(_getNumAggressors, doc="Number of rows in matrix passed to initialize(), minus one.")

    def _getSampleInterval(self):
        return float(self._sample_interval.value)

    sample_interval = property(
        _getSampleInterval, doc="Time interval between adjacent elements of the vector(s) passed to initialize()."
    )

    def _getBitTime(self):
        return float(self._bit_time.value)

    bit_time = property(_getBitTime, doc="Link unit interval, as passed to initialize().")

    def _getAmiParamsIn(self):
        return self._ami_params_in

    ami_params_in = property(_getAmiParamsIn, doc="The AMI parameter string passed to AMI_Init() by initialize().")

    def _getAmiParamsOut(self):
        return self._ami_params_out.value

    ami_params_out = property(_getAmiParamsOut, doc="The AMI parameter string returned by AMI_Init().")

    def _getMsg(self):
        return self._msg.value

    msg = property(_getMsg, doc="Message returned by most recent call to AMI_Init() or AMI_GetWave().")

    def _getClockTimes(self):
        return self._clock_times

    clock_times = property(_getClockTimes, doc="Clock times returned by most recent call to getWave().")
