// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include <linux/of_device.h>
#include <linux/mm.h>

#include <asm/io.h>

#include <esp_accelerator.h>
#include <esp.h>

#include "fft_64_rtl.h"

#define DRV_NAME	"fft_64_rtl"

/* <<--regs-->> */
#define FFT_64_FFT_POINTS_REG 0x40

struct fft_64_rtl_device {
	struct esp_device esp;
};

static struct esp_driver fft_64_driver;

static struct of_device_id fft_64_device_ids[] = {
	{
		.name = "SLD_FFT_64_RTL",
	},
	{
		.name = "eb_094",
	},
	{
		.compatible = "sld,fft_64_rtl",
	},
	{ },
};

static int fft_64_devs;

static inline struct fft_64_rtl_device *to_fft_64(struct esp_device *esp)
{
	return container_of(esp, struct fft_64_rtl_device, esp);
}

static void fft_64_prep_xfer(struct esp_device *esp, void *arg)
{
	struct fft_64_rtl_access *a = arg;

	/* <<--regs-config-->> */
	iowrite32be(a->fft_points, esp->iomem + FFT_64_FFT_POINTS_REG);
	iowrite32be(a->src_offset, esp->iomem + SRC_OFFSET_REG);
	iowrite32be(a->dst_offset, esp->iomem + DST_OFFSET_REG);

}

static bool fft_64_xfer_input_ok(struct esp_device *esp, void *arg)
{
	/* struct fft_64_rtl_device *fft_64 = to_fft_64(esp); */
	/* struct fft_64_rtl_access *a = arg; */

	return true;
}

static int fft_64_probe(struct platform_device *pdev)
{
	struct fft_64_rtl_device *fft_64;
	struct esp_device *esp;
	int rc;

	fft_64 = kzalloc(sizeof(*fft_64), GFP_KERNEL);
	if (fft_64 == NULL)
		return -ENOMEM;
	esp = &fft_64->esp;
	esp->module = THIS_MODULE;
	esp->number = fft_64_devs;
	esp->driver = &fft_64_driver;
	rc = esp_device_register(esp, pdev);
	if (rc)
		goto err;

	fft_64_devs++;
	return 0;
 err:
	kfree(fft_64);
	return rc;
}

static int __exit fft_64_remove(struct platform_device *pdev)
{
	struct esp_device *esp = platform_get_drvdata(pdev);
	struct fft_64_rtl_device *fft_64 = to_fft_64(esp);

	esp_device_unregister(esp);
	kfree(fft_64);
	return 0;
}

static struct esp_driver fft_64_driver = {
	.plat = {
		.probe		= fft_64_probe,
		.remove		= fft_64_remove,
		.driver		= {
			.name = DRV_NAME,
			.owner = THIS_MODULE,
			.of_match_table = fft_64_device_ids,
		},
	},
	.xfer_input_ok	= fft_64_xfer_input_ok,
	.prep_xfer	= fft_64_prep_xfer,
	.ioctl_cm	= FFT_64_RTL_IOC_ACCESS,
	.arg_size	= sizeof(struct fft_64_rtl_access),
};

static int __init fft_64_init(void)
{
	return esp_driver_register(&fft_64_driver);
}

static void __exit fft_64_exit(void)
{
	esp_driver_unregister(&fft_64_driver);
}

module_init(fft_64_init)
module_exit(fft_64_exit)

MODULE_DEVICE_TABLE(of, fft_64_device_ids);

MODULE_AUTHOR("Emilio G. Cota <cota@braap.org>");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("fft_64_rtl driver");
