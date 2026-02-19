// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef __ESP_CFG_000_H__
#define __ESP_CFG_000_H__

#include "libesp.h"
#include "sobel_v2_rtl.h"

typedef int64_t token_t;

/* <<--params-def-->> */
#define WIDTH 10
#define HEIGHT 10

/* <<--params-->> */
const int32_t width = WIDTH;
const int32_t height = HEIGHT;

#define NACC 1

struct sobel_v2_rtl_access sobel_v2_cfg_000[] = {
	{
		/* <<--descriptor-->> */
		.width = WIDTH,
		.height = HEIGHT,
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
		.devname = "sobel_v2_rtl.0",
		.ioctl_req = SOBEL_V2_RTL_IOC_ACCESS,
		.esp_desc = &(sobel_v2_cfg_000[0].esp),
	}
};

#endif /* __ESP_CFG_000_H__ */
