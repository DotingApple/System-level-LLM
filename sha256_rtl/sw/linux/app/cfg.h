// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef __ESP_CFG_000_H__
#define __ESP_CFG_000_H__

#include "libesp.h"
#include "sha256_rtl.h"

typedef int32_t token_t;

/* <<--params-def-->> */
#define SHA_MSG_SIZE 8
#define SHA_MODE 0

/* <<--params-->> */
const int32_t sha_msg_size = SHA_MSG_SIZE;
const int32_t sha_mode = SHA_MODE;

#define NACC 1

struct sha256_rtl_access sha256_cfg_000[] = {
	{
		/* <<--descriptor-->> */
		.sha_msg_size = SHA_MSG_SIZE,
		.sha_mode = SHA_MODE,
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
		.devname = "sha256_rtl.0",
		.ioctl_req = SHA256_RTL_IOC_ACCESS,
		.esp_desc = &(sha256_cfg_000[0].esp),
	}
};

#endif /* __ESP_CFG_000_H__ */
