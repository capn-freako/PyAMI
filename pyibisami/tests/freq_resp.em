@# Example input file for `run_tests.py'.
@# 
@# Original Author: David Banas
@# Original Date:   July 20, 2012
@# 
@# Copyright (c) 2012 David Banas; All rights reserved World wide.

<test>
    <name>@(name)</name>
    <result>Pass</result>
    <description>Model frequency response for: @(description)</description>
    <output>
@{
from pylab import *
import pyibisami.amimodel as ami
cla()
for cfg in data:
    cfg_name = cfg[0]
    params = cfg[1]
    initializer = ami.AMIModelInitializer(params[0])
    for item in params[1].items():
        exec ('initializer.' + item[0] + ' = ' + repr(item[1]))
    model.initialize(initializer)
    print '        <block name="Model Initialization (' + cfg_name + ')" type="text">'
    print model.msg
    print model.ami_params_out
    print '        </block>'
    h = model.initOut
    H = fft(h)
    T = model.sample_interval
    f = [i * 1.0 / (T * len(h)) for i in range(len(h) / 2)]
    plot(f, abs(H[:len(H)/2]), label=cfg_name)
title('Model Frequency Response')
xlabel('Frequency (Hz)')
legend()
filename = plot_names.next()
savefig(filename)
}
        <block name="Model Frequency Response" type="image">
            @(filename)
        </block>
    </output>
</test>

