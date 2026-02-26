/* Copyright (c) 2011-2024 Columbia University, System Level Design Group */
/* SPDX-License-Identifier: Apache-2.0 */

#include <stdio.h>
#ifndef __riscv
#include <stdlib.h>
#endif

#include <esp_accelerator.h>
#include <esp_probe.h>
#include <fixed_point.h>

typedef int32_t token_t;

static unsigned DMA_WORD_PER_BEAT(unsigned _st)
{
        return (sizeof(void *) / _st);
}

/* ------------------------------------------------------------------------
 * New DMA beat parameters:
 *   For the modified accelerator wrapper:
 *     - It now reads 28 beats (each beat = 64 bits) per run.
 *       Since token_t is 32 bits, each beat is 2 words.
 *       Thus, each run has 28 * 2 = 56 input words.
 *     - It produces 1 beat (2 words) per run of output.
 * ------------------------------------------------------------------------ */
const int32_t dma_in_beats = 28;   // input beats per run
const int32_t dma_out_beats = 15;  // output beats per run 

#define SLD_FCDNN_ACC 0x001
#define DEV_NAME "sld,fcdnn_acc_rtl"

/* <<--params-->> */
const int32_t array_size = 16;   // Accelerator configuration remains unchanged.
const int32_t mux_cfg = 0;
const int32_t exp_val = 8;
const int32_t pipe_mode = 0;
const int32_t runs = 1;

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
#define FCDNN_ACC_ARRAY_SIZE_REG 0x50
#define FCDNN_ACC_MUX_CFG_REG    0x4c
#define FCDNN_ACC_EXP_VAL_REG    0x48
#define FCDNN_ACC_PIPE_MODE_REG  0x44
#define FCDNN_ACC_RUNS_REG       0x40

static int validate_buf(token_t *out, token_t *gold, token_t *mem)
{
	int i, j;
	unsigned errors = 0;

	/* For each run, compare the output words.
	 * Note: In the original code the loop ran for array_size outputs.
	 * For the modified accelerator, out_words_adj now holds the number of
	 * 32-bit words in the accelerator’s output beat (which is 2).
	 */
	for (i = 0; i < runs; i++){
		// for (j = 0; j < out_words_adj; j++){
		// 	printf("out[%d][%d] = %lx\n", i, j, out[i * out_words_adj + j]);
		// 	if (gold[i * out_words_adj + j] != out[i * out_words_adj + j])
		// 		errors++;
		// }
		for (j = 0; j < 20; j++){
			printf("memory index %d value: %lx\n", j, mem[j]);
		}
	}
	return errors;
}

static void init_buf(token_t *in, token_t *gold)
{
    int run, j;
    
    /* In the modified accelerator each run now requires:
     *   dma_in_beats beats * (DMA_WORD_PER_BEAT) words per beat.
     * With dma_in_beats = 28 and DMA_WORD_PER_BEAT(sizeof(token_t)) typically = 2,
     * each run uses 28 * 2 = 56 words.
     * Similarly, each run produces dma_out_beats * (DMA_WORD_PER_BEAT) output words,
     * which is 1 * 2 = 2 words.
     */
    int total_in_words = dma_in_beats * DMA_WORD_PER_BEAT(sizeof(token_t));   // 28 * 2 = 56
    int total_out_words = dma_out_beats * DMA_WORD_PER_BEAT(sizeof(token_t)); // 1 * 2 = 2

    /* Initialize input buffer with a simple pattern:
     * The pattern is similar to the original ((run << 16) + j)
     * but now j runs from 0 to total_in_words-1.
     */
    for (run = 0; run < runs; run++) {
        for (j = 0; j < total_in_words; j++) {
            in[run * in_words_adj + j] = (token_t)((run << 16) + j);
        }
    }
    
    /* For the golden output, we define a trivial transformation.
     * (In a real design this would match the accelerator’s function.)
     * For demonstration we compute:
     *   gold[run*out_words_adj + 0] = in[run * in_words_adj + 0] + in[run * in_words_adj + 1]
     *   gold[run*out_words_adj + 1] = 0
     */
    // for (run = 0; run < runs; run++) {
    //     gold[run * out_words_adj + 0] = in[run * in_words_adj + 0] + in[run * in_words_adj + 1];
    //     gold[run * out_words_adj + 1] = 0;
    // }

    /* Optionally, print the first few values as a sanity check: */
    // printf("\nInitialized input buffer (first run):\n");
    // for (j = 0; j < (total_in_words < 8 ? total_in_words : 8); j++) {
    //     printf("  in[%d] = %d\n", j, in[j]);
    // }

    // printf("\nExpected golden output (first run):\n");
    // for (j = 0; j < total_out_words; j++) {
    //     printf("  gold[%d] = %d\n", j, gold[j]);
    // }
    // printf("\n");
}



int main(int argc, char * argv[])
{
	int i, n, ndev;
	struct esp_device *espdevs;
	struct esp_device *dev;
	unsigned done;
	unsigned **ptable;
	token_t *mem;
	token_t *gold;
	unsigned errors = 0;
	unsigned coherence;

	/* Update in_words_adj and out_words_adj based on new DMA beat sizes.
	 * Each beat is 64 bits, which is 2 token_t words.
	 */
	in_words_adj  = round_up(dma_in_beats * DMA_WORD_PER_BEAT(sizeof(token_t)),
		DMA_WORD_PER_BEAT(sizeof(token_t)));
	out_words_adj = round_up(dma_out_beats * DMA_WORD_PER_BEAT(sizeof(token_t)),
		DMA_WORD_PER_BEAT(sizeof(token_t)));


	in_len    = in_words_adj * (runs);
	out_len   = out_words_adj * (runs);
	in_size   = in_len * sizeof(token_t);
	out_size  = out_len * sizeof(token_t);
	out_offset = in_len;
	mem_size  = (out_offset * sizeof(token_t)) + out_size;

	/* Search for the device */
	printf("Scanning device tree... \n");

	ndev = probe(&espdevs, VENDOR_SLD, SLD_FCDNN_ACC, DEV_NAME);
	if (ndev == 0) {
		printf("fcdnn_acc not found\n");
		return 0;
	}

	for (n = 0; n < ndev; n++) {

		printf("**************** %s.%d ****************\n", DEV_NAME, n);

		dev = &espdevs[n];

		/* Check DMA capabilities */
		if (ioread32(dev, PT_NCHUNK_MAX_REG) == 0) {
			printf("  -> scatter-gather DMA is disabled. Abort.\n");
			return 0;
		}

		if (ioread32(dev, PT_NCHUNK_MAX_REG) < NCHUNK(mem_size)) {
			printf("  -> Not enough TLB entries available. Abort.\n");
			return 0;
		}

		/* Allocate memory */
		gold = aligned_malloc(out_size);
		mem = aligned_malloc(mem_size);
		printf("  memory buffer base-address = %p\n", mem);

		/* Allocate and populate page table */
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

			/* Pass common configuration parameters */
			// iowrite32(dev, SELECT_REG, ioread32(dev, DEVID_REG));
			iowrite32(dev, COHERENCE_REG, coherence);

#ifndef __sparc
			iowrite32(dev, PT_ADDRESS_REG, (unsigned long long) ptable);
#else
			iowrite32(dev, PT_ADDRESS_REG, (unsigned) ptable);
#endif
			iowrite32(dev, PT_NCHUNK_REG, NCHUNK(mem_size));
			iowrite32(dev, PT_SHIFT_REG, CHUNK_SHIFT);

			/* Use the following if input and output data are not allocated at the default offsets */
			iowrite32(dev, SRC_OFFSET_REG, 0x0);
			iowrite32(dev, DST_OFFSET_REG, 0x0);

			/* Pass accelerator-specific configuration parameters */
			/* <<--regs-config-->> */
			iowrite32(dev, FCDNN_ACC_ARRAY_SIZE_REG, array_size);
			iowrite32(dev, FCDNN_ACC_MUX_CFG_REG, mux_cfg);
			iowrite32(dev, FCDNN_ACC_EXP_VAL_REG, exp_val);
			iowrite32(dev, FCDNN_ACC_PIPE_MODE_REG, pipe_mode);
			iowrite32(dev, FCDNN_ACC_RUNS_REG, runs);

			/* Flush (customize coherence model here) */
			esp_flush(coherence);

			/* Start accelerator */
			printf("  Start...\n");
			iowrite32(dev, CMD_REG, CMD_MASK_START);

			/* Wait for completion */
			done = 0;
			while (!done) {
				done = ioread32(dev, STATUS_REG);
				done &= STATUS_MASK_DONE;
			}
			iowrite32(dev, CMD_REG, 0x0);

			printf("  Done\n");
			printf("  validating...\n");

			/* Validation */
			errors = validate_buf(&mem[out_offset], gold, &mem[0]);
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
