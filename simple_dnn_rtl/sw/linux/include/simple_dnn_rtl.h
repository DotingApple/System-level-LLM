// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef _SIMPLE_DNN_RTL_H_
#define _SIMPLE_DNN_RTL_H_

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

struct simple_dnn_rtl_access {
	struct esp_access esp;
	/* <<--regs-->> */
	unsigned num_in;
	unsigned num_out;
	unsigned num_hidden;
	unsigned src_offset;
	unsigned dst_offset;
};

#define SIMPLE_DNN_RTL_IOC_ACCESS	_IOW ('S', 0, struct simple_dnn_rtl_access)

#endif /* _SIMPLE_DNN_RTL_H_ */
