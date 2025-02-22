[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/capn-freako/PyAMI/master.svg)](https://results.pre-commit.ci/latest/github/capn-freako/PyAMI/master)

# PyIBIS-AMI

PyIBIS-AMI is a Python package of tools useful in the development and testing of IBIS-AMI models.
This library is used in [PyBERT](https://github.com/capn-freako/PyBERT) and also provides two
command line applications.

It can be installed via: `pip install PyIBIS-AMI`.

[View API/Developer's Documentation.](https://pyibis-ami.readthedocs.io/en/latest/)

## Command Line Tools

### Run IBIS-AMI Model Testing Notebook

```shell
$ run-notebook -h
Usage: run-notebook [OPTIONS] IBIS_FILE BIT_RATE

  Run a *Jupyter* notebook on an IBIS-AMI model file.

Options:
  -n, --notebook PATH  Override the default notebook file name.
  -o, --out-dir PATH   Override the name of the directory in which to place
                       the results.
  -p, --params TEXT    Directory (or, file) containing configuration sweeps.
  --debug              Provide extra debugging information.
  --is_tx              Flags a Tx model.
  --nspui INTEGER      Number of samples per unit interval.  [default: 32]
  --nbits INTEGER      Number of bits to run in simulations.  [default: 200]
  --plot-t-max FLOAT   Maximum time value for plots (s).  [default: 5e-10]
  --f-max FLOAT        Maximum frequency for transfer functions (Hz).
                       [default: 40000000000.0]
  --f-step FLOAT       Frequency step for transfer functions (Hz).  [default:
                       10000000.0]
  --fig-x INTEGER      x-dimmension for plot figures (in).  [default: 10]
  --fig-y INTEGER      y-dimmension for plot figures (in).  [default: 3]
  --version            Show the version and exit.
  -h, --help           Show this message and exit.
```

### AMI Config

```shell
ami_config -h
Usage: ami_config [OPTIONS] PY_FILE

  Configure IBIS-AMI model C++ source code, IBIS model, and AMI file.

  py_file: name of model configuration file (*.py)

Options:
  -h, --help  Show this message and exit.
```

### Run Tests

```shell
run_tests -h
Usage: run_tests [OPTIONS] [TESTS]...

  Run a series of tests on a AMI model DLL file.

  If no tests are specified on the command line, run all tests found in
  `test_dir'. (See `-t' option.)

  usage: %prog [options] [test1 [test2 ...]]

  Tests are written in the EmPy templating language, and produce XML output.
  (See the examples provided in the `examples' directory of the `pyibisami'
  Python package.)

  Test results should be viewed by loading the XML output file into a Web
  browser. By default, the XML output file refers to the supplied XSLT file,
  `test_results.xsl'. It is possible that you may need to copy this file
  from the pyibisami package directory to your local working directory, in
  order to avoid file loading errors in your Web browser.

Options:
  -t, --test_dir PATH  Sets the name of the directory from which tests are
                       taken.
  -m, --model PATH     Sets the AMI model DLL file name.
  -p, --params TEXT    List of lists of model configurations. Format:
                       <filename> or [(name, [(label, ({AMI params., in
                       "key:val" format},{Model params., in "key:val"
                       format})), ...]), ...]
  -x, --xml_file PATH  Sets the name of the XML output file. You should load
                       this file into your Web browser after the program
                       completion.
  -r, --ref_dir PATH   Sets the name of the directory from which reference
                       waveforms are taken.
  -o, --out_dir PATH   Sets the name of the directory in which to place the
                       results.
  -v, --version TEXT   Show program version info and exit.
  -h, --help           Show this message and exit.
  ```
