//////////////////////////////////////////////////////////////////////////////
// Matrix vector multiplication design with sparsity
// This is a Sparse Matrix-Vector Multiplication accelerator design. 
// The mathematical formula is Y = M * X where M is input sparse matrix, 
// X is input dense vector and Y is output dense vector. We support 8-bit 
// precision. Vector X is loaded in on-chip banked memory before start of 
// the operation. The input to the accelerator are 3 values corresponding 
// to each matrix element: data, col, number of non zero values in a row. 
// There are 32 channels which can run in parallel. Each channel has a MAC 
// unit. Computation for each row of the matrix is assigned to a channel 
// dynamically based on the number of non zero values in that row. The final
// accumulated value is written in the output memory. The write address is 
// based on row number. Hence, write is out of order with respect to rows 
// in output vector.
// Multipliers in channels followed by accumulators, Banked Vector Buffer 
// (RAM and crossbar) to store vector elements. Arbiter to fetch data from 
// RAMs store matrix elements. Uses CISR encoding. Multiple FIFOs.
//////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////
// Author: Aatman Borda
//////////////////////////////////////////////////////////////////////////////

//`define SIMULATION
`define COL_ID_BITS 8
`define ROW_ID_BITS 8
`define MAT_VAL_BITS 8
`define VEC_VAL_BITS 8
`define MULT_BITS (`VEC_VAL_BITS + `MAT_VAL_BITS)
`define NUM_CHANNEL 32
`define NUM_CHANNEL_BITS $clog2(`NUM_CHANNEL)
`define LANE_NUM (3 * `NUM_CHANNEL)
// `define LANE_NUM_BITS $clog2(`LANE_NUM)
//`define NUM_MAT_VALS 8864
`define NUM_MAT_VALS 4096
`define NUM_COL_IDS `NUM_MAT_VALS
`define NUM_ROW_IDS `NUM_MAT_VALS
`define NUM_VEC_VALS 128

//`define MAT_VAL_ADDR_WIDTH $clog2(`NUM_MAT_VALS)
`define MAT_VAL_ADDR_WIDTH 12
`define COL_ID_ADDR_WIDTH `MAT_VAL_ADDR_WIDTH
`define ROW_ID_ADDR_WIDTH `MAT_VAL_ADDR_WIDTH

`define FIFO_DEPTH 8
`define MAX_COLS (1<<`COL_ID_BITS)

// MACROS for BVB
`define BYTES_PER_ADDR_PER_BRAM 1
`define NUM_BRAMS 1
`define VEC_VAL_BYTES (`VEC_VAL_BITS/8)
`define VEC_VAL_OFFSET $clog2(`VEC_VAL_BITS)
`define NUM_VEC_VALS_PER_ADDR_PER_BRAM (`BYTES_PER_ADDR_PER_BRAM/`VEC_VAL_BYTES)
`define NUM_VEC_VALS_PER_ADDR `NUM_VEC_VALS_PER_ADDR_PER_BRAM*`NUM_BRAMS
`define NUM_VEC_VALS_PER_ADDR_BITS $clog2(`NUM_VEC_VALS_PER_ADDR)
`define NUM_ADDR (`NUM_VEC_VALS/`NUM_VEC_VALS_PER_ADDR)+1
`define BVB_AWIDTH `COL_ID_BITS
`define COUNTER_BITS $clog2(`NUM_ADDR)
`define LOCAL_ID_BITS `NUM_VEC_VALS_PER_ADDR_BITS

module spmv(
	input clk,
	input rst,

	output [`MULT_BITS-1:0] dout,

	output reg done_reg,

  input [`MAT_VAL_BITS-1:0] mat_val_din,
  input	[`COL_ID_BITS-1:0] col_id_din,
  input [`ROW_ID_BITS-1:0] row_id_din,

  input mat_val_wren,
  input col_id_wren,
  input row_id_wren,

  input [`MAT_VAL_ADDR_WIDTH-1:0] mat_val_addr_ext,
  input [`COL_ID_ADDR_WIDTH-1:0] col_id_addr_ext,
  input [`ROW_ID_ADDR_WIDTH-1:0] row_id_addr_ext,

	input [`NUM_VEC_VALS_PER_ADDR*`VEC_VAL_BITS-1:0] vector_din,
  input vector_wren,
  input [`BVB_AWIDTH-1:0] vector_addr_ext,
  input stall_fetcher,
  input [31:0] spmv_nnz,
  input [`ROW_ID_BITS-1:0]wr_addr_ext,
  input dma_write_chnl_ready_write_out,
  output reg wr_en
);

	// Row ID fifo signal
	wire [(`ROW_ID_BITS*`NUM_CHANNEL)-1:0] row_id;
	wire [`NUM_CHANNEL-1:0] row_id_empty;
	wire [`NUM_CHANNEL-1:0] row_id_rd_en;

	// column id fifo signals
	wire [(`COL_ID_BITS*`NUM_CHANNEL-1):0] col_id;
	wire [`NUM_CHANNEL-1:0] col_id_empty;
	wire [`NUM_CHANNEL-1:0] col_id_rd_en; 

	// matrix elements fifo signals
	wire [(`MAT_VAL_BITS*`NUM_CHANNEL)-1:0] mat_val;
	wire [`NUM_CHANNEL-1:0] mat_val_empty;
	wire [`NUM_CHANNEL-1:0] mat_val_rd_en;

	// The above the FIFOs are called fetcher FIFOs as they are a part of fetcher module and are filled by fetcher.

	// Fetcher module signals. There are just the above three put together.
	wire [((`ROW_ID_BITS+`COL_ID_BITS+`MAT_VAL_BITS)*`NUM_CHANNEL)-1:0] fetcher_out;
	wire [3*`NUM_CHANNEL-1:0] fetcher_empty;
	wire [3*`NUM_CHANNEL-1:0] fetcher_rd_en;

	// Vector values fifo signals
	wire [`VEC_VAL_BITS*`NUM_CHANNEL-1:0] vec_val;
	wire [`NUM_CHANNEL-1:0] vec_val_empty;
	wire [`NUM_CHANNEL-1:0] vec_val_rd_en;

	// 1 if at least 1 of the fetcher FIFOs is empty
	reg all_empty;

	// Signal to start the engine
	reg start;

	// Output data
	wire [(`MULT_BITS*`NUM_CHANNEL)-1:0] data_out;
	// output fifo empty signals
	wire [`NUM_CHANNEL-1:0] data_out_empty;
	// Address to store output data
	wire [(`ROW_ID_BITS*`NUM_CHANNEL)-1:0] addr_out;
	// output fifo read enable signal
	wire [`NUM_CHANNEL-1:0] out_rd_en;
	// reg [`NUM_CHANNEL-1:0] out_rd_en_reg;
	wire [`NUM_CHANNEL-1:0] out_rd_en_shifted;
	// Memory to write the output data

	wire [`MULT_BITS-1:0] data_out_shifted;
	wire [`ROW_ID_BITS-1:0] addr_out_shifted;
	wire [`MULT_BITS-1:0] wr_data;
	wire [`ROW_ID_BITS-1:0] wr_addr;
  wire [`ROW_ID_BITS-1:0] write_addr;
//	reg wr_en;

	// Signals to indicate that the computation is complete
	wire [`NUM_CHANNEL-1:0] done;
  wire fetcher_done;
	reg done_all, last;

	always@(posedge clk) begin
		if (rst) begin
			all_empty <= 1;
			start <= 0;
		end
		else begin
			all_empty <= (|fetcher_empty) & (~start);
			if (!all_empty) begin
				start <= 1;
			end
		end
	end

	reg [`NUM_CHANNEL_BITS-1:0] counter;
	reg [`NUM_CHANNEL_BITS-1:0] counter_delay;
	reg [`NUM_CHANNEL_BITS-1:0] counter_store;

	assign out_rd_en = (({`NUM_CHANNEL{1'b0}})|(1<<counter)) & ~data_out_empty;
	assign out_rd_en_shifted = out_rd_en >> counter;

	assign data_out_shifted = data_out >> (counter_delay*`MULT_BITS);
`ifdef QUARTUS
	genvar loop_idx;
	generate
		for (loop_idx = 0; loop_idx < `ROW_ID_BITS; loop_idx = loop_idx + 1) begin: gen_addr_out
			assign addr_out_shifted[loop_idx] = ^(addr_out[(loop_idx+1)*`NUM_CHANNEL-1:loop_idx*`NUM_CHANNEL]);
		end
	endgenerate
`else
	assign addr_out_shifted = addr_out >> (counter_delay*`ROW_ID_BITS);
`endif

	assign wr_data = data_out_shifted;
	assign wr_addr = addr_out_shifted;
  assign write_addr = (dma_write_chnl_ready_write_out) ? wr_addr_ext : wr_addr;

	always @ (posedge clk) begin
		if(rst) begin
			counter <= 0;
			counter_delay <= 0;
			last <= 0;
      done_reg <= 0;
		end
		else if(start) begin
		  done_all <= &done;
      if (!done_reg) begin
		    counter <= counter + 1;
		    counter_delay <= counter;
      end
		  if(out_rd_en_shifted[0]) begin
			  wr_en <= 1;
		  end
		  else begin
			  wr_en <= 0;
		  end
		  if(done_all & !last) begin
			  counter_store <= counter_delay;
			  last <= 1;
		  end
		  else if (last) begin
        if (counter_store == counter_delay) begin
          done_reg <= 1'b1;
        end
			  //done_reg <= (counter_store==counter_delay);
		  end
		end
	end

	spram #(
		.AWIDTH(`ROW_ID_BITS),
		.NUM_WORDS(`NUM_VEC_VALS),
		.DWIDTH(`MULT_BITS)
	) write_mem (
		.clk(clk),
//		.address(wr_addr),
    .address(write_addr),
		.wren(wr_en),
		.din(wr_data),
		.dout(dout)
	);

	// Assign FIFOs' read enables to the respective wires of fetcher read enable.
	assign fetcher_rd_en[3*`NUM_CHANNEL-1: 2*`NUM_CHANNEL] = row_id_rd_en;
	assign fetcher_rd_en[2*`NUM_CHANNEL-1: 1*`NUM_CHANNEL] = col_id_rd_en;
	assign fetcher_rd_en[1*`NUM_CHANNEL-1: 0] = mat_val_rd_en;

	fetcher fetcher (
		.clk(clk),
		.rst(rst),

		.mat_val_rd_en(fetcher_rd_en[1*`NUM_CHANNEL-1: 0]),
		.col_id_rd_en(fetcher_rd_en[2*`NUM_CHANNEL-1: 1*`NUM_CHANNEL]),
		.row_id_rd_en(fetcher_rd_en[3*`NUM_CHANNEL-1: 2*`NUM_CHANNEL]),

		.mat_val_out(fetcher_out[(1*`MAT_VAL_BITS*`NUM_CHANNEL)-1: 0]),
		.col_id_out(fetcher_out[(2*`COL_ID_BITS*`NUM_CHANNEL)-1: 1*`COL_ID_BITS*`NUM_CHANNEL]),
		.row_id_out(fetcher_out[(3*`ROW_ID_BITS*`NUM_CHANNEL)-1: 2*`ROW_ID_BITS*`NUM_CHANNEL]),

		.mat_val_empty(fetcher_empty[1*`NUM_CHANNEL-1: 0]),
		.col_id_empty(fetcher_empty[2*`NUM_CHANNEL-1: 1*`NUM_CHANNEL]),
		.row_id_empty(fetcher_empty[3*`NUM_CHANNEL-1: 2*`NUM_CHANNEL]),

		.done(fetcher_done),
    .mat_val_din(mat_val_din),
    .col_id_din(col_id_din),
    .row_id_din(row_id_din),
    .mat_val_wren(mat_val_wren),
    .col_id_wren(col_id_wren),
    .row_id_wren(row_id_wren),
    .mat_val_addr_ext(mat_val_addr_ext),
    .col_id_addr_ext(col_id_addr_ext),
    .row_id_addr_ext(row_id_addr_ext),
    .stall(stall_fetcher),
    .spmv_nnz(spmv_nnz)
	);

	assign row_id = fetcher_out[3*`ROW_ID_BITS*`NUM_CHANNEL-1: 2*`ROW_ID_BITS*`NUM_CHANNEL];
	assign row_id_empty = fetcher_empty[3*`NUM_CHANNEL-1: 2*`NUM_CHANNEL];

	assign col_id = fetcher_out[2*`COL_ID_BITS*`NUM_CHANNEL-1: 1*`COL_ID_BITS*`NUM_CHANNEL];
	assign col_id_empty = fetcher_empty[2*`NUM_CHANNEL-1: 1*`NUM_CHANNEL];

	assign mat_val = fetcher_out[1*`MAT_VAL_BITS*`NUM_CHANNEL-1: 0];
	assign mat_val_empty = fetcher_empty[1*`NUM_CHANNEL-1: 0];


	bvb bvb (
		.clk(clk),
		.rst(rst),
		.start(start),
		.id(col_id),
		.id_empty(col_id_empty),
		.id_rd_en(col_id_rd_en),
		.val(vec_val),
		.val_empty(vec_val_empty),
		.val_rd_en(vec_val_rd_en),
    .vector_din(vector_din),
    .vector_wren(vector_wren),
    .vector_addr_ext(vector_addr_ext)
	);

	Big_Channel Big_Channel_ (
		.clk(clk), 
		.rst(rst),
		.start(start), 
		.fetcher_done(fetcher_done),
		.mat_val(mat_val), 
		.mat_val_empty(mat_val_empty), 
		.mat_val_rd_en(mat_val_rd_en), 
		.vec_val(vec_val), 
		.vec_val_empty(vec_val_empty), 
		.vec_val_rd_en(vec_val_rd_en), 
		.row_id(row_id), 
		.row_id_empty(row_id_empty), 
		.row_id_rd_en(row_id_rd_en), 
		.data_out(data_out),
		.data_out_empty(data_out_empty),
		.addr_out(addr_out),
		.out_rd_en(out_rd_en),
		.done(done)
	);
endmodule

