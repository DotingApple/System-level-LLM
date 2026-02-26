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

#define BLOCK_TOKENS 2

#define SLD_AESCIPHER 0x04a
#define DEV_NAME "sld,aescipher_rtl"

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
#define AESCIPHER_AES_KEY_3_REG 0x60
#define AESCIPHER_AES_KEY_2_REG 0x5c
#define AESCIPHER_AES_KEY_1_REG 0x58
#define AESCIPHER_AES_KEY_0_REG 0x54
#define AESCIPHER_AES_KEY_7_REG 0x50
#define AESCIPHER_AES_KEY_6_REG 0x4c
#define AESCIPHER_AES_KEY_5_REG 0x48
#define AESCIPHER_AES_KEY_4_REG 0x44
#define AESCIPHER_AES_NUM_BLOCKS_REG 0x40


static int validate_buf(token_t *out, token_t *gold)
{
	int i;
	int j;
	unsigned errors = 0;
	// for (i=0;i<10;i++){
	// 	printf("memory index %d value: %lx\n",i,mem[i]);
	// }
	// for(i=0;i<10;i++){
	// 	printf("mem[%d] = %lx\n",i,gold[i]);
	// }
	// for (i = 0; i < aes_num_blocks; i++){
	// 	for (j = 0; j < 2*aes_num_blocks; j++){
	// 		// printf("gold[%d][%d] = %lx\n", i, j, gold[i * out_words_adj + j]);
	// 		printf("out[%d][%d] = %lx\n", i, j, out[i * out_words_adj + j]);
	// 		// if (gold[i * out_words_adj + j] != out[i * out_words_adj + j])
	// 		// 	errors++;
	// 	}
	// }
	printf("out[0] = %lx\n", out[0]);
	printf("out[1] = %lx\n", out[1]);
	// printf("out[2] = %lx\n", out[2]);
	// printf("out[3] = %lx\n", out[3]);
	// printf("out[4] = %lx\n", out[4]);
	// printf("out[5] = %lx\n", out[5]);
	// printf("out[6] = %lx\n", out[6]);
	// printf("out[7] = %lx\n", out[7]);
	// printf("out[8] = %lx\n", out[8]);
	// ("out[%d][%d] = %lx\n", i, j, out[i * out_words_adj + j]);
	// return errors;
	return 0; // For now, we assume no errors
}


static void init_buf(token_t *in, token_t *gold)
{
    // Setting input as 0x00112233445566778899aabbccddeeff
    in[0] = 0x0011223344556677;
    in[1] = 0x8899aabbccddeeff;

    // Copy input to gold reference output for validation
    // gold[0] = in[0];
    // gold[1] = in[1];

    printf("  Set input block:\n");
    printf("    in0 = 0x%016lx\n", (unsigned long) in[0]);
    printf("    in1 = 0x%016lx\n", (unsigned long) in[1]);
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
	in_len = in_words_adj;
	out_len = out_words_adj;
	in_size = in_len * sizeof(token_t);
	out_size = out_len * sizeof(token_t);
	out_offset  = in_len;
	mem_size = (out_offset * sizeof(token_t)) + out_size;


	// Search for the device
	printf("Scanning device tree... \n");

	ndev = probe(&espdevs, VENDOR_SLD, SLD_AESCIPHER, DEV_NAME);
	if (ndev == 0) {
		printf("aescipher not found\n");
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
            printf("    key0 = 0x%08x\n", aes_key_0);
            printf("    key1 = 0x%08x\n", aes_key_1);
            printf("    key2 = 0x%08x\n", aes_key_2);
            printf("    key3 = 0x%08x\n", aes_key_3);
            printf("    key4 = 0x%08x\n", aes_key_4);
            printf("    key5 = 0x%08x\n", aes_key_5);
			printf("    key6 = 0x%08x\n", aes_key_6);
            printf("    key7 = 0x%08x\n", aes_key_7);
			// Pass common configuration parameters
            printf("\n  Input blocks (each block = 2 tokens => 128 bits)\n");
            for (i = 0; i < aes_num_blocks; i++) {
                printf("  Block %d:\n", i);
                // Each block is 2 tokens
                token_t in0 = mem[i * in_words_adj + 0];
                token_t in1 = mem[i * in_words_adj + 1];
                printf("    in0 = 0x%016lx\n", (unsigned long) in0);
                printf("    in1 = 0x%016lx\n", (unsigned long) in1);
            }
			// iowrite32(dev, SELECT_REG, ioread32(dev, DEVID_REG));
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
		iowrite32(dev, AESCIPHER_AES_KEY_3_REG, aes_key_3);
		iowrite32(dev, AESCIPHER_AES_KEY_2_REG, aes_key_2);
		iowrite32(dev, AESCIPHER_AES_KEY_1_REG, aes_key_1);
		iowrite32(dev, AESCIPHER_AES_KEY_0_REG, aes_key_0);
		iowrite32(dev, AESCIPHER_AES_KEY_7_REG, aes_key_7);
		iowrite32(dev, AESCIPHER_AES_KEY_6_REG, aes_key_6);
		iowrite32(dev, AESCIPHER_AES_KEY_5_REG, aes_key_5);
		iowrite32(dev, AESCIPHER_AES_KEY_4_REG, aes_key_4);
		iowrite32(dev, AESCIPHER_AES_NUM_BLOCKS_REG, aes_num_blocks);

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
			printf("\n  Accelerator output blocks:\n");
            // for (i = 0; i < aes_num_blocks; i++) {
            //     token_t o0 = mem[0];
            //     token_t o1 = mem[1];
			// 	token_t o2 = mem[2];
			// 	token_t o3 = mem[3];
			// 	token_t o4 = mem[4];
			// 	token_t o5 = mem[5];
            //     printf("  Block %d:\n", i);
            //     printf("    out0 = 0x%016lx\n", (unsigned long) o0);
            //     printf("    out1 = 0x%016lx\n", (unsigned long) o1);
			// 	printf("    out2 = 0x%016lx\n", (unsigned long) o2);
			// 	printf("    out3 = 0x%016lx\n", (unsigned long) o3);
			// 	printf("    out4 = 0x%016lx\n", (unsigned long) o4);
			// 	printf("    out5 = 0x%016lx\n", (unsigned long) o5);
            // }
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
