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

@{
max_tap_pos = -1

for pname in ami_params['model'].keys():
    param = ami_params['model'][pname]
    tap_pos = param['tap_pos']
    if(tap_pos > max_tap_pos):
        max_tap_pos = tap_pos

print("        int taps[%d];" % (max_tap_pos + 1))

for pname in ami_params['model'].keys():
    param = ami_params['model'][pname]
    if(param['usage'] == 'In' or param['usage'] == 'InOut'):
        ptype = param['type']
        print("       ", param_types[ptype]['c_type'], pname, ";")
        print("       ", 'node_names.push_back("%s");' % pname)
        print("       ", '%s = %s(node_names,' % (pname, param_types[ptype]['getter']), param['default'], ');' )
        tap_pos = param['tap_pos']
        if (tap_pos > -1):
            print("       ", 'taps[%d] = %s;' % (tap_pos, pname))
        print("       ", 'node_names.pop_back();')
}
        taps[1] = tx_tap_units - (taps[0] + taps[2] + taps[3]);
        if ( (tx_tap_units - 2 * (taps[0] + taps[2] + taps[3])) < 6 )
            msg << "WARNING: Illegal Tx pre-emphasis tap configuration!\n";

        // Fill in params_.
        std::ostringstream params;
        params << "(example_tx";
        params << " (tx_tap_units " << tx_tap_units << ")";
@{
for tap_num in range(max_tap_pos + 1):
    print("       ", 'params << " (taps[%d] " << taps[%d] << ")";' % (tap_num, tap_num))
}
        tap_weights_.clear();
        int samples_per_bit = int(bit_time / sample_interval);
        int tap_signs[] = {-1, 1, -1, -1};
        have_preemph_ = true;
        for (auto i = 0; i <= @(max_tap_pos); i++) {
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

