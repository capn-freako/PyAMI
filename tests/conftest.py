import pytest


@pytest.fixture
def ami_test_file(tmp_path):
    """Return a golden AMI parameter file to test with."""
    ami_file = tmp_path.joinpath("test.ami")
    with open(ami_file, "w", encoding="UTF-8") as output:
        output.write(
            r"""(example_tx

    (Description "Example Tx model from ibisami package.")

    (Reserved_Parameters
         (AMI_Version
             (Usage Info )
             (Type String )
             (Value "5.1" )
             (Description "Version of IBIS standard we comply with." )
         )
         (Init_Returns_Impulse
             (Usage Info )
             (Type Boolean )
             (Value True )
             (Description "In fact, this model is, currently, Init-only." )
         )
         (GetWave_Exists
             (Usage Info )
             (Type Boolean )
             (Value True )
             (Description "This model is dual-mode, with GetWave() mimicking Init()." )
         )
    )
    (Model_Specific
         (tx_tap_units
             (Usage In )
             (Type Integer )
             (Range 27 6 27 )
             (Description "Total current available to FIR filter." )
         )
         (tx_tap_np1
             (Usage In )
             (Type Integer )
             (Range 0 0 10 )
             (Description "First (and only) pre-tap." )
         )
         (tx_tap_nm1
             (Usage In )
             (Type Integer )
             (Range 0 0 10 )
             (Description "First post-tap." )
         )
         (tx_tap_nm2
             (Usage In )
             (Type Integer )
             (Range 0 0 10 )
             (Description "Second post-tap." )
         )
    )

)

"""
        )
    return ami_file


@pytest.fixture
def ibis_test_file(tmp_path):
    """Return a golden ibis model file to test with."""
    ibis_file = tmp_path.joinpath("test.ibs")
    with open(ibis_file, "w", encoding="UTF-8") as output:
        output.write(
            r"""[IBIS Ver]   5.1



[File Name]  example_tx.ibs
[File Rev]   v0.1

[Date]       2019-02-10

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

[Copyright]    Copyright (c) 2016 David Banas; all rights reserved World wide.
[Component]    Example_Tx
[Manufacturer] (n/a)

[Package]

R_pkg     0.10     0.00     0.50
L_pkg    10.00n    0.10n   50.00n
C_pkg     1.00p    0.01p    5.00p


[Pin]  signal_name        model_name            R_pin  L_pin  C_pin
1p     Tx_1_P             example_tx
1n     Tx_1_N             example_tx
2p     Tx_2_P             example_tx
2n     Tx_2_N             example_tx
3p     Tx_3_P             example_tx
3n     Tx_3_N             example_tx

[Diff_Pin] inv_pin vdiff tdelay_typ tdelay_min tdelay_max
1p           1n     0.1V     NA         NA         NA
2p           2n     0.1V     NA         NA         NA
3p           3n     0.1V     NA         NA         NA

[Model]   example_tx
Model_type   Output

C_comp     1.00p    0.01p    5.00p
Cref  = 0
Vref  = 0.5
Vmeas = 0.5
Rref  = 50


[Algorithmic Model]
Executable linux_gcc4.1.2_32          example_tx_x86.so         example_tx.ami
Executable linux_gcc4.1.2_64          example_tx_x86_amd64.so   example_tx.ami
Executable Windows_VisualStudio_32    example_tx_x86.dll        example_tx.ami
Executable Windows_VisualStudio_64    example_tx_x86_amd64.dll  example_tx.ami
[End Algorithmic Model]

[Temperature_Range]     25.0      0.0    100.0
[Voltage_Range]         1.80     1.62     1.98


[Pulldown]
-1.80    -1.000e+01    -1.000e+01    -1.000e+01
0.00     0.000e+00     0.000e+00     0.000e+00
1.80     3.600e-02     4.000e-02     3.273e-02
3.60     1.000e+01     1.000e+01     1.000e+01

[Pullup]
-1.80    1.000e+01     1.000e+01     1.000e+01
0.00     -0.000e+00    -0.000e+00    -0.000e+00
1.80     -3.600e-02    -4.000e-02    -3.273e-02
3.60     -1.000e+01    -1.000e+01    -1.000e+01

[Ramp]
dV/dt_r    0.540/108.00p    0.512/511.58p    0.566/56.57p
dV/dt_f    0.540/108.00p    0.512/511.58p    0.566/56.57p

[END]
"""
        )
    return ibis_file
