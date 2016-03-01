#! /usr/bin/env python

"""
IBIS-AMI model source code and AMI file configuration utility.

Original author: David Banas
Original date:   February 26, 2016

This script gets called from a makefile, when either a C++ source code
file, or a *.AMI file, needs to be built from a EmPy template. This
gets triggered by one of two things:
    1. The common model configuration information has changed, or
    2. One of the EmPy template files was updated.

The idea, here, is that both the *.AMI file and the device specific
C++ source file should be configured from a common model configuration
file, so as to ensure consistency between the *.AMI file and the DLLs.

Copyright (c) 2016 David Banas; all rights reserved World wide.
"""

import argparse
import em
import imp

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
    parser = argparse.ArgumentParser(description='Configure IBIS-AMI model source code and/or *.AMI file.')
    parser.add_argument('out_file', type=str, help='name of generated file (*.cpp/ami)')
    parser.add_argument('em_file',  type=str, help='name of EmPy template file (*.em)')
    parser.add_argument('py_file',  type=str, help='name of model configuration file (*.py)')
    args = parser.parse_args()

    out_file = args.out_file
    em_file  = args.em_file
    py_file  = args.py_file

    with open(py_file, 'rt') as cfg_file:
        cfg = imp.load_module(py_file.rsplit('.', 1)[0], cfg_file, py_file, ('py', 'r', imp.PY_SOURCE))

    with open(out_file, 'wt') as out_file:
        interpreter = em.Interpreter(
            output = out_file,
            globals = {
                'ami_params'  : cfg.ami_params,
                'param_types' : param_types,
                'model_name'  : cfg.kFileBaseName,
                'description' : cfg.kDescription,
                }
            )
        try:
            interpreter.file(open(em_file))
        finally:
            interpreter.shutdown()

if __name__=="__main__":
    main()

