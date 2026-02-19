// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include <linux/of_device.h>
#include <linux/mm.h>

#include <asm/io.h>

#include <esp_accelerator.h>
#include <esp.h>

#include "aescipher_rtl.h"

#define DRV_NAME	"aescipher_rtl"

/* <<--regs-->> */
#define AESCIPHER_AES_KEY_3_REG 0x60
#define AESCIPHER_AES_KEY_2_REG 0x5c
#define AESCIPHER_AES_KEY_1_REG 0x58
#define AESCIPHER_AES_KEY_0_REG 0x54
#define AESCIPHER_AES_KEY_7_REG 0x50
#define AESCIPHER_AES_KEY_6_REG 0x4c
#define AESCIPHER_AES_KEY_5_REG 0x48
#define AESCIPHER_AES_KEY_4_REG 0x44
#define AESCIPHER_AES_NUM_BLOCKS_REG 0x40

struct aescipher_rtl_device {
	struct esp_device esp;
};

static struct esp_driver aescipher_driver;

static struct of_device_id aescipher_device_ids[] = {
	{
		.name = "SLD_AESCIPHER_RTL",
	},
	{
		.name = "eb_04a",
	},
	{
		.compatible = "sld,aescipher_rtl",
	},
	{ },
};

static int aescipher_devs;

static inline struct aescipher_rtl_device *to_aescipher(struct esp_device *esp)
{
	return container_of(esp, struct aescipher_rtl_device, esp);
}

static void aescipher_prep_xfer(struct esp_device *esp, void *arg)
{
	struct aescipher_rtl_access *a = arg;

	/* <<--regs-config-->> */
	iowrite32be(a->aes_key_3, esp->iomem + AESCIPHER_AES_KEY_3_REG);
	iowrite32be(a->aes_key_2, esp->iomem + AESCIPHER_AES_KEY_2_REG);
	iowrite32be(a->aes_key_1, esp->iomem + AESCIPHER_AES_KEY_1_REG);
	iowrite32be(a->aes_key_0, esp->iomem + AESCIPHER_AES_KEY_0_REG);
	iowrite32be(a->aes_key_7, esp->iomem + AESCIPHER_AES_KEY_7_REG);
	iowrite32be(a->aes_key_6, esp->iomem + AESCIPHER_AES_KEY_6_REG);
	iowrite32be(a->aes_key_5, esp->iomem + AESCIPHER_AES_KEY_5_REG);
	iowrite32be(a->aes_key_4, esp->iomem + AESCIPHER_AES_KEY_4_REG);
	iowrite32be(a->aes_num_blocks, esp->iomem + AESCIPHER_AES_NUM_BLOCKS_REG);
	iowrite32be(a->src_offset, esp->iomem + SRC_OFFSET_REG);
	iowrite32be(a->dst_offset, esp->iomem + DST_OFFSET_REG);

}

static bool aescipher_xfer_input_ok(struct esp_device *esp, void *arg)
{
	/* struct aescipher_rtl_device *aescipher = to_aescipher(esp); */
	/* struct aescipher_rtl_access *a = arg; */

	return true;
}

static int aescipher_probe(struct platform_device *pdev)
{
	struct aescipher_rtl_device *aescipher;
	struct esp_device *esp;
	int rc;

	aescipher = kzalloc(sizeof(*aescipher), GFP_KERNEL);
	if (aescipher == NULL)
		return -ENOMEM;
	esp = &aescipher->esp;
	esp->module = THIS_MODULE;
	esp->number = aescipher_devs;
	esp->driver = &aescipher_driver;
	rc = esp_device_register(esp, pdev);
	if (rc)
		goto err;

	aescipher_devs++;
	return 0;
 err:
	kfree(aescipher);
	return rc;
}

static int __exit aescipher_remove(struct platform_device *pdev)
{
	struct esp_device *esp = platform_get_drvdata(pdev);
	struct aescipher_rtl_device *aescipher = to_aescipher(esp);

	esp_device_unregister(esp);
	kfree(aescipher);
	return 0;
}

static struct esp_driver aescipher_driver = {
	.plat = {
		.probe		= aescipher_probe,
		.remove		= aescipher_remove,
		.driver		= {
			.name = DRV_NAME,
			.owner = THIS_MODULE,
			.of_match_table = aescipher_device_ids,
		},
	},
	.xfer_input_ok	= aescipher_xfer_input_ok,
	.prep_xfer	= aescipher_prep_xfer,
	.ioctl_cm	= AESCIPHER_RTL_IOC_ACCESS,
	.arg_size	= sizeof(struct aescipher_rtl_access),
};

static int __init aescipher_init(void)
{
	return esp_driver_register(&aescipher_driver);
}

static void __exit aescipher_exit(void)
{
	esp_driver_unregister(&aescipher_driver);
}

module_init(aescipher_init)
module_exit(aescipher_exit)

MODULE_DEVICE_TABLE(of, aescipher_device_ids);

MODULE_AUTHOR("Emilio G. Cota <cota@braap.org>");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("aescipher_rtl driver");
