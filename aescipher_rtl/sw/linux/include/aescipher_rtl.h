// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#ifndef _AESCIPHER_RTL_H_
#define _AESCIPHER_RTL_H_

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

struct aescipher_rtl_access {
	struct esp_access esp;
	/* <<--regs-->> */
	unsigned aes_key_3;
	unsigned aes_key_2;
	unsigned aes_key_1;
	unsigned aes_key_0;
	unsigned aes_key_7;
	unsigned aes_key_6;
	unsigned aes_key_5;
	unsigned aes_key_4;
	unsigned aes_num_blocks;
	unsigned src_offset;
	unsigned dst_offset;
};

#define AESCIPHER_RTL_IOC_ACCESS	_IOW ('S', 0, struct aescipher_rtl_access)

#endif /* _AESCIPHER_RTL_H_ */
