#!/bin/bash
# Non-interactive driver for tools/accgen/accgen.sh that reproduces the
# lstm_v2_rtl skeleton. Records the exact prompt values used.
#
# Intent: lstm_v2 differs from lstm_rtl only by accgen-prompt-driven
# "sizes". Same register list (3 registers: num_timesteps, hidden_dim,
# in_dim), same data width, same expressions -- the only meaningful
# change is the in_dim default (6000 -> 11000).
#
# After this script runs, apply the FSM port separately:
#   - copy lstm_rtl_basic_dma64.v body into lstm_v2_rtl_basic_dma64.v
#     (rename module only)
#   - copy lstm.c into lstm_v2.c, swap device identifiers, set
#     in_dim const to 11000
#   - sync accelerators/rtl/lstm_v2_rtl/ -> tech/virtex7/acc/lstm_v2_rtl/
#
# Prerequisites (accgen.sh RHEL bug fixes must be applied):
#   - rename exit-4 handled with || true
#   - RTL-flow module sed uses acc_full_name (not cc_full_name)

set -e

ESP_ROOT=${ESP_ROOT:-/home/cz2931/esp}
ACC_DIR=$ESP_ROOT/accelerators/rtl/lstm_v2_rtl

if [ -d "$ACC_DIR" ]; then
    echo "ERROR: $ACC_DIR already exists. Remove it first."
    exit 1
fi

cd "$ESP_ROOT"

# accgen.sh prompts, in order, with the values chosen for lstm_v2:
#
#   1.  accelerator name           -> lstm_v2
#   2.  flow                       -> R (RTL)
#   3.  ESP path                   -> (blank, default PWD)
#   4.  device id (3 hex digits)   -> 032
#                                     (0x031 used by lstm_rtl)
#   5.  register 0: num_timesteps  -> default 1, max 1024
#   6.  register 1: hidden_dim     -> default 64, max 64
#   7.  register 2: in_dim         -> default 11000, max 16384
#                                     (11000 so num_timesteps*in_dim*2
#                                      bytes >= 21,704, the fixed HW read
#                                      length; lstm_rtl's 6000 leaves the
#                                      tail of the read in uninitialised
#                                      DRAM)
#   8.  (blank register name ends the loop)
#   9.  data bit-width             -> 16 (matches LSTM core Q4.12)
#   10. input data size expr       -> num_timesteps * in_dim
#   11. output data size expr      -> num_timesteps * hidden_dim
#   12. chunking factor            -> 1
#   13. batching factor            -> 1
#   14. (IN_PLACE prompt skipped because in_size != out_size)

./tools/accgen/accgen.sh <<'EOF'
lstm_v2
R

032
num_timesteps
1
1024
hidden_dim
64
64
in_dim
11000
16384

16
num_timesteps * in_dim
num_timesteps * hidden_dim
1
1
EOF

echo ""
echo "=== lstm_v2_rtl skeleton generated ==="
