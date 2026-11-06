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

Optional features (extras)
--------------------------

The basic installation provides the core library (AMI/IBIS parsing, AMI DLL interaction)
and the `ami-config` and `check-ami` command line tools.
Everything else is an optional *extra*, installed by naming it in brackets:

`pip install 'pyibis-ami[gui]'`

=============  ============================================  ====================================================
Extra          Adds                                          Needed for
=============  ============================================  ====================================================
``gui``        `pyside6`, `matplotlib`                       The Qt widgets (``pyibisami.gui``), the
                                                             `pyibisami-gui` viewer, and ``open_gui()`` of
                                                             ``AMIParamConfigurator``/``IBISModel``
``report``     `matplotlib`, `reportlab`, `scipy`            `test-model` & `run-tests` (PDF/plot reports),
                                                             ``testing.test_defs.lossy_channel()``/
                                                             ``reflective_channel()``
``notebook``   `jupyter`, `papermill`, `lxml-html-clean`,    `run-notebook`
               plus the ``report`` extra
``all``        all of the above
=============  ============================================  ====================================================

Several extras may be combined, e.g.: `pip install 'pyibis-ami[gui,report]'`

Using a feature whose extra isn't installed raises an ``ImportError`` naming the extra to install.

The ``gui`` extra's widgets are built on PySide6.

Testing the installation
------------------------

Either way, as a check on correct installation, run the following command:

`python -c "import pyibisami"`

And if you don't get a traceback/error then you've installed the package successfully!

Getting started
---------------

Load an IBIS file, pick a model, and read its ``.ami`` parameters:

.. code-block:: python

    from pyibisami.ibis.file import IBISModel
    from pyibisami.ami.configurator import AMIParamConfigurator

    ibis = IBISModel("my_part.ibs")
    print(ibis.component_choices, ibis.pin_choices, ibis.model_choices)
    ibis.select(model=ibis.model_choices[0])
    print(ibis.dll_path, ibis.ami_path)  # this platform's AMI executable and .ami file

    cfg = AMIParamConfigurator(ibis.ami_path.read_text())
    print(cfg.current_values())

With the ``gui`` extra, `pyibisami-gui my_part.ibs` opens the same file in a viewer.
Every command line tool takes ``--help``.

Upgrading from an older version? See :doc:`upgrading`.
