#! /usr/bin/env python

"""
Model configurator for ibisami example Tx model.  This is used in conjunction with ami_config.

Original author: David Banas
Original date:   August 19, 2015

The intent is that this example configurator can be used as a starting
point for other custom models.

Copyright (c) 2015 David Banas; all rights reserved World wide.
"""

kFileBaseName = "example_tx"
kDescription = "Example Tx model from ibisami package."

# These are used to configure the IBIS model.
#
# Lists should contain 3 values:
# typical, min/slow/weak, and max/fast/strong, in that order.
# (The singular exception is 'c_comp', which should contain 3 values,
# in NUMERICAL typ, min, max order.)
ibis_params = {
    "file_name": kFileBaseName + ".ibs",
    "file_rev": "v0.1",
    "copyright": "Copyright (c) 2016 David Banas; all rights reserved World wide.",
    "component": "Example_Tx",
    "manufacturer": "(n/a)",
    "r_pkg": [0.1, 0.001, 0.5],
    "l_pkg": [10.0e-9, 0.1e-9, 50.0e-9],
    "c_pkg": [1.0e-12, 0.01e-12, 5.0e-12],
    "model_name": kFileBaseName,
    "model_type": "Output",
    "c_comp": [1.0e-12, 0.01e-12, 5.0e-12],
    "c_ref": 0,
    "v_ref": 0.5,
    "v_meas": 0.5,
    "r_ref": 50,
    "temperature_range": [25, 0, 100],
    "voltage_range": [1.8, 1.62, 1.98],
    "impedance": [50.0, 45.0, 55.0],
    "slew_rate": [5.0e9, 1.0e9, 10.0e9],
}

# These are used to configure the AMI model.
ami_params = {
    # These will go in the [Reserved_Parameters] section of the *.AMI file.
    "reserved": {
        "AMI_Version": {
            "type": "STRING",
            "usage": "Info",
            "format": "Value",
            "default": '"5.1"',
            "description": '"Version of IBIS standard we comply with."',
        },
        "Init_Returns_Impulse": {
            "type": "BOOL",
            "usage": "Info",
            "format": "Value",
            "default": "True",
            "description": '"In fact, this model is, currently, Init-only."',
        },
        "GetWave_Exists": {
            "type": "BOOL",
            "usage": "Info",
            "format": "Value",
            "default": "True",
            "description": '"This model is dual-mode, with GetWave() mimicking Init()."',
        },
    },
    # These will go in the [Model_Specific] section of the *.AMI file.
    "model": {
        "tx_tap_units": {
            "type": "INT",
            "usage": "In",
            "format": "Range",
            "min": 6,  # Check this.
            "max": 27,
            "default": 27,
            "tap_pos": -1,  # Pre-emph. FIR tap position; '-1' means "n/a".
            "description": '"Total current available to FIR filter."',
        },
        "tx_tap_np1": {
            "type": "INT",
            "usage": "In",
            "format": "Range",
            "min": 0,
            "max": 10,
            "default": 0,
            "tap_pos": 0,
            "description": '"First (and only) pre-tap."',
        },
        "tx_tap_nm1": {
            "type": "INT",
            "usage": "In",
            "format": "Range",
            "min": 0,
            "max": 10,
            "default": 0,
            "tap_pos": 2,
            "description": '"First post-tap."',
        },
        "tx_tap_nm2": {
            "type": "INT",
            "usage": "In",
            "format": "Range",
            "min": 0,
            "max": 10,
            "default": 0,
            "tap_pos": 3,
            "description": '"Second post-tap."',
        },
    },
}
