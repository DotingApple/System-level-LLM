// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include <linux/of_device.h>
#include <linux/mm.h>

#include <asm/io.h>

#include <esp_accelerator.h>
#include <esp.h>

#include "sha256_rtl.h"

#define DRV_NAME	"sha256_rtl"

/* <<--regs-->> */
#define SHA256_SHA_MSG_SIZE_REG 0x44
#define SHA256_SHA_MODE_REG 0x40

struct sha256_rtl_device {
	struct esp_device esp;
};

static struct esp_driver sha256_driver;

static struct of_device_id sha256_device_ids[] = {
	{
		.name = "SLD_SHA256_RTL",
	},
	{
		.name = "eb_007",
	},
	{
		.compatible = "sld,sha256_rtl",
	},
	{ },
};

static int sha256_devs;

static inline struct sha256_rtl_device *to_sha256(struct esp_device *esp)
{
	return container_of(esp, struct sha256_rtl_device, esp);
}

static void sha256_prep_xfer(struct esp_device *esp, void *arg)
{
	struct sha256_rtl_access *a = arg;

	/* <<--regs-config-->> */
	iowrite32be(a->sha_msg_size, esp->iomem + SHA256_SHA_MSG_SIZE_REG);
	iowrite32be(a->sha_mode, esp->iomem + SHA256_SHA_MODE_REG);
	iowrite32be(a->src_offset, esp->iomem + SRC_OFFSET_REG);
	iowrite32be(a->dst_offset, esp->iomem + DST_OFFSET_REG);

}

static bool sha256_xfer_input_ok(struct esp_device *esp, void *arg)
{
	/* struct sha256_rtl_device *sha256 = to_sha256(esp); */
	/* struct sha256_rtl_access *a = arg; */

	return true;
}

static int sha256_probe(struct platform_device *pdev)
{
	struct sha256_rtl_device *sha256;
	struct esp_device *esp;
	int rc;

	sha256 = kzalloc(sizeof(*sha256), GFP_KERNEL);
	if (sha256 == NULL)
		return -ENOMEM;
	esp = &sha256->esp;
	esp->module = THIS_MODULE;
	esp->number = sha256_devs;
	esp->driver = &sha256_driver;
	rc = esp_device_register(esp, pdev);
	if (rc)
		goto err;

	sha256_devs++;
	return 0;
 err:
	kfree(sha256);
	return rc;
}

static int __exit sha256_remove(struct platform_device *pdev)
{
	struct esp_device *esp = platform_get_drvdata(pdev);
	struct sha256_rtl_device *sha256 = to_sha256(esp);

	esp_device_unregister(esp);
	kfree(sha256);
	return 0;
}

static struct esp_driver sha256_driver = {
	.plat = {
		.probe		= sha256_probe,
		.remove		= sha256_remove,
		.driver		= {
			.name = DRV_NAME,
			.owner = THIS_MODULE,
			.of_match_table = sha256_device_ids,
		},
	},
	.xfer_input_ok	= sha256_xfer_input_ok,
	.prep_xfer	= sha256_prep_xfer,
	.ioctl_cm	= SHA256_RTL_IOC_ACCESS,
	.arg_size	= sizeof(struct sha256_rtl_access),
};

static int __init sha256_init(void)
{
	return esp_driver_register(&sha256_driver);
}

static void __exit sha256_exit(void)
{
	esp_driver_unregister(&sha256_driver);
}

module_init(sha256_init)
module_exit(sha256_exit)

MODULE_DEVICE_TABLE(of, sha256_device_ids);

MODULE_AUTHOR("Emilio G. Cota <cota@braap.org>");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("sha256_rtl driver");
