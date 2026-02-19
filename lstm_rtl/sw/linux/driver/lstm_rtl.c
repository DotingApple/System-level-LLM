// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include <linux/of_device.h>
#include <linux/mm.h>

#include <asm/io.h>

#include <esp_accelerator.h>
#include <esp.h>

#include "lstm_rtl.h"

#define DRV_NAME	"lstm_rtl"

/* <<--regs-->> */
#define LSTM_IN_DIM_REG 0x48
#define LSTM_HIDDEN_DIM_REG 0x44
#define LSTM_NUM_TIMESTEPS_REG 0x40

struct lstm_rtl_device {
	struct esp_device esp;
};

static struct esp_driver lstm_driver;

static struct of_device_id lstm_device_ids[] = {
	{
		.name = "SLD_LSTM_RTL",
	},
	{
		.name = "eb_031",
	},
	{
		.compatible = "sld,lstm_rtl",
	},
	{ },
};

static int lstm_devs;

static inline struct lstm_rtl_device *to_lstm(struct esp_device *esp)
{
	return container_of(esp, struct lstm_rtl_device, esp);
}

static void lstm_prep_xfer(struct esp_device *esp, void *arg)
{
	struct lstm_rtl_access *a = arg;

	/* <<--regs-config-->> */
	iowrite32be(a->in_dim, esp->iomem + LSTM_IN_DIM_REG);
	iowrite32be(a->hidden_dim, esp->iomem + LSTM_HIDDEN_DIM_REG);
	iowrite32be(a->num_timesteps, esp->iomem + LSTM_NUM_TIMESTEPS_REG);
	iowrite32be(a->src_offset, esp->iomem + SRC_OFFSET_REG);
	iowrite32be(a->dst_offset, esp->iomem + DST_OFFSET_REG);

}

static bool lstm_xfer_input_ok(struct esp_device *esp, void *arg)
{
	/* struct lstm_rtl_device *lstm = to_lstm(esp); */
	/* struct lstm_rtl_access *a = arg; */

	return true;
}

static int lstm_probe(struct platform_device *pdev)
{
	struct lstm_rtl_device *lstm;
	struct esp_device *esp;
	int rc;

	lstm = kzalloc(sizeof(*lstm), GFP_KERNEL);
	if (lstm == NULL)
		return -ENOMEM;
	esp = &lstm->esp;
	esp->module = THIS_MODULE;
	esp->number = lstm_devs;
	esp->driver = &lstm_driver;
	rc = esp_device_register(esp, pdev);
	if (rc)
		goto err;

	lstm_devs++;
	return 0;
 err:
	kfree(lstm);
	return rc;
}

static int __exit lstm_remove(struct platform_device *pdev)
{
	struct esp_device *esp = platform_get_drvdata(pdev);
	struct lstm_rtl_device *lstm = to_lstm(esp);

	esp_device_unregister(esp);
	kfree(lstm);
	return 0;
}

static struct esp_driver lstm_driver = {
	.plat = {
		.probe		= lstm_probe,
		.remove		= lstm_remove,
		.driver		= {
			.name = DRV_NAME,
			.owner = THIS_MODULE,
			.of_match_table = lstm_device_ids,
		},
	},
	.xfer_input_ok	= lstm_xfer_input_ok,
	.prep_xfer	= lstm_prep_xfer,
	.ioctl_cm	= LSTM_RTL_IOC_ACCESS,
	.arg_size	= sizeof(struct lstm_rtl_access),
};

static int __init lstm_init(void)
{
	return esp_driver_register(&lstm_driver);
}

static void __exit lstm_exit(void)
{
	esp_driver_unregister(&lstm_driver);
}

module_init(lstm_init)
module_exit(lstm_exit)

MODULE_DEVICE_TABLE(of, lstm_device_ids);

MODULE_AUTHOR("Emilio G. Cota <cota@braap.org>");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("lstm_rtl driver");
