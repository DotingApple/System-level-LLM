// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef __ESP_CFG_000_H__
#define __ESP_CFG_000_H__

#include "libesp.h"
#include "fcdnn_acc_rtl.h"

typedef int32_t token_t;

/* <<--params-def-->> */
#define ARRAY_SIZE 16
#define MUX_CFG 0
#define EXP_VAL 8
#define PIPE_MODE 0
#define RUNS 1

/* <<--params-->> */
const int32_t array_size = ARRAY_SIZE;
const int32_t mux_cfg = MUX_CFG;
const int32_t exp_val = EXP_VAL;
const int32_t pipe_mode = PIPE_MODE;
const int32_t runs = RUNS;

#define NACC 1

struct fcdnn_acc_rtl_access fcdnn_acc_cfg_000[] = {
	{
		/* <<--descriptor-->> */
		.array_size = ARRAY_SIZE,
		.mux_cfg = MUX_CFG,
		.exp_val = EXP_VAL,
		.pipe_mode = PIPE_MODE,
		.runs = RUNS,
		.src_offset = 0,
		.dst_offset = 0,
		.esp.coherence = ACC_COH_NONE,
		.esp.p2p_store = 0,
		.esp.p2p_nsrcs = 0,
		.esp.p2p_srcs = {"", "", "", ""},
	}
};

esp_thread_info_t cfg_000[] = {
	{
		.run = true,
		.devname = "fcdnn_acc_rtl.0",
		.ioctl_req = FCDNN_ACC_RTL_IOC_ACCESS,
		.esp_desc = &(fcdnn_acc_cfg_000[0].esp),
	}
};

#endif /* __ESP_CFG_000_H__ */
