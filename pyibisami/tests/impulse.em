@# Example input file for `run_tests.py'.
@# 
@# Original Author: David Banas
@# Original Date:   July 20, 2012
@# 
@# Copyright (c) 2012 David Banas; All rights reserved World wide.

<test>
    <name>@(name)</name>
    <result>Pass</result>
    <description>Model impulse response for: @(description)</description>
    <output>
@{
from pylab import *
#import amimodel as ami           # Use this one for developing/testing.
import pyibisami.amimodel as ami # Use this one for distribution.
cla()
for cfg in data:
    cfg_name = cfg[0]
    params = cfg[1]
    if(len(cfg) > 2):
        reference = ref_dir + '/' + name.split()[0] + '/' + cfg[2]
    else:
        reference = None
    initializer = ami.AMIModelInitializer(params[0])
    items = params[1].items()
    items.sort(reverse=True)
    for item in items:
        exec ('initializer.' + item[0] + ' = ' + repr(item[1]))
    model.initialize(initializer)
    print '        <block name="Model Initialization (' + cfg_name + ')" type="text">'
    print model.msg
    print model.ami_params_out
    print '        </block>'
    h = model.initOut
    T = model.sample_interval
    t = [i * T for i in range(len(h))]
    rgb_main, rgb_ref = plot_colors.next()
    color_main = "#%02X%02X%02X" % (rgb_main[0] * 0xFF, rgb_main[1] * 0xFF, rgb_main[2] * 0xFF)
    color_ref = "#%02X%02X%02X" % (rgb_ref[0] * 0xFF, rgb_ref[1] * 0xFF, rgb_ref[2] * 0xFF)
    plot(t, h, label=cfg_name, color=color_main)
    if(reference):
        r = ami.interpFile(reference, T)
        plot(t, r, label=cfg_name+'_ref', color=color_ref)
title('Model Impulse Response')
xlabel('Time (sec.)')
legend()
filename = plot_names.next()
savefig(filename)
}
        <block name="Model Impulse Response" type="image">
            @(filename)
        </block>
    </output>
</test>

