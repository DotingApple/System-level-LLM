// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include <linux/of_device.h>
#include <linux/mm.h>

#include <asm/io.h>

#include <esp_accelerator.h>
#include <esp.h>

#include "simple_dnn_rtl.h"

#define DRV_NAME	"simple_dnn_rtl"

/* <<--regs-->> */
#define SIMPLE_DNN_NUM_IN_REG 0x48
#define SIMPLE_DNN_NUM_OUT_REG 0x44
#define SIMPLE_DNN_NUM_HIDDEN_REG 0x40

struct simple_dnn_rtl_device {
	struct esp_device esp;
};

static struct esp_driver simple_dnn_driver;

static struct of_device_id simple_dnn_device_ids[] = {
	{
		.name = "SLD_SIMPLE_DNN_RTL",
	},
	{
		.name = "eb_005",
	},
	{
		.compatible = "sld,simple_dnn_rtl",
	},
	{ },
};

static int simple_dnn_devs;

static inline struct simple_dnn_rtl_device *to_simple_dnn(struct esp_device *esp)
{
	return container_of(esp, struct simple_dnn_rtl_device, esp);
}

static void simple_dnn_prep_xfer(struct esp_device *esp, void *arg)
{
	struct simple_dnn_rtl_access *a = arg;

	/* <<--regs-config-->> */
	iowrite32be(a->num_in, esp->iomem + SIMPLE_DNN_NUM_IN_REG);
	iowrite32be(a->num_out, esp->iomem + SIMPLE_DNN_NUM_OUT_REG);
	iowrite32be(a->num_hidden, esp->iomem + SIMPLE_DNN_NUM_HIDDEN_REG);
	iowrite32be(a->src_offset, esp->iomem + SRC_OFFSET_REG);
	iowrite32be(a->dst_offset, esp->iomem + DST_OFFSET_REG);

}

static bool simple_dnn_xfer_input_ok(struct esp_device *esp, void *arg)
{
	/* struct simple_dnn_rtl_device *simple_dnn = to_simple_dnn(esp); */
	/* struct simple_dnn_rtl_access *a = arg; */

	return true;
}

static int simple_dnn_probe(struct platform_device *pdev)
{
	struct simple_dnn_rtl_device *simple_dnn;
	struct esp_device *esp;
	int rc;

	simple_dnn = kzalloc(sizeof(*simple_dnn), GFP_KERNEL);
	if (simple_dnn == NULL)
		return -ENOMEM;
	esp = &simple_dnn->esp;
	esp->module = THIS_MODULE;
	esp->number = simple_dnn_devs;
	esp->driver = &simple_dnn_driver;
	rc = esp_device_register(esp, pdev);
	if (rc)
		goto err;

	simple_dnn_devs++;
	return 0;
 err:
	kfree(simple_dnn);
	return rc;
}

static int __exit simple_dnn_remove(struct platform_device *pdev)
{
	struct esp_device *esp = platform_get_drvdata(pdev);
	struct simple_dnn_rtl_device *simple_dnn = to_simple_dnn(esp);

	esp_device_unregister(esp);
	kfree(simple_dnn);
	return 0;
}

static struct esp_driver simple_dnn_driver = {
	.plat = {
		.probe		= simple_dnn_probe,
		.remove		= simple_dnn_remove,
		.driver		= {
			.name = DRV_NAME,
			.owner = THIS_MODULE,
			.of_match_table = simple_dnn_device_ids,
		},
	},
	.xfer_input_ok	= simple_dnn_xfer_input_ok,
	.prep_xfer	= simple_dnn_prep_xfer,
	.ioctl_cm	= SIMPLE_DNN_RTL_IOC_ACCESS,
	.arg_size	= sizeof(struct simple_dnn_rtl_access),
};

static int __init simple_dnn_init(void)
{
	return esp_driver_register(&simple_dnn_driver);
}

static void __exit simple_dnn_exit(void)
{
	esp_driver_unregister(&simple_dnn_driver);
}

module_init(simple_dnn_init)
module_exit(simple_dnn_exit)

MODULE_DEVICE_TABLE(of, simple_dnn_device_ids);

MODULE_AUTHOR("Emilio G. Cota <cota@braap.org>");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("simple_dnn_rtl driver");
