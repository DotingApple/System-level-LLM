module sha256_top(
  input  wire         clk,
  input  wire         reset_n,
  input  wire         init,
  input  wire         next,
  input  wire         mode,
  input  wire [511:0] block,

  output wire         ready,
  output wire [255:0] digest,
  output wire         digest_valid
);

  localparam H0_CONST = 32'h6a09e667;
  localparam H1_CONST = 32'hbb67ae85;
  localparam H2_CONST = 32'h3c6ef372;
  localparam H3_CONST = 32'ha54ff53a;
  localparam H4_CONST = 32'h510e527f;
  localparam H5_CONST = 32'h9b05688c;
  localparam H6_CONST = 32'h1f83d9ab;
  localparam H7_CONST = 32'h5be0cd19;

  localparam ROUNDS_NUM = 63;

  localparam STATE_IDLE        = 0;
  localparam STATE_ROUND_CYCLE = 1;
  localparam STATE_DONE        = 2;

  reg [31:0] a0_reg;
  reg [31:0] a0;
  reg [31:0] a1_reg;
  reg [31:0] a1;
  reg [31:0] a2_reg;
  reg [31:0] a2;
  reg [31:0] a3_reg;
  reg [31:0] a3;
  reg [31:0] a4_reg;
  reg [31:0] a4;
  reg [31:0] a5_reg;
  reg [31:0] a5;
  reg [31:0] a6_reg;
  reg [31:0] a6;
  reg [31:0] a7_reg;
  reg [31:0] a7;
  reg        a_save;

  reg [31:0] H0_reg;
  reg [31:0] H0;
  reg [31:0] H1_reg;
  reg [31:0] H1;
  reg [31:0] H2_reg;
  reg [31:0] H2;
  reg [31:0] H3_reg;
  reg [31:0] H3;
  reg [31:0] H4_reg;
  reg [31:0] H4;
  reg [31:0] H5_reg;
  reg [31:0] H5;
  reg [31:0] H6_reg;
  reg [31:0] H6;
  reg [31:0] H7_reg;
  reg [31:0] H7;
  reg        H_save;

  reg [5:0] t_ctr_reg;
  reg [5:0] t_ctr_new;
  reg       t_ctr_we;
  reg       t_ctr_inc;
  reg       t_ctr_rst;

  reg digest_valid_reg;
  reg digest_valid_new;
  reg digest_valid_we;

  reg [1:0] sha256_ctrl_reg;
  reg [1:0] sha256_ctrl_new;
  reg       sha256_ctrl_we;


  reg digest_init;
  reg digest_update;

  reg state_init;
  reg state_update;

  reg first_block;

  reg ready_flag;

  reg [31:0] t1;
  reg [31:0] t2;

  reg [31:0] k_data;

  reg         w_init;
  reg         w_next;
  reg  [5:0]  w_round;
  wire [31:0] w_data;

  always @* begin: round_mux
    case(t_ctr_reg)
      00: k_data = 32'h428a2f98;
      01: k_data = 32'h71374491;
      02: k_data = 32'hb5c0fbcf;
      03: k_data = 32'he9b5dba5;
      04: k_data = 32'h3956c25b;
      05: k_data = 32'h59f111f1;
      06: k_data = 32'h923f82a4;
      07: k_data = 32'hab1c5ed5;
      08: k_data = 32'hd807aa98;
      09: k_data = 32'h12835b01;
      10: k_data = 32'h243185be;
      11: k_data = 32'h550c7dc3;
      12: k_data = 32'h72be5d74;
      13: k_data = 32'h80deb1fe;
      14: k_data = 32'h9bdc06a7;
      15: k_data = 32'hc19bf174;
      16: k_data = 32'he49b69c1;
      17: k_data = 32'hefbe4786;
      18: k_data = 32'h0fc19dc6;
      19: k_data = 32'h240ca1cc;
      20: k_data = 32'h2de92c6f;
      21: k_data = 32'h4a7484aa;
      22: k_data = 32'h5cb0a9dc;
      23: k_data = 32'h76f988da;
      24: k_data = 32'h983e5152;
      25: k_data = 32'ha831c66d;
      26: k_data = 32'hb00327c8;
      27: k_data = 32'hbf597fc7;
      28: k_data = 32'hc6e00bf3;
      29: k_data = 32'hd5a79147;
      30: k_data = 32'h06ca6351;
      31: k_data = 32'h14292967;
      32: k_data = 32'h27b70a85;
      33: k_data = 32'h2e1b2138;
      34: k_data = 32'h4d2c6dfc;
      35: k_data = 32'h53380d13;
      36: k_data = 32'h650a7354;
      37: k_data = 32'h766a0abb;
      38: k_data = 32'h81c2c92e;
      39: k_data = 32'h92722c85;
      40: k_data = 32'ha2bfe8a1;
      41: k_data = 32'ha81a664b;
      42: k_data = 32'hc24b8b70;
      43: k_data = 32'hc76c51a3;
      44: k_data = 32'hd192e819;
      45: k_data = 32'hd6990624;
      46: k_data = 32'hf40e3585;
      47: k_data = 32'h106aa070;
      48: k_data = 32'h19a4c116;
      49: k_data = 32'h1e376c08;
      50: k_data = 32'h2748774c;
      51: k_data = 32'h34b0bcb5;
      52: k_data = 32'h391c0cb3;
      53: k_data = 32'h4ed8aa4a;
      54: k_data = 32'h5b9cca4f;
      55: k_data = 32'h682e6ff3;
      56: k_data = 32'h748f82ee;
      57: k_data = 32'h78a5636f;
      58: k_data = 32'h84c87814;
      59: k_data = 32'h8cc70208;
      60: k_data = 32'h90befffa;
      61: k_data = 32'ha4506ceb;
      62: k_data = 32'hbef9a3f7;
      63: k_data = 32'hc67178f2;
    endcase
  end

  sha256_w_mem w_mem_inst(
    .clk     (clk      ),
    .reset_n (reset_n  ),
    .block   (block    ),
    .round   (t_ctr_reg),
    .init    (w_init   ),
    .next    (w_next   ),
    .w       (w_data   )
  );

  assign ready = ready_flag;
  assign digest = {H0_reg, H1_reg, H2_reg, H3_reg, H4_reg, H5_reg, H6_reg, H7_reg};
  assign digest_valid = digest_valid_reg;

  always @ (posedge clk or negedge reset_n) begin: reg_update
    if (!reset_n) begin
      a0_reg <= 32'h0;
      a1_reg <= 32'h0;
      a2_reg <= 32'h0;
      a3_reg <= 32'h0;
      a4_reg <= 32'h0;
      a5_reg <= 32'h0;
      a6_reg <= 32'h0;
      a7_reg <= 32'h0;

      H0_reg <= 32'h0;
      H1_reg <= 32'h0;
      H2_reg <= 32'h0;
      H3_reg <= 32'h0;
      H4_reg <= 32'h0;
      H5_reg <= 32'h0;
      H6_reg <= 32'h0;
      H7_reg <= 32'h0;

      digest_valid_reg <= 0;
      t_ctr_reg        <= 6'h0;
      sha256_ctrl_reg  <= STATE_IDLE;
    end
    else begin
      if (a_save) begin
        a0_reg <= a0;
        a1_reg <= a1;
        a2_reg <= a2;
        a3_reg <= a3;
        a4_reg <= a4;
        a5_reg <= a5;
        a6_reg <= a6;
        a7_reg <= a7;
      end
      if (H_save) begin
        H0_reg <= H0;
        H1_reg <= H1;
        H2_reg <= H2;
        H3_reg <= H3;
        H4_reg <= H4;
        H5_reg <= H5;
        H6_reg <= H6;
        H7_reg <= H7;
      end
      if (t_ctr_we)
        t_ctr_reg <= t_ctr_new;
      if (digest_valid_we)
        digest_valid_reg <= digest_valid_new;
      if (sha256_ctrl_we)
        sha256_ctrl_reg <= sha256_ctrl_new;
    end
  end

  always @* begin: digest_logic
    H0 = 32'h0;
    H1 = 32'h0;
    H2 = 32'h0;
    H3 = 32'h0;
    H4 = 32'h0;
    H5 = 32'h0;
    H6 = 32'h0;
    H7 = 32'h0;
    H_save = 0;
    
    if (digest_init) begin
      H_save = 1;
      if (mode) begin
        H0 = H0_CONST;
        H1 = H1_CONST;
        H2 = H2_CONST;
        H3 = H3_CONST;
        H4 = H4_CONST;
        H5 = H5_CONST;
        H6 = H6_CONST;
        H7 = H7_CONST;
      end
    end
    if (digest_update) begin
      H0 = H0_reg + a0_reg;
      H1 = H1_reg + a1_reg;
      H2 = H2_reg + a2_reg;
      H3 = H3_reg + a3_reg;
      H4 = H4_reg + a4_reg;
      H5 = H5_reg + a5_reg;
      H6 = H6_reg + a6_reg;
      H7 = H7_reg + a7_reg;
      H_save = 1;
    end
  end

  always @* begin: t1_logic
    reg [31:0] sum1;
    reg [31:0] ch;

    sum1 = {a4_reg[5:0], a4_reg[31:6]} ^ {a4_reg[10:0], a4_reg[31:11]} ^ {a4_reg[24:0], a4_reg[31:25]};

    ch = (a4_reg & a5_reg) ^ ((~a4_reg) & a6_reg);

    t1 = a7_reg + sum1 + ch + w_data + k_data;
  end

  always @* begin: t2_logic
    reg [31:0] sum0;
    reg [31:0] maj;

    sum0 = {a0_reg[1:0], a0_reg[31:2]} ^ {a0_reg[12:0], a0_reg[31:13]} ^ {a0_reg[21:0], a0_reg[31:22]};
    maj = (a0_reg & a1_reg) ^ (a0_reg & a2_reg) ^ (a1_reg & a2_reg);
    t2 = sum0 + maj;
  end


  always @* begin: state_logic
    a0 = 32'h0;
    a1 = 32'h0;
    a2 = 32'h0;
    a3 = 32'h0;
    a4 = 32'h0;
    a5 = 32'h0;
    a6 = 32'h0;
    a7 = 32'h0;
    a_save = 0;

    if (state_init) begin
      a_save = 1;
      if (first_block) begin
        if (mode) begin
          a0  = H0_CONST;
          a1  = H1_CONST;
          a2  = H2_CONST;
          a3  = H3_CONST;
          a4  = H4_CONST;
          a5  = H5_CONST;
          a6  = H6_CONST;
          a7  = H7_CONST;
        end
      end
      else begin
        a0  = H0_reg;
        a1  = H1_reg;
        a2  = H2_reg;
        a3  = H3_reg;
        a4  = H4_reg;
        a5  = H5_reg;
        a6  = H6_reg;
        a7  = H7_reg;
      end
    end

    if (state_update) begin
      a0  = t1 + t2;
      a1  = a0_reg;
      a2  = a1_reg;
      a3  = a2_reg;
      a4  = a3_reg + t1;
      a5  = a4_reg;
      a6  = a5_reg;
      a7  = a6_reg;
      a_save = 1;
    end
  end

  always @* begin: t_ctr
    t_ctr_new = 0;
    t_ctr_we  = 0;

    if (t_ctr_rst) begin
        t_ctr_new = 0;
        t_ctr_we  = 1;
      end

    if (t_ctr_inc) begin
        t_ctr_new = t_ctr_reg + 1'b1;
        t_ctr_we  = 1;
      end
  end 

  always @* begin: sha256_ctrl_fsm
    digest_init      = 0;
    digest_update    = 0;
    state_init       = 0;
    state_update     = 0;
    first_block      = 0;
    ready_flag       = 0;
    w_init           = 0;
    w_next           = 0;
    t_ctr_inc        = 0;
    t_ctr_rst        = 0;
    digest_valid_new = 0;
    digest_valid_we  = 0;
    sha256_ctrl_new  = STATE_IDLE;
    sha256_ctrl_we   = 0;


    case (sha256_ctrl_reg)
      STATE_IDLE:  begin
        ready_flag = 1;

        if (init) begin
          digest_init      = 1;
          w_init           = 1;
          state_init       = 1;
          first_block      = 1;
          t_ctr_rst        = 1;
          digest_valid_new = 0;
          digest_valid_we  = 1;
          sha256_ctrl_new  = STATE_ROUND_CYCLE;
          sha256_ctrl_we   = 1;
        end
        
        if (next) begin
          t_ctr_rst        = 1;
          w_init           = 1;
          state_init       = 1;
          digest_valid_new = 0;
          digest_valid_we  = 1;
          sha256_ctrl_new  = STATE_ROUND_CYCLE;
          sha256_ctrl_we   = 1;
        end
      end


      STATE_ROUND_CYCLE: begin
        w_next       = 1;
        state_update = 1;
        t_ctr_inc    = 1;

        if (t_ctr_reg == ROUNDS_NUM) begin
          sha256_ctrl_new = STATE_DONE;
          sha256_ctrl_we  = 1;
        end
      end


      STATE_DONE: begin
        digest_update    = 1;
        digest_valid_new = 1;
        digest_valid_we  = 1;

        sha256_ctrl_new = STATE_IDLE;
        sha256_ctrl_we  = 1;
      end
    endcase
  end

endmodule