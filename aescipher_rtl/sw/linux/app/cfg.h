// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef __ESP_CFG_000_H__
#define __ESP_CFG_000_H__

#include "libesp.h"
#include "aescipher_rtl.h"

typedef int64_t token_t;

/* <<--params-def-->> */
#define AES_KEY_3 0x0d0e0f10
#define AES_KEY_2 0x090a0b0c
#define AES_KEY_1 0x05060708
#define AES_KEY_0 0x01020304
#define AES_KEY_7 0x1d1e1f00
#define AES_KEY_6 0x191a1b1c
#define AES_KEY_5 0x15161718
#define AES_KEY_4 0x11121314
#define AES_NUM_BLOCKS 1

/* <<--params-->> */
const int32_t aes_key_3 = AES_KEY_3;
const int32_t aes_key_2 = AES_KEY_2;
const int32_t aes_key_1 = AES_KEY_1;
const int32_t aes_key_0 = AES_KEY_0;
const int32_t aes_key_7 = AES_KEY_7;
const int32_t aes_key_6 = AES_KEY_6;
const int32_t aes_key_5 = AES_KEY_5;
const int32_t aes_key_4 = AES_KEY_4;
const int32_t aes_num_blocks = AES_NUM_BLOCKS;

#define NACC 1

struct aescipher_rtl_access aescipher_cfg_000[] = {
	{
		/* <<--descriptor-->> */
		.aes_key_3 = AES_KEY_3,
		.aes_key_2 = AES_KEY_2,
		.aes_key_1 = AES_KEY_1,
		.aes_key_0 = AES_KEY_0,
		.aes_key_7 = AES_KEY_7,
		.aes_key_6 = AES_KEY_6,
		.aes_key_5 = AES_KEY_5,
		.aes_key_4 = AES_KEY_4,
		.aes_num_blocks = AES_NUM_BLOCKS,
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
		.devname = "aescipher_rtl.0",
		.ioctl_req = AESCIPHER_RTL_IOC_ACCESS,
		.esp_desc = &(aescipher_cfg_000[0].esp),
	}
};

#endif /* __ESP_CFG_000_H__ */
