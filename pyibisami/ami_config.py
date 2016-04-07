#! /usr/bin/env python

"""
IBIS-AMI model source code, AMI file, and IBIS file configuration utility.

Original author: David Banas
Original date:   February 26, 2016

This script gets called from a makefile, when any of the following need
rebuilding:
  - a C++ source code file
  - a *.AMI file
  - a *.IBS file
and rebuilds all three.
(We rebuild all three, because it doesn't take very long, and we can
insure consistency this way.)

This gets triggered by one of two things:
    1. The common model configuration information has changed, or
    2. One of the EmPy template files was updated.

The idea, here, is that the *.IBS file, the *.AMI file, and the
C++ source file should be configured from a common model configuration
file, so as to ensure consistency between the three.

Copyright (c) 2016 David Banas; all rights reserved World wide.
"""

import argparse
import em
import imp
import os.path as op
from datetime import date

param_types = {
    'INT' : {
        'c_type'   : 'int',
        'ami_type' : 'Integer',
        'getter'   : 'get_param_int',
        },
    'FLOAT' : {
        'c_type'   : 'float',
        'ami_type' : 'Float',
        'getter'   : 'get_param_float',
        },
    'BOOL' : {
        'c_type'   : 'bool',
        'ami_type' : 'Boolean',
        'getter'   : 'get_param_bool',
        },
    'STRING' : {
        'c_type'   : 'char *',
        'ami_type' : 'String',
        'getter'   : 'get_param_str',
        },
    }

def main():
    parser = argparse.ArgumentParser(description='Configure IBIS-AMI model C++ source code, IBIS model, and AMI file.')
    parser.add_argument('py_file',  type=str, help='name of model configuration file (*.py)')
    args = parser.parse_args()

    # Confirm the existence of the model configuration file.
    py_file  = args.py_file
    if(not op.isfile(py_file)):
        raise RuntimeError("Model configuration file, %s, not found." % (py_file))
    else:
        py_file = op.abspath(py_file)

    file_base_name = op.splitext(op.basename(py_file))[0]

    # Read model configuration information.
    print "Reading model configuration information from file: %s." % (py_file)
    with open(py_file, 'rt') as cfg_file:
        cfg = imp.load_module(file_base_name, cfg_file, py_file, ('py', 'r', imp.PY_SOURCE))

    # Configure the 3 files.
    for ext in ['cpp', 'ami', 'ibs']:
        out_file = file_base_name + '.' + ext
        if(ext == 'ami'):
            em_file  = op.dirname(__file__) + '/generic.ami.em'
        else:
            em_file  = out_file + '.' + 'em'
        print "Buidling '%s' from '%s'..." % (out_file, em_file)
        with open(out_file, 'wt') as out_file:
            interpreter = em.Interpreter(
                output = out_file,
                globals = {
                    'ami_params'  : cfg.ami_params,
                    'ibis_params' : cfg.ibis_params,
                    'param_types' : param_types,
                    'model_name'  : cfg.kFileBaseName,
                    'description' : cfg.kDescription,
                    'date'        : str(date.today()),
                    }
                )
            try:
                interpreter.file(open(em_file))
            finally:
                interpreter.shutdown()

if __name__=="__main__":
    main()

