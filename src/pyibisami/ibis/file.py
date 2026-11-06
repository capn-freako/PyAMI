"""A class for encapsulating IBIS model files.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

**Note:** The ``IBISModel`` class, defined here, needs to be kept separate from the
other IBIS-related classes, defined in the ``model`` module, in order to
avoid circular imports.

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

import logging
import platform
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

from ..events import InvalidValueError, Signal
from .analog import Pin

# ``TX_MODEL_TYPES``/``RX_MODEL_TYPES`` live in ``.model`` (which can't import this module); re-exported here.
from .model import RX_MODEL_TYPES, TX_MODEL_TYPES, Component, Model
from .parser import parse_ibis_file

__all__ = ["IBISModel", "RX_MODEL_TYPES", "TX_MODEL_TYPES"]

logger = logging.getLogger(__name__)

Selection = tuple[str, list[str], str, list[str], str]  # component, pin choices, pin, model choices, model


def _model_types(value: Optional[Iterable[str]]) -> Optional[frozenset[str]]:
    """``None``, or a collection of ``Model_type`` names as a lower-cased ``frozenset``.

    Raises:
        InvalidValueError: ``value`` is a single string (it would otherwise be read one character at a time), or
            not a collection.
    """
    if value is None:
        return None
    if isinstance(value, str):
        raise InvalidValueError(f"model_types must be None or a collection of Model_type names, not a string: {value!r}")
    try:
        return frozenset(str(mtype).lower() for mtype in value)
    except TypeError as err:
        raise InvalidValueError(f"model_types must be None or a collection of Model_type names; got {value!r}") from err


class IBISModel:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """A parsed IBIS file, with a selection of one component, pin and model.

    The intended use model is as follows:

     1. Instantiate this class once per IBIS file, giving its name (or use ``from_text()``).
        Any spec warnings found while parsing are in ``ibis_parsing_errors``.

     2. Select a component, pin and model: set ``component_name``, ``pin_name`` or ``model_name`` (a new component
        selects its first offered pin, and a new pin its first offered model), or several at once with
        ``select()``; or let the user do it, in the ``gui`` extra's ``IbisSelector`` (or ``open_gui()``).
        The offered names are in ``component_choices``, ``pin_choices`` and ``model_choices``; the selected
        objects in ``component``, ``pin`` (a ``Pin`` record) and ``model``.

    To offer only some kinds of pin (e.g. - only Tx pins), give the ``model_types`` to allow::

        IBISModel(ibis_file_name, model_types=TX_MODEL_TYPES)

    Signals (``pyibisami.events.Signal``):

    - ``selection_changed(component_name, pin_name, model_name)``, after any change of the selection.
    - ``choices_changed()``, after any change of ``component_choices``, ``pin_choices`` or ``model_choices``
      (e.g. - a ``model_types`` change that keeps the selection).
    - ``alert(msg)``, with each user-facing notice (e.g. - whether the selected model has an AMI
      executable for this platform); also logged. See ``pyibisami.gui.show_alerts()``. The first model's is fired
      while loading, before anyone can connect: ``last_alert`` keeps the latest.
    """

    def __init__(
        self: "IBISModel",
        ibis_file_name: str | Path,
        *,
        model_types: Optional[Iterable[str]] = None,
    ) -> None:
        """
        Args:
            ibis_file_name: The name of the IBIS file.

        Keyword Args:
            model_types: Offer only the pins (and models) with one of these ``Model_type`` s (any case);
                e.g. - ``TX_MODEL_TYPES`` or ``RX_MODEL_TYPES``. ``None`` offers all.
                May be changed later, through the ``model_types`` property.
                Default: ``None``

        Raises:
            ValueError: If the file can't be parsed, or no component has a pin to offer.
            InvalidValueError: If ``model_types`` is a single string, or not a collection.

        Notes:
            1. For parsing details, enable ``DEBUG`` logging for the ``pyibisami.ibis`` logger.
            2. A pin is offered if any of its models (e.g. - in a ``[Model Selector]``) has an allowed
                ``Model_type``; only those models are offered for it.
            3. If a later ``model_types`` change leaves nothing to offer,
                the selection is kept and an ``alert`` is fired.
        """
        logger.debug("Loading IBIS file: %s", ibis_file_name)
        with open(ibis_file_name, "r", encoding="utf-8") as file:
            text = file.read()
        self._load(text, Path(ibis_file_name).absolute().parent, str(ibis_file_name), model_types)

    @classmethod
    def from_text(
        cls, text: str, ibis_dir: str | Path = ".", *, model_types: Optional[Iterable[str]] = None
    ) -> "IBISModel":
        """An ``IBISModel`` from the contents of an IBIS file.

        Args:
            text: The IBIS file contents.
            ibis_dir: The directory the files it names (e.g. - ``Executable`` s) are resolved against.
                Default: the current directory

        Keyword Args:
            model_types: As for ``__init__``.
        """
        obj = cls.__new__(cls)
        obj._load(text, Path(ibis_dir).absolute(), "<text>", model_types)  # pylint: disable=protected-access
        return obj

    def _load(self, text: str, ibis_dir: Path, source: str, model_types: Optional[Iterable[str]]) -> None:
        "Parse ``text`` and make the initial selection."
        self.alert = Signal()
        self.selection_changed = Signal()
        self.choices_changed = Signal()
        self._last_alert: Optional[str] = None
        self._model_types = _model_types(model_types)
        self._ibis_dir = ibis_dir

        err_str, model_dict = parse_ibis_file(text)
        self._file_name: str = model_dict.get("file_name", "(n/a)")
        self._ibis_ver: Any = model_dict.get("ibis_ver", "(n/a)")
        self._file_rev: str = model_dict.get("file_rev", "(n/a)")
        self._date: str = model_dict.get("date", "(n/a)")
        if err_str != "Success!":
            raise ValueError(f"Couldn't parse IBIS file {source}: {err_str}")
        logger.debug("IBIS parsing: %s", err_str)
        if "components" not in model_dict or not model_dict["components"]:
            logger.debug("Parsed IBIS model dictionary:\n%s", model_dict)
            raise ValueError("This IBIS model has no components!")
        if "models" not in model_dict or not model_dict["models"]:
            logger.debug("Parsed IBIS model dictionary:\n%s", model_dict)
            raise ValueError("This IBIS model has no models!")

        self._models: dict[str, Model] = model_dict["models"]
        self._components: dict[str, Component] = model_dict["components"]
        self._model_selectors: dict[str, list[str]] = dict(model_dict.get("model_selectors", {}))

        # Only components with a pin naming a defined model (of an allowed ``model_types``) are offered for selection.
        # (Skipped ones remain in ``components``; e.g. - for ``get_pins_qualified()``.)
        comps = self._selectable_components()
        for cname in self._components:
            if cname not in comps:
                if self._model_types is None:
                    logger.warning("Component '%s' has no pins with a defined model; it can't be selected.", cname)
                else:
                    logger.warning("Component '%s' has no pins with a model of Model_type %s; it can't be selected.",
                                   cname, sorted(self._model_types))
        if not comps:
            raise ValueError(self._no_selectable_component())

        self._ibis_parsing_errors = err_str  # Plus any spec warnings (already logged by the parser).
        if model_dict.get("warnings"):
            self._ibis_parsing_errors += "\nWarnings:\n" + "\n".join(f"- {w}" for w in model_dict["warnings"])

        self._component_choices = comps
        self._component_name = comps[0]
        self._pin_choices = self._selectable_pins(self._components[comps[0]])
        self._pin_name = self._pin_choices[0]
        self._model_choices = self._selectable_model_names(self._pin_model(comps[0], self._pin_name))
        self._model_name = self._model_choices[0]
        self._announce_model()

    def __str__(self):
        return f"IBIS Model '{self._file_name}'"

    def info(self):
        """Basic information about the IBIS model."""
        res = "\n".join([
            f"ibis_ver:\t{self._ibis_ver}",
            f"file_name:\t{self._file_name}",
            f"file_rev:\t{self._file_rev}"])
        res += f"\ndate:\t\t{self._date}\n"
        res += "\nComponents:"
        res += "\n=========="
        for c in self._components:
            res += f"\n{c}:\n---\n{self._components[c]}\n"
        res += "\nModel Selectors:"
        res += "\n===============\n"
        for s in self._model_selectors:
            res += f"{s}\n"
        res += "\nModels:"
        res += "\n======"
        for m in self._models:
            res += f"\n{m}:\n---\n{self._models[m]}"
        return res

    def open_gui(self) -> bool:
        """Let the user select a component, pin and model, in a modal dialog.

        Requires the ``gui`` extra: ``pip install 'pyibis-ami[gui]'``.

        Returns:
            ``True`` if the user accepted the dialog (the selection follows the dialog either way).
        """
        from ..gui.dialogs import select_ibis_model  # pylint: disable=import-outside-toplevel
        return select_ibis_model(self)

    # File contents.

    @property
    def file_name(self) -> str:
        "The ``[File Name]``."
        return self._file_name

    @property
    def ibis_ver(self) -> Any:
        "The ``[IBIS Ver]``."
        return self._ibis_ver

    @property
    def file_rev(self) -> str:
        "The ``[File Rev]``."
        return self._file_rev

    @property
    def date(self) -> str:
        "The ``[Date]`` (``(n/a)`` if absent)."
        return self._date

    @property
    def last_alert(self) -> Optional[str]:
        "The latest ``alert`` message (e.g. - the first model's, fired while loading); ``None`` if none yet."
        return self._last_alert

    @property
    def ibis_parsing_errors(self) -> str:
        "The parse status, plus any spec warnings found while parsing."
        return self._ibis_parsing_errors

    @property
    def components(self) -> dict[str, Component]:
        "Every ``[Component]``, by name (including any not offered for selection)."
        return dict(self._components)

    @property
    def component_names(self) -> list[str]:
        "The names of every ``[Component]``, in file order."
        return list(self._components)

    @property
    def model_names(self) -> list[str]:
        "The names of every ``[Model]``, in file order."
        return list(self._models)

    @property
    def model_selectors(self) -> dict[str, list[str]]:
        "Each ``[Model Selector]``'s entries, by selector name."
        return dict(self._model_selectors)

    def get_model(self, mname: str) -> Model:
        """
        Retrieve the named model if it exists.

        Args:
            mname: The name of the model to fetch.

        Returns:
            The ``Model`` object with the given name.

        Raises:
            ``KeyError`` if the given model name can't be found.
        """

        return self._models[mname]

    def get_model_names(self, mname: str) -> list[str]:
        """
        Return the list of models associated with a particular name.

        Args:
            mname: The name of the requested model or model selector.

        Returns:
            A list of actual model names associated with the requested name.

        Notes:
            1. The caller may provide the name of either a model or model selector.
            2. An empty list is returned if the given name is unrecognized.
            3. A model selector's entries naming an undefined model are dropped, with a warning.
        """

        if mname in self._model_selectors:
            names = []
            for pr in self._model_selectors[mname]:
                if pr[0] in self._models:
                    names.append(pr[0])
                else:
                    logger.warning("Model selector '%s' names undefined model '%s'; ignoring it.", mname, pr[0])
            return names
        if mname in self._models:
            return [mname]
        return []

    def get_pins(self) -> list[str]:
        "All the selected component's pin names (``pin_choices`` has the ones offered)."
        return list(self.component.pins)

    def get_pins_qualified(self, is_tx: bool, comp_name: Optional[str] = None) -> list[str]:
        """
        Get the list of appropriate pins, given requested type (i.e. - Tx or Rx).

        Args:
            is_tx: Return Tx pins when ``True``; Rx pins when ``False``.

        Keyword Args:
            comp_name: Fetch the pins for the named component when given;
                otherwise, use the currently selected component.
                Default: ``None``

        Returns:
            The names of the qualifying pins, in file order.

        Raises:
            ValueError: If ``comp_name`` names no component in this file.

        Notes:
            1. A pin's direction follows its models' ``Model_type`` s (IBIS 8.0 Table 47);
                see ``TX_MODEL_TYPES`` and ``RX_MODEL_TYPES``. ``I/O`` types are both;
                ``Terminator``, ``Series`` and ``Series_switch`` are neither.
                A pin qualifies if any of its models (e.g. - in a ``[Model Selector]``) does,
                as with the ``model_types`` argument.
            2. Pins naming an undefined model are skipped. (The parser already drops ``POWER``, ``GND``, ``NC`` and ``CIRCUITCALL`` pins.)
        """
        if comp_name is None:
            comp = self.component
        elif comp_name in self._components:
            comp = self._components[comp_name]
        else:
            raise ValueError(f"No component named '{comp_name}'; available: {list(self._components)}")
        pins = comp.pins
        mtypes = TX_MODEL_TYPES if is_tx else RX_MODEL_TYPES

        def pin_ok(pname):
            (mname, _) = pins[pname]
            return any(self._models[name].mtype.lower() in mtypes for name in self.get_model_names(mname))

        return list(filter(pin_ok, list(pins)))

    # Selection.

    @property
    def model_types(self) -> Optional[frozenset[str]]:
        "The ``Model_type`` s offered for selection (lower-cased); ``None`` offers all."
        return self._model_types

    @model_types.setter
    def model_types(self, value: Optional[Iterable[str]]) -> None:
        "Re-filter the choices, keeping each selection that's still offered; undo a change that leaves nothing."
        old, self._model_types = self._model_types, _model_types(value)
        comps = self._selectable_components()
        if not comps:
            msg = self._no_selectable_component()
            self._model_types = old
            self._notify(f"{msg} Keeping the previous model_types and selection.")
            return
        # A pin is kept only with its component, and a model only with its pin.
        component = self._component_name if self._component_name in comps else comps[0]
        pins = self._selectable_pins(self._components[component])
        pin = self._pin_name if component == self._component_name and self._pin_name in pins else pins[0]
        models = self._selectable_model_names(self._pin_model(component, pin))
        model = self._model_name if pin == self._pin_name and self._model_name in models else models[0]
        self._commit((component, pins, pin, models, model), component_choices=comps)

    @property
    def component_choices(self) -> list[str]:
        "The components offered for selection: those with a pin to offer."
        return list(self._component_choices)

    @property
    def pin_choices(self) -> list[str]:
        "The selected component's pins offered for selection (``pin(signal)`` names)."
        return list(self._pin_choices)

    @property
    def model_choices(self) -> list[str]:
        "The selected pin's models offered for selection (several, for a ``[Model Selector]``)."
        return list(self._model_choices)

    @property
    def component_name(self) -> str:
        "The selected component's name. Setting it selects that component's first offered pin and model."
        return self._component_name

    @component_name.setter
    def component_name(self, name: str) -> None:
        self.select(component=name)

    @property
    def pin_name(self) -> str:
        "The selected pin's ``pin(signal)`` name. Setting it selects that pin's first offered model."
        return self._pin_name

    @pin_name.setter
    def pin_name(self, name: str) -> None:
        self.select(pin=name)

    @property
    def model_name(self) -> str:
        "The selected model's name."
        return self._model_name

    @model_name.setter
    def model_name(self, name: str) -> None:
        self.select(model=name)

    def select(
        self, component: Optional[str] = None, pin: Optional[str] = None, model: Optional[str] = None
    ) -> None:
        """Select a component, pin and/or model at once, with one ``selection_changed``.

        A pin not given stays, unless a component is given: then it's that component's first offered pin.
        Likewise, a model not given stays unless a component or pin is given.

        Raises:
            InvalidValueError: A name isn't offered (e.g. - a pin that isn't one of the given component's).
                Nothing is changed.
        """
        if component is None:
            component = self._component_name
        elif component not in self._component_choices:
            raise InvalidValueError(f"Component {component!r} isn't offered; choices: {self._component_choices}")
        pins = self._selectable_pins(self._components[component])
        new_component = component != self._component_name
        if pin is None:
            pin = pins[0] if new_component else self._pin_name
        elif pin not in pins:
            raise InvalidValueError(f"Pin {pin!r} isn't offered for component {component!r}; choices: {pins}")
        models = self._selectable_model_names(self._pin_model(component, pin))
        if model is None:
            model = models[0] if new_component or pin != self._pin_name else self._model_name
        elif model not in models:
            raise InvalidValueError(f"Model {model!r} isn't offered for pin {pin!r}; choices: {models}")
        self._commit((component, pins, pin, models, model))

    @property
    def component(self) -> Component:
        "The selected ``Component``."
        return self._components[self._component_name]

    @property
    def pin(self) -> Pin:
        "The selected pin's row of the ``[Pin]`` table."
        return Pin.from_entry(self._pin_name, self.component.pins[self._pin_name])

    @property
    def model(self) -> Model:
        "The selected ``Model``."
        return self._models[self._model_name]

    def _commit(self, selection: Selection, component_choices: Optional[list[str]] = None) -> None:
        "Store a checked selection (and new component choices); announce what changed."
        component, pins, pin, models, model = selection
        old = (self._component_name, self._pin_name, self._model_name)
        old_choices = (self._component_choices, self._pin_choices, self._model_choices)
        if component_choices is not None:
            self._component_choices = component_choices
        self._component_name, self._pin_choices, self._pin_name = component, pins, pin
        self._model_choices, self._model_name = models, model
        if model != old[2]:
            self._announce_model()
        if (self._component_choices, pins, models) != old_choices:
            self.choices_changed.emit()
        if (component, pin, model) != old:
            self.selection_changed.emit(component, pin, model)

    def _pin_model(self, component: str, pin: str) -> str:
        "The model (or model selector) name a component's pin names."
        return self._components[component].pins[pin][0]

    def _selectable_model_names(self, mname: str) -> list[str]:
        "``get_model_names(mname)``, keeping only the models of an allowed ``model_types``."
        names = self.get_model_names(mname)
        if self._model_types is None:
            return names
        return [name for name in names if self._models[name].mtype.lower() in self._model_types]

    def _selectable_pins(self, comp: Component) -> list[str]:
        """
        A component's pins that name a defined model or model selector (with a model of an allowed ``model_types``).

        Notes:
            1. The parser already drops ``POWER``, ``GND``, ``NC`` and ``CIRCUITCALL`` pins.
            2. Components with none aren't offered for selection; see ``_load``.
        """
        pins = comp.pins
        return [pname for pname in pins if self._selectable_model_names(pins[pname][0])]

    def _selectable_components(self) -> list[str]:
        "The components with a selectable pin."
        return [cname for cname, comp in self._components.items() if self._selectable_pins(comp)]

    def _no_selectable_component(self) -> str:
        "Why no component can be selected."
        if self._model_types is None:
            return "No component in this IBIS model has a pin with a defined model!"
        return (f"No component ({', '.join(self._components)}) has a pin with a model of Model_type "
                f"{sorted(self._model_types)}; Model_types found: "
                f"{sorted({m.mtype for m in self._models.values()})}")

    def _notify(self, msg: str) -> None:
        "Log a user-facing notice and fire it through ``alert``."
        logger.info(msg)
        self._last_alert = msg
        self.alert.emit(msg)

    def _announce_model(self) -> None:
        "Tell the user whether the selected model has an AMI executable for this platform."
        name = self._model_name
        model = self._models[name]
        try:
            model.get_ami_files()
        except ValueError:
            logger.warning(
                "Model `%s` has both Executable_Tx and Executable_Rx for this platform; the direction is ambiguous, "
                "so `dll_file`/`ami_file` give the first listed (%s). Use Model.get_ami_files(is_tx) to choose.",
                name, model.dll_file)
        if model.dll_file:
            self._notify(f"Model `{name}` has an AMI executable for this platform: {model.dll_file}")
        elif model.is_ami:
            self._notify(
                f"Model `{name}` has an [Algorithmic Model], but no executable for this platform: "
                f"{platform.system()}-{platform.architecture()[0]}")
        else:
            self._notify(f"Model `{name}` has no [Algorithmic Model].")

    # Files.

    @property
    def dll_file(self) -> str:
        """The currently selected model's executable model file for this platform (``Model.dll_file``).

        Direction-blind: from the model's first ``Executable`` line for this platform;
        for an ``I/O`` model, use ``model.get_ami_files(is_tx)``.
        """
        return self.model.dll_file

    @property
    def ami_file(self) -> str:
        """The currently selected model's AMI parameter file for this platform (``Model.ami_file``).

        Direction-blind: from the model's first ``Executable`` line for this platform;
        for an ``I/O`` model, use ``model.get_ami_files(is_tx)``.
        """
        return self.model.ami_file

    @property
    def ibis_dir(self) -> Path:
        "Absolute path of the directory holding the IBIS file."
        return self._ibis_dir

    def resolve_file(self, file_name: str) -> Optional[Path]:
        """Resolve a file named in the IBIS file (e.g. - an ``Executable`` entry) against ``ibis_dir``.

        Args:
            file_name: The file name, as written in the IBIS file.

        Returns:
            ``ibis_dir / file_name``, or ``None`` if ``file_name`` is empty.

        Notes:
            1. IBIS 8.0 Section 10.1 (p.214) requires the executable model file and the AMI parameter file
            to be in the IBIS file's directory, or in a relative path under it.
        """
        return self._ibis_dir / file_name if file_name else None

    @property
    def dll_path(self) -> Optional[Path]:
        "The selected model's executable model file for this platform, resolved; ``None`` if none."
        return self.resolve_file(self.dll_file)

    @property
    def ami_path(self) -> Optional[Path]:
        "The selected model's AMI parameter file for this platform, resolved; ``None`` if none."
        return self.resolve_file(self.ami_file)
