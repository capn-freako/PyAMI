@# Example input file for `run_tests.py'.
@#
@# Original Author: David Banas
@# Original Date:   July 20, 2012
@#
@# Copyright (c) 2012 David Banas; All rights reserved World wide.

<test>
    <name>@(name)</name>
    <result>Visual</result>
    <description>Model frequency response for: @(description)</description>
    <output>
@{
import matplotlib
matplotlib.use('Agg')
from pylab import *
from numpy import cumsum, concatenate
import pyibisami.ami_model as ami
figure(1)
cla()
figure(2)
cla()
ref = None
for cfg in data:
    cfg_name = cfg[0]
    params = cfg[1]
    if(len(cfg) > 2):
        reference = ref_dir + '/' + name.split()[0] + '/' + cfg[2]
    else:
        reference = None
    initializer = ami.AMIModelInitializer(params[0])
    items = params[1].items()
    items = sorted(items, reverse=True)  # Note: This step is MANDATORY!
    for item in items:
        exec ('initializer.' + item[0] + ' = ' + repr(item[1]))
    model.initialize(initializer)
    print('        <block name="Model Initialization (' + cfg_name + ')" type="text">')
    print("MUT:")
    print(model.msg)
    print(model.ami_params_out)
    h = model.initOut
    T = model.sample_interval
    t = array([i * T for i in range(len(h))])
    s = cumsum(h) * T  # Step response.
    # The weird shifting by half the h-vector length is to better accomodate frequency-domain models.
    half_len = len(h) // 2
    s2 = model.getWave(array([0.0] * half_len + [1.0] * half_len), len(h))[0]
    s2_plot = pad(s2[half_len:], (0, half_len), 'edge')
    h2 = diff(s2)
    H = fft(h)
    H *= s[-1] / abs(H[0])  # Normalize for proper d.c.
    H2 = fft(h2)
    f = array([i * 1.0 // (T * len(h)) for i in range(len(h) // 2)])
    rgb_main, rgb_ref = next(plot_colors)
    rgb_main = tuple(int(color * 0xFF) for color in rgb_main)
    rgb_ref = tuple(int(color * 0xFF) for color in rgb_ref)
    color_main = f"#{rgb_main[0]:02x}{rgb_main[1]:02x}{rgb_main[2]:02x}"
    color_ref = f"#{rgb_ref[0]:02x}{rgb_ref[1]:02x}{rgb_ref[2]:02x}"
    figure(1)
    plot(t * 1.e9, s,       label=cfg_name+'_Init',    color=color_main)
    plot(t * 1.e9, s2_plot, '.', label=cfg_name+'_GetWave', color=color_main)
    figure(2)
    semilogx(f / 1.e9, 20. * log10(abs(H[:len(f)])),        label=cfg_name+'_Init',    color=color_main)
    semilogx(f / 1.e9, 20. * log10(abs(H2[:len(f)])), '.',  label=cfg_name+'_GetWave', color=color_main)
    if reference:
        try:
            if(ref is None):
                ref = ami.AMIModel(reference)
            initializer.root_name = 'easic_rx'
            ref.initialize(initializer)
            print("Reference:")
            print(ref.msg)
            print(ref.ami_params_out)
            href = ref.initOut
            sref = cumsum(href) * T
            Href = fft(href)
            Href *= sref[-1] / abs(Href[0])  # Normalize for proper d.c.
            r = Href
        except:
            r = ami.interpFile(reference, T)
        semilogx(f / 1.e9, 20. * log10(abs(r[:len(r)/2])), label=cfg_name+'_ref', color=color_ref)
    print('        </block>')
figure(1)
title('Model Step Response')
xlabel('Time (ns)')
ylabel('s(t) (V)')
axis(xmax=1)
legend(loc='upper right')
filename1 = next(plot_names)
savefig(filename1)
figure(2)
title('Model Frequency Response')
xlabel('Frequency (GHz)')
ylabel('|H(f)| (dB)')
axis(xmin=0.1, xmax=20, ymin=-30)
legend(loc='lower left')
filename2 = next(plot_names)
savefig(filename2)
}
        <block name="Model Step Response" type="image">@(filename1)</block>
        <block name="Model Frequency Response" type="image">@(filename2)</block>
    </output>
</test>
