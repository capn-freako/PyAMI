"""
A class for encapsulating IBIS model files.

Original Author: David Banas <capn.freako@gmail.com>

Original Date:   November 1, 2019

For information regarding the IBIS modeling standard, visit:
https://ibis.org/

*Note:* The `IBISModel` class, defined here, needs to be kept separate from the
other IBIS-related classes, defined in the `ibis_model` module, in order to
avoid circular imports.

Copyright (c) 2019 by David Banas; All rights reserved World wide.
"""

import platform

from datetime     import datetime
from traits.api   import HasTraits, Trait, String, Float, List, Property, cached_property, Dict
from traitsui.api import Item, View, ModalButtons, Group, spring, VGroup, HGroup
from chaco.api    import ArrayPlotData, Plot
from enable.component_editor import ComponentEditor
from traitsui.message import message

from pyibisami.ibis_parser import parse_ibis_file

class IBISModel(HasTraits):
    """
    HasTraits subclass for wrapping and interacting with an IBIS model.

    This class can be configured to present a customized GUI to the user
    for interacting with a particular IBIS model (i.e. - selecting components,
    pins, and models).

    The intended use model is as follows:

     1. Instantiate this class only once per IBIS model file.
        When instantiating, provide the unprocessed contents of the IBIS
        file, as a single string. This class will take care of getting
        that string parsed properly, and report any errors or warnings
        it encounters, in its `ibis_parsing_errors` property.

     2. When you want to let the user select a particular component/pin/model,
        call the newly created instance, as if it were a function, passing
        no arguments.
        The instance will then present a GUI to the user,
        allowing him to select a particular component/pin/model, which may then
        be retrieved, via the `model` property.
        The latest user selections will be remembered,
        as long as the instance remains in scope.

    Any errors or warnings encountered while parsing are available, in
    the `ibis_parsing_errors` property.

    The complete dictionary containing all parsed models may be retrieved,
    via the `model_dict` property.
    """

    debug = False

    pins   = Property(List, depends_on=["comp"])
    models = Property(Dict, depends_on=["pin"])

    def __init__(self, ibis_file_contents_str):
        """
        Args:
            ibis_file_contents_str (str): The unprocessed contents of
                the IBIS file, as a single string.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super(IBISModel, self).__init__()

        self._log = "Initializing..."

        # Parse the IBIS file contents, storing any errors or warnings.
        err_str, model_dict = parse_ibis_file(ibis_file_contents_str)
        if 'components' not in model_dict or not model_dict['components']:
            raise ValueError("This IBIS model has no components! Parser messages:\n" + err_str)
        if 'models' not in model_dict or not model_dict['models']:
            raise ValueError("This IBIS model has no models! Parser messages:\n" + err_str)
        components = model_dict['components']
        models     = model_dict['models']
        self.log("IBIS parsing errors/warnings:\n" + err_str)

        # Add Traits for various attributes found in the IBIS file.
        self.add_trait('comp',      Trait(list(components)[0], components))
        self.add_trait('pin',       Trait(list(self.pins)[0],   self.pins))
        self.add_trait('mod',       Trait(list(models)[0], models))
        self.add_trait('ibis_ver',  Float(model_dict['ibis_ver']))
        self.add_trait('file_name', String(model_dict['file_name']))
        self.add_trait('file_rev',  String(model_dict['file_rev']))
        self.add_trait('date',      String(model_dict['date']))

        self._ibis_parsing_errors = err_str
        self._model_dict = model_dict
        self._models = models
        self._os_type = platform.system()           # These 2 are used, to choose
        self._os_bits = platform.architecture()[0]  # the correct AMI executable.

        self._mod_changed(list(models)[0])  # Wasn't be called at automatically.

    def __str__(self):
        res = ""
        try:
            for k in ['ibis_ver', 'file_name', 'file_rev']:
                res += k + ':\t' + str(self._model_dict[k]) + '\n'
        except:
            print(self._model_dict)
            raise
        res += 'date' + ':\t\t' + str(self._model_dict['date']) + '\n'
        res += "\nComponents:"
        res += "\n=========="
        for c in list(self._model_dict['components']):
            res += "\n" + c + ":\n" + "---\n" + str(self._model_dict['components'][c]) + "\n"
        res += "\nModels:"
        res += "\n======"
        for m in list(self._model_dict['models']):
            res += "\n" + m + ":\n" + "---\n" + str(self._model_dict['models'][m])
        return res

    def __call__(self):
        """Present a customized GUI to the user, for model selection, etc."""
        self.edit_traits(kind='livemodal')

    # Logger & Pop-up
    def log(self, msg, alert=False):
        """Log a message to the console and, optionally, to terminal and/or pop-up dialog."""
        _msg = msg.strip()
        txt = "\n[{}]: {}\n".format(datetime.now(), _msg)
        self._log += txt
        if self.debug:
            print(txt)
        if alert:
            message(_msg, "PyAMI Alert")

    def default_traits_view(self):
        view = View(
            VGroup(
                HGroup(
                    Item('file_name', label='File name', style='readonly'),
                    spring,
                    Item('file_rev', label='rev', style='readonly'),
                ),
                HGroup(
                    Item('ibis_ver', label='IBIS ver', style='readonly'),
                    spring,
                    Item('date', label='Date', style='readonly'),
                ),
                HGroup(
                    Item('comp', label='Component'),
                    Item('pin',  label='Pin'),
                    Item('mod',  label='Model'),
                ),
            ),
            resizable=False,
            buttons=ModalButtons,
            title="PyBERT IBIS Model Selector",
            id="pybert.pybert_ami.model_selector",
        )
        return view

    @cached_property
    def _get_pins(self):
        return self.comp_.pins

    @cached_property
    def _get_models(self):
        # comp = self.comp_
        # (model, rlcs) = comp.pin
        (model, rlcs) = self.pin_
        return {model: self._models[model]}

    @property
    def ibis_parsing_errors(self):
        """Any errors or warnings encountered, while parsing the IBIS file contents."""
        return self._ibis_parsing_errors

    @property
    def model_dict(self):
        "Dictionary of all model keywords."
        return self._model_dict

    @property
    def model(self):
        """The model selected most recently by the user.

        Returns the first model parsed, if the user hasn't made a selection yet.
        """
        return self.mod_

    @property
    def dll_file(self):
        """Any errors or warnings encountered, while parsing the IBIS file contents."""
        return self._dll_file

    @property
    def ami_file(self):
        """Any errors or warnings encountered, while parsing the IBIS file contents."""
        return self._ami_file

    def _comp_changed(self, new_value):
        self.remove_trait('pin')
        self.add_trait('pin', Trait(list(self.pins)[0], self.pins))

    def _pin_changed(self, new_value):
        self.mod = list(self.models)[0]
        # models = self.models
        # self.remove_trait('mod')
        # self.add_trait('mod', Trait(list(models)[0], models))

    def _mod_changed(self, new_value):
        model = self._models[new_value]
        fnames = []
        dll_file = ""
        ami_file = ""
        if self._os_type == 'Windows':
            if self._os_bits == '64bit':
                fnames = model._exec64Wins
            else:
                fnames = model._exec32Wins
        else:
            if self._os_bits == '64bit':
                fnames = model._exec64Lins
            else:
                fnames = model._exec32Lins
        if fnames:
            dll_file = fnames[0]
            ami_file = fnames[1]
        elif 'algorithmic_model' in model._subDict:
            self.log(f'There was an [Algorithmic Model] keyword for this model,\nbut no executable for your platform: {os_type}-{os_bits};\nPyBERT native equalization modeling being used instead.',
                alert=True)
        else:
            self.log('There was no [Algorithmic Model] keyword for this model;\nPyBERT native equalization modeling being used instead.',
                alert=True)
        self._dll_file = dll_file
        self._ami_file = ami_file
