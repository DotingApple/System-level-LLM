// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef __ESP_CFG_000_H__
#define __ESP_CFG_000_H__

#include "libesp.h"
#include "lstm_rtl.h"

typedef int16_t token_t;

/* <<--params-def-->> */
#define IN_DIM 168
#define HIDDEN_DIM 64
#define NUM_TIMESTEPS 1

/* <<--params-->> */
const int32_t in_dim = IN_DIM;
const int32_t hidden_dim = HIDDEN_DIM;
const int32_t num_timesteps = NUM_TIMESTEPS;

#define NACC 1

struct lstm_rtl_access lstm_cfg_000[] = {
	{
		/* <<--descriptor-->> */
		.in_dim = IN_DIM,
		.hidden_dim = HIDDEN_DIM,
		.num_timesteps = NUM_TIMESTEPS,
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
		.devname = "lstm_rtl.0",
		.ioctl_req = LSTM_RTL_IOC_ACCESS,
		.esp_desc = &(lstm_cfg_000[0].esp),
	}
};

#endif /* __ESP_CFG_000_H__ */
