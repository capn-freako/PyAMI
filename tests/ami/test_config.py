from pathlib import Path
from unittest.mock import patch

import pytest

import pyibisami.ami.config as config


class TestAMIConfig(object):
    @patch.object(config, "date", autospec=True)
    def test_ami_config(self, mock_date):
        """Using the example_tx.py and supporting cpp.em file verify the output."""

        mock_date.today.return_value = "2019-02-10"
        configurator = config.ami_config
        with pytest.deprecated_call():
            configurator(Path(__file__).parents[1].joinpath("examples", "example_tx.py"))

        with open(Path(__file__).parents[1].joinpath("examples", "example_tx.ami")) as ami_file:
            ami = ami_file.read()
            assert (
                ami
                == r"""(example_tx

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

        with open(Path(__file__).parents[1].joinpath("examples", "example_tx.cpp")) as cpp_file:
            cpp = cpp_file.read()
            assert (
                cpp
                == r"""/** \file example_tx.cpp
 *  \brief Example of using ibisami to build a Tx model.
 *
 * Original author: David Banas <br>
 * Original date:   May 8, 2015
 * Initial conversion to EmPy template format: Feb 25, 2016
 *
 * Copyright (c) 2015 David Banas; all rights reserved World wide.
 */

#define TAP_SCALE 0.0407

#include <string>
#include <vector>
#include "include/ami_tx.h"

/// An example device specific Tx model implementation.
class MyTx : public AmiTx {
    typedef AmiTx inherited;

 public:
    MyTx() {}
    ~MyTx() {}
    void init(double *impulse_matrix, const long number_of_rows,
            const long aggressors, const double sample_interval,
            const double bit_time, const std::string& AMI_parameters_in) override {

        // Let our base class do its thing.
        inherited::init(impulse_matrix, number_of_rows, aggressors,
            sample_interval, bit_time, AMI_parameters_in);

        // Grab our parameters and configure things accordingly.
        std::vector<std::string> node_names; node_names.clear();
        std::ostringstream msg;

        msg << "Initializing Tx...\n";

        int taps[4];
        int tx_tap_units ;
        node_names.push_back("tx_tap_units");
        tx_tap_units = get_param_int(node_names, 27 );
        node_names.pop_back();
        int tx_tap_np1 ;
        node_names.push_back("tx_tap_np1");
        tx_tap_np1 = get_param_int(node_names, 0 );
        taps[0] = tx_tap_np1;
        node_names.pop_back();
        int tx_tap_nm1 ;
        node_names.push_back("tx_tap_nm1");
        tx_tap_nm1 = get_param_int(node_names, 0 );
        taps[2] = tx_tap_nm1;
        node_names.pop_back();
        int tx_tap_nm2 ;
        node_names.push_back("tx_tap_nm2");
        tx_tap_nm2 = get_param_int(node_names, 0 );
        taps[3] = tx_tap_nm2;
        node_names.pop_back();

        taps[1] = tx_tap_units - (taps[0] + taps[2] + taps[3]);
        if ( (tx_tap_units - 2 * (taps[0] + taps[2] + taps[3])) < 6 )
            msg << "WARNING: Illegal Tx pre-emphasis tap configuration!\n";

        // Fill in params_.
        std::ostringstream params;
        params << "(example_tx";
        params << " (tx_tap_units " << tx_tap_units << ")";
        params << " (taps[0] " << taps[0] << ")";
        params << " (taps[1] " << taps[1] << ")";
        params << " (taps[2] " << taps[2] << ")";
        params << " (taps[3] " << taps[3] << ")";

        tap_weights_.clear();
        int samples_per_bit = int(bit_time / sample_interval);
        int tap_signs[] = {-1, 1, -1, -1};
        have_preemph_ = true;
        for (auto i = 0; i <= 3; i++) {
            tap_weights_.push_back(taps[i] * TAP_SCALE * tap_signs[i]);
            params << " (tap_weights_[" << i << "] " << tap_weights_.back() << ")";
            for (auto j = 1; j < samples_per_bit; j++)
                tap_weights_.push_back(0.0);
        }
        param_str_ = params.str() + "\n";
        msg_ = msg.str() + "\n";
    }
} my_tx;

AMIModel *ami_model = &my_tx;  ///< The pointer required by the API implementation.
"""
            )
        Path(__file__).parents[1].joinpath("examples", "example_tx.ami").unlink()
        Path(__file__).parents[1].joinpath("examples", "example_tx.ibs").unlink()
        Path(__file__).parents[1].joinpath("examples", "example_tx.cpp").unlink()


def _copy_example(tmp_path, drop_line=None):
    "Copy the example model configurator (and its C++ template) into ``tmp_path``."
    examples = Path(__file__).parents[1].joinpath("examples")
    lines = examples.joinpath("example_tx.py").read_text(encoding="utf-8").splitlines(keepends=True)
    tmp_path.joinpath("example_tx.py").write_text(
        "".join(line for line in lines if line.strip() != drop_line), encoding="utf-8")
    tmp_path.joinpath("example_tx.cpp.em").write_text(
        examples.joinpath("example_tx.cpp.em").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path.joinpath("example_tx.py")


def test_ami_config_builds_parsable_ibs(tmp_path):
    from pyibisami.ibis.file import IBISModel

    with pytest.deprecated_call():
        config.ami_config(_copy_example(tmp_path))
    assert IBISModel(str(tmp_path / "example_tx.ibs")).file_name == "example_tx.ibs"


def test_ami_config_template_error_fails_cleanly(tmp_path):
    """A template error must fail the command (exit 1) and leave no partial output file behind."""
    from click.testing import CliRunner

    py_file = _copy_example(tmp_path, drop_line='"version": "5.1",')
    result = CliRunner().invoke(config.main, [str(py_file)])
    assert result.exit_code == 1
    assert "Error: Building 'example_tx.ibs' from 'generic.ibs.em' failed: KeyError: 'version'" in result.output
    assert not tmp_path.joinpath("example_tx.ibs").exists()
