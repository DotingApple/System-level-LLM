// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include <linux/of_device.h>
#include <linux/mm.h>

#include <asm/io.h>

#include <esp_accelerator.h>
#include <esp.h>

#include "sobel_v2_rtl.h"

#define DRV_NAME	"sobel_v2_rtl"

/* <<--regs-->> */
#define SOBEL_V2_WIDTH_REG 0x44
#define SOBEL_V2_HEIGHT_REG 0x40

struct sobel_v2_rtl_device {
	struct esp_device esp;
};

static struct esp_driver sobel_v2_driver;

static struct of_device_id sobel_v2_device_ids[] = {
	{
		.name = "SLD_SOBEL_V2_RTL",
	},
	{
		.name = "eb_014",
	},
	{
		.compatible = "sld,sobel_v2_rtl",
	},
	{ },
};

static int sobel_v2_devs;

static inline struct sobel_v2_rtl_device *to_sobel_v2(struct esp_device *esp)
{
	return container_of(esp, struct sobel_v2_rtl_device, esp);
}

static void sobel_v2_prep_xfer(struct esp_device *esp, void *arg)
{
	struct sobel_v2_rtl_access *a = arg;

	/* <<--regs-config-->> */
	iowrite32be(a->width, esp->iomem + SOBEL_V2_WIDTH_REG);
	iowrite32be(a->height, esp->iomem + SOBEL_V2_HEIGHT_REG);
	iowrite32be(a->src_offset, esp->iomem + SRC_OFFSET_REG);
	iowrite32be(a->dst_offset, esp->iomem + DST_OFFSET_REG);

}

static bool sobel_v2_xfer_input_ok(struct esp_device *esp, void *arg)
{
	/* struct sobel_v2_rtl_device *sobel_v2 = to_sobel_v2(esp); */
	/* struct sobel_v2_rtl_access *a = arg; */

	return true;
}

static int sobel_v2_probe(struct platform_device *pdev)
{
	struct sobel_v2_rtl_device *sobel_v2;
	struct esp_device *esp;
	int rc;

	sobel_v2 = kzalloc(sizeof(*sobel_v2), GFP_KERNEL);
	if (sobel_v2 == NULL)
		return -ENOMEM;
	esp = &sobel_v2->esp;
	esp->module = THIS_MODULE;
	esp->number = sobel_v2_devs;
	esp->driver = &sobel_v2_driver;
	rc = esp_device_register(esp, pdev);
	if (rc)
		goto err;

	sobel_v2_devs++;
	return 0;
 err:
	kfree(sobel_v2);
	return rc;
}

static int __exit sobel_v2_remove(struct platform_device *pdev)
{
	struct esp_device *esp = platform_get_drvdata(pdev);
	struct sobel_v2_rtl_device *sobel_v2 = to_sobel_v2(esp);

	esp_device_unregister(esp);
	kfree(sobel_v2);
	return 0;
}

static struct esp_driver sobel_v2_driver = {
	.plat = {
		.probe		= sobel_v2_probe,
		.remove		= sobel_v2_remove,
		.driver		= {
			.name = DRV_NAME,
			.owner = THIS_MODULE,
			.of_match_table = sobel_v2_device_ids,
		},
	},
	.xfer_input_ok	= sobel_v2_xfer_input_ok,
	.prep_xfer	= sobel_v2_prep_xfer,
	.ioctl_cm	= SOBEL_V2_RTL_IOC_ACCESS,
	.arg_size	= sizeof(struct sobel_v2_rtl_access),
};

static int __init sobel_v2_init(void)
{
	return esp_driver_register(&sobel_v2_driver);
}

static void __exit sobel_v2_exit(void)
{
	esp_driver_unregister(&sobel_v2_driver);
}

module_init(sobel_v2_init)
module_exit(sobel_v2_exit)

MODULE_DEVICE_TABLE(of, sobel_v2_device_ids);

MODULE_AUTHOR("Emilio G. Cota <cota@braap.org>");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("sobel_v2_rtl driver");
