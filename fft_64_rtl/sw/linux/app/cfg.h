// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef __ESP_CFG_000_H__
#define __ESP_CFG_000_H__

#include "libesp.h"
#include "fft_64_rtl.h"

typedef int16_t token_t;

/* <<--params-def-->> */
#define FFT_POINTS 64

/* <<--params-->> */
const int32_t fft_points = FFT_POINTS;

#define NACC 1

struct fft_64_rtl_access fft_64_cfg_000[] = {
	{
		/* <<--descriptor-->> */
		.fft_points = FFT_POINTS,
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
		.devname = "fft_64_rtl.0",
		.ioctl_req = FFT_64_RTL_IOC_ACCESS,
		.esp_desc = &(fft_64_cfg_000[0].esp),
	}
};

#endif /* __ESP_CFG_000_H__ */
