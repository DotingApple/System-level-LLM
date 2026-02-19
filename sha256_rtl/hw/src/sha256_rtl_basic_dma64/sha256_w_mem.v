module sha256_w_mem(
  input wire         clk,
  input wire         reset_n,
  input wire [511:0] block,
  input wire [5:0]   round,
  input wire         init,
  input wire         next,
  
  output wire [31:0] w
);

  reg [31:0] w_mem_reg [0:15];
  reg [31:0] w_mem00;
  reg [31:0] w_mem01;
  reg [31:0] w_mem02;
  reg [31:0] w_mem03;
  reg [31:0] w_mem04;
  reg [31:0] w_mem05;
  reg [31:0] w_mem06;
  reg [31:0] w_mem07;
  reg [31:0] w_mem08;
  reg [31:0] w_mem09;
  reg [31:0] w_mem10;
  reg [31:0] w_mem11;
  reg [31:0] w_mem12;
  reg [31:0] w_mem13;
  reg [31:0] w_mem14;
  reg [31:0] w_mem15;
  reg        w_mem_save;

  reg [31:0] w_tmp;
  reg [31:0] w_new;

  reg [31:0] w_0;
  reg [31:0] w_1;
  reg [31:0] w_9;
  reg [31:0] w_14;
  reg [31:0] d0;
  reg [31:0] d1;

  assign w = w_tmp;

  always @ (posedge clk or negedge reset_n) begin: reg_update
    integer i;

    if (!reset_n) begin
      for (i = 0 ; i < 16 ; i = i + 1) begin
        w_mem_reg[i] <= 32'h0;
	    end
    end
    else begin
      if (w_mem_save) begin
        w_mem_reg[00] <= w_mem00;
        w_mem_reg[01] <= w_mem01;
        w_mem_reg[02] <= w_mem02;
        w_mem_reg[03] <= w_mem03;
        w_mem_reg[04] <= w_mem04;
        w_mem_reg[05] <= w_mem05;
        w_mem_reg[06] <= w_mem06;
        w_mem_reg[07] <= w_mem07;
        w_mem_reg[08] <= w_mem08;
        w_mem_reg[09] <= w_mem09;
        w_mem_reg[10] <= w_mem10;
        w_mem_reg[11] <= w_mem11;
        w_mem_reg[12] <= w_mem12;
        w_mem_reg[13] <= w_mem13;
        w_mem_reg[14] <= w_mem14;
        w_mem_reg[15] <= w_mem15;
      end
    end
  end

  always @* begin: select_w
    if (round < 16)
      w_tmp = w_mem_reg[round[3:0]];
    else
      w_tmp = w_new;
  end


  always @* begin: w_mem_update_logic
    w_mem00 = 32'h0;
    w_mem01 = 32'h0;
    w_mem02 = 32'h0;
    w_mem03 = 32'h0;
    w_mem04 = 32'h0;
    w_mem05 = 32'h0;
    w_mem06 = 32'h0;
    w_mem07 = 32'h0;
    w_mem08 = 32'h0;
    w_mem09 = 32'h0;
    w_mem10 = 32'h0;
    w_mem11 = 32'h0;
    w_mem12 = 32'h0;
    w_mem13 = 32'h0;
    w_mem14 = 32'h0;
    w_mem15 = 32'h0;
    
    w_mem_save = 0;

    w_0  = w_mem_reg[0];
    w_1  = w_mem_reg[1];
    w_9  = w_mem_reg[9];
    w_14 = w_mem_reg[14];

    d0 = {w_1[6:0], w_1[31:7]} ^ {w_1[17:0], w_1[31:18]} ^ {3'b000, w_1[31:3]};

    d1 = {w_14[16:0], w_14[31:17]} ^ {w_14[18:0], w_14[31:19]} ^ {10'b0000000000, w_14[31:10]};

    w_new = d1 + w_9 + d0 + w_0;

    if (init) begin
      w_mem00 = block[511:480];
      w_mem01 = block[479:448];
      w_mem02 = block[447:416];
      w_mem03 = block[415:384];
      w_mem04 = block[383:352];
      w_mem05 = block[351:320];
      w_mem06 = block[319:288];
      w_mem07 = block[287:256];
      w_mem08 = block[255:224];
      w_mem09 = block[223:192];
      w_mem10 = block[191:160];
      w_mem11 = block[159:128];
      w_mem12 = block[127: 96];
      w_mem13 = block[95 : 64];
      w_mem14 = block[63 : 32];
      w_mem15 = block[31 :  0];
      
      w_mem_save = 1;
    end

    if (next && (round > 15)) begin
      w_mem00 = w_mem_reg[01];
      w_mem01 = w_mem_reg[02];
      w_mem02 = w_mem_reg[03];
      w_mem03 = w_mem_reg[04];
      w_mem04 = w_mem_reg[05];
      w_mem05 = w_mem_reg[06];
      w_mem06 = w_mem_reg[07];
      w_mem07 = w_mem_reg[08];
      w_mem08 = w_mem_reg[09];
      w_mem09 = w_mem_reg[10];
      w_mem10 = w_mem_reg[11];
      w_mem11 = w_mem_reg[12];
      w_mem12 = w_mem_reg[13];
      w_mem13 = w_mem_reg[14];
      w_mem14 = w_mem_reg[15];
      w_mem15 = w_new;
      
      w_mem_save = 1;
    end
  end
endmodule