""" setup.py - Distutils setup file for PyIBIS-AMI package

    David Banas
"""
from setuptools import find_packages, setup

setup(
    name="PyIBIS-AMI",
    version="3.5.7",
    package_dir={'': 'src'},
    packages=find_packages(where='src', exclude=["docs", "tests"]),
    include_package_data=True,
    description="Facilitates working directly with IBIS-AMI DLLs from the Python command prompt.",
    install_requires=[
        "click==8.1.3",
        "empy==3.3.4",
        "numpy==1.23.3",
        "scipy==1.9.2",
        "matplotlib==3.6.1",
        "parsec==3.14",
        "traits==6.4.1",
        "traitsui==7.4.1",
        "chaco==5.0.0",
        "enable==5.3.1",
    ],
    entry_points={
        "console_scripts": [
            "ami-config = pyibisami.ami.config:main",
            "run-tests = pyibisami.tools.run_tests:main",
        ]
    },
    license="BSD",
    long_description=open("README.md").read(),
    url="https://github.com/capn-freako/PyAMI/wiki",
    author="David Banas",
    author_email="capn.freako@gmail.com",
    keywords=["ibis-ami"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: System :: Emulators",
        "Topic :: Utilities",
    ],
)
