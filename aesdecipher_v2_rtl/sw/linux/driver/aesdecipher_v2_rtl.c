// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include <linux/of_device.h>
#include <linux/mm.h>

#include <asm/io.h>

#include <esp_accelerator.h>
#include <esp.h>

#include "aesdecipher_v2_rtl.h"

#define DRV_NAME	"aesdecipher_v2_rtl"

/* <<--regs-->> */
#define AESDECIPHER_V2_AES_KEY_3_REG 0x60
#define AESDECIPHER_V2_AES_KEY_2_REG 0x5c
#define AESDECIPHER_V2_AES_KEY_1_REG 0x58
#define AESDECIPHER_V2_AES_KEY_0_REG 0x54
#define AESDECIPHER_V2_AES_KEY_7_REG 0x50
#define AESDECIPHER_V2_AES_KEY_6_REG 0x4c
#define AESDECIPHER_V2_AES_KEY_5_REG 0x48
#define AESDECIPHER_V2_AES_KEY_4_REG 0x44
#define AESDECIPHER_V2_AES_NUM_BLOCKS_REG 0x40

struct aesdecipher_v2_rtl_device {
	struct esp_device esp;
};

static struct esp_driver aesdecipher_v2_driver;

static struct of_device_id aesdecipher_v2_device_ids[] = {
	{
		.name = "SLD_AESDECIPHER_V2_RTL",
	},
	{
		.name = "eb_030",
	},
	{
		.compatible = "sld,aesdecipher_v2_rtl",
	},
	{ },
};

static int aesdecipher_v2_devs;

static inline struct aesdecipher_v2_rtl_device *to_aesdecipher_v2(struct esp_device *esp)
{
	return container_of(esp, struct aesdecipher_v2_rtl_device, esp);
}

static void aesdecipher_v2_prep_xfer(struct esp_device *esp, void *arg)
{
	struct aesdecipher_v2_rtl_access *a = arg;

	/* <<--regs-config-->> */
	iowrite32be(a->aes_key_3, esp->iomem + AESDECIPHER_V2_AES_KEY_3_REG);
	iowrite32be(a->aes_key_2, esp->iomem + AESDECIPHER_V2_AES_KEY_2_REG);
	iowrite32be(a->aes_key_1, esp->iomem + AESDECIPHER_V2_AES_KEY_1_REG);
	iowrite32be(a->aes_key_0, esp->iomem + AESDECIPHER_V2_AES_KEY_0_REG);
	iowrite32be(a->aes_key_7, esp->iomem + AESDECIPHER_V2_AES_KEY_7_REG);
	iowrite32be(a->aes_key_6, esp->iomem + AESDECIPHER_V2_AES_KEY_6_REG);
	iowrite32be(a->aes_key_5, esp->iomem + AESDECIPHER_V2_AES_KEY_5_REG);
	iowrite32be(a->aes_key_4, esp->iomem + AESDECIPHER_V2_AES_KEY_4_REG);
	iowrite32be(a->aes_num_blocks, esp->iomem + AESDECIPHER_V2_AES_NUM_BLOCKS_REG);
	iowrite32be(a->src_offset, esp->iomem + SRC_OFFSET_REG);
	iowrite32be(a->dst_offset, esp->iomem + DST_OFFSET_REG);

}

static bool aesdecipher_v2_xfer_input_ok(struct esp_device *esp, void *arg)
{
	/* struct aesdecipher_v2_rtl_device *aesdecipher_v2 = to_aesdecipher_v2(esp); */
	/* struct aesdecipher_v2_rtl_access *a = arg; */

	return true;
}

static int aesdecipher_v2_probe(struct platform_device *pdev)
{
	struct aesdecipher_v2_rtl_device *aesdecipher_v2;
	struct esp_device *esp;
	int rc;

	aesdecipher_v2 = kzalloc(sizeof(*aesdecipher_v2), GFP_KERNEL);
	if (aesdecipher_v2 == NULL)
		return -ENOMEM;
	esp = &aesdecipher_v2->esp;
	esp->module = THIS_MODULE;
	esp->number = aesdecipher_v2_devs;
	esp->driver = &aesdecipher_v2_driver;
	rc = esp_device_register(esp, pdev);
	if (rc)
		goto err;

	aesdecipher_v2_devs++;
	return 0;
 err:
	kfree(aesdecipher_v2);
	return rc;
}

static int __exit aesdecipher_v2_remove(struct platform_device *pdev)
{
	struct esp_device *esp = platform_get_drvdata(pdev);
	struct aesdecipher_v2_rtl_device *aesdecipher_v2 = to_aesdecipher_v2(esp);

	esp_device_unregister(esp);
	kfree(aesdecipher_v2);
	return 0;
}

static struct esp_driver aesdecipher_v2_driver = {
	.plat = {
		.probe		= aesdecipher_v2_probe,
		.remove		= aesdecipher_v2_remove,
		.driver		= {
			.name = DRV_NAME,
			.owner = THIS_MODULE,
			.of_match_table = aesdecipher_v2_device_ids,
		},
	},
	.xfer_input_ok	= aesdecipher_v2_xfer_input_ok,
	.prep_xfer	= aesdecipher_v2_prep_xfer,
	.ioctl_cm	= AESDECIPHER_V2_RTL_IOC_ACCESS,
	.arg_size	= sizeof(struct aesdecipher_v2_rtl_access),
};

static int __init aesdecipher_v2_init(void)
{
	return esp_driver_register(&aesdecipher_v2_driver);
}

static void __exit aesdecipher_v2_exit(void)
{
	esp_driver_unregister(&aesdecipher_v2_driver);
}

module_init(aesdecipher_v2_init)
module_exit(aesdecipher_v2_exit)

MODULE_DEVICE_TABLE(of, aesdecipher_v2_device_ids);

MODULE_AUTHOR("Emilio G. Cota <cota@braap.org>");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("aesdecipher_v2_rtl driver");
