import pytest

from pyibisami.ami.parameter import AMIParamError


class Test_AMI_Parameter(object):
    def test_AMIParamError(self):
        with pytest.raises(Exception):
            raise AMIParamError("Test")
