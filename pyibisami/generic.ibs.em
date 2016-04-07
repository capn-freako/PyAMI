[IBIS Ver]   5.1

@{
from numpy import array

file_name         = ibis_params['file_name']
file_rev          = ibis_params['file_rev']
copyright         = ibis_params['copyright']
component         = ibis_params['component']
manufacturer      = ibis_params['manufacturer']
r_pkg             = ibis_params['r_pkg']
l_pkg             = ibis_params['l_pkg']
c_pkg             = ibis_params['c_pkg']
model_name        = ibis_params['model_name']
model_type        = ibis_params['model_type']
c_comp            = ibis_params['c_comp']
c_ref             = ibis_params['c_ref']
v_ref             = ibis_params['v_ref']
v_meas            = ibis_params['v_meas']
r_ref             = ibis_params['r_ref']
temperature_range = ibis_params['temperature_range']
voltage_range     = ibis_params['voltage_range']
impedance         = ibis_params['impedance']
slew_rate         = ibis_params['slew_rate']
}

[File Name]  @(file_name)
[File Rev]   @(file_rev)

[Date]       @(date)

[Source]     ibisami, a public domain IBIS-AMI model creation infrastructure

[Disclaimer]
THIS MODEL IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS MODEL, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

[Notes]
This IBIS file was generated, using the template file,
"example_tx.ibs.em", from ibisami, a public domain IBIS-AMI model
creation infrastructure. To learn more, visit:

https://github.com/capn-freako/ibisami/wiki

[Copyright]    @(copyright)
[Component]    @(component)
[Manufacturer] @(manufacturer)

[Package]

@{
print "R_pkg    %5.2f    %5.2f    %5.2f"  % (r_pkg[0],         r_pkg[1],         r_pkg[2])
print "L_pkg    %5.2fn   %5.2fn   %5.2fn" % (l_pkg[0] * 1.e9,  l_pkg[1] * 1.e9,  l_pkg[2] * 1.e9)
print "C_pkg    %5.2fp   %5.2fp   %5.2fp" % (c_pkg[0] * 1.e12, c_pkg[1] * 1.e12, c_pkg[2] * 1.e12)
}

[Pin]  signal_name        model_name            R_pin  L_pin  C_pin
1p     Tx_1_P             @(model_name)
1n     Tx_1_N             @(model_name)
2p     Tx_2_P             @(model_name)
2n     Tx_2_N             @(model_name)
3p     Tx_3_P             @(model_name)
3n     Tx_3_N             @(model_name)

[Diff_Pin] inv_pin vdiff tdelay_typ tdelay_min tdelay_max
1p           1n     0.1V     NA         NA         NA
2p           2n     0.1V     NA         NA         NA
3p           3n     0.1V     NA         NA         NA

[Model]   @(model_name)
Model_type   @(model_type)

@{
print "C_comp    %5.2fp   %5.2fp   %5.2fp" % (c_comp[0] * 1.e12, c_comp[1] * 1.e12, c_comp[2] * 1.e12)
if(model_type == 'Output'):
    print "Cref  = {}".format(c_ref)
    print "Vref  = {}".format(v_ref)
    print "Vmeas = {}".format(v_meas)
    print "Rref  = {}".format(r_ref)
else:
    print "Vinl = {}".format(voltage_range[0] / 2. - 0.025)
    print "Vinh = {}".format(voltage_range[0] / 2. + 0.025)
}

[Algorithmic Model]
Executable linux_gcc4.1.2_32          @(model_name)_x86.so     @(model_name).ami
Executable linux_gcc4.1.2_64          @(model_name)_amd64.so   @(model_name).ami
Executable Windows_VisualStudio_32    @(model_name)_x86.dll    @(model_name).ami
Executable Windows_VisualStudio_64    @(model_name)_amd64.dll  @(model_name).ami
[End Algorithmic Model]

@{
print "[Temperature_Range]    %5.1f    %5.1f    %5.1f" % (temperature_range[0], temperature_range[1], temperature_range[2])
print "[Voltage_Range]        %5.2f    %5.2f    %5.2f" % (voltage_range[0],     voltage_range[1],     voltage_range[2])
}

@{
if(model_type == 'Output'):
    print "[Pulldown]"
    print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (-1. * voltage_range[0], -10., -10., -10.)
    for v in [k * voltage_range[0] for k in range(2)]:
        i = v / array(impedance)
        print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (v, i[0], i[1], i[2])
    print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (2. * voltage_range[0], 10., 10., 10.)

    print "[Pullup]"
    print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (-1. * voltage_range[0], 10., 10., 10.)
    for v in [k * voltage_range[0] for k in range(2)]:
        i = -1. * v / array(impedance)
        print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (v, i[0], i[1], i[2])
    print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (2. * voltage_range[0], -10., -10., -10.)

    print "[Ramp]"
    dv = 0.6 * array([v * 50. / (50. + z) for (v, z) in zip(voltage_range, impedance)])
    dt = 1.e12 * dv / array(slew_rate)
    print "dV/dt_r    %5.3f/%5.2fp    %5.3f/%5.2fp    %5.3f/%5.2fp" % (dv[0], dt[0], dv[1], dt[1], dv[2], dt[2])
    print "dV/dt_f    %5.3f/%5.2fp    %5.3f/%5.2fp    %5.3f/%5.2fp" % (dv[0], dt[0], dv[1], dt[1], dv[2], dt[2])
    print
else:
    print "[GND Clamp]"
    print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (-1. * voltage_range[0], -10., -10., -10.)
    for v in [k * voltage_range[0] for k in range(3)]:
        i = v / array(impedance)
        print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (v, i[0], i[1], i[2])
    print
    print "[Power Clamp]"
    print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (-1. * voltage_range[0], 10., 10., 10.)
    print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (0., 0., 0., 0.)
    print "%-5.2f    %-10.3e    %-10.3e    %-10.3e" % (2. * voltage_range[0], 0., 0., 0.)
    print
}

[END]

