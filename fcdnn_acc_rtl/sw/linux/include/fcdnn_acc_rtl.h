// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef _FCDNN_ACC_RTL_H_
#define _FCDNN_ACC_RTL_H_

#ifdef __KERNEL__
#include <linux/ioctl.h>
#include <linux/types.h>
#else
#include <sys/ioctl.h>
#include <stdint.h>
#ifndef __user
#define __user
#endif
#endif /* __KERNEL__ */

#include <esp.h>
#include <esp_accelerator.h>

struct fcdnn_acc_rtl_access {
	struct esp_access esp;
	/* <<--regs-->> */
	unsigned array_size;
	unsigned mux_cfg;
	unsigned exp_val;
	unsigned pipe_mode;
	unsigned runs;
	unsigned src_offset;
	unsigned dst_offset;
};

#define FCDNN_ACC_RTL_IOC_ACCESS	_IOW ('S', 0, struct fcdnn_acc_rtl_access)

#endif /* _FCDNN_ACC_RTL_H_ */
