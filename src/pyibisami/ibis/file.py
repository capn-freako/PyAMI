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
from typing import Optional

from traits.api import (
    Any,
    Dict,
    Enum,
    Event,
    Float,
    HasTraits,
    List,
    Property,
    Str,
    String,
    TraitType,
    cached_property,
)

# ``TX_MODEL_TYPES``/``RX_MODEL_TYPES`` live in ``.model`` (which can't import this module); re-exported here.
from .model import RX_MODEL_TYPES, TX_MODEL_TYPES, Component, Model
from .parser import parse_ibis_file

logger = logging.getLogger(__name__)


class ModelTypes(TraitType):
    """``None``, or a collection of ``Model_type`` names, held as a lower-cased ``frozenset``.

    A single string is rejected (it would otherwise be read one character at a time).
    """

    default_value = None
    info_text = "None or a collection of Model_type names (not a single string)"

    def validate(self, obj, name, value):
        if value is None:
            return None
        if isinstance(value, str):
            self.error(obj, name, value)
        try:
            return frozenset(str(mtype).lower() for mtype in value)
        except TypeError:
            return self.error(obj, name, value)


class IBISModel(HasTraits):  # pylint: disable=too-many-instance-attributes
    """HasTraits subclass for wrapping and interacting with an IBIS model.

    This class can be configured to present a customized GUI to the user
    for interacting with a particular IBIS model (i.e. - selecting components,
    pins, and models).

    The intended use model is as follows:

     1. Instantiate this class only once per IBIS model file.
        When instantiating, provide the name of the IBIS file.
        This class will take care of opening that file,
        parsing its contents, and reporting any errors or warnings
        it encounters, in its ``ibis_parsing_errors`` property.

     2. When you want to let the user select a particular component/pin/model,
        call the newly created instance, as if it were a function, passing
        no arguments.
        The instance will then present a GUI to the user,
        allowing him to select a particular component/pin/model, which may then
        be retrieved, via the ``model`` property.
        The latest user selections will be remembered,
        as long as the instance remains in scope.

    To offer only some kinds of pin (e.g. - only Tx pins), give the ``model_types`` to allow::

        IBISModel(ibis_file_name, model_types=TX_MODEL_TYPES)

    Any errors or warnings encountered while parsing are available, in
    the ``ibis_parsing_errors`` property.

    User-facing notices (e.g. - whether the selected model has an AMI executable
    for this platform) are logged and also fired through the ``alert`` event,
    which GUIs may observe; see ``pyibisami.gui.ibis.show_alerts()``.

    The complete dictionary containing all parsed models may be retrieved,
    via the ``model_dict`` property.
    """

    pin_ = Property(Any, depends_on=["pin"])
    pin_rlcs = Property(Dict, depends_on=["pin"])
    model = Property(Any, depends_on=["mod"])
    comps = List  # Always holds the list of valid component selections.
    pins = List  # Always holds the list of valid pin selections, given a component selection.
    models = List  # Always holds the list of valid model selections, given a pin selection.
    alert = Event(Str)  # Fired with each user-facing notice; GUIs observe this.
    model_types = ModelTypes  # ``Model_type`` s offered for selection (any case); ``None`` (the default) offers all.

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
        else:
            if mname in self._models:
                return [mname]
            else:
                return []

    def get_models(self, mname: str) -> list[str]:
        """Deprecated synonym of ``get_model_names``"""
        return self.get_model_names(mname)

    def get_pins(self):
        return list(self.comp_.pins)

    def _selectable_model_names(self, mname: str) -> list[str]:
        "``get_model_names(mname)``, keeping only the models of an allowed ``model_types``."
        names = self.get_model_names(mname)
        if self.model_types is None:
            return names
        return [name for name in names if self._models[name].mtype.lower() in self.model_types]  # type: ignore

    def _selectable_pins(self, comp: Optional[Component] = None) -> list[str]:
        """
        A component's pins that name a defined model or model selector (with a model of an allowed ``model_types``).

        Keyword Args:
            comp: The component to inspect; the currently selected one when ``None``.
                Default: ``None``

        Notes:
            1. The parser already drops ``POWER``, ``GND``, ``NC`` and ``CIRCUITCALL`` pins.
            2. Components with none aren't offered for selection; see ``__init__``.
        """
        pins = (comp if comp is not None else self.comp_).pins
        return [pname for pname in pins if self._selectable_model_names(pins[pname][0])]

    def _selectable_components(self) -> list[str]:
        "The components with a selectable pin."
        return [cname for cname, comp in self._components.items() if self._selectable_pins(comp)]

    def _no_selectable_component(self) -> str:
        "Why no component can be selected."
        if self.model_types is None:
            return "No component in this IBIS model has a pin with a defined model!"
        return (f"No component ({', '.join(self._components)}) has a pin with a model of Model_type "
                f"{sorted(self.model_types)}; Model_types found: "  # type: ignore
                f"{sorted({m.mtype for m in self._models.values()})}")

    def get_pins_qualified(self, is_tx: bool, comp_name: Optional[str] = None) -> list[Any]:
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
            comp = self.comp_  # type: ignore
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

    def __init__(
        self: "IBISModel",
        ibis_file_name: str,
        *,
        model_types: Optional[Iterable[str]] = None,
    ) -> None:
        """
        Args:
            ibis_file_name (str): The name of the IBIS file.

        Keyword Args:
            model_types: Offer only the pins (and models) with one of these ``Model_type`` s (any case);
                e.g. - ``TX_MODEL_TYPES`` or ``RX_MODEL_TYPES``. ``None`` offers all.
                May be changed later, through the ``model_types`` trait.
                Default: ``None``

        Raises:
            ValueError: If no component has a pin to offer.
            TraitError: If ``model_types`` is a single string, or not a collection.

        Notes:
            1. For parsing details, enable ``DEBUG`` logging for the ``pyibisami.ibis`` logger.
            2. A pin is offered if any of its models (e.g. - in a ``[Model Selector]``) has an allowed
                ``Model_type``; only those models are offered for it.
            3. If a later ``model_types`` change leaves nothing to offer,
                the selection is kept and an ``alert`` is fired.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super().__init__()
        self.trait_setq(model_types=model_types)  # Quietly: there's no selection to update yet.

        logger.debug("Loading IBIS file: %s", ibis_file_name)
        self._ibis_dir = Path(ibis_file_name).absolute().parent

        # Parse the IBIS file contents, storing any errors or warnings, and validate it.
        with open(ibis_file_name, "r", encoding="utf-8") as file:
            ibis_file_contents_str = file.read()
        err_str, model_dict = parse_ibis_file(ibis_file_contents_str)
        self._file_name: str = model_dict.get("file_name", "(n/a)")
        self._ibis_ver: float = model_dict.get("ibis_ver", "(n/a)")
        self._file_rev: str = model_dict.get("file_rev", "(n/a)")
        self._date: str = model_dict.get("date", "(n/a)")
        if err_str == "Success!":
            logger.debug("IBIS parsing: %s", err_str)
        else:
            logger.warning("IBIS parsing errors/warnings in %s:\n%s", ibis_file_name, err_str)
        if "components" not in model_dict or not model_dict["components"]:
            logger.debug("Parsed IBIS model dictionary:\n%s", model_dict)
            raise ValueError("This IBIS model has no components!")
        components = model_dict["components"]
        if "models" not in model_dict or not model_dict["models"]:
            logger.debug("Parsed IBIS model dictionary:\n%s", model_dict)
            raise ValueError("This IBIS model has no models!")

        self._model_dict: dict[str, Any] = model_dict
        self._models: dict[str, Model] = model_dict["models"]
        self._components: dict[str, Component] = components
        self._model_selectors: dict[str, list[str]] = {}
        if "model_selectors" in model_dict:
            self._model_selectors.update(model_dict["model_selectors"])

        # Only components with a pin naming a defined model (of an allowed ``model_types``) are offered for selection.
        # (Skipped ones remain in ``_components``; e.g. - for ``get_pins_qualified()``.)
        comps = self._selectable_components()
        for cname in components:
            if cname not in comps:
                if model_types is None:
                    logger.warning("Component '%s' has no pins with a defined model; it can't be selected.", cname)
                else:
                    logger.warning("Component '%s' has no pins with a model of Model_type %s; it can't be selected.",
                                   cname, sorted(self.model_types))  # type: ignore
        if not comps:
            raise ValueError(self._no_selectable_component())

        # Add Traits for various attributes found in the IBIS file.
        self.comps = comps  # type: ignore
        self.add_trait("comp", Enum(comps[0], values="comps"))
        self.pins = self._selectable_pins()  # type: ignore
        try:
            self.add_trait("pin", Enum(self.pins[0], values="pins"))  # type: ignore
        except Exception as err:
            raise ValueError(f"self.pins: {self.pins}") from err
        (mname, _) = self.pin_
        self.models = self._selectable_model_names(mname)  # type: ignore
        self.add_trait("mod", Enum(self.models[0], values="models"))  # type: ignore
        self.add_trait("ibis_ver", Float(model_dict["ibis_ver"]))
        self.add_trait("file_name", String(model_dict["file_name"]))
        self.add_trait("file_rev", String(model_dict["file_rev"]))
        if "date" in model_dict:
            self.add_trait("date", String(model_dict["date"]))
        else:
            self.add_trait("date", String("(n/a)"))

        self._ibis_parsing_errors = err_str

        self._comp_changed(comps[0])  # Wasn't being called automatically.
        # Wasn't being called automatically:
        self._pin_changed(self.pins[0])  # type: ignore

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

    def __call__(self):
        """Present a customized GUI to the user, for model selection, etc.

        Subsequent ``alert`` s are shown as pop-up dialogs.
        Requires the ``gui`` extra: ``pip install 'pyibis-ami[gui]'``.
        """
        from ..gui.ibis import show_alerts  # pylint: disable=import-outside-toplevel
        show_alerts(self)
        # self.configure_traits(kind='modal')  # Waiting for Enthought/Traits PR1841 to be accepted.
        self.configure_traits()

    def _notify(self, msg: str) -> None:
        "Log a user-facing notice and fire it through the ``alert`` event."
        logger.info(msg)
        self.alert = msg

    def default_traits_view(self):
        "Default Traits/UI view definition."
        from ..gui.ibis import make_ibis_file_view  # pylint: disable=import-outside-toplevel
        return make_ibis_file_view(self)

    @property
    def comp_(self) -> Component:
        "The selected ``Component``."
        return self._components[self.comp]  # type: ignore

    @cached_property
    def _get_pin_(self):
        return self.comp_.pins[self.pin]

    @cached_property
    def _get_pin_rlcs(self):
        (_, pin_rlcs) = self.pin_
        return pin_rlcs

    @cached_property
    def _get_model(self):
        return self._models[self.mod]

    @property
    def ibis_parsing_errors(self):
        """Any errors or warnings encountered, while parsing the IBIS file
        contents."""
        return self._ibis_parsing_errors

    @property
    def model_dict(self):
        "Dictionary of all model keywords."
        return self._model_dict

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

    def _comp_changed(self, new_value):
        del new_value
        self.pins = self._selectable_pins()
        old_pin = self.pin  # type: ignore
        self.pin = self.pins[0]
        if self.pin == old_pin:  # A pin of the same name in the new component fires no ``pin`` change.
            self._pin_changed(self.pin)

    def _pin_changed(self, new_value):
        # (mname, rlc_dict) = self.pin_  # Doesn't work. Because ``pin_`` is a cached property and hasn't yet been marked "dirty"?
        (mname, _) = self.comp_.pins[new_value]
        self.models = self._selectable_model_names(mname)
        self.mod = self.models[0]

    def _model_types_changed(self, old, new):  # pylint: disable=unused-argument
        "Re-filter the selections, keeping each one that's still offered; undo a change that leaves nothing."
        comps = self._selectable_components()
        if not comps:
            msg = self._no_selectable_component()
            self.trait_setq(model_types=old)  # Quietly: the lists and selection still match ``old``.
            self._notify(f"{msg} Keeping the previous model_types and selection.")
            return
        # A pin is kept only with its component, and a model only with its pin. (The handlers are called
        # explicitly: shrinking an ``Enum``'s list can change its value without a change event.)
        (comp, pin, mod) = (self.comp, self.pin, self.mod)  # type: ignore
        self.comps = comps
        if comp not in comps:
            self.comp = comps[0]
            self._comp_changed(self.comp)  # Its first offered pin and model.
            return
        self.pins = self._selectable_pins()
        if pin not in self.pins:
            self.pin = self.pins[0]
            self._pin_changed(self.pin)  # Its first offered model.
            return
        (mname, _) = self.comp_.pins[pin]
        self.models = self._selectable_model_names(mname)
        if mod not in self.models:
            self.mod = self.models[0]

    def _mod_changed(self, new_value):
        model = self._models[new_value]
        try:
            model.get_ami_files()
        except ValueError:
            logger.warning(
                "Model `%s` has both Executable_Tx and Executable_Rx for this platform; the direction is ambiguous, "
                "so `dll_file`/`ami_file` give the first listed (%s). Use Model.get_ami_files(is_tx) to choose.",
                new_value, model.dll_file)
        if model.dll_file:
            self._notify(f"Model `{new_value}` has an AMI executable for this platform: {model.dll_file}")
        elif model.is_ami:
            self._notify(
                f"Model `{new_value}` has an [Algorithmic Model], but no executable for this platform: "
                f"{platform.system()}-{platform.architecture()[0]}")
        else:
            self._notify(f"Model `{new_value}` has no [Algorithmic Model].")
