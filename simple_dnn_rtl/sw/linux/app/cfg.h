// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef __ESP_CFG_000_H__
#define __ESP_CFG_000_H__

#include "libesp.h"
#include "simple_dnn_rtl.h"

typedef int32_t token_t;

/* <<--params-def-->> */
#define NUM_IN 3
#define NUM_OUT 1
#define NUM_HIDDEN 8

/* <<--params-->> */
const int32_t num_in = NUM_IN;
const int32_t num_out = NUM_OUT;
const int32_t num_hidden = NUM_HIDDEN;

#define NACC 1

struct simple_dnn_rtl_access simple_dnn_cfg_000[] = {
	{
		/* <<--descriptor-->> */
		.num_in = NUM_IN,
		.num_out = NUM_OUT,
		.num_hidden = NUM_HIDDEN,
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
		.devname = "simple_dnn_rtl.0",
		.ioctl_req = SIMPLE_DNN_RTL_IOC_ACCESS,
		.esp_desc = &(simple_dnn_cfg_000[0].esp),
	}
};

#endif /* __ESP_CFG_000_H__ */
