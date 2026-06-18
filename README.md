[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/capn-freako/PyAMI/master.svg)](https://results.pre-commit.ci/latest/github/capn-freako/PyAMI/master)

# PyIBIS-AMI

PyIBIS-AMI is a Python package of tools useful in the development and testing of IBIS-AMI models.
This library is used in [PyBERT](https://github.com/capn-freako/PyBERT) and also provides three
command line applications.

It can be installed via: `pip install PyIBIS-AMI`.

[View API/Developer's Documentation.](https://pyibis-ami.readthedocs.io/en/latest/)

## Command Line Tools

### IBIS-AMI Model Testing

**PyIBIS-AMI Native:**

```
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

### IBIS-AMI Model Pre-build Configuration

```
ami_config -h
Usage: ami_config [OPTIONS] PY_FILE

  Configure IBIS-AMI model C++ source code, IBIS model, and AMI file.

  py_file: name of model configuration file (*.py)

Options:
  -h, --help  Show this message and exit.
```
