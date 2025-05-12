@{
from numpy import array

version           = ibis_params['version']
file_name         = ibis_params['file_name']
file_rev          = ibis_params['file_rev']
copyright         = ibis_params['copyright']
source            = ibis_params['source']
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

[IBIS Ver]   @(version)
[File Name]  @(file_name)
[File Rev]   @(file_rev)

[Date]       @(date)

[Source]     @(source)

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
This IBIS file was generated using the template file: "generic.ibs.em".

[Copyright]    @(copyright)

[Component]    @(component)
[Manufacturer] @(manufacturer)

[Package]

@{
print("R_pkg    %5.2f    %5.2f    %5.2f"  % (r_pkg[0],         r_pkg[1],         r_pkg[2]))
print("L_pkg    %5.2fn   %5.2fn   %5.2fn" % (l_pkg[0] * 1.e9,  l_pkg[1] * 1.e9,  l_pkg[2] * 1.e9))
print("C_pkg    %5.2fp   %5.2fp   %5.2fp" % (c_pkg[0] * 1.e12, c_pkg[1] * 1.e12, c_pkg[2] * 1.e12))
}

[Pin]  signal_name        model_name            R_pin  L_pin  C_pin
@{
if model_type.startswith("Output") or model_type == "Repeater":
    for n in range(3):
        print(f"{n + 1}p     Tx_{n + 1}_P             {model_name}_Tx")
        print(f"{n + 1}n     Tx_{n + 1}_N             {model_name}_Tx")
if model_type.startswith("Input") or model_type == "Repeater":
    for n in range(3):
        print(f"{n + 4}p     Rx_{n + 4}_P             {model_name}_Rx")
        print(f"{n + 4}n     Rx_{n + 4}_N             {model_name}_Rx")
}

[Diff_Pin] inv_pin vdiff tdelay_typ tdelay_min tdelay_max
@{
if model_type.startswith("Output") or model_type == "Repeater":
    for n in range(3):
        print(f"{n + 1}p     {n + 1}n     0.1V    NA    NA    NA")
if model_type.startswith("Input") or model_type == "Repeater":
    for n in range(3):
        print(f"{n + 4}p     {n + 4}n     0.1V    NA    NA    NA")
}

@{
if model_type == "Repeater":
    print("[Repeater Pin]  tx_non_inv_pin")
    for n in range(3):
        print(f"       {n + 4}p              {n + 1}p")
}

@{
if model_type.startswith("Output") or model_type == "Repeater":
    print(f"[Model]   {model_name}_Tx")
    print("Model_type   Output")
    print(f"C_comp    {c_comp[0]*1.e12:5.2f}p   {c_comp[1]*1.e12:5.2f}p   {c_comp[2]*1.e12:5.2f}p")
    print(f"Cref  = {c_ref}")
    print(f"Vref  = {v_ref}")
    print(f"Vmeas = {v_meas}")
    print(f"Rref  = {r_ref}")
    print("")
    print("[Algorithmic Model]")
    print(f"Executable linux_gcc4.1.2_32        {model_name}_tx_x86.so         {model_name}_tx.ami")
    print(f"Executable linux_gcc4.1.2_64        {model_name}_tx_x86_amd64.so   {model_name}_tx.ami")
    print(f"Executable Windows_VisualStudio_32  {model_name}_tx_x86.dll        {model_name}_tx.ami")
    print(f"Executable Windows_VisualStudio_64  {model_name}_tx_x86_amd64.dll  {model_name}_tx.ami")
    print("[End Algorithmic Model]")
    print("")
    print("[Pulldown]")
    print(f"{-1.*voltage_range[0]:-5.2f}    -10.0    -10.0    -10.0")
    for v in [k * voltage_range[0] for k in range(2)]:
        i = v / array(impedance)
        print(f"{v:-5.2f}    {i[0]:-10.3e}    {i[1]:-10.3e}    {i[2]:-10.3e}")
    print(f"{2.*voltage_range[0]:-5.2f}    10.0    10.0    10.0")

    print("[Pullup]")
    print(f"{-1.*voltage_range[0]:-5.2f}    10.0    10.0    10.0")
    for v in [k * voltage_range[0] for k in range(2)]:
        i = -1. * v / array(impedance)
        print(f"{v:-5.2f}    {i[0]:-10.3e}    {i[1]:-10.3e}    {i[2]:-10.3e}")
    print(f"{2.*voltage_range[0]:-5.2f}    -10.0    -10.0    -10.0")

    print("[Ramp]")
    dv = 0.6 * array([v * 50. / (50. + z) for (v, z) in zip(voltage_range, impedance)])
    dt = 1.e12 * dv / array(slew_rate)
    print(f"dV/dt_r    {dv[0]:5.3f}/{dt[0]:05.2f}p    {dv[1]:5.3f}/{dt[1]:05.2f}p    {dv[2]:5.3f}/{dt[2]:05.2f}p")
    print(f"dV/dt_f    {dv[0]:5.3f}/{dt[0]:05.2f}p    {dv[1]:5.3f}/{dt[1]:05.2f}p    {dv[2]:5.3f}/{dt[2]:05.2f}p")
    print("")
    print("[GND Clamp]")
    print(f"{-1.*voltage_range[0]:-5.2f}    0.0    0.0    0.0")
    for v in [k * voltage_range[0] for k in range(3)]:
        i = v / array(impedance) / 2
        print(f"{v:-5.2f}    0.0  0.0  0.0")
    print("")
    print("[Power Clamp]")
    print(f"{-1.*voltage_range[0]:-5.2f}    0.0    0.0    0.0")
    for v in [k * voltage_range[0] for k in range(3)]:
        i = v / array(impedance) / 2
        print(f"{v:-5.2f}    0.0  0.0  0.0")
    print("")
    print(f"[Temperature_Range]    {temperature_range[0]:5.1f}    {temperature_range[1]:5.1f}    {temperature_range[2]:5.1f}")
    print(f"[Voltage_Range]        {voltage_range[0]:5.2f}    {voltage_range[1]:5.2f}    {voltage_range[2]:5.2f}")
}

@{
if model_type.startswith("Input") or model_type == "Repeater":
    print(f"[Model]   {model_name}_Rx")
    print("Model_type   Input")
    print(f"C_comp    {c_comp[0]*1.e12:5.2f}p   {c_comp[1]*1.e12:5.2f}p   {c_comp[2]*1.e12:5.2f}p")
    print(f"Vinl = {voltage_range[0]/2.-0.025}")
    print(f"Vinh = {voltage_range[0]/2.+0.025}")
    print("")
    print("[Algorithmic Model]")
    print(f"Executable linux_gcc4.1.2_32        {model_name}_rx_x86.so         {model_name}_rx.ami")
    print(f"Executable linux_gcc4.1.2_64        {model_name}_rx_x86_amd64.so   {model_name}_rx.ami")
    print(f"Executable Windows_VisualStudio_32  {model_name}_rx_x86.dll        {model_name}_rx.ami")
    print(f"Executable Windows_VisualStudio_64  {model_name}_rx_x86_amd64.dll  {model_name}_rx.ami")
    print("[End Algorithmic Model]")
    print("")
    print("[GND Clamp]")
    print(f"{-1.*voltage_range[0]:-5.2f}    -10.0    -10.0    -10.0")
    for v in [k * voltage_range[0] for k in range(3)]:
        i = v / array(impedance) / 2
        print(f"{v:-5.2f}    {i[0]:-10.3e}    {i[1]:-10.3e}    {i[2]:-10.3e}")
    print("")
    print("[Power Clamp]")
    print(f"{-1.*voltage_range[0]:-5.2f}    10.0    10.0    10.0")
    for v in [k * voltage_range[0] for k in range(3)]:
        i = v / array(impedance) / 2
        print(f"{v:-5.2f}    {-i[0]:-10.3e}    {-i[1]:-10.3e}    {-i[2]:-10.3e}")
    print("")
    print(f"[Temperature_Range]    {temperature_range[0]:5.1f}    {temperature_range[1]:5.1f}    {temperature_range[2]:5.1f}")
    print(f"[Voltage_Range]        {voltage_range[0]:5.2f}    {voltage_range[1]:5.2f}    {voltage_range[2]:5.2f}")
}

[END]
