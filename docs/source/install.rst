Installation Instructions
=========================

Installation into system Python environment
-------------------------------------------

If you don't mind installing *PyIBIS-AMI* into your system Python package library then installation is as simple as:

`pip install pyibis-ami`

Installation into custom virtual Python environment
---------------------------------------------------

If, instead, you'd prefer to confine the *PyIBIS-AMI* package to a virtual environment, thus protecting your system Python installation from it, then execute these commands, in order:

1. `python3 -m venv ~/.venv/pyibisami` (Creates a new Python virtual environment named "pyibisami".)

2. `. ~/.venv/pyibisami/bin/activate` (on Windows: `. ~/.venv/pyibisami/Scripts/activate`) (Activates the new environment.)

    - At this point, you should begin seeing "(pyibisami)" at the beginning of your command prompt, indicating that you have activated your `pyibisami` Python virtual environment activated.

3. `pip install pyibis-ami` (Installs the *PyIBIS-AMI* package into your new virtual environment.)

Testing the installation
------------------------

Either way, as a check on correct installation, run the following command:

`python -c "import pyibisami"`

And if you don't get a traceback/error then you've installed the package successfully!
