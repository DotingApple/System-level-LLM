// ==============================================================
//  conv_new_rtl_basic_dma64   (two-pixels / 64-bit READ; 1-pixel WRITE)
//  --------------------------------------------------------------
//  • READ side: 2 048 beats × 64-bit  = 16 kB   (pixel-even / pixel-odd)
//  • WRITE side: 4 096 beats × 64-bit = 16 kB   (one 20-bit word per beat)
//  • Stuck-at-state-4 bug fixed:
//      – correct byte count in WRITE-command
// ==============================================================

module conv_new_rtl_basic_dma64
#(
    parameter IMG_PIXELS  = 4096,   // pixels per pass  (64 × 64)
    parameter MAP_WORDS   = 4096,   // words in each convolution map
    parameter FIFO_DEPTH  = 8       // write-side skid FIFO
)
(
    // ─── global ────────────────────────────────────────────────
    input  wire         clk,
    input  wire         rst,                // active-low

    // ─── DMA READ : DRAM → accelerator ────────────────────────
    input  wire         dma_read_ctrl_ready,
    output reg          dma_read_ctrl_valid,
    output reg  [31:0]  dma_read_ctrl_data_index,
    output reg  [31:0]  dma_read_ctrl_data_length,
    output reg  [2:0]   dma_read_ctrl_data_size,

    input  wire         dma_read_chnl_valid,
    input  wire [63:0]  dma_read_chnl_data,
    output reg          dma_read_chnl_ready,

    // ─── DMA WRITE : accelerator → DRAM ───────────────────────
    input  wire         dma_write_ctrl_ready,
    output reg          dma_write_ctrl_valid,
    output reg  [31:0]  dma_write_ctrl_data_index,
    output reg  [31:0]  dma_write_ctrl_data_length,
    output reg  [2:0]   dma_write_ctrl_data_size,

    input  wire         dma_write_chnl_ready,
    output reg          dma_write_chnl_valid,
    output reg  [63:0]  dma_write_chnl_data,

    // ─── configuration / status ───────────────────────────────
    input  wire [31:0]  conf_info_param_height, // unused – kept for ESP
    input  wire [31:0]  conf_info_param_width,  // unused – kept for ESP
    input  wire         conf_done,
    output reg          acc_done,
    output reg  [31:0]  debug
);

    // ─────────── byte addresses in DRAM ───────────────────────
    localparam IMG_BASE   = 32'h0000_0000;
    localparam MAP0_BASE  = 32'h0000_0000;                  // kernel-0
    localparam MAP1_BASE  = 32'h0000_4000;                  // kernel-1  (+16 kB)
    localparam MAP_BYTES  = MAP_WORDS * 4;                  // *** FIX ***

    // ─────────── internal regs / wires ────────────────────────
    reg  [2:0]  state;
    reg  [12:0] pix_ctr;          // 0 … 4095 (pixels  OR write-beats)
    reg         pass_cnt;         // 0 = kernel-0, 1 = kernel-1

    // read-side unpacker
    reg         pix_phase;        // 0 = even pixel, 1 = odd pixel
    reg  [63:0] word_buf;

    reg  [19:0] idata_r;
    reg         ready_pulse;

    wire [11:0] conv_iaddr;
    wire        conv_cwr;
    wire [19:0] conv_cdata_wr;
    wire [2:0]  conv_csel;
    wire        conv_busy;

    // ─── tiny FIFO for write channel ──────────────────────────
    reg  [FIFO_DEPTH-1:0]          fifo_val;
    reg  [63:0]                    fifo_dat [0:FIFO_DEPTH-1];

    // ─── accelerator instance (unchanged) ─────────────────────
    conv_new u_conv_new (
        .clk      (clk),
        .reset    (~rst),
        .ready    (ready_pulse),
        .busy     (conv_busy),
        .iaddr    (conv_iaddr),
        .idata    (idata_r),
        .crd      (), .cdata_rd (), .caddr_rd (),
        .cwr      (conv_cwr),
        .cdata_wr (conv_cdata_wr),
        .caddr_wr (), .csel     (conv_csel)
    );

    // ─── FSM encoding ─────────────────────────────────────────
    localparam  S_IDLE      = 3'd0,
                S_RD_CMD    = 3'd1,
                S_RD_DATA   = 3'd2,
                S_WAIT_DONE = 3'd3,
                S_WR_CMD    = 3'd4,
                S_WR_DATA   = 3'd5;

    // ─── sequential logic ─────────────────────────────────────
    integer i;
    always @(posedge clk or negedge rst) begin
        if (!rst) begin
            state     <= S_IDLE;
            pix_ctr   <= 0;
            pass_cnt  <= 0;
            {dma_read_ctrl_valid, dma_read_chnl_ready,
             dma_write_ctrl_valid,dma_write_chnl_valid} <= 0;
            {dma_read_ctrl_data_index, dma_read_ctrl_data_length,
             dma_read_ctrl_data_size,  dma_write_ctrl_data_index,
             dma_write_ctrl_data_length,dma_write_ctrl_data_size} = 0;
            {pix_phase, word_buf, idata_r, ready_pulse} = 0;
            fifo_val  <= 0;
            acc_done  <= 0;
            debug     <= 0;
        end else begin
            // default strobes
            ready_pulse         <= 0;
            dma_write_chnl_valid<= 0;
            dma_read_chnl_ready <= 0;

            //------------------------------------------------------------------
            case (state)
            //------------------------------------------------------------------
            S_IDLE: begin
                acc_done <= 0;
                if (conf_done) begin
                    // READ command: 16 kB, 64-bit beats
                    dma_read_ctrl_valid       <= 1'b1;
                    dma_read_ctrl_data_index  <= IMG_BASE;
                    dma_read_ctrl_data_length <= 32'd16384;   // 16 kB
                    dma_read_ctrl_data_size   <= 3'd3;        // 64-bit beat
                    state <= S_RD_CMD;
                end
            end
            //------------------------------------------------------------------
            S_RD_CMD: begin
                if (dma_read_ctrl_ready) begin
                    dma_read_ctrl_valid <= 0;
                    pix_ctr   <= 0;
                    pix_phase <= 0;
                    state     <= S_RD_DATA;
                end
            end
            //------------------------------------------------------------------
            //  Two-pixel unpacker
            //------------------------------------------------------------------
            S_RD_DATA: begin
                dma_read_chnl_ready <= (pix_phase == 0);

                if (pix_phase == 0) begin
                    if (dma_read_chnl_valid) begin
                        word_buf  <= dma_read_chnl_data;
                        idata_r   <= dma_read_chnl_data[19:0];
                        pix_phase <= 1;
                        if (pix_ctr == 0) ready_pulse <= 1;
                        pix_ctr <= pix_ctr + 1;
                        if (pix_ctr == IMG_PIXELS-1) state <= S_WAIT_DONE;
                    end
                end else begin
                    idata_r   <= word_buf[51:32];
                    pix_phase <= 0;
                    pix_ctr   <= pix_ctr + 1;
                    if (pix_ctr == IMG_PIXELS-1) state <= S_WAIT_DONE;
                end
            end
            //------------------------------------------------------------------
            S_WAIT_DONE: begin
                if (conv_cwr && (conv_csel == (3'd1 + pass_cnt))) begin
                    dma_write_ctrl_valid       <= 1'b1;
                    dma_write_ctrl_data_index  <= pass_cnt ? MAP1_BASE
                                                           : MAP0_BASE;
                    dma_write_ctrl_data_length <= MAP_BYTES;   // *** FIX ***
                    dma_write_ctrl_data_size   <= 3'd2;        // 32-bit word
                    state <= S_WR_CMD;
                end
            end
            //------------------------------------------------------------------
            S_WR_CMD: begin
                if (dma_write_ctrl_ready) begin
                    dma_write_ctrl_valid <= 0;
                    pix_ctr              <= 0;      // reuse as beat counter
                    fifo_val             <= 0;
                    state                <= S_WR_DATA;
                end
            end
            //------------------------------------------------------------------
            //  WRITE path with FIFO  (unchanged)
            //------------------------------------------------------------------
            S_WR_DATA: begin
                if (conv_cwr && (conv_csel == (3'd1 + pass_cnt))) begin
                    for (i = 0; i < FIFO_DEPTH; i = i + 1)
                        if (!fifo_val[i]) begin
                            fifo_val[i] <= 1'b1;
                            fifo_dat[i] <= {44'd0, conv_cdata_wr};
                            break;
                        end
                end

                if (fifo_val[0]) begin
                    dma_write_chnl_valid <= 1'b1;
                    dma_write_chnl_data  <= fifo_dat[0];
                end

                if (fifo_val[0] && dma_write_chnl_ready) begin
                    for (i = 0; i < FIFO_DEPTH-1; i = i + 1) begin
                        fifo_val[i] <= fifo_val[i+1];
                        fifo_dat[i] <= fifo_dat[i+1];
                    end
                    fifo_val[FIFO_DEPTH-1] <= 1'b0;
                    pix_ctr <= pix_ctr + 1;

                    if (pix_ctr == MAP_WORDS-1) begin
                        if (pass_cnt == 0) begin
                            // second kernel pass
                            pass_cnt <= 1;
                            dma_read_ctrl_valid       <= 1'b1;
                            dma_read_ctrl_data_index  <= IMG_BASE;
                            dma_read_ctrl_data_length <= 32'd16384;
                            dma_read_ctrl_data_size   <= 3'd3;
                            state <= S_RD_CMD;
                        end else begin
                            // done
                            acc_done <= 1;
                            pass_cnt <= 0;
                            state    <= S_IDLE;
                        end
                    end
                end
            end
            //------------------------------------------------------------------
            default: state <= S_IDLE;
            endcase

            debug <= {29'd0, state};
        end
    end

endmodule
