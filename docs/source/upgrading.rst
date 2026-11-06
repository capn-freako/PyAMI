Upgrading
=========

From v10.x to v11.0
-------------------

Version 11.0 removes *Traits*, *TraitsUI*, *Chaco*, *Enable* and *PyFace* entirely: the model classes
(``AMIParamConfigurator``, ``AmiParamTuner``, ``IBISModel``, ``Component``, ``Model``) are plain Python classes,
illegal values raise ``pyibisami.events.InvalidValueError``, changes are announced through ``pyibisami.events.Signal``,
and the GUI is rebuilt on Qt (PySide6). *PyIBIS-AMI* ships no compatibility shims.

How much work the upgrade is depends on how your application uses *PyIBIS-AMI*:

=========================================  ===================================================================
Your application...                        Path
=========================================  ===================================================================
uses no GUI (scripts, CLIs, reports)       :ref:`upgrade-renames`: renames only.
has its own GUI, not built on Traits       :ref:`upgrade-renames`, then embed the Qt widgets
                                           (``pyibisami.gui``) or connect your own to the ``Signal`` s.
is built on Traits/TraitsUI (e.g. PyBERT)  :ref:`upgrade-renames`, then :ref:`upgrade-traits-shim`,
                                           kept in *your* application.
=========================================  ===================================================================

.. _upgrade-renames:

Renames and removals
~~~~~~~~~~~~~~~~~~~~

Every application needs these. None of the old names are kept as aliases, so each one fails loudly
(``AttributeError``/``ImportError``) rather than silently doing something else.

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
  ``ibis.select(component=, pin=, model=)``; ``ibis.selection_changed`` (``cb(component, pin, model)``).
- ``ibis.comps``, ``ibis.pins``, ``ibis.models``: ``ibis.component_choices``, ``pin_choices``, ``model_choices``.
- ``ibis.comp_``: ``ibis.component``. ``ibis.pin_``, ``ibis.pin_rlcs``: ``ibis.pin`` (a ``Pin``: ``pin``,
  ``signal``, ``model``, ``r_pin``, ``l_pin``, ``c_pin``).
- ``ibis.model_dict``: ``ibis.model_names``, ``get_model()``, ``components``, ``model_selectors``.
- ``ibis.get_models()``: ``ibis.get_model_names()``. ``Component.pin``: ``ibis.pin``, or ``Component.pin_table``.
- ``Model.plot_iv`` (Chaco): ``pyibisami.gui.IVPlot(model.iv_data, keyword="pulldown")`` (one tab per table:
  ``pulldown``, ``pullup``, ``gnd_clamp``, ``power_clamp``).
- ``Model`` display values (``vmeas``, ``vrange``, ...) are read-only properties.

Changes that don't fail loudly (check your code for them):

- ``IVCurve.ground_referenced()`` no longer negates ``[Pullup]``/``[POWER Clamp]`` currents: every table keeps the
  IBIS sense (positive into the pin). Code that flipped them back, or relied on the flip, now gets the other sign.
  ``IVData.series()`` converts each corner with that corner's ``[Voltage Range]``, and leaves out ``NA`` cells.
- An ``IBISModel`` fires the first model's ``alert`` while loading, before you can connect: read ``last_alert``.
  A ``model_types`` change that keeps the selection fires ``choices_changed``, not ``selection_changed``.

New in 11.0: ``Model.waveforms``/``rising``/``falling`` (``[Rising Waveform]``/``[Falling Waveform]``; see
``pyibisami.ibis.vt``), ``IVCurve.na_min``/``na_max``, ``IBISModel.from_text()``, and the `pyibisami-gui` viewer.

.. _upgrade-traits-shim:

A Traits adapter for Traits applications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An application whose views are built on Traits/TraitsUI (*PyBERT*, for one) can keep them by wrapping the plain
objects in a small ``HasTraits`` adapter. Keep the adapter in your application, which already depends on *Traits*:
*PyIBIS-AMI*'s core must stay importable without it.

Give the adapter **only the 11.0 names**. Re-adding ``comp``/``pin``/``mod`` would hide the renames in one place
while the rest of the code (and anything that reaches the plain object) uses the new ones; instead, make the old
names fail with a pointer to their replacements, so each use is found and updated once.

The adapter mirrors the plain object in both directions: user edits on a trait are pushed to the core setter (which
validates), and the core's ``Signal`` refreshes the traits. A flag stops the two from triggering each other.

.. code-block:: python

    from traits.api import Bool, HasTraits, Instance, List, Str, TraitError, observe

    from pyibisami.events import InvalidValueError
    from pyibisami.ibis.file import IBISModel

    _SELECTION = ("component_name", "pin_name", "model_name")
    _RENAMED = {
        "comp": "component_name", "pin": "pin_name", "mod": "model_name",
        "comps": "component_choices", "pins": "pin_choices", "models": "model_choices",
        "model_dict": "components / model_names / model_selectors",
    }


    class IbisTraits(HasTraits):
        "Traits view of an ``IBISModel``, with the 11.0 names only."

        ibis = Instance(IBISModel)
        component_name = Str()
        pin_name = Str()
        model_name = Str()
        component_choices = List(Str)
        pin_choices = List(Str)
        model_choices = List(Str)
        _syncing = Bool(False)

        def __init__(self, ibis: IBISModel, **kwargs):
            super().__init__(ibis=ibis, **kwargs)
            self._pull()
            self._disconnects = [ibis.selection_changed.connect(lambda *_: self._pull()),
                                 ibis.choices_changed.connect(self._pull)]

        def close(self) -> None:
            "Stop following the ``IBISModel`` (or it keeps this adapter alive)."
            for disconnect in self._disconnects:
                disconnect()

        def _pull(self) -> None:  # core -> traits
            self._syncing = True
            try:
                self.trait_set(
                    component_choices=self.ibis.component_choices,
                    pin_choices=self.ibis.pin_choices,
                    model_choices=self.ibis.model_choices,
                    **{name: getattr(self.ibis, name) for name in _SELECTION},
                )
            finally:
                self._syncing = False

        @observe(",".join(_SELECTION), post_init=True)
        def _push(self, event) -> None:  # traits -> core
            if self._syncing:
                return
            try:
                setattr(self.ibis, event.name, event.new)
            except InvalidValueError as err:
                self._pull()  # put the trait back to the core's (unchanged) value
                raise TraitError(str(err)) from err

        def __getattr__(self, name):
            if name in _RENAMED:
                raise AttributeError(f"{name!r} was removed in pyibisami 11.0; use {_RENAMED[name]!r}")
            raise AttributeError(name)

An ``AMIParamConfigurator`` adapter follows the same pattern, with one trait per settable parameter:

.. code-block:: python

    from traits.api import Any, HasTraits

    from pyibisami.ami.configurator import AMIParamConfigurator, display_name


    class AmiTraits(HasTraits):
        "Traits view of an ``AMIParamConfigurator``: one trait per settable parameter, named by ``display_name()``."

        def __init__(self, cfg: AMIParamConfigurator, **kwargs):
            super().__init__(**kwargs)
            self.cfg = cfg
            self._paths = {display_name(path): path for path, _ in cfg.iter_settable()}
            for name, path in self._paths.items():
                self.add_trait(name, Any(cfg.fetch_param_val(path)))
            self._syncing = False
            self.observe(self._push, list(self._paths))
            self._disconnect = cfg.values_changed.connect(self._pull)

        def _pull(self, path, old, new) -> None:  # core -> traits
            self._syncing = True
            try:
                setattr(self, display_name(path), new)
            finally:
                self._syncing = False

        def _push(self, event) -> None:  # traits -> core (validates; raises InvalidValueError)
            if not self._syncing:
                self.cfg.set_param_val(self._paths[event.name], event.new)

Points to get right:

- **Threads**: a ``Signal`` calls its callbacks on the thread that made the change. If a worker thread changes the
  core object while a TraitsUI view is open, deliver the refresh to the UI thread (e.g. ``observe(...,
  dispatch="ui")`` on the view's side, or ``pyface.api.GUI.invoke_later(self._pull)``).
- **Errors**: the core raises ``InvalidValueError``, not ``TraitError``; translate it where your views expect
  ``TraitError``, as above.
- **Lifetime**: ``Signal.connect()`` holds the callback strongly; call the returned disconnect function when the
  adapter is discarded.
- **Display names vs. model names**: trait names come from ``display_name()`` (``tx_tap_pre1``), but the paths
  sent to ``set_param_val()`` and to the model keep the ``.ami`` file's names (``-1``).
- **Check the payloads** before relying on them: ``selection_changed(component, pin, model)``, ``choices_changed()``,
  ``values_changed(path, old, new)``, ``sim_corner_changed(old, new)``, ``alert(msg)``.

From v9.x to v10.0
------------------

Version 10.0 makes the GUI, report, and notebook dependencies optional, as well as *SciPy* (now in ``report``).
If you relied on them being installed along with *PyIBIS-AMI*,
install the appropriate extra (see :doc:`install`); e.g. - `pip install 'pyibis-ami[all]'`

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
