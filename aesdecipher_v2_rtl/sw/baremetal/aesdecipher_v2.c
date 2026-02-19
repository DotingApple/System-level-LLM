/* Copyright (c) 2011-2024 Columbia University, System Level Design Group */
/* SPDX-License-Identifier: Apache-2.0 */

#include <stdio.h>
#ifndef __riscv
#include <stdlib.h>
#endif

#include <esp_accelerator.h>
#include <esp_probe.h>
#include <fixed_point.h>

typedef int64_t token_t;

static unsigned DMA_WORD_PER_BEAT(unsigned _st)
{
        return (sizeof(void *) / _st);
}


#define SLD_AESDECIPHER_V2 0x030
#define DEV_NAME "sld,aesdecipher_v2_rtl"

/* <<--params-->> */
const int32_t aes_key_3 = 0x0d0e0f10;
const int32_t aes_key_2 = 0x090a0b0c;
const int32_t aes_key_1 = 0x05060708;
const int32_t aes_key_0 = 0x01020304;
const int32_t aes_key_7 = 0x1d1e1f00;
const int32_t aes_key_6 = 0x191a1b1c;
const int32_t aes_key_5 = 0x15161718;
const int32_t aes_key_4 = 0x11121314;
const int32_t aes_num_blocks = 1;

static unsigned in_words_adj;
static unsigned out_words_adj;
static unsigned in_len;
static unsigned out_len;
static unsigned in_size;
static unsigned out_size;
static unsigned out_offset;
static unsigned mem_size;

/* Size of the contiguous chunks for scatter/gather */
#define CHUNK_SHIFT 20
#define CHUNK_SIZE BIT(CHUNK_SHIFT)
#define NCHUNK(_sz) ((_sz % CHUNK_SIZE == 0) ?		\
			(_sz / CHUNK_SIZE) :		\
			(_sz / CHUNK_SIZE) + 1)

/* User defined registers */
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


static int validate_buf(token_t *out, token_t *gold)
{
	int i;
	int j;
	unsigned errors = 0;

	// for (i = 0; i < 1; i++)
	// 	for (j = 0; j < 2*aes_num_blocks; j++)
	// 		if (gold[i * out_words_adj + j] != out[i * out_words_adj + j])
	// 			errors++;
	printf("out[0] = %lx\n", out[0]);
	printf("out[1] = %lx\n", out[1]);
	return errors;
}


static void init_buf (token_t *in, token_t * gold)
{
	int i;
	int j;
    // Setting input as 0x00112233445566778899aabbccddeeff
    in[0] = 0x0011223344556677;
    in[1] = 0x8899aabbccddeeff;

    // Copy input to gold reference output for validation
    // gold[0] = in[0];
    // gold[1] = in[1];

    printf("  Set input block:\n");
    printf("    in0 = 0x%016lx\n", (unsigned long) in[0]);
    printf("    in1 = 0x%016lx\n", (unsigned long) in[1]);
	// for (i = 0; i < 1; i++)
	// 	for (j = 0; j < 2*aes_num_blocks; j++)
	// 		in[i * in_words_adj + j] = (token_t) j;

	// for (i = 0; i < 1; i++)
	// 	for (j = 0; j < 2*aes_num_blocks; j++)
	// 		gold[i * out_words_adj + j] = (token_t) j;
}


int main(int argc, char * argv[])
{
	int i;
	int n;
	int ndev;
	struct esp_device *espdevs;
	struct esp_device *dev;
	unsigned done;
	unsigned **ptable;
	token_t *mem;
	token_t *gold;
	unsigned errors = 0;
	unsigned coherence;

	if (DMA_WORD_PER_BEAT(sizeof(token_t)) == 0) {
		in_words_adj = 2*aes_num_blocks;
		out_words_adj = 2*aes_num_blocks;
	} else {
		in_words_adj = round_up(2*aes_num_blocks, DMA_WORD_PER_BEAT(sizeof(token_t)));
		out_words_adj = round_up(2*aes_num_blocks, DMA_WORD_PER_BEAT(sizeof(token_t)));
	}
	in_len = in_words_adj * (1);
	out_len = out_words_adj * (1);
	in_size = in_len * sizeof(token_t);
	out_size = out_len * sizeof(token_t);
	out_offset  = in_len;
	mem_size = (out_offset * sizeof(token_t)) + out_size;


	// Search for the device
	printf("Scanning device tree... \n");

	ndev = probe(&espdevs, VENDOR_SLD, SLD_AESDECIPHER_V2, DEV_NAME);
	if (ndev == 0) {
		printf("aesdecipher_v2 not found\n");
		return 0;
	}

	for (n = 0; n < ndev; n++) {

		printf("**************** %s.%d ****************\n", DEV_NAME, n);

		dev = &espdevs[n];

		// Check DMA capabilities
		if (ioread32(dev, PT_NCHUNK_MAX_REG) == 0) {
			printf("  -> scatter-gather DMA is disabled. Abort.\n");
			return 0;
		}

		if (ioread32(dev, PT_NCHUNK_MAX_REG) < NCHUNK(mem_size)) {
			printf("  -> Not enough TLB entries available. Abort.\n");
			return 0;
		}

		// Allocate memory
		gold = aligned_malloc(out_size);
		mem = aligned_malloc(mem_size);
		printf("  memory buffer base-address = %p\n", mem);

		// Alocate and populate page table
		ptable = aligned_malloc(NCHUNK(mem_size) * sizeof(unsigned *));
		for (i = 0; i < NCHUNK(mem_size); i++)
			ptable[i] = (unsigned *) &mem[i * (CHUNK_SIZE / sizeof(token_t))];

		printf("  ptable = %p\n", ptable);
		printf("  nchunk = %lu\n", NCHUNK(mem_size));

#ifndef __riscv
		for (coherence = ACC_COH_NONE; coherence <= ACC_COH_RECALL; coherence++) {
#else
		{
			/* TODO: Restore full test once ESP caches are integrated */
			coherence = ACC_COH_NONE;
#endif
			printf("  --------------------\n");
			printf("  Generate input...\n");
			init_buf(mem, gold);

			// Pass common configuration parameters

			iowrite32(dev, SELECT_REG, ioread32(dev, DEVID_REG));
			iowrite32(dev, COHERENCE_REG, coherence);

#ifndef __sparc
			iowrite32(dev, PT_ADDRESS_REG, (unsigned long long) ptable);
#else
			iowrite32(dev, PT_ADDRESS_REG, (unsigned) ptable);
#endif
			iowrite32(dev, PT_NCHUNK_REG, NCHUNK(mem_size));
			iowrite32(dev, PT_SHIFT_REG, CHUNK_SHIFT);

			// Use the following if input and output data are not allocated at the default offsets
			iowrite32(dev, SRC_OFFSET_REG, 0x0);
			iowrite32(dev, DST_OFFSET_REG, 0x0);

			// Pass accelerator-specific configuration parameters
			/* <<--regs-config-->> */
		iowrite32(dev, AESDECIPHER_V2_AES_KEY_3_REG, aes_key_3);
		iowrite32(dev, AESDECIPHER_V2_AES_KEY_2_REG, aes_key_2);
		iowrite32(dev, AESDECIPHER_V2_AES_KEY_1_REG, aes_key_1);
		iowrite32(dev, AESDECIPHER_V2_AES_KEY_0_REG, aes_key_0);
		iowrite32(dev, AESDECIPHER_V2_AES_KEY_7_REG, aes_key_7);
		iowrite32(dev, AESDECIPHER_V2_AES_KEY_6_REG, aes_key_6);
		iowrite32(dev, AESDECIPHER_V2_AES_KEY_5_REG, aes_key_5);
		iowrite32(dev, AESDECIPHER_V2_AES_KEY_4_REG, aes_key_4);
		iowrite32(dev, AESDECIPHER_V2_AES_NUM_BLOCKS_REG, aes_num_blocks);

			// Flush (customize coherence model here)
			esp_flush(coherence);

			// Start accelerators
			printf("  Start...\n");
			iowrite32(dev, CMD_REG, CMD_MASK_START);

			// Wait for completion
			done = 0;
			while (!done) {
				done = ioread32(dev, STATUS_REG);
				done &= STATUS_MASK_DONE;
			}
			iowrite32(dev, CMD_REG, 0x0);

			printf("  Done\n");
			printf("  validating...\n");

			/* Validation */
			errors = validate_buf(&mem[out_offset], gold);
			if (errors)
				printf("  ... FAIL\n");
			else
				printf("  ... PASS\n");
		}
		aligned_free(ptable);
		aligned_free(mem);
		aligned_free(gold);
	}

	return 0;
}
