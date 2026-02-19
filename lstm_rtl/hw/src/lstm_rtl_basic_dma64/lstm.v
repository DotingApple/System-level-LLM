//////////////////////////////////////////////////////////////////////////////
// Author: Aishwarya Rajen
//////////////////////////////////////////////////////////////////////////////

//`define SIMULATION_MEMORY
`define ARRAY_DEPTH 64      //Number of Hidden neurons
`define INPUT_DEPTH 100	    //LSTM input vector dimensions
`define DATA_WIDTH 16		//16 bit representation
`define INWEIGHT_DEPTH 6400 //100x64
`define HWEIGHT_DEPTH 4096  //64x64
`define varraysize 1600   //100x16
`define uarraysize 1024  //64x16

/////////////////////////////////////////////////////////////////////////////////
//LSTM layer design
/////////////////////////////////////////////////////////////////////////////////
//
//This verilog implementation can be used for LSTM inference applications.
//LSTM contains four gates :Input,Output,Forget and Cell State.
//The architecture is such that the four gates can be parallelized for the 
//most part except for the ending few stages were previous cycle output is 
//required. The weights of the gates (obtained from training using Python or
//other sources) is stored and accessed through BRAMs on the FPGA.
//Fixed Point 16 (4.12) format is used
//This is a pipelined LSTM network design with the following blocks:
//1.MVM - Matrix vector multiplication Block
//	Every cycle one row of the matrix gets multiplied with the vector producing 
//	one 16 bit output which can get processed by further stages.
//2.ELEMENT WISE ADD 
//	16 bit addition
//3.SIGMOID
//	LUT based Sigmoid approximation
//4.ELEMENT WISE MULTIPLICATION
//	2s complement based signed multiplication
//5.TANH
//	LUT based tanH approximation
//
//////////////////////////////////////////////////////////////////////////////////



module lstm(
input clk,
input reset,
input start,  		   //start the computation
input [6:0] start_addr,   //start address of the Xin bram (input words to LSTM)
input [6:0] end_addr,	  //end address of the Xin bram 
input wren_a_u,
input wren_a_w,	//write enable for the hidden weights U and input weights W
input wren_a_b,	//write enable for the bias weights B
input wren_a_x,	//write enable for all the weights
input [`uarraysize-1:0] wdata_u,
input [`varraysize-1:0] wdata_v,
input [`DATA_WIDTH-1:0] wdata_b,
input [`varraysize-1:0] wdata_x,
input              load_mode,   
input  [6:0]       load_addr,
output ht_valid,	//indicates the output ht_out is valid in those cycles
output [`DATA_WIDTH-1:0] ht_out, //output ht from the lstm
output reg cycle_complete,	//generates a pulse when a cycle fo 64 ht outputs are complete
output reg Done        //Stays high indicating the end of lstm output computation for all the Xin words provided.
);

wire [`uarraysize-1:0] Ui_in;
wire [`varraysize-1:0] Wi_in;
wire [`uarraysize-1:0] Uf_in;
wire [`varraysize-1:0] Wf_in;
wire [`uarraysize-1:0] Uo_in;
wire [`varraysize-1:0] Wo_in;
wire [`uarraysize-1:0] Uc_in;
wire [`varraysize-1:0] Wc_in;
wire [`varraysize-1:0] x_in;
reg [`uarraysize-1:0] h_in;


//reg [`uarraysize-1:0] dummyin_u;
//reg [`varraysize-1:0] dummyin_v;
//reg [`DATA_WIDTH-1:0] dummyin_b;

wire [`DATA_WIDTH-1:0] bi_in;
wire [`DATA_WIDTH-1:0] bf_in;
wire [`DATA_WIDTH-1:0] bo_in;
wire [`DATA_WIDTH-1:0] bc_in;
reg [`DATA_WIDTH-1:0] C_in;
//wire [`varraysize-1:0] xdata_b_ext;
//wire [`uarraysize-1:0] hdata_b_ext;

//keeping an additional bit so that the counters don't get reset to 0 automatically after 63 
//and start repeating access to elements prematurely
reg [6:0] inaddr; 
reg [6:0] waddr;
//reg wren_a;
reg [6:0] c_count;
reg [6:0] b_count;
reg [6:0] ct_count;
reg [6:0] count;
reg [6:0] i,j;
reg [5:0] h_count;

wire [`DATA_WIDTH-1:0] ht;
reg [`uarraysize-1:0] ht_prev;
reg [`uarraysize-1:0] Ct;
wire [`DATA_WIDTH-1:0] add_cf;
//reg wren_a_ct, wren_b_cin;

assign ht_out = ht;


//indicates that the ht_out output is valid 
assign ht_valid = (count>16)? 1'b1: 1'b0;


//BRAMs storing the input and hidden weights of each of the gates
//Hidden weights are represented by U and Input weights by W
spram_u Ui_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr ),.wren_a(wren_a_u),.data_a(wdata_u),.out_a(Ui_in));
spram_u Uf_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr ),.wren_a(wren_a_u),.data_a(wdata_u),.out_a(Uf_in));
spram_u Uo_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr ),.wren_a(wren_a_u),.data_a(wdata_u),.out_a(Uo_in));
spram_u Uc_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr ),.wren_a(wren_a_u),.data_a(wdata_u),.out_a(Uc_in));
spram_v Wi_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr ),.wren_a(wren_a_w),.data_a(wdata_v),.out_a(Wi_in));
spram_v Wf_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr ),.wren_a(wren_a_w),.data_a(wdata_v),.out_a(Wf_in));
spram_v Wo_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr ),.wren_a(wren_a_w),.data_a(wdata_v),.out_a(Wo_in));
spram_v Wc_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr ),.wren_a(wren_a_w),.data_a(wdata_v),.out_a(Wc_in));

//BRAM of the input vectors to LSTM
spram_v Xi_mem(.clk(clk),.address_a(load_mode ? load_addr : inaddr ),.wren_a(wren_a_x),.data_a(wdata_x),.out_a(x_in));

//BRAM storing Bias of each gate
spram_b bi_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr),.wren_a(wren_a_b),.data_a(wdata_b),.out_a(bi_in));
spram_b bf_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr),.wren_a(wren_a_b),.data_a(wdata_b),.out_a(bf_in));
spram_b bo_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr),.wren_a(wren_a_b),.data_a(wdata_b),.out_a(bo_in));
spram_b bc_mem(.clk(clk),.address_a(load_mode ? load_addr : waddr),.wren_a(wren_a_b),.data_a(wdata_b),.out_a(bc_in));



lstm_top lstm(.clk(clk),.rst(reset),.ht_out(ht),.Ui_in(Ui_in),.Wi_in(Wi_in),.Uf_in(Uf_in),.Wf_in(Wf_in),.Uo_in(Uo_in),.Wo_in(Wo_in),
.Uc_in(Uc_in),.Wc_in(Wc_in),.x_in(x_in),.h_in(h_in),.C_in(C_in),.bi_in(bi_in),.bf_in(bf_in),.bo_in(bo_in),.bc_in(bc_in),.add_cf(add_cf));

always @(posedge clk) begin
 if(reset == 1'b1 || start==1'b0) 
  begin      
	   count <= 0;
	   b_count <=0;
	   h_count <= 0;
	   c_count <= 0;
	   ct_count <=0;
	   Ct <= 0;
	   C_in <=0;
	   h_in <= 0;
	   ht_prev <= 0;
	   //wren_a <= 0;
	   //wren_a_ct <= 1;
	   //wren_b_cin <= 0;
	   cycle_complete <=0;
	   Done <= 0;
   	   waddr <=0;	
	   inaddr <= start_addr;
	  
	   //dummy ports initialize
	   //dummyin_u <= 0; 
	   //dummyin_v <=0;
	   //dummyin_b <= 0;
 
  end
  else begin
	
	if(h_count == `ARRAY_DEPTH-1) begin
		cycle_complete <= 1; 
		waddr <= 0;
		count <=0;
		b_count <= 0;
		ct_count <=0;
		c_count <= 0;
	
		if(inaddr == end_addr)
			Done <= 1;			
		else begin
			inaddr <= inaddr+1'b1;
			h_count <= 0;

		 end
	 end
	 else begin
		cycle_complete <= 0;
		if (waddr < 63) begin
			waddr <= waddr + 1'b1;
		end else begin
			waddr <= 0;
		end
    	// waddr <= waddr+1'b1;
	  	count <= count+1'b1;
	 
		if(count>7)     //delay before bias add
			b_count <= b_count+1'b1; 

		if(count >8)  begin //delay before Cin elmul
			c_count <=c_count+1'b1;
			case(c_count)
			0: C_in<=Ct[16*0+:16] ;
			1: C_in<=Ct[16*1+:16] ;
			2: C_in<=Ct[16*2+:16] ;
			3: C_in<=Ct[16*3+:16] ;
			4: C_in<=Ct[16*4+:16] ;
			5: C_in<=Ct[16*5+:16] ;
			6: C_in<=Ct[16*6+:16] ;
			7: C_in<=Ct[16*7+:16] ;
			8: C_in<=Ct[16*8+:16] ;
			9: C_in<=Ct[16*9+:16] ;
			10: C_in <=Ct[16*10+:16];
			11: C_in <=Ct[16*11+:16];
			12: C_in <=Ct[16*12+:16];
			13: C_in <=Ct[16*13+:16];
			14: C_in <=Ct[16*14+:16];
			15: C_in <=Ct[16*15+:16];
			16: C_in <=Ct[16*16+:16];
			17: C_in <=Ct[16*17+:16];
			18: C_in <=Ct[16*18+:16];
			19: C_in <=Ct[16*19+:16];
			20: C_in <=Ct[16*20+:16];
			21: C_in <=Ct[16*21+:16];
			22: C_in <=Ct[16*22+:16];
			23: C_in <=Ct[16*23+:16];
			24: C_in <=Ct[16*24+:16];
			25: C_in <=Ct[16*25+:16];
			26: C_in <=Ct[16*26+:16];
			27: C_in <=Ct[16*27+:16];
			28: C_in <=Ct[16*28+:16];
			29: C_in <=Ct[16*29+:16];
			30: C_in <=Ct[16*30+:16];
			31: C_in <=Ct[16*31+:16];
			32: C_in <=Ct[16*32+:16];
			33: C_in <=Ct[16*33+:16];
			34: C_in <=Ct[16*34+:16];
			35: C_in <=Ct[16*35+:16];
			36: C_in <=Ct[16*36+:16];
			37: C_in <=Ct[16*37+:16];
			38: C_in <=Ct[16*38+:16];
			39: C_in <=Ct[16*39+:16];
			40: C_in <=Ct[16*40+:16];
			41: C_in <=Ct[16*41+:16];
			42: C_in <=Ct[16*42+:16];
			43: C_in <=Ct[16*43+:16];
			44: C_in <=Ct[16*44+:16];
			45: C_in <=Ct[16*45+:16];
			46: C_in <=Ct[16*46+:16];
			47: C_in <=Ct[16*47+:16];
			48: C_in <=Ct[16*48+:16];
			49: C_in <=Ct[16*49+:16];
			50: C_in <=Ct[16*50+:16];
			51: C_in <=Ct[16*51+:16];
			52: C_in <=Ct[16*52+:16];
			53: C_in <=Ct[16*53+:16];
			54: C_in <=Ct[16*54+:16];
			55: C_in <=Ct[16*55+:16];
			56: C_in <=Ct[16*56+:16];
			57: C_in <=Ct[16*57+:16];
			58: C_in <=Ct[16*58+:16];
			59: C_in <=Ct[16*59+:16];
			60: C_in <=Ct[16*60+:16];
			61: C_in <=Ct[16*61+:16];
			62: C_in <=Ct[16*62+:16];
			63: C_in <=Ct[16*63+:16];
			default : C_in <= 0;
		endcase	
		end

		if(count >11) begin  //for storing output of Ct
			ct_count <= ct_count+1'b1;
		 //storing cell state
			case(ct_count)
			0:	Ct[16*0+:16] <= add_cf;
			1:	Ct[16*1+:16] <= add_cf;
			2:	Ct[16*2+:16] <= add_cf;
			3:	Ct[16*3+:16] <= add_cf;
			4:	Ct[16*4+:16] <= add_cf;
			5:	Ct[16*5+:16] <= add_cf;
			6:	Ct[16*6+:16] <= add_cf;
			7:	Ct[16*7+:16] <= add_cf;
			8:	Ct[16*8+:16] <= add_cf;
			9:	Ct[16*9+:16] <= add_cf;
			10:	Ct[16*10+:16] <=add_cf;
			11:	Ct[16*11+:16] <=add_cf;
			12:	Ct[16*12+:16] <=add_cf;
			13:	Ct[16*13+:16] <=add_cf;
			14:	Ct[16*14+:16] <=add_cf;
			15:	Ct[16*15+:16] <=add_cf;
			16:	Ct[16*16+:16] <=add_cf;
			17:	Ct[16*17+:16] <=add_cf;
			18:	Ct[16*18+:16] <=add_cf;
			19:	Ct[16*19+:16] <=add_cf;
			20:	Ct[16*20+:16] <=add_cf;
			21:	Ct[16*21+:16] <=add_cf;
			22:	Ct[16*22+:16] <=add_cf;
			23:	Ct[16*23+:16] <=add_cf;
			24:	Ct[16*24+:16] <=add_cf;
			25:	Ct[16*25+:16] <=add_cf;
			26:	Ct[16*26+:16] <=add_cf;
			27:	Ct[16*27+:16] <=add_cf;
			28:	Ct[16*28+:16] <=add_cf;
			29:	Ct[16*29+:16] <=add_cf;
			30:	Ct[16*30+:16] <=add_cf;
			31:	Ct[16*31+:16] <=add_cf;
			32:	Ct[16*32+:16] <=add_cf;
			33:	Ct[16*33+:16] <=add_cf;
			34:	Ct[16*34+:16] <=add_cf;
			35:	Ct[16*35+:16] <=add_cf;
			36:	Ct[16*36+:16] <=add_cf;
			37:	Ct[16*37+:16] <=add_cf;
			38:	Ct[16*38+:16] <=add_cf;
			39:	Ct[16*39+:16] <=add_cf;
			40:	Ct[16*40+:16] <=add_cf;
			41:	Ct[16*41+:16] <=add_cf;
			42:	Ct[16*42+:16] <=add_cf;
			43:	Ct[16*43+:16] <=add_cf;
			44:	Ct[16*44+:16] <=add_cf;
			45:	Ct[16*45+:16] <=add_cf;
			46:	Ct[16*46+:16] <=add_cf;
			47:	Ct[16*47+:16] <=add_cf;
			48:	Ct[16*48+:16] <=add_cf;
			49:	Ct[16*49+:16] <=add_cf;
			50:	Ct[16*50+:16] <=add_cf;
			51:	Ct[16*51+:16] <=add_cf;
			52:	Ct[16*52+:16] <=add_cf;
			53:	Ct[16*53+:16] <=add_cf;
			54:	Ct[16*54+:16] <=add_cf;
			55:	Ct[16*55+:16] <=add_cf;
			56:	Ct[16*56+:16] <=add_cf;
			57:	Ct[16*57+:16] <=add_cf;
			58:	Ct[16*58+:16] <=add_cf;
			59:	Ct[16*59+:16] <=add_cf;
			60:	Ct[16*60+:16] <=add_cf;
			61:	Ct[16*61+:16] <=add_cf;
			62:	Ct[16*62+:16] <=add_cf;
			63:	Ct[16*63+:16] <=add_cf;
			default : Ct <= 0;
		 endcase
		end
		if(count >16) begin
			h_count <= h_count + 1'b1;
			case(h_count)
			0:	ht_prev[16*0+:16] <= ht;
			1:	ht_prev[16*1+:16] <= ht;
			2:	ht_prev[16*2+:16] <= ht;
			3:	ht_prev[16*3+:16] <= ht;
			4:	ht_prev[16*4+:16] <= ht;
			5:	ht_prev[16*5+:16] <= ht;
			6:	ht_prev[16*6+:16] <= ht;
			7:	ht_prev[16*7+:16] <= ht;
			8:	ht_prev[16*8+:16] <= ht;
			9:	ht_prev[16*9+:16] <= ht;
			10:	ht_prev[16*10+:16] <= ht;
			11:	ht_prev[16*11+:16] <= ht;
			12:	ht_prev[16*12+:16] <= ht;
			13:	ht_prev[16*13+:16] <= ht;
			14:	ht_prev[16*14+:16] <= ht;
			15:	ht_prev[16*15+:16] <= ht;
			16:	ht_prev[16*16+:16] <= ht;
			17:	ht_prev[16*17+:16] <= ht;
			18:	ht_prev[16*18+:16] <= ht;
			19:	ht_prev[16*19+:16] <= ht;
			20:	ht_prev[16*20+:16] <= ht;
			21:	ht_prev[16*21+:16] <= ht;
			22:	ht_prev[16*22+:16] <= ht;
			23:	ht_prev[16*23+:16] <= ht;
			24:	ht_prev[16*24+:16] <= ht;
			25:	ht_prev[16*25+:16] <= ht;
			26:	ht_prev[16*26+:16] <= ht;
			27:	ht_prev[16*27+:16] <= ht;
			28:	ht_prev[16*28+:16] <= ht;
			29:	ht_prev[16*29+:16] <= ht;
			30:	ht_prev[16*30+:16] <= ht;
			31:	ht_prev[16*31+:16] <= ht;
			32:	ht_prev[16*32+:16] <= ht;
			33:	ht_prev[16*33+:16] <= ht;
			34:	ht_prev[16*34+:16] <= ht;
			35:	ht_prev[16*35+:16] <= ht;
			36:	ht_prev[16*36+:16] <= ht;
			37:	ht_prev[16*37+:16] <= ht;
			38:	ht_prev[16*38+:16] <= ht;
			39:	ht_prev[16*39+:16] <= ht;
			40:	ht_prev[16*40+:16] <= ht;
			41:	ht_prev[16*41+:16] <= ht;
			42:	ht_prev[16*42+:16] <= ht;
			43:	ht_prev[16*43+:16] <= ht;
			44:	ht_prev[16*44+:16] <= ht;
			45:	ht_prev[16*45+:16] <= ht;
			46:	ht_prev[16*46+:16] <= ht;
			47:	ht_prev[16*47+:16] <= ht;
			48:	ht_prev[16*48+:16] <= ht;
			49:	ht_prev[16*49+:16] <= ht;
			50:	ht_prev[16*50+:16] <= ht;
			51:	ht_prev[16*51+:16] <= ht;
			52:	ht_prev[16*52+:16] <= ht;
			53:	ht_prev[16*53+:16] <= ht;
			54:	ht_prev[16*54+:16] <= ht;
			55:	ht_prev[16*55+:16] <= ht;
			56:	ht_prev[16*56+:16] <= ht;
			57:	ht_prev[16*57+:16] <= ht;
			58:	ht_prev[16*58+:16] <= ht;
			59:	ht_prev[16*59+:16] <= ht;
			60:	ht_prev[16*60+:16] <= ht;
			61:	ht_prev[16*61+:16] <= ht;
			62:	ht_prev[16*62+:16] <= ht;
			63:	ht_prev[16*63+:16] <= ht;
			default: ht_prev <= 0;
			endcase
		 end
			
	end
		


	if(cycle_complete==1) begin
		  h_in <= ht_prev; 
	end

  end
 end
 


endmodule



