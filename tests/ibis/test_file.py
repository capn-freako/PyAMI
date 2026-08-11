from pyibisami.ibis.file import IBISModel


def test_ibis_model_construction(ibis_test_file):
    """IBISModel should construct without error from a valid IBIS file.

    Regression test: `IBISModel.__init__` unconditionally calls `self.log()`,
    which previously raised `AttributeError` (`datetime.timezone` doesn't
    exist on the `datetime.datetime` class), so every construction crashed.
    """
    model = IBISModel(ibis_test_file, debug=False, gui=False)
    assert model.file_name == "example_tx.ibs"
