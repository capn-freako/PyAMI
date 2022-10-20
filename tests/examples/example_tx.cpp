/** \file example_tx.cpp
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

