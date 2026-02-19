// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include <linux/of_device.h>
#include <linux/mm.h>

#include <asm/io.h>

#include <esp_accelerator.h>
#include <esp.h>

#include "fcdnn_acc_rtl.h"

#define DRV_NAME	"fcdnn_acc_rtl"

/* <<--regs-->> */
#define FCDNN_ACC_ARRAY_SIZE_REG 0x50
#define FCDNN_ACC_MUX_CFG_REG 0x4c
#define FCDNN_ACC_EXP_VAL_REG 0x48
#define FCDNN_ACC_PIPE_MODE_REG 0x44
#define FCDNN_ACC_RUNS_REG 0x40

struct fcdnn_acc_rtl_device {
	struct esp_device esp;
};

static struct esp_driver fcdnn_acc_driver;

static struct of_device_id fcdnn_acc_device_ids[] = {
	{
		.name = "SLD_FCDNN_ACC_RTL",
	},
	{
		.name = "eb_001",
	},
	{
		.compatible = "sld,fcdnn_acc_rtl",
	},
	{ },
};

static int fcdnn_acc_devs;

static inline struct fcdnn_acc_rtl_device *to_fcdnn_acc(struct esp_device *esp)
{
	return container_of(esp, struct fcdnn_acc_rtl_device, esp);
}

static void fcdnn_acc_prep_xfer(struct esp_device *esp, void *arg)
{
	struct fcdnn_acc_rtl_access *a = arg;

	/* <<--regs-config-->> */
	iowrite32be(a->array_size, esp->iomem + FCDNN_ACC_ARRAY_SIZE_REG);
	iowrite32be(a->mux_cfg, esp->iomem + FCDNN_ACC_MUX_CFG_REG);
	iowrite32be(a->exp_val, esp->iomem + FCDNN_ACC_EXP_VAL_REG);
	iowrite32be(a->pipe_mode, esp->iomem + FCDNN_ACC_PIPE_MODE_REG);
	iowrite32be(a->runs, esp->iomem + FCDNN_ACC_RUNS_REG);
	iowrite32be(a->src_offset, esp->iomem + SRC_OFFSET_REG);
	iowrite32be(a->dst_offset, esp->iomem + DST_OFFSET_REG);

}

static bool fcdnn_acc_xfer_input_ok(struct esp_device *esp, void *arg)
{
	/* struct fcdnn_acc_rtl_device *fcdnn_acc = to_fcdnn_acc(esp); */
	/* struct fcdnn_acc_rtl_access *a = arg; */

	return true;
}

static int fcdnn_acc_probe(struct platform_device *pdev)
{
	struct fcdnn_acc_rtl_device *fcdnn_acc;
	struct esp_device *esp;
	int rc;

	fcdnn_acc = kzalloc(sizeof(*fcdnn_acc), GFP_KERNEL);
	if (fcdnn_acc == NULL)
		return -ENOMEM;
	esp = &fcdnn_acc->esp;
	esp->module = THIS_MODULE;
	esp->number = fcdnn_acc_devs;
	esp->driver = &fcdnn_acc_driver;
	rc = esp_device_register(esp, pdev);
	if (rc)
		goto err;

	fcdnn_acc_devs++;
	return 0;
 err:
	kfree(fcdnn_acc);
	return rc;
}

static int __exit fcdnn_acc_remove(struct platform_device *pdev)
{
	struct esp_device *esp = platform_get_drvdata(pdev);
	struct fcdnn_acc_rtl_device *fcdnn_acc = to_fcdnn_acc(esp);

	esp_device_unregister(esp);
	kfree(fcdnn_acc);
	return 0;
}

static struct esp_driver fcdnn_acc_driver = {
	.plat = {
		.probe		= fcdnn_acc_probe,
		.remove		= fcdnn_acc_remove,
		.driver		= {
			.name = DRV_NAME,
			.owner = THIS_MODULE,
			.of_match_table = fcdnn_acc_device_ids,
		},
	},
	.xfer_input_ok	= fcdnn_acc_xfer_input_ok,
	.prep_xfer	= fcdnn_acc_prep_xfer,
	.ioctl_cm	= FCDNN_ACC_RTL_IOC_ACCESS,
	.arg_size	= sizeof(struct fcdnn_acc_rtl_access),
};

static int __init fcdnn_acc_init(void)
{
	return esp_driver_register(&fcdnn_acc_driver);
}

static void __exit fcdnn_acc_exit(void)
{
	esp_driver_unregister(&fcdnn_acc_driver);
}

module_init(fcdnn_acc_init)
module_exit(fcdnn_acc_exit)

MODULE_DEVICE_TABLE(of, fcdnn_acc_device_ids);

MODULE_AUTHOR("Emilio G. Cota <cota@braap.org>");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("fcdnn_acc_rtl driver");
