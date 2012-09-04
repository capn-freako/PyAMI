''' setup.py - Distutils setup file for PyIBIS-AMI package

    David Banas
    July 7, 2012
'''

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup

setup(
    name='PyIBIS-AMI',
    version='0.9',
    packages=['pyibisami',],
    package_data={
        'pyibisami': ['tests/*.em', 'test_results.x?l', '*.png', 'test_runs/*.run'],
    },
    install_requires = ['EmPy', 'numpy', 'matplotlib'],
    license='BSD',
    long_description=open('README.txt').read(),
    url='https://github.com/capn-freako/PyAMI/wiki',
    author='David Banas',
    author_email='capn.freako@gmail.com',
)

