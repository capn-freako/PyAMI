''' setup.py - Distutils setup file for PyIBIS-AMI package

    David Banas
    July 7, 2012
'''

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup

setup(
    name='PyIBIS-AMI',
    version='2.0.1',
    packages=['pyibisami',],
    description='Facilitates working directly with IBIS-AMI DLLs from the Python command prompt.',
    package_data={
        'pyibisami': ['tests/*.em', 'test_results.x?l', '*.png', 'test_runs/*.run', 'generic*.em'],
    },
    install_requires = [
        'empy',
        'numpy>=1.10.4',
        'scipy>=0.17.1',
        'matplotlib>=1.5.1',
        'parsec',
        ],
    license='BSD',
    long_description=open('README.txt').read(),
    url='https://github.com/capn-freako/PyAMI/wiki',
    author='David Banas',
    author_email='capn.freako@gmail.com',
    keywords = ['ibis-ami', ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: System :: Emulators",
        "Topic :: Utilities"
    ]
)

