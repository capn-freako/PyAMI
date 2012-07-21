@# Example input file for `run_tests.py'.
@# 
@# Original Author: David Banas
@# Original Date:   July 20, 2012
@# 
@# Copyright (c) 2012 David Banas; All rights reserved World wide.

<test>
    <name>@(name)</name>
    <result>Pass</result>
    <description>A simple test of a model frequency response.</description>
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
            @{H = fft(h)}
            @{T = model.sample_interval}
            @{f = [i * 1.0 / (T * len(h)) for i in range(len(h) / 2)]}
            @{plot(f, abs(H[:len(H)/2]), label='Mode=0')}
            @{data.ami_params['Mode'] = '1'}
            @{model.initialize(data)}
        <block name="Model Initialization (Mode = 1)" type="text">
            @{print model.msg}
            @{print model.ami_params_out}
        </block>
            @{h = model.initOut}
            @{H = fft(h)}
            @{plot(f, abs(H[:len(H)/2]), label='Mode=1')}
            @{data.ami_params['Mode'] = '2'}
            @{model.initialize(data)}
        <block name="Model Initialization (Mode = 2)" type="text">
            @{print model.msg}
            @{print model.ami_params_out}
        </block>
            @{h = model.initOut}
            @{H = fft(h)}
            @{plot(f, abs(H[:len(H)/2]), label='Mode=2')}
            @{title('Model Frequency Response')}
            @{xlabel('Frequency (Hz)')}
            @{legend()}
            @{filename = plot_names.next()}
            @{savefig(filename)}
        <block name="Model Frequency Response" type="image">
            @(filename)
        </block>
    </output>
</test>

