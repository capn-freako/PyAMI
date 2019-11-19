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

from traits.api   import HasTraits, Trait, String, Float, List, Property, cached_property, Dict
from traitsui.api import Item, View, ModalButtons, Group, spring
from chaco.api    import ArrayPlotData, Plot
from enable.component_editor import ComponentEditor

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

    pins   = Property(List, depends_on=["comp"])
    models = Property(Dict, depends_on=["comp", "pin"])

    @cached_property
    def _get_pins(self):
        return self.comp_.pins

    @cached_property
    def _get_models(self):
        comp = self.comp_
        (model, rlcs) = comp.pin
        return {model: self._models[model]}

    def __init__(self, ibis_file_contents_str):
        """
        Args:
            ibis_file_contents_str (str): The unprocessed contents of
                the IBIS file, as a single string.
        """

        # Super-class initialization is ABSOLUTELY NECESSARY, in order
        # to get all the Traits/UI machinery setup correctly.
        super(IBISModel, self).__init__()

        # Parse the IBIS file contents, storing any errors or warnings,
        # and customize the view accordingly.
        err_str, model_dict = parse_ibis_file(ibis_file_contents_str)
        if 'components' not in model_dict or not model_dict['components']:
            print(err_str)
            print(model_dict)
            raise ValueError("This IBIS model has no components!")
        if 'models' not in model_dict or not model_dict['models']:
            raise ValueError("This IBIS model has no models!")
        components = model_dict['components']
        models     = model_dict['models']
        self.add_trait('comp',      Trait(list(components)[0], components))
        self.add_trait('pin',       Trait(list(self.pins)[0], self.pins))
        self.add_trait('mod',       Trait(list(models)[0], models))
        self.add_trait('ibis_ver',  Float(model_dict['ibis_ver']))
        self.add_trait('file_name', String(model_dict['file_name']))
        self.add_trait('file_rev',  String(model_dict['file_rev']))
        self.add_trait('date',      String(model_dict['date']))
        self._content = [
            Group(
                Group(
                    Item('file_name', label='File name', style='readonly'),
                    spring,
                    Item('file_rev', label='rev', style='readonly'),
                    orientation="horizontal",
                ),
                Group(
                    Item('ibis_ver', label='IBIS ver', style='readonly'),
                    spring,
                    Item('date', label='Date', style='readonly'),
                    orientation="horizontal",
                ),
                label='Info', show_border=True,
            ),
            Group(
                Item('comp', label='Component'),
                Item('pin',  label='Pin'),
                Item('mod',  label='Model'),
                orientation="horizontal",
            ),
            ]

        self._ibis_parsing_errors = err_str
        self._model_dict = model_dict
        self._models = models

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
        self.edit_traits()

    def default_traits_view(self):
        view = View(
            resizable=False,
            buttons=ModalButtons,
            title="PyBERT IBIS Model Selector",
            id="pybert.pybert_ami.model_selector",
        )
        view.set_content(self._content)
        return view

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

    def _comp_changed(self, new_value):
        self.remove_trait('pin')
        self.add_trait('pin', Trait(list(self.pins)[0], self.pins))

    def _pin_changed(self, new_value):
        self.remove_trait('mod')
        self.add_trait('mod', Trait(list(self.models)[0], self.models))
