"""
Class definitions for working with IBIS-AMI models.

Original Author: David Banas

Original Date:   July 3, 2012

Copyright (c) 2019 David Banas; All rights reserved World wide.
"""

import copy as cp
from ctypes import CDLL, byref, c_char_p, c_double  # pylint: disable=no-name-in-module
from pathlib import Path
from typing import Any, Optional

import numpy as np
from numpy.random     import default_rng

from pyibisami.common import Rvec, deconv_same


def loadWave(filename: str) -> tuple[Rvec, Rvec]:
    """
    Load a waveform file.

    The file should consist of any number of lines, where each line
    contains, first, a time value and, second, a voltage value.
    Assume the first line is a header, and discard it.

    Specifically, this function may be used to load in waveform files
    saved from *CosmosScope*.

    Args:
        filename: Name of waveform file to read in.

    Returns:
        A pair of *NumPy* arrays containing the time and voltage values, respectively.
    """

    with open(filename, "r", encoding="utf-8") as theFile:
        theFile.readline()  # Consume the header line.
        time = []
        voltage = []
        for line in theFile:
            tmp = list(map(float, line.split()))
            time.append(tmp[0])
            voltage.append(tmp[1])
        return (np.array(time), np.array(voltage))


def interpFile(filename: str, sample_per: float) -> Rvec:
    """
    Read in a waveform from a file, and convert it to the given sample rate,
    using linear interpolation.

    Args:
        filename: Name of waveform file to read in.
        sample_per: New sample interval, in seconds.

    Returns:
        A *NumPy* array containing the resampled waveform.
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
    """
    Class containing the initialization data for an instance of ``AMIModel``.

    Created primarily to facilitate use of the PyAMI package at the
    pylab command prompt, this class can be used by the pylab user, in
    order to store all the data required to initialize an instance of
    class ``AMIModel``. In this way, the pylab user may assemble the
    AMIModel initialization data just once, and modify it incrementally,
    as she experiments with different initialization settings. In this
    way, she can avoid having to type a lot of redundant constants every
    time she invokes the AMIModel constructor.
    """

    # pylint: disable=too-few-public-methods,too-many-instance-attributes

    ami_params = {"root_name": ""}

    _init_data = {
        "channel_response": (c_double * 128)(0.0, 1.0, 0.0),
        "row_size": 128,
        "num_aggressors": 0,
        "sample_interval": c_double(25.0e-12),
        "bit_time": c_double(0.1e-9),
    }

    def __init__(self, ami_params: dict, info_params: Optional[dict] = None, **optional_args):
        """
        Constructor accepts a mandatory dictionary containing the AMI
        parameters, as well as optional information parameter dictionary
        and initialization data overrides, and validates them, before
        using them to update the local initialization data structures.

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
        self.info_params = info_params

        # Need to reverse sort, in order to catch ``sample_interval`` and ``row_size``,
        # before ``channel_response``, since ``channel_response`` depends upon ``sample_interval``,
        # when ``h`` is a file name, and overwrites ``row_size``, in any case.
        keys = list(optional_args.keys())
        keys.sort(reverse=True)
        if keys:
            for key in keys:
                if key in self._init_data:
                    self._init_data[key] = optional_args[key]

    def __str__(self):
        return "\n\t".join([
            "AMIModelInitializer instance:",
            f"`ami_params`: {self.ami_params}",
            f"`info_params`: {self.ami_params}"])

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


class AMIModel:  # pylint: disable=too-many-instance-attributes
    """
    Class defining the structure and behavior of an IBIS-AMI Model.

    Notes:
        1. Makes the calling of ``AMI_Close()`` automagic,
        by calling it from the destructor.
    """

    def __init__(self, filename: str):
        """
        Load the dll and bind the 3 AMI functions.

        Args:
            filename: The DLL/SO file name.

        Raises:
            OSError: If given file cannot be opened.
        """

        self._filename = filename
        self._ami_mem_handle = None
        my_dll = CDLL(filename)
        self._amiInit = my_dll.AMI_Init
        self._amiClose = my_dll.AMI_Close
        try:
            self._amiGetWave = my_dll.AMI_GetWave
        except Exception:  # pylint: disable=broad-exception-caught
            self._amiGetWave = None  # type: ignore

    def __del__(self):
        """
        Destructor - Calls ``AMI_Close()`` with handle to AMI model memory.

        This obviates the need for the user to call the ``AMI_Close()``
        function explicitly, and guards against memory leaks, during
        PyLab command prompt operation, by ensuring that ``AMI_Close()``
        gets called automagically when the model goes out of scope.
        """
        if self._ami_mem_handle:
            self._amiClose(self._ami_mem_handle)

    def __str__(self):
        return "\n\t".join([
            f"AMIModel instance: `{self._filename}`",
            f"Length of initOut = {len(self._initOut)}",
            f"row_size = {self._row_size}",
            f"num_aggressors = {self._num_aggressors}",
            f"sample_interval = {self._sample_interval}",
            f"bit_time = {self._bit_time}",
            f"samps_per_bit = {self._samps_per_bit}",
            f"bits_per_call = {self._bits_per_call}",
            f"ami_params_in = {self._ami_params_in}",
            f"ami_params_out = {self._ami_params_out}",
            f"&ami_mem_handle = {byref(self._ami_mem_handle)}",
            f"Message = {self._msg}",
            f"AMI_Init(): {self._amiInit}",
            f"AMI_GetWave(): {self._amiGetWave}",
            f"AMI_Close(): {self._amiClose}",])

    def initialize(self, init_object: AMIModelInitializer):
        """
        Wraps the ``AMI_Init()`` function.

        Args:
            init_object: The model initialization data.

        Notes:
            1. Takes an instance of ``AMIModelInitializer`` as its only argument.
            This allows model initialization data to be constructed once,
            and modified incrementally in between multiple calls of
            ``initialize``. This is useful for *PyLab* command prompt testing.

        ToDo:
            1. Allow for non-integral number of samples per unit interval.
        """

        # Free any memory allocated by the previous initialization.
        if self._ami_mem_handle:
            self._amiClose(self._ami_mem_handle)

        # Set up the AMI_Init() arguments.
        self._channel_response = (   # pylint: disable=attribute-defined-outside-init
            init_object._init_data[  # pylint: disable=protected-access
                "channel_response"
            ]
        )
        self._initOut = cp.copy(self._channel_response)  # type: ignore  # pylint: disable=attribute-defined-outside-init
        self._row_size = init_object._init_data[  # pylint: disable=protected-access,attribute-defined-outside-init
            "row_size"
        ]
        self._num_aggressors = init_object._init_data[  # pylint: disable=protected-access,attribute-defined-outside-init
            "num_aggressors"
        ]
        self._sample_interval = (    # pylint: disable=attribute-defined-outside-init
            init_object._init_data[  # pylint: disable=protected-access
                "sample_interval"
            ]
        )
        self._bit_time = init_object._init_data[  # pylint: disable=protected-access,attribute-defined-outside-init
            "bit_time"
        ]
        self._info_params = init_object.info_params  # pylint: disable=attribute-defined-outside-init

        # Check GetWave() consistency if possible.
        if init_object.info_params and init_object.info_params["GetWave_Exists"]:
            if not self._amiGetWave:
                raise RuntimeError(
                    "Reserved parameter `GetWave_Exists` is True, but I can't bind to `AMI_GetWave()`!"
                )

        # Construct the AMI parameters string.
        def sexpr(pname, pval):
            """Create an S-expression from a parameter name/value pair, calling
            recursively as needed to elaborate sub-parameter dictionaries."""
            if isinstance(pval, str):
                return f'({pname} "{pval}")'
            if isinstance(pval, dict):
                subs = []
                for sname in pval:
                    subs.append(sexpr(sname, pval[sname]))
                return sexpr(pname, " ".join(subs))
            return f"({pname} {pval})"

        ami_params_in = f"({init_object.ami_params['root_name']} "
        for item in list(init_object.ami_params.items()):
            if not item[0] == "root_name":
                ami_params_in += sexpr(item[0], item[1])
        ami_params_in += ")"
        self._ami_params_in = ami_params_in.encode("utf-8")  # pylint: disable=attribute-defined-outside-init

        # Set handle types.
        self._ami_params_out = c_char_p(b"")  # pylint: disable=attribute-defined-outside-init
        self._ami_mem_handle = c_char_p(None)  # type: ignore  # pylint: disable=attribute-defined-outside-init
        self._msg = c_char_p(b"")  # pylint: disable=attribute-defined-outside-init

        # Call AMI_Init(), via our Python wrapper.
        try:
            self._amiInit(
                byref(self._initOut),  # type: ignore
                self._row_size,
                self._num_aggressors,
                self._sample_interval,
                self._bit_time,
                self._ami_params_in,  # Prevents model from mucking up our input parameter string.
                byref(self._ami_params_out),
                byref(self._ami_mem_handle),  # type: ignore
                byref(self._msg),
            )
        except OSError as err:
            print("pyibisami.ami_model.AMIModel.initialize(): Call to AMI_Init() bombed:")
            print(err)
            print(f"AMI_Init() address = {self._amiInit}")
            print("Values sent into AMI_Init():")
            print(f"&initOut = {byref(self._initOut)}")  # type: ignore
            print(f"row_size = {self._row_size}")
            print(f"num_aggressors = {self._num_aggressors}")
            print(f"sample_interval = {self._sample_interval}")
            print(f"bit_time = {self._bit_time}")
            print(f"ami_params_in = {ami_params_in}")
            print(f"&ami_params_out = {byref(self._ami_params_out)}")
            print(f"&ami_mem_handle = {byref(self._ami_mem_handle)}")  # type: ignore
            print(f"&msg = {byref(self._msg)}")
            raise err

        # Initialize attributes used by getWave().
        bit_time = init_object.bit_time
        sample_interval = init_object.sample_interval
        # ToDo: Fix this. There isn't actually a requirement that `bit_time` be an integral multiple of `sample_interval`.
        # And there may be an advantage to having it not be!
        # if (bit_time % sample_interval) > (sample_interval / 100):
        #     raise ValueError(
        #         f"Bit time ({bit_time * 1e9: 6.3G} ns) must be an integral multiple of sample interval ({sample_interval * 1e9: 6.3G} ns)."
        #     )
        self._samps_per_bit = int(bit_time / sample_interval)  # pylint: disable=attribute-defined-outside-init
        self._bits_per_call = (  # pylint: disable=attribute-defined-outside-init
            init_object.row_size / self._samps_per_bit
        )

    def getWave(self, wave: Rvec, bits_per_call: int = 0) -> tuple[Rvec, Rvec, list[str]]:  # noqa: F405
        """
        Performs time domain processing of input waveform, using the ``AMI_GetWave()`` function.

        Args:
            wave: Waveform to be processed.

        Keyword Args:
            bits_per_call: Number of bits to use, per call to ``AMI_GetWave()``.
                Default: 0 (Means "Use existing value.")

        Returns:
            A tuple containing

                - the processed waveform,
                - the recovered slicer sampling instants, and
                - the list of output parameter strings received from each call to ``AMI_GetWave()``.

        Notes:
            1. The returned clock times are given in "pre-edge-aligned" fashion,
            which means their values are: sampling instant - ui/2.
        """

        if bits_per_call:
            self._bits_per_call = int(bits_per_call)  # pylint: disable=attribute-defined-outside-init
        bits_per_call = int(self._bits_per_call)
        samps_per_call = int(self._samps_per_bit * bits_per_call)

        # Create the required C types.
        Signal = c_double * samps_per_call
        Clocks = c_double * (bits_per_call + 1)  # The "+1" is critical, to prevent access violations by the model.

        idx = 0  # Holds the starting index of the next processing chunk.
        _clock_times = Clocks(0.0)
        wave_out: list[float] = []
        clock_times: list[float] = []
        params_out: list[str] = []
        input_len = len(wave)
        while idx < input_len:
            remaining_samps = input_len - idx
            if remaining_samps < samps_per_call:
                Signal = c_double * remaining_samps
                tmp_wave = wave[idx:]
            else:
                tmp_wave = wave[idx: idx + samps_per_call]
            _wave = Signal(*tmp_wave)
            try:
                self._amiGetWave(
                    byref(_wave), len(_wave), byref(_clock_times),
                    byref(self._ami_params_out), self._ami_mem_handle
                )  # type: ignore
            except OSError:
                print(self)
                print(f"byref(_wave): {byref(_wave)}")
                print(f"len(_wave): {len(_wave)}")
                print(f"byref(_clock_times): {byref(_clock_times)}")
                print(f"byref(self._ami_params_out): {byref(self._ami_params_out)}")
                print(f"self._ami_mem_handle: {self._ami_mem_handle}")
                raise
            wave_out.extend(_wave)
            clock_times.extend(_clock_times)
            params_out.append(self.ami_params_out)
            idx += len(_wave)

        return np.array(wave_out), np.array(clock_times[: len(wave_out) // self._samps_per_bit]), params_out

    def get_responses(  # pylint: disable=too-many-locals
        self,
        bits_per_call: int = 0,
        pad_bits: int = 10,
        nbits: int = 200,
        calc_getw: bool = True
    ) -> dict[str, Any]:
        """
        Get the impulse response of an initialized IBIS-AMI model, alone and convolved with the channel.

        Keyword Args:
            bits_per_call: Number of bits to include in the input to `GetWave()`.
                Default: 0 (Means "use model's existing value".)
            pad_bits: Number of bits to pad leading edge with when calling `GetWave()`,
                to protect from initial garbage in `GetWave()` output.
                Default: 10
            nbits: Number of "real" bits to use for `GetWave()` testing.
                Default: 200
            calc_getw: Calculate ``GetWave()`` responses, also, when True.
                Default: True

        Returns:
            Dictionary containing the responses under the following keys

                - "imp_resp_init": The model's impulse response, from its `AMI_Init()` function (V/sample).
                - "out_resp_init": `imp_resp_init` convolved with the channel.
                - "imp_resp_getw": The model's impulse response, from its `AMI_GetWave()` function (V/sample).
                - "out_resp_getw": `imp_resp_getw` convolved with the channel.

        Notes:
            1. If either set of keys (i.e. - "..._init" or "..._getw")
            is missing from the returned dictionary, it means that
            that mode of operation (`AMI_Init()` or `AMI_GetWave()`)
            was not available in the given model.

            2. An empty dictionary implies that neither the `Init_Returns_Impulse`
            nor the `GetWave_Exists` AMI reserved parameter was True.

            3. Note that impulse responses are returned with units: (V/sample), not (V/s).

        ToDo:
            1. Implement `bit_gen`.
            2. Implement `ignore_bits`.
        """

        rslt = {}

        # Capture needed parameter definitions.
        ui = self.bit_time
        ts = self.sample_interval
        info_params = self.info_params
        ignore_bits = info_params["Ignore_Bits"].pvalue if "Ignore_Bits" in info_params else 0

        # Capture/convert instance variables.
        chnl_imp = np.array(self.channel_response) * ts     # input (a.k.a. - "channel") impulse response (V/sample)
        out_imp = np.array(self.initOut) * ts               # output impulse response (V/sample)

        # Calculate some needed intermediate values.
        nspui = int(ui / ts)            # samps per UI
        pad_samps = pad_bits * nspui    # leading edge padding samples for GetWave() calls
        len_h = len(out_imp)
        t = np.array([i * ts for i in range(-pad_samps, len_h - pad_samps)])
        f = np.array([i * 1.0 / (ts * len_h) for i in range(len_h // 2 + 1)])  # Assumes `rfft()` is used.

        # Extract and return the model responses.
        if self.info_params["Init_Returns_Impulse"]:
            h_model = deconv_same(out_imp, chnl_imp)  # noqa: F405
            rslt["imp_resp_init"] = np.roll(h_model, -len(h_model) // 2 + 3 * nspui)

            h_init = np.roll(out_imp, pad_samps)
            s_init = np.cumsum(h_init)                 # Step response.
            p_init = s_init - np.pad(s_init[:-nspui], (nspui, 0), mode='constant', constant_values=0)
            H_init = np.fft.rfft(self.initOut)
            H_init *= s_init[-1] / np.abs(H_init[0])   # Normalize for proper d.c.
            rslt["out_resp_init"] = (t, h_init, s_init, p_init, f, H_init)

        if calc_getw and self.info_params["GetWave_Exists"]:
            # Get model's step response.
            rng = default_rng()
            u = np.concatenate(
                (rng.integers(low=0, high=2, size=ignore_bits),
                 np.array([0] * pad_bits + [1] * nbits))).repeat(nspui) - 0.5
            wave_out, _, _ = self.getWave(u, bits_per_call=bits_per_call)

            # Calculate impulse response from step response.
            rslt["imp_resp_getw"] = np.diff(wave_out[(ignore_bits + pad_bits) * nspui:])

            # Get step response of channel + model.
            wave_in = np.convolve(u, chnl_imp)[:len(u)]
            wave_out, _, _ = self.getWave(wave_in, bits_per_call=bits_per_call)
            s_getw = wave_out[ignore_bits * nspui:][:len(t)] + 0.5
            # Match the d.c. offset of Init() output, for easier comparison of Init() & GetWave() outputs.
            s_getw -= s_getw[pad_samps - 1]
            p_getw = s_getw - np.pad(s_getw[:-nspui], (nspui, 0), mode='constant', constant_values=0)
            _s = s_getw[pad_samps:]
            h_getw = np.insert(np.diff(_s), 0, _s[0])
            len_hgw = len(h_getw)
            if len_hgw > len_h:
                h_getw = h_getw[:len_h]
            else:
                h_getw = np.pad(h_getw, (0, len_h - len_hgw))
            H_getw = np.fft.rfft(h_getw)
            rslt["out_resp_getw"] = (t, h_getw, s_getw, p_getw, f, H_getw)

        return rslt

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

    ami_params_out = property(
        _getAmiParamsOut, doc="The AMI parameter string returned by either `AMI_Init()` or `AMI_GetWave()`."
    )

    def _getMsg(self):
        return self._msg.value

    msg = property(_getMsg, doc="Message returned by most recent call to AMI_Init() or AMI_GetWave().")

    def _getClockTimes(self):
        return self.clock_times

    clock_times = property(_getClockTimes, doc="Clock times returned by most recent call to getWave().")

    def _getInfoParams(self):
        return self._info_params

    info_params = property(_getInfoParams, doc="Reserved AMI parameter values for this model.")
