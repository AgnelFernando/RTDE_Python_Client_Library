#!/usr/bin/env python
# Copyright (c) 2020-2022, Universal Robots A/S,
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the Universal Robots A/S nor the names of its
#      contributors may be used to endorse or promote products derived
#      from this software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL UNIVERSAL ROBOTS A/S BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import argparse
import logging
import sys

sys.path.append("../")
import rtde.rtde as rtde
import rtde.rtde_config as rtde_config
import rtde.csv_writer as csv_writer
import rtde.csv_binary_writer as csv_binary_writer

# parameters
parser = argparse.ArgumentParser()
parser.add_argument(
    "--host", default="localhost", help="name of host to connect to (localhost)"
)
parser.add_argument(
    "--samples", type=int, default=0, help="number of samples to record"
)
parser.add_argument(
    "--frequency", type=int, default=125, help="the sampling frequency in Herz"
)


parser.add_argument(
    "--buffered",
    help="Use buffered receive which doesn't skip data",
    action="store_true",
)
args = parser.parse_args()

conf = rtde_config.ConfigFile("record_configuration.xml")
output_names, output_types = conf.get_recipe("out")

con = rtde.RTDE(args.host, 30004)
con.connect()

# get controller version
con.get_controller_version()

# setup recipes
if not con.send_output_setup(output_names, output_types, frequency=args.frequency):
    logging.error("Unable to configure output")
    sys.exit()

# start data synchronization
if not con.send_start():
    logging.error("Unable to start synchronization")
    sys.exit()


with open("robot_data.csv", "w") as csvfile:
    writer = csv_writer.CSVWriter(csvfile, output_names, output_types)

    writer.writeheader()

    i = 1
    prev_state = None
    keep_running = True
    threshold = 1e-3
    
    while keep_running:

        if i % args.frequency == 0:
            if args.samples > 0:
                sys.stdout.write("\r")
                sys.stdout.write("{:.2%} done.".format(float(i) / float(args.samples)))
                sys.stdout.flush()
            else:
                sys.stdout.write("\r")
                sys.stdout.write("{:3d} samples.".format(i))
                sys.stdout.flush()
        if args.samples > 0 and i >= args.samples:
            keep_running = False
        try:
            state = con.receive_buffered(args.binary) if args.buffered else con.receive(args.binary)
            
            if state is not None:
                significant_change = False
                if prev_state is None:
                    writer.writerow(state)
                else:
                    val_new = state.__dict__['actual_q']
                    val_old = prev_state
                    if any([abs(val_new[i] - val_old[i]) > threshold for i in range(len(val_new))]):
                        significant_change = True
                
                if significant_change:
                    writer.writerow(state)

                prev_state = state.__dict__['actual_q']  
                i += 1

        except KeyboardInterrupt:
            keep_running = False
        except rtde.RTDEException:
            con.disconnect()
            sys.exit()


sys.stdout.write("\rComplete!            \n")

con.send_pause()
con.disconnect()
