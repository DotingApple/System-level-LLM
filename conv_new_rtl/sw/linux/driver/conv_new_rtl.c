// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include <linux/of_device.h>
#include <linux/mm.h>

#include <asm/io.h>

#include <esp_accelerator.h>
#include <esp.h>

#include "conv_new_rtl.h"

#define DRV_NAME	"conv_new_rtl"

/* <<--regs-->> */
#define CONV_NEW_PARAM_HEIGHT_REG 0x44
#define CONV_NEW_PARAM_WIDTH_REG 0x40

struct conv_new_rtl_device {
	struct esp_device esp;
};

static struct esp_driver conv_new_driver;

static struct of_device_id conv_new_device_ids[] = {
	{
		.name = "SLD_CONV_NEW_RTL",
	},
	{
		.name = "eb_321",
	},
	{
		.compatible = "sld,conv_new_rtl",
	},
	{ },
};

static int conv_new_devs;

static inline struct conv_new_rtl_device *to_conv_new(struct esp_device *esp)
{
	return container_of(esp, struct conv_new_rtl_device, esp);
}

static void conv_new_prep_xfer(struct esp_device *esp, void *arg)
{
	struct conv_new_rtl_access *a = arg;

	/* <<--regs-config-->> */
	iowrite32be(a->param_height, esp->iomem + CONV_NEW_PARAM_HEIGHT_REG);
	iowrite32be(a->param_width, esp->iomem + CONV_NEW_PARAM_WIDTH_REG);
	iowrite32be(a->src_offset, esp->iomem + SRC_OFFSET_REG);
	iowrite32be(a->dst_offset, esp->iomem + DST_OFFSET_REG);

}

static bool conv_new_xfer_input_ok(struct esp_device *esp, void *arg)
{
	/* struct conv_new_rtl_device *conv_new = to_conv_new(esp); */
	/* struct conv_new_rtl_access *a = arg; */

	return true;
}

static int conv_new_probe(struct platform_device *pdev)
{
	struct conv_new_rtl_device *conv_new;
	struct esp_device *esp;
	int rc;

	conv_new = kzalloc(sizeof(*conv_new), GFP_KERNEL);
	if (conv_new == NULL)
		return -ENOMEM;
	esp = &conv_new->esp;
	esp->module = THIS_MODULE;
	esp->number = conv_new_devs;
	esp->driver = &conv_new_driver;
	rc = esp_device_register(esp, pdev);
	if (rc)
		goto err;

	conv_new_devs++;
	return 0;
 err:
	kfree(conv_new);
	return rc;
}

static int __exit conv_new_remove(struct platform_device *pdev)
{
	struct esp_device *esp = platform_get_drvdata(pdev);
	struct conv_new_rtl_device *conv_new = to_conv_new(esp);

	esp_device_unregister(esp);
	kfree(conv_new);
	return 0;
}

static struct esp_driver conv_new_driver = {
	.plat = {
		.probe		= conv_new_probe,
		.remove		= conv_new_remove,
		.driver		= {
			.name = DRV_NAME,
			.owner = THIS_MODULE,
			.of_match_table = conv_new_device_ids,
		},
	},
	.xfer_input_ok	= conv_new_xfer_input_ok,
	.prep_xfer	= conv_new_prep_xfer,
	.ioctl_cm	= CONV_NEW_RTL_IOC_ACCESS,
	.arg_size	= sizeof(struct conv_new_rtl_access),
};

static int __init conv_new_init(void)
{
	return esp_driver_register(&conv_new_driver);
}

static void __exit conv_new_exit(void)
{
	esp_driver_unregister(&conv_new_driver);
}

module_init(conv_new_init)
module_exit(conv_new_exit)

MODULE_DEVICE_TABLE(of, conv_new_device_ids);

MODULE_AUTHOR("Emilio G. Cota <cota@braap.org>");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("conv_new_rtl driver");
