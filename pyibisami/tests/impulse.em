@# Example input file for `run_tests.py'.
@# 
@# Original Author: David Banas
@# Original Date:   July 20, 2012
@# 
@# Copyright (c) 2012 David Banas; All rights reserved World wide.

<test>
    <name>@(name)</name>
    <result>Pass</result>
    <description>A simple test of a model impulse response.</description>
    <output>
            @{from pylab import *}
            @{cla()}
            @{data.ami_params['Mode'] = '0'}
            @{model.initialize(data)}
        <block name="Model Initialization (Mode = 0)" type="text">
            @{print model.msg}
            @{print model.ami_params_out}
        </block>
            @{h = model.initOut}
            @{T = model.sample_interval}
            @{t = [i * T for i in range(len(h))]}
            @{plot(t, h, label='Mode=0')}
            @{data.ami_params['Mode'] = '1'}
            @{model.initialize(data)}
        <block name="Model Initialization (Mode = 1)" type="text">
            @{print model.msg}
            @{print model.ami_params_out}
        </block>
            @{h = model.initOut}
            @{plot(t, h, label='Mode=1')}
            @{data.ami_params['Mode'] = '2'}
            @{model.initialize(data)}
        <block name="Model Initialization (Mode = 2)" type="text">
            @{print model.msg}
            @{print model.ami_params_out}
        </block>
            @{h = model.initOut}
            @{plot(t, h, label='Mode=2')}
            @{title('Model Impulse Response')}
            @{xlabel('Time (sec.)')}
            @{legend()}
            @{filename = plot_names.next()}
            @{savefig(filename)}
        <block name="Model Impulse Response" type="image">
            @(filename)
        </block>
    </output>
</test>

