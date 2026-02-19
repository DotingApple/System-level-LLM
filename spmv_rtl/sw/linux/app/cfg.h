// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef __ESP_CFG_000_H__
#define __ESP_CFG_000_H__

#include "libesp.h"
#include "spmv_rtl.h"

typedef int64_t token_t;

/* <<--params-def-->> */
#define SPMV_NNZ 4096
#define SPMV_VEC_LEN 128

/* <<--params-->> */
const int32_t spmv_nnz = SPMV_NNZ;
const int32_t spmv_vec_len = SPMV_VEC_LEN;

#define NACC 1

struct spmv_rtl_access spmv_cfg_000[] = {
	{
		/* <<--descriptor-->> */
		.spmv_nnz = SPMV_NNZ,
		.spmv_vec_len = SPMV_VEC_LEN,
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
		.devname = "spmv_rtl.0",
		.ioctl_req = SPMV_RTL_IOC_ACCESS,
		.esp_desc = &(spmv_cfg_000[0].esp),
	}
};

#endif /* __ESP_CFG_000_H__ */
