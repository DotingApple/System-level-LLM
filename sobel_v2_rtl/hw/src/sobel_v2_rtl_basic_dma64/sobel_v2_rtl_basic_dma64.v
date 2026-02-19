`timescale 1ns / 1ps
// =============================================================================
//  sobel_v2_rtl_basic_dma64 – burst-read / burst-write version
// =============================================================================
module sobel_v2_rtl_basic_dma64
#(
    parameter integer MAX_PIXELS = 4096          // compile-time memory budget
) (
    // ── global ─────────────────────────────────────────────────────────────
    input  wire         clk,
    input  wire         rst,            // active-low

    // ── configuration ─────────────────────────────────────────────────────
    input  wire [31:0]  conf_info_width,
    input  wire [31:0]  conf_info_height,
    input  wire         conf_done,

    // ── DMA READ control ──────────────────────────────────────────────────
    output wire         dma_read_ctrl_valid,
    output wire [31:0]  dma_read_ctrl_data_index,
    output wire [31:0]  dma_read_ctrl_data_length,
    output wire [2:0]   dma_read_ctrl_data_size,
    input  wire         dma_read_ctrl_ready,

    // ── DMA READ channel ─────────────────────────────────────────────────
    output wire         dma_read_chnl_ready,
    input  wire         dma_read_chnl_valid,
    input  wire [63:0]  dma_read_chnl_data,

    // ── DMA WRITE control ────────────────────────────────────────────────
    output wire         dma_write_ctrl_valid,
    output wire [31:0]  dma_write_ctrl_data_index,
    output wire [31:0]  dma_write_ctrl_data_length,
    output wire [2:0]   dma_write_ctrl_data_size,
    input  wire         dma_write_ctrl_ready,

    // ── DMA WRITE channel ────────────────────────────────────────────────
    input  wire         dma_write_chnl_ready,
    output wire         dma_write_chnl_valid,
    output wire [63:0]  dma_write_chnl_data,

    // ── user outputs ─────────────────────────────────────────────────────
    output reg          acc_done,
    output wire [31:0]  debug
);
    // ────────────────────────────────────────────────────────────────────
    //  Local constants / FSM
    // ────────────────────────────────────────────────────────────────────
    typedef enum logic [2:0] {
        S_IDLE            = 3'd0,
        S_READ_CTRL_WAIT  = 3'd1,
        S_READ            = 3'd2,
        S_PROCESS         = 3'd3,
        S_WRITE_CTRL_WAIT = 3'd4,
        S_WRITE           = 3'd5
    } fsm_t;

    fsm_t           state;

    // ── bookkeeping ──────────────────────────────────────────────────────
    wire [31:0] num_pixels = conf_info_width * conf_info_height;   // total
    // compile-time guard
    always @(*) if (num_pixels > MAX_PIXELS)
        $error("Frame size exceeds MAX_PIXELS=%0d", MAX_PIXELS);

    // ── frame / result buffers ───────────────────────────────────────────
    reg [7:0]  frame_buf  [0:MAX_PIXELS-1];
    reg [7:0]  result_buf [0:MAX_PIXELS-1];

    // ── generic indices / counters ───────────────────────────────────────
    reg [31:0] rd_count;          // counts pixels accepted during READ
    reg [31:0] proc_idx;          // current pixel being processed
    reg [31:0] wr_count;          // pixels written back during WRITE

    // ── Sobel window wires ───────────────────────────────────────────────
    reg [7:0] lu, cu, ru, lc, rc, lb, cb, rb;
    wire [7:0] sobel_out;

    SobelFilter sobel_filter_i (
        .lu(lu), .cu(cu), .ru(ru),
        .lc(lc), .rc(rc),
        .lb(lb), .cb(cb), .rb(rb),
        .edge_lum(sobel_out)
    );
    localparam int PIXELS_PER_BEAT = 8;

    wire [31:0] num_beats =
            (num_pixels + PIXELS_PER_BEAT - 1) / PIXELS_PER_BEAT;  // ceil

    assign dma_read_ctrl_data_length  = num_beats;
    assign dma_write_ctrl_data_length = num_beats;

    // ── DMA READ control (single burst) ──────────────────────────────────
    assign dma_read_ctrl_valid       = (state == S_READ_CTRL_WAIT);
    assign dma_read_ctrl_data_index  = 32'd0;
    // assign dma_read_ctrl_data_length = num_pixels;     // 1 beat = 8 pixels
    assign dma_read_ctrl_data_size   = 3'd3;           // 8-byte beats

    // ready for every beat in S_READ
    assign dma_read_chnl_ready       = (state == S_READ);

    // ── DMA WRITE control (single burst) ─────────────────────────────────
    assign dma_write_ctrl_valid       = (state == S_WRITE_CTRL_WAIT);
    assign dma_write_ctrl_data_index  = 32'd0;
    // assign dma_write_ctrl_data_length = num_pixels;
    assign dma_write_ctrl_data_size   = 3'd3;

    // ── WRITE data channel ───────────────────────────────────────────────
    reg  [63:0] write_word;
    assign dma_write_chnl_valid = (state == S_WRITE);
    assign dma_write_chnl_data  = write_word;

    // ── debug port ───────────────────────────────────────────────────────
    assign debug = {29'd0, state};

    // ────────────────────────────────────────────────────────────────────
    //  Main FSM
    // ────────────────────────────────────────────────────────────────────
    integer k;         // used for for-loops (synthesis-friendly)

    always @(posedge clk or negedge rst) begin
        if (!rst) begin
            state     <= S_IDLE;
            rd_count  <= 0;
            proc_idx  <= 0;
            wr_count  <= 0;
            acc_done  <= 1'b0;
            write_word<= 64'd0;
            lu <= 8'd0; 
            cu <= 8'd0; 
            ru <= 8'd0;
            lc <= 8'd0;             
            rc <= 8'd0;
            lb <= 8'd0; 
            cb <= 8'd0; 
            rb <= 8'd0;
        end else begin
            //------------------------------------------------------------------
            //  STATE MACHINE
            //------------------------------------------------------------------
            case (state)
                // ==========================================================
                S_IDLE: begin
                    if (~conf_done) begin                    // host idle
                        rd_count <= 0;
                        proc_idx <= 0;
                        wr_count <= 0;
                        acc_done <= 1'b0;
                    end else if (conf_done) begin
                        state <= S_READ_CTRL_WAIT;
                    end
                end

                // ==========================================================
                S_READ_CTRL_WAIT: begin
                    if (dma_read_ctrl_ready)
                        state <= S_READ;
                end

                // ==========================================================
                S_READ: begin
                    if (dma_read_chnl_valid) begin
                        // Unpack eight pixels and push into frame buffer
                        for (k = 0; k < 8; k = k + 1)
                            if (rd_count + k < num_pixels)
                                frame_buf[rd_count + k] <=
                                        dma_read_chnl_data[63 - k*8 -: 8];
                        rd_count <= rd_count + 8;

                        if (rd_count + 8 >= num_pixels)
                            state <= S_PROCESS;     // all data is in
                    end
                end

                // ==========================================================
                S_PROCESS: begin
                    //------------------------------------------------------------------
                    //  One pixel processed per cycle
                    //------------------------------------------------------------------
                    // boundary → zero
                    if ( (proc_idx < conf_info_width) ||                       // top
                         (proc_idx >= num_pixels - conf_info_width) ||         // bottom
                         ((proc_idx % conf_info_width) == 0) ||                // left
                         ((proc_idx % conf_info_width) == conf_info_width-1)   // right
                    ) begin
                        result_buf[proc_idx] <= 8'd0;
                    end else begin
                        // Load 3 × 3 neighbourhood into registers
                        lu <= frame_buf[proc_idx - conf_info_width - 1];
                        cu <= frame_buf[proc_idx - conf_info_width    ];
                        ru <= frame_buf[proc_idx - conf_info_width + 1];

                        lc <= frame_buf[proc_idx - 1];
                        rc <= frame_buf[proc_idx + 1];

                        lb <= frame_buf[proc_idx + conf_info_width - 1];
                        cb <= frame_buf[proc_idx + conf_info_width    ];
                        rb <= frame_buf[proc_idx + conf_info_width + 1];

                        // one cycle later sobel_out is valid; latch immediately
                        result_buf[proc_idx] <= sobel_out;
                    end

                    proc_idx <= proc_idx + 1;
                    if (proc_idx + 1 == num_pixels)
                        state <= S_WRITE_CTRL_WAIT;
                end

                // ==========================================================
                S_WRITE_CTRL_WAIT: begin
                    if (dma_write_ctrl_ready) begin
                        wr_count   <= 0;
                        state      <= S_WRITE;
                    end
                end

                // ==========================================================
                S_WRITE: begin
                    if (dma_write_chnl_ready) begin
                        // pack 8 pixels into one 64-bit word
                        for (k = 0; k < 8; k = k + 1)
                            write_word[63 - k*8 -: 8] <=
                                (wr_count + k < num_pixels)
                                    ? result_buf[wr_count + k] : 8'd0;

                        wr_count <= wr_count + 8;

                        if (wr_count + 8 >= num_pixels) begin
                            acc_done <= 1'b1;
                            state    <= S_IDLE;
                        end
                    end
                end

                // ==========================================================
                default: state <= S_IDLE;
            endcase
        end
    end
endmodule
