''' setup.py - Distutils setup file for PyIBIS-AMI package

    David Banas
    July 7, 2012
'''

from distutils.core import setup

setup(
    name='PyIBIS-AMI',
    version='0.4',
    packages=['pyibisami',],
    package_data={
        'pyibisami': ['tests/*.em', 'test_results.x?l', '*.png'],
    },
    license='BSD',
    long_description=open('README.txt').read(),
    url='https://github.com/capn-freako/PyAMI/wiki',
    author='David Banas',
    author_email='capn.freako@gmail.com',
)
