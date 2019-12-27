""" setup.py - Distutils setup file for PyIBIS-AMI package

    David Banas
"""
from setuptools import setup, find_packages

setup(
    name="PyIBIS-AMI",
    version="3.3.0",
    packages=find_packages(exclude=["docs", "tests"]),
    include_package_data=True,
    description="Facilitates working directly with IBIS-AMI DLLs from the Python command prompt.",
    install_requires=[
        "Click",
        "empy",
        "numpy",
        "scipy",
        "matplotlib",
        "parsec",
        "traits",
        "traitsui",
    ],
    entry_points={
        "console_scripts": [
            "ami-config = pyibisami.ami_config:main",
            "run-tests = pyibisami.run_tests:main",
        ]
    },
    license="BSD",
    long_description=open("README.md").read(),
    url="https://github.com/capn-freako/PyAMI/wiki",
    author="David Banas",
    author_email="capn.freako@gmail.com",
    keywords=["ibis-ami"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: System :: Emulators",
        "Topic :: Utilities",
    ],
)
