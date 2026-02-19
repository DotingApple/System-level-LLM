// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef _SHA256_RTL_H_
#define _SHA256_RTL_H_

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

struct sha256_rtl_access {
	struct esp_access esp;
	/* <<--regs-->> */
	unsigned sha_msg_size;
	unsigned sha_mode;
	unsigned src_offset;
	unsigned dst_offset;
};

#define SHA256_RTL_IOC_ACCESS	_IOW ('S', 0, struct sha256_rtl_access)

#endif /* _SHA256_RTL_H_ */
