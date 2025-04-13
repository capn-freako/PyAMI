"""
IBIS-AMI reserved parameter names, as a Python ``dataclass``.

Original author: David Banas <capn.freako@gmail.com>

Original date:   March 17, 2025

Copyright (c) 2025 David Banas; all rights reserved World wide.
"""

from dataclasses import dataclass


@dataclass
class AmiReservedParameterName():
    "IBIS-AMI Reserved Parameter Name"

    pname: str

    def __post_init__(self):
        "Validate parameter name."

        if self.pname not in RESERVED_PARAM_NAMES:
            raise ValueError(f"Parameter name: {self.pname}, is not an IBIS-AMI reserved parameter name!")


RESERVED_PARAM_NAMES = [
    "AMI_Version",
    "Init_Returns_Impulse",
    "GetWave_Exists",
    "Use_Init_Output",
    "Max_Init_Aggressors",
    "Ignore_Bits",
    "Resolve_Exists",
    "Model_Name",
    "Special_Param_Names",
    "Component_Name",
    "Signal_Name",
    "Rx_Decision_Time",
    "DC_Offset",
    "Rx_Use_Clock_Input",
    "Supporting_Files",
    "DLL_Path",
    "DLL_ID",
    "Tx_Jitter",
    "Tx_DCD",
    "Tx_Rj",
    "Tx_Dj",
    "Tx_Sj",
    "Tx_Sj_Frequency",
    "Rx_DCD",
    "Rx_Rj",
    "Rx_Dj",
    "Rx_Sj",
    "Rx_Clock_PDF",
    "Rx_Clock_Recovery_Mean",
    "Rx_Clock_Recovery_Rj",
    "Rx_Clock_Recovery_Dj",
    "Rx_Clock_Recovery_Sj",
    "Rx_Clock_Recovery_DCD",
    "Rx_Receiver_Sensitivity",
    "Rx_Noise",
    "Rx_GaussianNoise",
    "Rx_UniformNoise",
    "Modulation",
    "PAM4_Mapping",
    "PAM4_UpperThreshold",
    "PAM4_CenterThreshold",
    "PAM4_LowerThreshold",
    "PAM4_UpperEyeOffset",
    "PAM4_CenterEyeOffset",
    "PAM4_LowerEyeOffset",
    "Repeater_Type",
    "BCI_Protocol",
    "BCI_ID",
    "BCI_State",
    "BCI_Message_Interval_UI",
    "BCI_Training_UI",
    "BCI_Training_Mode",
    "Ts4file",
    "Tx_V",
    "Tx_R",
    "Rx_R",
]
