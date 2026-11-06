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

Upgrading from v10.x
--------------------

Version 11.0 removes *Traits*, *TraitsUI*, *Chaco*, *Enable* and *PyFace* entirely: the model classes are plain
Python classes, and the GUI is rebuilt on Qt (PySide6). There are no compatibility shims.

- ``except TraitError`` on an illegal value: ``except InvalidValueError`` (``pyibisami.events``; a ``ValueError``).
- ``from pyibisami.ami.parser import AMIParamConfigurator``: import it from ``pyibisami.ami.configurator``.
- ``cfg.<trait name>``, ``cfg.trait_set(...)``: ``cfg.fetch_param_val(path)``, ``cfg.set_param_val(path, value)``;
  also ``cfg.current_values()``/``apply_values()``/``reset_to_defaults()``.
- ``cfg.observe(cb, name)``: ``cfg.values_changed.connect(cb)`` (``cb(path, old, new)``); ``cfg.sim_corner_changed``.
- ``cfg()``, ``ibis()``, ``comp()``, ``model()``: ``cfg.open_gui()``, ``ibis.open_gui()``; or embed
  ``AmiParamEditor``/``IbisBrowser`` (``pyibisami.gui``).
- ``get_init(...)`` without ``ami_params`` no longer opens a GUI: it sends the current values (``input_ami_params``).
- ``make_param_traits()``, ``trait_name_part()``: gone; ``display_name_part()``/``display_name()`` give the
  ``pre1``/``post0`` display names.
- ``AmiParamTuner`` is a dataclass, with the same fields.
- ``ibis.observe(cb, "alert")`` (``event.new``): ``ibis.alert.connect(cb)`` (``cb(msg)``).
- ``ibis.comp``, ``ibis.pin``, ``ibis.mod`` (names): ``ibis.component_name``, ``ibis.pin_name``, ``ibis.model_name``;
  ``ibis.select(component=, pin=, model=)``; ``ibis.selection_changed``.
- ``ibis.comps``, ``ibis.pins``, ``ibis.models``: ``ibis.component_choices``, ``pin_choices``, ``model_choices``.
- ``ibis.comp_``: ``ibis.component``. ``ibis.pin_``, ``ibis.pin_rlcs``: ``ibis.pin`` (a ``Pin``: ``pin``,
  ``signal``, ``model``, ``r_pin``, ``l_pin``, ``c_pin``).
- ``ibis.model_dict``: ``ibis.model_names``, ``get_model()``, ``components``, ``model_selectors``.
- ``ibis.get_models()``: ``ibis.get_model_names()``. ``Component.pin``: ``ibis.pin``, or ``Component.pin_table``.
- ``Model.plot_iv`` (Chaco): ``pyibisami.gui.IVPlot(model.iv_data)``.
- ``Model`` display values (``vmeas``, ``vrange``, ...) are read-only properties.

New in 11.0: ``Model.waveforms``/``rising``/``falling`` (``[Rising Waveform]``/``[Falling Waveform]``; see
``pyibisami.ibis.vt``), ``IVCurve.na_min``/``na_max``, ``IBISModel.from_text()``, and the `pyibisami-gui` viewer.

Upgrading from v9.x
-------------------

Version 10.0 makes the GUI, report, and notebook dependencies optional, as well as *SciPy* (now in ``report``).
If you relied on them being installed along with *PyIBIS-AMI*,
install the appropriate extra (see above); e.g. - `pip install 'pyibis-ami[all]'`

Other changes affecting library users:

- ``make_gui()`` and ``make_gui_items()`` moved from ``pyibisami.ami.parser``
  to ``pyibisami.gui.ami_config``, and no longer return ``Trait`` s.
  The ``Trait`` s are built by the new ``pyibisami.ami.configurator.make_param_traits()``.
- ``AMIParamConfigurator`` moved from ``pyibisami.ami.parser`` to the new ``pyibisami.ami.configurator``
  (with ``make_param_traits()`` and ``trait_name_part()``); the old imports still work.
- Tap parameters (named ``-1``, ``0``, ``1``, ...) get trait names ``pre1``, ``post0``, ``post1``, ...
  (e.g. - ``tx_tap_pre1``), since tap numbers aren't valid trait names.
  The names sent to the model, and the ``branch_names`` paths of ``fetch_param_val()``/``set_param_val()``,
  keep the ``.ami`` file's names.
- Every ``.ami`` ``Format`` now parses. ``Increment``/``Steps`` parameters offer only their legal values;
  ``Corner`` parameters follow the new ``AMIParamConfigurator.sim_corner`` (``typ``/``min``/``max``);
  ``Table``, ``Gaussian``, ``Dual-Dirac`` and ``DjRj`` parameters are sent as written, with no trait.
  A parameter that can't be built is skipped, with a warning in ``ami_parsing_errors``; the rest of the file loads.
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
- ``IBISModel`` takes no ``is_tx`` argument (removed in v9.0; ``IBISModel(ibis_file, True)`` raises ``TypeError``).
  To offer only Tx (or Rx) pins in its selector, use the new keyword-only ``model_types`` argument;
  e.g. - ``IBISModel(ibis_file, model_types=TX_MODEL_TYPES)``
  (``TX_MODEL_TYPES``/``RX_MODEL_TYPES`` are in ``pyibisami.ibis.file``).
  Its views' titles no longer mention *PyBERT*, and the selector's ``id`` is now ``pyibisami_ibis_model_selector``.
- ``IBISModel`` raises ``ValueError`` (``Couldn't parse IBIS file ...``, with the line and column)
  when the file doesn't parse, instead of logging a warning.
  Spec violations that don't stop loading are appended to ``ibis_parsing_errors``.
- ``IBISModel.dll_file``/``ami_file`` now come from the selected model (``Model.dll_file``/``ami_file``),
  and the new ``dll_path``/``ami_path`` give them resolved against ``ibis_dir``.
  They take the model's first ``Executable`` line for this platform, whatever its direction;
  for an ``I/O`` model with both ``Executable_Tx`` and ``Executable_Rx``, use ``Model.get_ami_files(is_tx)``.
  The private ``Model._exec32Wins`` etc. were removed; ``Model.ami_files`` and ``Model.executables`` remain.
- ``Model.zout``/``slew``/``zin`` are ``None`` (and the ``Model`` has no such trait) where the ``Model_type``
  or its data gives no value; they are now also set for ``3-state``, ``Open_*`` and ``I/O_open_*`` models.
- ``IBISModel.log()`` and ``IBISModel.log_txt`` were removed,
  as was the ``debug`` argument of ``IBISModel`` and ``pyibisami.ibis.parser.parse_ibis_file()``.
  *PyIBIS-AMI* reports through the standard ``logging`` module, under the ``pyibisami`` logger,
  and (as a library) never configures logging itself; configure it in your application,
  e.g. - ``logging.basicConfig(level=logging.INFO)``.
  (For IBIS parsing details, enable ``DEBUG`` for the ``pyibisami.ibis`` logger.)
  The command line tools do configure it, sending ``INFO`` (``DEBUG``, with ``--debug``) messages to the console.
- The PDF/plot reporting modules moved into the new ``pyibisami.report`` package,
  which requires the ``report`` extra:

  =======================================  ======================================
  Old                                      New
  =======================================  ======================================
  ``pyibisami.testing.test_models``        ``pyibisami.report.test_models``
  ``pyibisami.testing.ami_tests``          ``pyibisami.report.ami_tests``
  ``pyibisami.testing.ami_tests_helpers``  ``pyibisami.report.ami_tests_helpers``
  ``pyibisami.testing.ibis_file_tests``    ``pyibisami.report.ibis_file_tests``
  ``pyibisami.util.plot``                  ``pyibisami.report.plot``
  ``pyibisami.util.reportlab``             ``pyibisami.report.pdf``
  =======================================  ======================================

  ``pyibisami.testing`` (test definitions, ``[AMI Test Configuration]`` runner) needs only the core install.
  The ``debug`` argument was also removed from the functions that only passed it on to ``IBISModel``
  (``get_ibis_contents()``, ``test_ami_models()``, ``test_ibis_ami_models()``, ``mk_default_test_sweep_file()``),
  and from ``pyibisami.report.plot.plot_resps()``, whose debugging output is now logged.
- `test-model` now exits with status 1 (and an ``Error:`` message) when testing fails, instead of 0.

Testing the installation
------------------------

Either way, as a check on correct installation, run the following command:

`python -c "import pyibisami"`

And if you don't get a traceback/error then you've installed the package successfully!
