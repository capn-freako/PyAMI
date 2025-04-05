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

import platform
from datetime import datetime

from traits.api import (
    Any,
    Dict,
    Enum,
    Float,
    HasTraits,
    List,
    Property,
    String,
    Trait,
    cached_property,
)
from traitsui.api import HGroup, Item, ModalButtons, VGroup, View, spring
from traitsui.message import message

from pyibisami.ibis.parser import parse_ibis_file


class IBISModel(HasTraits):  # pylint: disable=too-many-instance-attributes
    """HasTraits subclass for wrapping and interacting with an IBIS model.

    This class can be configured to present a customized GUI to the user
    for interacting with a particular IBIS model (i.e. - selecting components,
    pins, and models).

    The intended use model is as follows:

     1. Instantiate this class only once per IBIS model file.
        When instantiating, provide the unprocessed contents of the IBIS
        file, as a single string. This class will take care of getting
        that string parsed properly, and report any errors or warnings
        it encounters, in its ``ibis_parsing_errors`` property.

     2. When you want to let the user select a particular component/pin/model,
        call the newly created instance, as if it were a function, passing
        no arguments.
        The instance will then present a GUI to the user,
        allowing him to select a particular component/pin/model, which may then
        be retrieved, via the ``model`` property.
        The latest user selections will be remembered,
        as long as the instance remains in scope.

    Any errors or warnings encountered while parsing are available, in
    the ``ibis_parsing_errors`` property.

    The complete dictionary containing all parsed models may be retrieved,
    via the ``model_dict`` property.
    """

    _log = ""

    pin_ = Property(Any, depends_on=["pin"])
    pin_rlcs = Property(Dict, depends_on=["pin"])
    model = Property(Any, depends_on=["mod"])
    pins = List  # Always holds the list of valid pin selections, given a component selection.
    models = List  # Always holds the list of valid model selections, given a pin selection.

    def get_models(self, mname):
        """Return the list of models associated with a particular name."""
        model_dict = self._model_dict
        if "model_selectors" in model_dict and mname in model_dict["model_selectors"]:
            return list(map(lambda pr: pr[0], model_dict["model_selectors"][mname]))
        return [mname]

    def get_pins(self):
        """Get the list of appropriate pins, given our type (i.e. - Tx or Rx)."""
        pins = self.comp_.pins

        def pin_ok(pname):
            (mname, _) = pins[pname]
            mods = self.get_models(mname)
            mod = self._models[mods[0]]
            mod_type = mod.mtype.lower()
            tx_ok = mod_type in ("output", "i/o")
            if self._is_tx:
                return tx_ok
            return not tx_ok

        return list(filter(pin_ok, list(pins)))

    def __init__(self, ibis_file_name, is_tx, debug=False, gui=True):
        """
        Args:
            ibis_file_name (str): The name of the IBIS file.
            is_tx (bool): True if this is a Tx model.

        Keyword Args:
            debug (bool): Output debugging info to console when true.
                Default = False
            gui (bool): Set to `False` for command line and/or script usage.
                Default = True.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super().__init__()

        self.debug = debug
        self.GUI = gui
        if debug:
            self.log("pyibisami.ibis_file.IBISModel initializing in debug mode...")
        else:
            self.log("pyibisami.ibis_file.IBISModel initializing in non-debug mode...")

        # Parse the IBIS file contents, storing any errors or warnings, and validate it.
        with open(ibis_file_name, "r", encoding="utf-8") as file:
            ibis_file_contents_str = file.read()
        err_str, model_dict = parse_ibis_file(ibis_file_contents_str, debug=debug)
        self.log("IBIS parsing errors/warnings:\n" + err_str)
        if "components" not in model_dict or not model_dict["components"]:
            print(f":\n{model_dict}", flush=True)
            raise ValueError("This IBIS model has no components!")
        components = model_dict["components"]
        if "models" not in model_dict or not model_dict["models"]:
            raise ValueError("This IBIS model has no models!")
        models = model_dict["models"]
        self._model_dict = model_dict
        self._models = models
        self._is_tx = is_tx

        # Add Traits for various attributes found in the IBIS file.
        self.add_trait("comp", Trait(list(components)[0], components))  # Doesn't need a custom mapper, because
        self.pins = self.get_pins()  # the thing above it (file) can't change.
        self.add_trait("pin", Enum(self.pins[0], values="pins"))
        (mname, _) = self.pin_
        self.models = self.get_models(mname)
        self.add_trait("mod", Enum(self.models[0], values="models"))
        self.add_trait("ibis_ver", Float(model_dict["ibis_ver"]))
        self.add_trait("file_name", String(model_dict["file_name"]))
        self.add_trait("file_rev", String(model_dict["file_rev"]))
        if "date" in model_dict:
            self.add_trait("date", String(model_dict["date"]))
        else:
            self.add_trait("date", String("(n/a)"))

        self._ibis_parsing_errors = err_str
        self._os_type = platform.system()  # These 2 are used, to choose
        self._os_bits = platform.architecture()[0]  # the correct AMI executable.

        self._comp_changed(list(components)[0])  # Wasn't being called automatically.
        self._pin_changed(self.pins[0])  # Wasn't being called automatically.

        self.log("Done.")

    def __str__(self):
        return f"IBIS Model '{self._model_dict['file_name']}'"

    def info(self):
        """Basic information about the IBIS model."""
        res = ""
        try:
            for k in ["ibis_ver", "file_name", "file_rev"]:
                res += k + ":\t" + str(self._model_dict[k]) + "\n"
        except Exception as err:
            print(f"{err}")
            print(self._model_dict)
            raise
        res += "date" + ":\t\t" + str(self._model_dict["date"]) + "\n"
        res += "\nComponents:"
        res += "\n=========="
        for c in list(self._model_dict["components"]):
            res += "\n" + c + ":\n" + "---\n" + str(self._model_dict["components"][c]) + "\n"
        res += "\nModel Selectors:"
        res += "\n===============\n"
        for s in list(self._model_dict["model_selectors"]):
            res += f"{s}\n"
        res += "\nModels:"
        res += "\n======"
        for m in list(self._model_dict["models"]):
            res += "\n" + m + ":\n" + "---\n" + str(self._model_dict["models"][m])
        return res

    def __call__(self):
        """Present a customized GUI to the user, for model selection, etc."""
        self.edit_traits(kind="livemodal")

    # Logger & Pop-up
    def log(self, msg, alert=False):
        """Log a message to the console and, optionally, to terminal and/or
        pop-up dialog."""
        _msg = msg.strip()
        txt = f"\n[{datetime.now()}]: IBISModel: {_msg}\n"
        self._log += txt
        if self.debug:
            print(txt, flush=True)
        if alert and self.GUI:
            message(_msg, "PyAMI Alert")

    def default_traits_view(self):
        "Default Traits/UI view definition."
        view = View(
            VGroup(
                HGroup(
                    Item("file_name", label="File name", style="readonly"),
                    spring,
                    Item("file_rev", label="rev", style="readonly"),
                ),
                HGroup(
                    Item("ibis_ver", label="IBIS ver", style="readonly"),
                    spring,
                    Item("date", label="Date", style="readonly"),
                ),
                HGroup(
                    Item("comp", label="Component"),
                    Item("pin", label="Pin"),
                    Item("mod", label="Model"),
                ),
            ),
            resizable=False,
            buttons=ModalButtons,
            title="PyBERT IBIS Model Selector",
            id="pybert.pybert_ami.model_selector",
        )
        return view

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
    def log_txt(self):
        """The complete log since instantiation."""
        return self._log

    @property
    def model_dict(self):
        "Dictionary of all model keywords."
        return self._model_dict

    @property
    def dll_file(self):
        "Shared object file."
        return self._dll_file

    @property
    def ami_file(self):
        "AMI file."
        return self._ami_file

    def _comp_changed(self, new_value):
        del new_value
        self.pins = self.get_pins()
        self.pin = self.pins[0]

    def _pin_changed(self, new_value):
        # (mname, rlc_dict) = self.pin_  # Doesn't work. Because ``pin_`` is a cached property and hasn't yet been marked "dirty"?
        (mname, _) = self.comp_.pins[new_value]
        self.models = self.get_models(mname)
        self.mod = self.models[0]

    def _mod_changed(self, new_value):
        model = self._models[new_value]
        os_type = self._os_type
        os_bits = self._os_bits
        fnames = []
        dll_file = ""
        ami_file = ""
        if os_type.lower() == "windows":
            if os_bits == "64bit":
                fnames = model._exec64Wins  # pylint: disable=protected-access
            else:
                fnames = model._exec32Wins  # pylint: disable=protected-access
        else:
            if os_bits == "64bit":
                fnames = model._exec64Lins  # pylint: disable=protected-access
            else:
                fnames = model._exec32Lins  # pylint: disable=protected-access
        if fnames:
            dll_file = fnames[0]
            ami_file = fnames[1]
            self.log(
                "There was an [Algorithmic Model] keyword in this model.\n \
If you wish to use the AMI model associated with this IBIS model,\n \
please, go the 'Equalization' tab and enable it now.",
                alert=True,
            )
        elif "algorithmic_model" in model._subDict:  # pylint: disable=protected-access
            self.log(
                f"There was an [Algorithmic Model] keyword for this model,\n \
but no executable for your platform: {os_type}-{os_bits};\n \
PyBERT native equalization modeling being used instead.",
                alert=True,
            )
        else:
            self.log(
                "There was no [Algorithmic Model] keyword for this model;\n \
PyBERT native equalization modeling being used instead.",
                alert=True,
            )
        self._dll_file = dll_file  # pylint: disable=attribute-defined-outside-init
        self._ami_file = ami_file  # pylint: disable=attribute-defined-outside-init
