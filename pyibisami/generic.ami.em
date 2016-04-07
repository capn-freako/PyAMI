(@model_name

    (Description "@description")

@{
import sys
from pyibisami import ami_config as ac

for (sec_name, sec_key) in [('Reserved_Parameters', 'reserved'), ('Model_Specific', 'model')]:
    print "    (%s" % sec_name
    for param_name in ami_params[sec_key]:
        param = ami_params[sec_key][param_name]
        try:
            ac.print_param("        ", param_name, param)
        except Exception as e:
            e.args += (param_name,)
            raise
    print "    )"
}
)

