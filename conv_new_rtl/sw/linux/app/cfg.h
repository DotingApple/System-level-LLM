// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef __ESP_CFG_000_H__
#define __ESP_CFG_000_H__

#include "libesp.h"
#include "conv_new_rtl.h"

typedef int32_t token_t;

/* <<--params-def-->> */
#define PARAM_HEIGHT 64
#define PARAM_WIDTH 64

/* <<--params-->> */
const int32_t param_height = PARAM_HEIGHT;
const int32_t param_width = PARAM_WIDTH;

#define NACC 1

struct conv_new_rtl_access conv_new_cfg_000[] = {
	{
		/* <<--descriptor-->> */
		.param_height = PARAM_HEIGHT,
		.param_width = PARAM_WIDTH,
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
		.devname = "conv_new_rtl.0",
		.ioctl_req = CONV_NEW_RTL_IOC_ACCESS,
		.esp_desc = &(conv_new_cfg_000[0].esp),
	}
};

#endif /* __ESP_CFG_000_H__ */
