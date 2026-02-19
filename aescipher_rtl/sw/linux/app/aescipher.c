// Copyright (c) 2011-2024 Columbia University, System Level Design Group
// SPDX-License-Identifier: Apache-2.0
#include "libesp.h"
#include "cfg.h"

static unsigned in_words_adj;
static unsigned out_words_adj;
static unsigned in_len;
static unsigned out_len;
static unsigned in_size;
static unsigned out_size;
static unsigned out_offset;
static unsigned size;

/* User-defined code */
static int validate_buffer(token_t *out, token_t *gold)
{
	int i;
	int j;
	unsigned errors = 0;

	for (i = 0; i < aes_num_blocks; i++)
		for (j = 0; j < 2*aes_num_blocks; j++)
			if (gold[i * out_words_adj + j] != out[i * out_words_adj + j])
				errors++;

	return errors;
}


/* User-defined code */
static void init_buffer(token_t *in, token_t * gold)
{
	int i;
	int j;

	for (i = 0; i < aes_num_blocks; i++)
		for (j = 0; j < 2*aes_num_blocks; j++)
			in[i * in_words_adj + j] = (token_t) j;

	for (i = 0; i < aes_num_blocks; i++)
		for (j = 0; j < 2*aes_num_blocks; j++)
			gold[i * out_words_adj + j] = (token_t) j;
}


/* User-defined code */
static void init_parameters()
{
	if (DMA_WORD_PER_BEAT(sizeof(token_t)) == 0) {
		in_words_adj = 2*aes_num_blocks;
		out_words_adj = 2*aes_num_blocks;
	} else {
		in_words_adj = round_up(2*aes_num_blocks, DMA_WORD_PER_BEAT(sizeof(token_t)));
		out_words_adj = round_up(2*aes_num_blocks, DMA_WORD_PER_BEAT(sizeof(token_t)));
	}
	in_len = in_words_adj * (aes_num_blocks);
	out_len =  out_words_adj * (aes_num_blocks);
	in_size = in_len * sizeof(token_t);
	out_size = out_len * sizeof(token_t);
	out_offset = 0;
	size = (out_offset * sizeof(token_t)) + out_size;
}


int main(int argc, char **argv)
{
	int errors;

	token_t *gold;
	token_t *buf;

	init_parameters();

	buf = (token_t *) esp_alloc(size);
	cfg_000[0].hw_buf = buf;
    
	gold = malloc(out_size);

	init_buffer(buf, gold);

	printf("\n====== %s ======\n\n", cfg_000[0].devname);
	/* <<--print-params-->> */
	printf("  .aes_key_3 = %d\n", aes_key_3);
	printf("  .aes_key_2 = %d\n", aes_key_2);
	printf("  .aes_key_1 = %d\n", aes_key_1);
	printf("  .aes_key_0 = %d\n", aes_key_0);
	printf("  .aes_key_7 = %d\n", aes_key_7);
	printf("  .aes_key_6 = %d\n", aes_key_6);
	printf("  .aes_key_5 = %d\n", aes_key_5);
	printf("  .aes_key_4 = %d\n", aes_key_4);
	printf("  .aes_num_blocks = %d\n", aes_num_blocks);
	printf("\n  ** START **\n");

	esp_run(cfg_000, NACC);

	printf("\n  ** DONE **\n");

	errors = validate_buffer(&buf[out_offset], gold);

	free(gold);
	esp_free(buf);

	if (!errors)
		printf("+ Test PASSED\n");
	else
		printf("+ Test FAILED\n");

	printf("\n====== %s ======\n\n", cfg_000[0].devname);

	return errors;
}
