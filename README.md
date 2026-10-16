[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/capn-freako/PyAMI/master.svg)](https://results.pre-commit.ci/latest/github/capn-freako/PyAMI/master)

# PyIBIS-AMI

PyIBIS-AMI is a Python package of tools useful in the development and testing of IBIS-AMI models.
It parses IBIS (`.ibs`) and AMI (`.ami`) files, drives a model's `AMI_Init()` / `AMI_GetWave()`
functions from Python, and provides several command line applications.
This library is used in [PyBERT](https://github.com/capn-freako/PyBERT).

[View API/Developer's Documentation.](https://pyibis-ami.readthedocs.io/en/latest/)

## Installation

```bash
pip install PyIBIS-AMI
```

The basic install contains the core library, plus the `ami-config` and `check-ami` tools.
Optional features are installed as extras, e.g. `pip install 'PyIBIS-AMI[gui]'`:

| Extra      | Needed for                                                      |
|------------|-----------------------------------------------------------------|
| `gui`      | Traits/UI GUIs (AMI parameter configurator, IBIS model viewers) |
| `report`   | `test-model` and `run-tests`                                    |
| `notebook` | `run-notebook`                                                  |
| `all`      | All of the above                                                |

The `gui` extra doesn't include a Qt binding; install one too, if you have none (e.g. `pip install pyside6`).

## Python Example

Load an IBIS-AMI model, initialize it with its default parameter values, and run a bit stream through it:

```python
import logging

import numpy as np

from pyibisami.ami.model import AMIModel
from pyibisami.ami.parser import AMIParamConfigurator
from pyibisami.ibis.file import IBISModel

# PyIBIS-AMI only logs (to loggers under `pyibisami`); it's silent until you configure logging.
# Show warnings and above from everything, plus `pyibisami`'s debug messages:
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("pyibisami").setLevel(logging.DEBUG)
# Or, tune one module, e.g. quiet the IBIS parser:
logging.getLogger("pyibisami.ibis.parser").setLevel(logging.INFO)
log = logging.getLogger("example")  # This script's own messages.
log.setLevel(logging.INFO)

# Parse the IBIS file. The first component/pin/model is selected by default;
# change the selection via `ibis.comp`, `ibis.pin`, and `ibis.mod`.
ibis = IBISModel("example_tx.ibs")

# Parse the selected model's AMI file and take its default parameter values.
# (For an I/O model with both Tx and Rx executables, use `ibis.model.get_ami_files(is_tx)` to pick one.)
with open(ibis.ami_path, encoding="utf-8") as f:
    ami_cfg = AMIParamConfigurator(f.read())
ami_params = ami_cfg.input_ami_params  # e.g. {'root_name': 'example_tx', 'tx_tap_units': 27, ...}

# Build the `AMI_Init()` input: 10 Gb/s, 32 samples per UI, ideal channel (unit impulse).
bit_time = 100e-12
sample_interval = bit_time / 32
h = np.zeros(256)
h[0] = 1 / sample_interval
initializer = ami_cfg.get_init(bit_time, sample_interval, h, ami_params=ami_params)

# Load the model's DLL/SO (for this platform) and call `AMI_Init()`.
model = AMIModel(str(ibis.dll_path))
model.initialize(initializer)
log.info("AMI_Init() message: %s", model.msg.decode().strip())
log.info("AMI_Init() output parameters: %s", model.ami_params_out)
h_out = np.array(model.initOut)  # Channel impulse response, convolved with the model's

# Run a random NRZ bit stream through `AMI_GetWave()`, if the model has one.
if model.has_getwave:
    bits = np.random.randint(2, size=1000)
    wave_in = np.repeat(2.0 * bits - 1.0, 32)
    wave_out, clock_times, params_out = model.getWave(wave_in)

    # Plot the first 50 bits of the input and output waveforms (needs `matplotlib`).
    import matplotlib.pyplot as plt

    n = 50 * 32
    t_ns = np.arange(n) * sample_interval * 1e9
    plt.plot(t_ns, wave_in[:n], label="wave_in")
    plt.plot(t_ns, wave_out[:n], label="wave_out")
    plt.xlabel("Time (ns)")
    plt.ylabel("Amplitude (V)")
    plt.legend()
    plt.show()
```

## Command Line Tools

| Command        | Purpose                                                                | Extra      |
|----------------|------------------------------------------------------------------------|------------|
| `test-model`   | Test an IBIS-AMI model, producing a PDF report                         | `report`   |
| `check-ami`    | Run the `[AMI Test Configuration]` blocks of an IBIS 8.0 file          | (core)     |
| `run-notebook` | Run a Jupyter notebook on an IBIS-AMI model                            | `notebook` |
| `run-tests`    | Run EmPy-based tests on an AMI model DLL, producing XML output (older) | `report`   |
| `ami-config`   | Generate model C++ source, `.ibs`, and `.ami` files (deprecated)       | (core)     |

All commands accept `-h`/`--help`.

### IBIS-AMI Model Testing

**PyIBIS-AMI Native:**

```bash
% test-model -h
Usage: test-model [OPTIONS] IBIS_FILE

Options:
  -m, --model TEXT   Name of IBIS-AMI model to test.
  -p, --params TEXT  Directory containing test configuration sweeps.
  -d, --debug        Provide extra debugging information.
  --version          Show the version and exit.
  -h, --help         Show this message and exit.
```

**IBIS v8.0:**

Runs the `[AMI Test Configuration]` blocks of an IBIS 8.0 file (§10.11).
From Python, use `pyibisami.testing.ami_test_config.run_ami_test_config()` (one configuration)
or `run_all_ami_test_configs()` (all of a model's).

```bash
% check-ami -h
Usage: check-ami [OPTIONS] IBIS_FILE

  Run [AMI Test Configuration] blocks embedded in an IBIS file (IBIS 8.0
  §10.11).

  Parses IBIS_FILE, locates the target model, then calls AMI_Init() (and
  AMI_GetWave() for Time_domain configs) and compares the outputs against the
  golden data files referenced in each [AMI Test Configuration] block.

  Exits with status 1 if any configuration fails.

Options:
  -m, --model-name TEXT  Name of the [Model] to test.  Required when the .ibs
                         file defines more than one model.
  -c, --config TEXT      Name of a single [AMI Test Configuration] to run.
                         Runs all configs when omitted.
  --tol-ir FLOAT         Absolute tolerance for impulse-response comparison.
                         [default: 1e-06]
  --tol-wave FLOAT       Absolute tolerance for waveform comparison.
                         [default: 1e-06]
  -h, --help             Show this message and exit.
```
