// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include <linux/of_device.h>
#include <linux/mm.h>

#include <asm/io.h>

#include <esp_accelerator.h>
#include <esp.h>

#include "spmv_rtl.h"

#define DRV_NAME	"spmv_rtl"

/* <<--regs-->> */
#define SPMV_SPMV_NNZ_REG 0x44
#define SPMV_SPMV_VEC_LEN_REG 0x40

struct spmv_rtl_device {
	struct esp_device esp;
};

static struct esp_driver spmv_driver;

static struct of_device_id spmv_device_ids[] = {
	{
		.name = "SLD_SPMV_RTL",
	},
	{
		.name = "eb_0a1",
	},
	{
		.compatible = "sld,spmv_rtl",
	},
	{ },
};

static int spmv_devs;

static inline struct spmv_rtl_device *to_spmv(struct esp_device *esp)
{
	return container_of(esp, struct spmv_rtl_device, esp);
}

static void spmv_prep_xfer(struct esp_device *esp, void *arg)
{
	struct spmv_rtl_access *a = arg;

	/* <<--regs-config-->> */
	iowrite32be(a->spmv_nnz, esp->iomem + SPMV_SPMV_NNZ_REG);
	iowrite32be(a->spmv_vec_len, esp->iomem + SPMV_SPMV_VEC_LEN_REG);
	iowrite32be(a->src_offset, esp->iomem + SRC_OFFSET_REG);
	iowrite32be(a->dst_offset, esp->iomem + DST_OFFSET_REG);

}

static bool spmv_xfer_input_ok(struct esp_device *esp, void *arg)
{
	/* struct spmv_rtl_device *spmv = to_spmv(esp); */
	/* struct spmv_rtl_access *a = arg; */

	return true;
}

static int spmv_probe(struct platform_device *pdev)
{
	struct spmv_rtl_device *spmv;
	struct esp_device *esp;
	int rc;

	spmv = kzalloc(sizeof(*spmv), GFP_KERNEL);
	if (spmv == NULL)
		return -ENOMEM;
	esp = &spmv->esp;
	esp->module = THIS_MODULE;
	esp->number = spmv_devs;
	esp->driver = &spmv_driver;
	rc = esp_device_register(esp, pdev);
	if (rc)
		goto err;

	spmv_devs++;
	return 0;
 err:
	kfree(spmv);
	return rc;
}

static int __exit spmv_remove(struct platform_device *pdev)
{
	struct esp_device *esp = platform_get_drvdata(pdev);
	struct spmv_rtl_device *spmv = to_spmv(esp);

	esp_device_unregister(esp);
	kfree(spmv);
	return 0;
}

static struct esp_driver spmv_driver = {
	.plat = {
		.probe		= spmv_probe,
		.remove		= spmv_remove,
		.driver		= {
			.name = DRV_NAME,
			.owner = THIS_MODULE,
			.of_match_table = spmv_device_ids,
		},
	},
	.xfer_input_ok	= spmv_xfer_input_ok,
	.prep_xfer	= spmv_prep_xfer,
	.ioctl_cm	= SPMV_RTL_IOC_ACCESS,
	.arg_size	= sizeof(struct spmv_rtl_access),
};

static int __init spmv_init(void)
{
	return esp_driver_register(&spmv_driver);
}

static void __exit spmv_exit(void)
{
	esp_driver_unregister(&spmv_driver);
}

module_init(spmv_init)
module_exit(spmv_exit)

MODULE_DEVICE_TABLE(of, spmv_device_ids);

MODULE_AUTHOR("Emilio G. Cota <cota@braap.org>");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("spmv_rtl driver");
