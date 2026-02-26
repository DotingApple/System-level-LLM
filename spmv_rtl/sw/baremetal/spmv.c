/* Copyright (c) 2011-2024 Columbia University, System Level Design Group */
/* SPDX-License-Identifier: Apache-2.0 */

#include <stdio.h>
#include <stdlib.h>
#include <esp_accelerator.h>
#include <esp_probe.h>
#include <fixed_point.h>
#include <stdint.h>
#include <string.h>

#define ROWS 128
#define COLS 128
// Number of nonzeros, e.g. 4096
#define SPMV_NNZ 4096
#define SPMV_VEC_LEN 128

// We now treat the DMA buffer as an array of 64-bit words.
typedef uint64_t word_t;

#define SLD_SPMV 0x0a1
#define DEV_NAME "sld,spmv_rtl"

/* <<--params-->> */
static unsigned in_words_adj;
static unsigned out_words_adj;
static unsigned in_len;   // in number of 64-bit words
static unsigned out_len;  
static unsigned in_size;  // in bytes
static unsigned out_size; // in bytes
static unsigned out_offset;
static unsigned mem_size;

/* Size of the contiguous chunks for scatter/gather */
#define CHUNK_SHIFT 20
#define CHUNK_SIZE (1UL << CHUNK_SHIFT)
#define NCHUNK(_sz) (((_sz) % CHUNK_SIZE == 0) ? \
                     ((_sz) / CHUNK_SIZE) : \
                     ((_sz) / CHUNK_SIZE) + 1)

/* User defined registers */
/* <<--regs-->> */
#define SPMV_SPMV_NNZ_REG       0x44
#define SPMV_SPMV_VEC_LEN_REG   0x40

/*
   We now store:
     1. Matrix nonzero data in the first SPMV_NNZ words.
        For each nonzero i:
           Bits [7:0]   = A[row, col] (the nonzero value, 8-bit)
           Bits [15:8]  = col index   (8-bit)
           Bits [23:16] = row index   (8-bit)
        (We only use the lower 24 bits of each 64-bit word.)
     2. After those 4096 words, we store the dense input vector X (SPMV_VEC_LEN words),
        each with an 8-bit value in the low byte.
*/

/*
   Updated init_buf_64:
   - We assume each row gets nnz_per_row nonzeros, with the first 'leftover' rows
     getting one extra nonzero.
   - We reorder the matrix data as follows:
       For each block of 32 rows:
         For each nonzero position j (which becomes the new col_id),
         iterate through all rows in the block.
         That is, for block 0 (rows 0–31) we emit the j=0 entry for rows 0–31,
         then the j=1 entry for rows 0–31, and so on.
         Then proceed to block 1 (rows 32–63), etc.
   - The original data and col values are computed using the row‑major global index.
*/
static void init_buf_64(word_t *in)
{
    int block_size = 32;  // Size of each quadrant
    int num_blocks = 4;   // 4 quadrants
    int nonzeros_per_block = SPMV_NNZ / num_blocks;  // 1024 nonzeros per quadrant
    int nnz_index = 0;
    
    // For each quadrant
    for (int block = 0; block < num_blocks; block++) {
        int start_row = block * block_size;
        int end_row = start_row + block_size;
        int start_col = block * block_size;
        int end_col = start_col + block_size;
        
        // For each column in this quadrant
        for (int col = start_col; col < end_col; col++) {
            // For each row in this quadrant
            for (int row = start_row; row < end_row; row++) {
                // Only create a nonzero if we haven't exceeded the per-quadrant limit
                if (nnz_index < (block + 1) * nonzeros_per_block) {
                    // Data value is row+1 as specified
                    uint8_t data = (uint8_t)(128 - row);
                    uint8_t c = (uint8_t)col;
                    uint8_t r = (uint8_t)row;
                    
                    // Pack into 64-bit word:
                    //   bits [7:0]   = data
                    //   bits [15:8]  = col
                    //   bits [23:16] = row
                    word_t w = 0;
                    w |= ((word_t)data & 0xFF);
                    w |= (((word_t)c & 0xFF) << 8);
                    w |= (((word_t)r & 0xFF) << 16);
                    
                    in[nnz_index] = w;
                    nnz_index++;
                }
            }
        }
    }
    
    // Verification
    printf("Generated %d nonzeros out of %d requested\n", nnz_index, SPMV_NNZ);
    
    // Check if we have exactly SPMV_NNZ nonzeros
    if (nnz_index < SPMV_NNZ) {
        printf("Warning: Not enough row/col combinations to fill %d nonzeros\n", SPMV_NNZ);
        // Fill remaining with zeros if needed
        while (nnz_index < SPMV_NNZ) {
            word_t w = 0;
            in[nnz_index] = w;
            nnz_index++;
        }
    } else if (nnz_index > SPMV_NNZ) {
        printf("Error: Generated too many nonzeros\n");
    }
    
    // Store the dense vector after the matrix data
    for (int i = 0; i < SPMV_VEC_LEN; i++) {
        uint8_t x_val = (uint8_t)((i % 255) + 1);
        in[SPMV_NNZ + i] = (word_t)x_val;
    }
}

/*
   Compute the expected result y in software, to verify correctness.
   We read SPMV_NNZ words from the input buffer to get (row, col, data).
   Then we use X stored at in[SPMV_NNZ + i].
*/
static void compute_y(uint16_t *y)
{
    // Initialize output vector to zeros
    for (int row = 0; row < SPMV_VEC_LEN; row++) {
        y[row] = 0;
    }
    
    int block_size = 32;
    int num_blocks = 4;
    int nonzeros_per_block = SPMV_NNZ / num_blocks;
    int count = 0;
    
    // Process nonzeros in the same order as initialization
    for (int block = 0; block < num_blocks; block++) {
        int start_row = block * block_size;
        int end_row = start_row + block_size;
        int start_col = block * block_size;
        int end_col = start_col + block_size;
        
        // For each column in this quadrant
        for (int col = start_col; col < end_col; col++) {
            // Get the corresponding x value
            uint8_t x_val = (uint8_t)((col % 255) + 1);
            
            // For each row in this quadrant
            for (int row = start_row; row < end_row; row++) {
                // Only process if we haven't exceeded the per-quadrant limit
                if (count < (block + 1) * nonzeros_per_block) {
                    // Data value based on row+1
                    uint8_t data = (uint8_t)(128 - row);
                    
                    // Accumulate to output
                    y[row] += (uint8_t)data * (uint8_t)x_val;
                    count++;
                }
            }
        }
    }
}

/*
   Accelerator output is also an array of 64-bit words,
   but typically only the low bits are used (e.g. 16 bits).
   We'll assume the accelerator writes each final y[i] in the low 16 bits.
*/
static int validate_buf(word_t *out, uint16_t *gold)
{
    int errors = 0;
    for (int j = 0; j < SPMV_VEC_LEN; j++) {
        uint16_t result = (uint16_t)(out[j] & 0xFFFF);
        if (result != (uint16_t) gold[j]) {
            errors++;
            printf("MISMATCH result = %d, gold = %d\n", result, gold[j]);
        }
    }
    return errors;
}

int main(int argc, char *argv[])
{
    int i, n;
    int ndev;
    struct esp_device *espdevs;
    struct esp_device *dev;
    unsigned done;
    unsigned **ptable;
    word_t *mem;
    uint16_t y[SPMV_VEC_LEN];
    unsigned errors = 0;
    unsigned coherence;

    in_words_adj  = SPMV_NNZ + SPMV_VEC_LEN;
    out_words_adj = SPMV_VEC_LEN;
    in_len  = in_words_adj;
    out_len = out_words_adj;
    in_size  = in_len  * sizeof(word_t);
    out_size = out_len * sizeof(word_t);
    out_offset = in_len;
    mem_size = (out_offset * sizeof(word_t)) + out_size;

    printf("Scanning device tree... \n");
    ndev = probe(&espdevs, VENDOR_SLD, SLD_SPMV, DEV_NAME);
    if (ndev == 0) {
        printf("spmv not found\n");
        return 0;
    }

    for (n = 0; n < ndev; n++) {
        printf("**************** %s.%d ****************\n", DEV_NAME, n);
        dev = &espdevs[n];

        if (ioread32(dev, PT_NCHUNK_MAX_REG) == 0) {
            printf("  -> scatter-gather DMA is disabled. Abort.\n");
            return 0;
        }
        if (ioread32(dev, PT_NCHUNK_MAX_REG) < NCHUNK(mem_size)) {
            printf("  -> Not enough TLB entries available. Abort.\n");
            return 0;
        }

        mem = aligned_malloc(mem_size);
        printf("  memory buffer base-address = %p\n", mem);

        ptable = aligned_malloc(NCHUNK(mem_size) * sizeof(unsigned *));
        for (i = 0; i < NCHUNK(mem_size); i++)
            ptable[i] = (unsigned *)&mem[i * (CHUNK_SIZE / sizeof(word_t))];
        printf("  ptable = %p\n", ptable);
        printf("  nchunk = %lu\n", NCHUNK(mem_size));

#ifndef __riscv
        for (coherence = ACC_COH_NONE; coherence <= ACC_COH_RECALL; coherence++) {
#else
        {
            coherence = ACC_COH_NONE;
#endif
            printf("  --------------------\n");
            printf("  Generating input buffer...\n");
            init_buf_64(mem);

            compute_y(y);

            // iowrite32(dev, SELECT_REG, ioread32(dev, DEVID_REG));
            iowrite32(dev, COHERENCE_REG, coherence);
#ifndef __sparc
            iowrite32(dev, PT_ADDRESS_REG, (unsigned long long)ptable);
#else
            iowrite32(dev, PT_ADDRESS_REG, (unsigned)ptable);
#endif
            iowrite32(dev, PT_NCHUNK_REG, NCHUNK(mem_size));
            iowrite32(dev, PT_SHIFT_REG, CHUNK_SHIFT);
            iowrite32(dev, SRC_OFFSET_REG, 0x0);
            iowrite32(dev, DST_OFFSET_REG, 0x0);

            iowrite32(dev, SPMV_SPMV_NNZ_REG, SPMV_NNZ);
            iowrite32(dev, SPMV_SPMV_VEC_LEN_REG, SPMV_VEC_LEN);

            esp_flush(coherence);

            printf("  Start...\n");
            iowrite32(dev, CMD_REG, CMD_MASK_START);

            done = 0;
            while (!done) {
                done = ioread32(dev, STATUS_REG);
                done &= STATUS_MASK_DONE;
            }
            iowrite32(dev, CMD_REG, 0x0);
            printf("  Done\n");

            printf("  Validating...\n");
            errors = validate_buf(&mem[out_offset], y);
            if (errors)
                printf("  ... FAIL (%u errors)\n", errors);
            else
                printf("  ... PASS\n");
        }
        aligned_free(ptable);
        aligned_free(mem);
    }
    return 0;
}

