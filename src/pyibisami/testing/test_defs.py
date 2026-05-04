"""
Help for defining test definitions for use with ``test_models`` and its supporting infrastructure.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   May 3, 2026

Copyright (C) 2026 David Banas; all rights reserved World wide.
"""

from abc                import abstractmethod
from dataclasses        import dataclass
from pathlib            import Path
from typing             import Any, Generator, Optional

import numpy as np
from scipy.interpolate  import interp1d
from scipy.signal       import butter, freqs, lfilter

from ..common           import Rvec, raised_cosine

SIM_PARAMS = [
	"channel_response",
	"sample_interval",
	"bit_time",
	"row_size",
	"num_aggressors",
	"nbits",
]


@dataclass(frozen=True)
class TestDefinition:
	"Defines one iteration of a PyIBIS-AMI IBIS-AMI model testing sweep."

	description: str
	ami_params: dict[str, Any]
	sim_params: dict[str, Any]
	reference: Optional[Path] = None

	def __post_init__(self):
		if not isinstance(self.description, str):
			raise TypeError(f"The `description` field should contain a string, not a {type(self.description)}.")
		if not isinstance(self.ami_params, dict):
			raise TypeError(f"The `ami_params` field should contain a dictionary, not a {type(self.ami_params)}.")
		if not isinstance(self.sim_params, dict):
			raise TypeError(f"The `sim_params` field should contain a dictionary, not a {type(self.sim_params)}.")
		sim_params_keys = list(self.sim_params.keys())
		if sim_params_keys:
			first_key = sim_params_keys[0]
			if first_key not in SIM_PARAMS:
				raise ValueError(f"Values of keys in the `sim_params` dictionary must be one of: {SIM_PARAMS}, not {first_key}")
		if self.reference:
			if not isinstance(self.reference, Path):
				raise TypeError(f"The `reference` field should contain a Path, not a {type(self.reference)}.")
			if not self.reference.exists():
				raise ValueError(f"The given reference file path: {Path}, does not exist.")


class TestSweep:
    "Abstract class defining the function signature for an AMI test sweep generator."

    @abstractmethod
    def test_sweep(self) -> Generator[TestDefinition, None, None]:
        """
        Perform some tests on an ``AMIModel`` instance.

        Returns:
            A generator of ``TestDefinition``s.
        """

        raise NotImplementedError


# ToDo: Implement `mk_default_test_sweep_file`.

# def mk_default_test_sweep_file(ibis_file: Path, is_tx: bool, debug: bool) -> Path:
#     """
#     Create a parameter sweep specification template file for an IBIS-AMI model.

#     Args:
#         ibis_file: The ``*.ibs`` file defining the IBIS-AMI model of interest.
#         is_tx: True for Tx model.

#     Keyword Args:
#         debug: Set to ``True`` for debugging mode.
#         	Default: ``False``

#     Returns:
#         The path to the created parameter sweep specification template file.
#     """

#     # Import the `*.ibs` file.
#     try:
#         ibis = IBISModel(ibis_file, is_tx, debug=debug, gui=False)
#         dName = ibis_file.parent
#         assert ibis.ami_file, RuntimeError(
#             "Missing AMI file definition in IBIS file!"
#         )
#         ami_file = dName / ibis.ami_file
#     except Exception as err:
#         raise RuntimeError(f"Failed to open/import IBIS file: {ibis_file}!") from err

#     # Import the `*.ami` file.
#     try:
#         with open(ami_file, mode="r", encoding="utf-8") as pfile:
#             pcfg = AMIParamConfigurator(pfile.read())
#     except Exception as err:
#         raise RuntimeError(f"Failed to open/import AMI file: {ami_file}!") from err
#     if pcfg.ami_parsing_errors:
#         print(f"Non-fatal parsing errors:\n{pcfg.ami_parsing_errors}")

#     # Write parameter sweep specification template file.
#     root_name = str(pcfg.input_ami_params[ParamName("root_name")])
#     sweep_file_path = (Path("test_runs") / Path(root_name) / Path("defaults").with_suffix(".py")).resolve()
#     sweep_file_path.parent.mkdir(parents=True, exist_ok=True)
#     with open(sweep_file_path, mode="wt", encoding="utf-8") as sweep_file:
#         sweep_file.write(f"Template for specifying `{root_name}` parameter sweeps.\n")
#         sweep_file.write("\n('Defaults', \\\n")
#         sweep_file.write(
#             ", \\\n   ".join(
#                 [f"  ({{'root_name' : '{root_name}'"] +  # noqa: W504
#                 [f" '{ami_param_name}': {pcfg.input_ami_params[ami_param_name]}"
#                     for ami_param_name in pcfg.input_ami_params
#                     if ami_param_name != "root_name"] +  # noqa: W504
#                 ["}, {} \\\n"]
#             ))
#         sweep_file.write("  ) \\\n")
#         sweep_file.write(")\n")

#     return sweep_file_path


def perfect_channel(
	osf: int, nbits: int, ts: float
) -> Rvec:
	"""
	Perfect channel response (i.e - Kronecker delta)

	Args:
		osf: Over-sampling factor of returned vector.
		nbits: Total number of bits in returned vector.
		ts: Sampling interval of returned vector.

	Returns:
		The perfect channel response.
	"""

	return np.array([1.0] + [0.0] * (osf - 1) + [0.0] * (nbits - 1) * osf) / ts


def lossy_channel(
	osf: int, nbits: int, ts: float,
	bw: float = 0.05
) -> Rvec:
	"""
	Perfect channel response (i.e - Kronecker delta)

	Args:
		osf: Over-sampling factor of returned vector.
		nbits: Total number of bits in returned vector.
		ts: Sampling interval of returned vector.

	Keyword Args:
		bw: Bandwidth of filter used (bit_rate)

	Returns:
		The perfect channel response.
	"""

	bit_rate = 1 / ts / osf
	b, a = butter(1, bw * bit_rate, fs = 1 / ts)
	return lfilter(
	    b, a, np.array([0., 1.] + [0.] * (osf - 2) + [0.0] * (nbits - 1) * osf)
	) / ts


def reflective_channel(
	osf: int, nbits: int, ts: float,
    f_max: float = 40e9, f_step: float = 10e6
	) -> Rvec:
	"""
	Perfect channel response (i.e - Kronecker delta)

	Args:
		osf: Over-sampling factor of returned vector.
		nbits: Total number of bits in returned vector.
		ts: Sampling interval of returned vector.

	Keyword Args:
		f_max: Maximum frequency of interest.
		f_step: Frequency step to use.

	Returns:
		The perfect channel response.
	"""

	bit_rate = 1 / ts / osf
	t = np.arange(nbits * osf) * ts
	f = np.arange(0, f_max + f_step, f_step)
	w = 2 * np.pi * f
	_ts = 0.5 / f_max
	t_fft = np.array([n * _ts for n in range(2 * (len(f) - 1))])
	b, a = butter(1, 2 * np.pi * bit_rate / 2, analog=True)
	_, H = freqs(b, a, worN=w)
	td = 1 / bit_rate   # one-way channel delay = UI
	r = 0.2             # reflection coefficient
	H *= (1 - r) * np.exp(-1j * w * td) / (1 - r * np.exp(-2j * w * td))
	h = np.fft.irfft(raised_cosine(H)) / _ts
	krnl = interp1d(t_fft, h)
	return krnl(t)
