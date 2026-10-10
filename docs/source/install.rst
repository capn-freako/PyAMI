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
``gui``        `chaco`, `enable`, `traitsui`                 GUIs: ``AMIParamConfigurator.open_gui()``,
                                                             calling ``IBISModel``/``Component``/``Model``
                                                             instances, ``Model.plot_iv``
``report``     `matplotlib`, `reportlab`                     `test-model` & `run-tests` (PDF/plot reports)
``notebook``   `jupyter`, `papermill`, `lxml-html-clean`,    `run-notebook`
               `matplotlib`
``all``        all of the above
=============  ============================================  ====================================================

Several extras may be combined, e.g.: `pip install 'pyibis-ami[gui,report]'`

Using a feature whose extra isn't installed raises an ``ImportError`` naming the extra to install.

The ``gui`` extra doesn't install a Qt binding, so that applications (e.g. - *PyBERT*) may choose their own.
If none is chosen (via the ``QT_API`` environment variable), the first one installed is used.
If you have none, install one; e.g.: `pip install pyside6`

Upgrading from v9.x
-------------------

Version 10.0 makes the GUI, report, and notebook dependencies optional.
If you relied on them being installed along with *PyIBIS-AMI*,
install the appropriate extra (see above); e.g. - `pip install 'pyibis-ami[all]'`

Other changes affecting library users:

- ``make_gui()`` and ``make_gui_items()`` moved from ``pyibisami.ami.parser``
  to ``pyibisami.gui.ami_config``, and no longer return ``Trait`` s.
  The ``Trait`` s are built by the new ``pyibisami.ami.parser.make_param_traits()``.
- The I-V curve data of an IBIS ``[Model]`` is now available, without any GUI dependency,
  via ``Model.iv_data`` (see ``pyibisami.ibis.iv``).
  ``Model.plot_iv`` is still available, but now requires the ``gui`` extra,
  and is built upon first access.
- ``IBISModel`` no longer takes a ``gui`` argument, and never opens dialogs on its own.
  Its notices are sent to the ``pyibisami.ibis.file`` logger (``INFO``; other messages at ``DEBUG``)
  and fired through its new ``alert`` event (a Traits ``Event(Str)``), which applications may observe.
  ``pyibisami.gui.ibis.show_alerts(ibis)`` shows them as pop-up dialogs;
  calling the ``IBISModel`` instance (to open its GUI) does this automatically.
  The notice texts are now application-neutral (no references to *PyBERT* tabs).
- ``IBISModel.log()`` and ``IBISModel.log_txt`` were removed, and its ``debug`` argument no longer prints to the console.
  *PyIBIS-AMI* reports through the standard ``logging`` module, under the ``pyibisami`` logger,
  and (as a library) never configures logging itself; configure it in your application,
  e.g. - ``logging.basicConfig(level=logging.INFO)``.
  The command line tools do configure it, sending ``INFO`` (``DEBUG``, with ``--debug``) messages to the console.

Testing the installation
------------------------

Either way, as a check on correct installation, run the following command:

`python -c "import pyibisami"`

And if you don't get a traceback/error then you've installed the package successfully!
