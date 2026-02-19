module conv_new(clk, reset, ready, busy, iaddr, idata, crd, cdata_rd, caddr_rd, cwr, cdata_wr, caddr_wr, csel);
	input clk;
	input reset;
	output reg [11:0] iaddr;
	input [19:0] idata;
	input ready;
	output reg busy;
	output reg [2:0] csel;
	output reg crd;
	input [19:0] cdata_rd;
	output reg [11:0] caddr_rd;
	output reg cwr;
	output reg [19:0] cdata_wr;
	output reg [11:0] caddr_wr;
	reg signed [35:0] data_lu, data_cu, data_ru, data_lc, data_cc, data_rc, data_dl, data_dc, data_dr;
	reg signed [35:0] data_total, temp, temp2;
	reg signed [19:0] data [0:4095];
	reg signed [19:0] data_4096 [0:4095];
	reg signed [19:0] data_1024 [0:1023];
	reg [6:0] x,y;
	reg kernel_choose, done, second_round;
	wire signed [19:0] kernel0 [0:8];
	wire signed [19:0] kernel1 [0:8];
	wire signed [19:0] kernel [0:8];
	wire signed [19:0] bias1, bias2, bias;
	
	assign kernel0[0] = 20'h0A89E;
	assign kernel0[1] = 20'h092D5;
	assign kernel0[2] = 20'h06D43;
	assign kernel0[3] = 20'h01004;
	assign kernel0[4] = 20'hF8F71;
	assign kernel0[5] = 20'hF6E54;
	assign kernel0[6] = 20'hFA6D7;
	assign kernel0[7] = 20'hFC834;
	assign kernel0[8] = 20'hFAC19;
	assign kernel1[0] = 20'hFDB55;
	assign kernel1[1] = 20'h02992;
	assign kernel1[2] = 20'hFC994;
	assign kernel1[3] = 20'h050FD;
	assign kernel1[4] = 20'h02F20;
	assign kernel1[5] = 20'h0202D;
	assign kernel1[6] = 20'h03BD7;
	assign kernel1[7] = 20'hFD369;
	assign kernel1[8] = 20'h05E68;
	assign kernel[0] = kernel_choose == 0 ? kernel0[0] : kernel1[0];
	assign kernel[1] = kernel_choose == 0 ? kernel0[1] : kernel1[1];
	assign kernel[2] = kernel_choose == 0 ? kernel0[2] : kernel1[2];
	assign kernel[3] = kernel_choose == 0 ? kernel0[3] : kernel1[3];
	assign kernel[4] = kernel_choose == 0 ? kernel0[4] : kernel1[4];
	assign kernel[5] = kernel_choose == 0 ? kernel0[5] : kernel1[5];
	assign kernel[6] = kernel_choose == 0 ? kernel0[6] : kernel1[6];
	assign kernel[7] = kernel_choose == 0 ? kernel0[7] : kernel1[7];
	assign kernel[8] = kernel_choose == 0 ? kernel0[8] : kernel1[8];
	assign bias = (kernel_choose == 0) ? bias1 : bias2;
	assign bias1 = 20'h01310;
	assign bias2 = 20'hF7295;
	reg [3:0] state;
	reg [3:0] nextState;
	reg [15:0] addr_local;
	reg store_conv, store_flatten, conving, maxpooling, start_conv;
	parameter NOWORK = 0;
	parameter GETDATA = 1;
	parameter ZEROPADDING = 2;
	parameter CONV = 3;
	parameter RELU = 4;
	parameter MAXPOOL = 5;
	parameter FLATTEN = 6;
	parameter STOREDATA = 7;
	parameter FINISH = 8;
	parameter kernel0_conv = 1;
	parameter kernel1_conv = 2;
	parameter kernel0_conv_maxpool = 3;
	parameter kernel1_conv_maxpool = 4;
	parameter flatten = 5;
	
	parameter c_data = 64;
	parameter m_data = 32;
	
	always@(ready or reset or done)begin
		if(reset) begin
			busy = 0;
		end
		else if(ready) begin

			busy = 1;
		end
		else if(done) begin
			busy = 0;
		end
		
	end
	always@(busy or iaddr or x or y or caddr_wr)begin
		
		if(reset)begin
		    nextState <= NOWORK;
			kernel_choose = 0;
			conving = 0;
			maxpooling = 0;
			done = 0;
			second_round = 0;
			store_flatten = 0;
		end
		case(state)
			NOWORK: begin
				if(busy == 1)
					nextState = GETDATA;
			end
			GETDATA: begin
				if(second_round == 1)
					kernel_choose = 1;
				conving = 1;
				maxpooling = 0;
				if(iaddr == 4095)begin
					nextState = CONV;
				end
			end
			CONV: begin
				maxpooling = 0;
				conving = 1;
				if(x == 63 && y == 63)begin 
					nextState = RELU;
					
				end
			end
			RELU: begin
				if(x == 63 && y == 63)
					nextState = STOREDATA;
			end
			MAXPOOL: begin
				maxpooling = 1;
				conving = 0;
				if((x >> 1)== 31 && (y >> 1) == 31)begin
					nextState = STOREDATA;
					
				end
			end
			STOREDATA:begin
				if(conving && caddr_wr == 4095)begin
					nextState = MAXPOOL;
					conving = 0;
				end
				if(maxpooling)begin
					if(caddr_wr == 1023)begin
						if(store_flatten == 0)
							store_flatten = 1;
					end
					else if(caddr_wr == 2047 || caddr_wr == 2046)begin
						if(kernel_choose == 0)begin
							nextState = GETDATA;
							second_round = 1;
							store_flatten = 0;
						end
						else if(kernel_choose == 1) begin
							nextState = FINISH;
						end
					end
				end
					
			end
			FINISH:begin
				done = 1;
			end
			
		endcase
	end
	always@(posedge clk)begin
		if(reset)begin
			state <= 0;
		end
		else begin
			state <= nextState;
		end
	end
	always@(posedge clk)begin
		crd = 0;
		cwr = 0;
		if(reset)begin
			x <= 0;
			y <= 0;
			addr_local <= 0;
			iaddr <= x + y * 64;
		end
		case(state)
			GETDATA:begin
				crd = 1;
				iaddr <= x + y * 64;
				data[iaddr] <= idata;
				if(iaddr == 4095)begin
					x <= 0;
					y <= 0;
				end
				else if(x < 63)begin
					x <= x + 1;
				end
				else if(y < 63)begin
					x <= 0;
					y <= y + 1;
				end
				else begin
					x <= 0;
					y <= 0;
				end
			end
			CONV:begin
				
				if(x == 0 || y == 0)
					data_lu = 0;
				else begin
					data_lu = data[x - 1 + (y - 1) * 64] * kernel[0];
				end
				if(y == 0)
					data_cu = 0;
				else
					data_cu = data[x + (y - 1) * 64] * kernel[1];
				if(x == 63 || y == 0)
					data_ru = 0;
				else
					data_ru = data[(x + 1) + (y - 1) * 64] * kernel[2];
				if(x == 0)
					data_lc = 0;
				else
					data_lc = data[x - 1 + y * 64] * kernel[3];
				data_cc = data[x + y * 64] * kernel[4];
				if(x == 63)
					data_rc = 0;
				else
					data_rc = data[(x + 1)+ y * 64] * kernel[5];
				if(x == 0 || y == 63)
					data_dl = 0;
				else
					data_dl = data[x - 1+ (y + 1) * 64] * kernel[6];
				if(y == 63)
					data_dc = 0;
				else
					data_dc = data[x + (y + 1) * 64] * kernel[7];
				if(x == 63 || y == 63)
					data_dr = 0;
				else
					data_dr = data[x + 1+ (y + 1) * 64] * kernel[8];
				//data_total = {{11{data_lu[35]}},data_lu[35:16]} + {{11{data_cu[35]}},data_cu[35:16]} + {{11{data_ru[35]}},data_ru[35:16]} + {{11{data_lc[35]}},data_lc[35:16]} + {{11{data_cc[35]}},data_cc[35:16]} + {{11{data_rc[35]}},data_rc[35:16]} + {{11{data_dl[35]}},data_dl[35:16]} + {{11{data_dc[35]}},data_dc[35:16]} + {{11{data_dr[35]}},data_dr[35:16]};
				data_total = data_lu + data_cu + data_ru + data_lc + data_cc + data_rc + data_dl + data_dc + data_dr;

				data_4096[x + y * 64] <= data_total[35:16] + bias + data_total[15];
				if (x < 63)begin
					x <= x + 1;
				end
				else if(y < 63)begin
					x <= 0;
					y <= y + 1;
				end
				else begin
					y <= 0;
					x <= 0;
				end
				
				
 			end
			RELU:begin
				data_4096[addr_local] <= (data_4096[addr_local][19] == 0) ? data_4096[addr_local] : 0;
				addr_local <= x + (y * 64);
				if (x < 63)begin
					x <= x + 1;
				end
				else if(y < 63)begin
					x <= 0;
					y <= y + 1;
				end
				else begin
					y <= 0;
					x <= 0;
				end
			end
			MAXPOOL:begin
				temp = data_4096[x + 64 * y] > data_4096[x + 1 + y * 64] ? data_4096[x + 64 * y] : data_4096[x + 1 + y * 64];
				temp2 = data_4096[x + 64 * (y + 1)] > data_4096[x + 1 + (y + 1) * 64] ? data_4096[x + 64 * (y + 1)] : data_4096[x + 1 + (y + 1) * 64];
				data_total = temp > temp2 ? temp : temp2;
				data_1024[(x >> 1) + (y >> 1) * 32] <= data_total;
				if((x >> 1) < 31)begin
					x <= x + 2;
				end
				else begin
					x <= 0;
					y <= y + 2;
				end
				if((x >> 1) == 31 && (y >> 1) == 31)begin
					x <= 0;
					y <= 0;
				end
			end
			STOREDATA:begin
				cwr = 1;
				if (store_flatten == 1)begin
					csel = 5;
					caddr_wr <= (x + y * 32) * 2 + kernel_choose;
					cdata_wr <= data_1024[x + y * 32];
					if(caddr_wr >= 2046)begin
						x <= 0;
						y <= 0;
					end
					if(x < 31)begin
						x <= x + 1;
					end
					else if(y < 31)begin
						x <= 0;
						y <= y + 1;
					end
					else begin
						x <= 0;
						y <= 0;
					end
						
				end
				else if(conving == 1)begin
					if(kernel_choose == 0)
						csel = 1;
					else 
						csel = 2;
					caddr_wr <= x + y * 64;
					cdata_wr <= data_4096[x + y * 64];
					if(caddr_wr == 4095)begin
						x <= 0;
						y <= 0;
					end
					else if(x < 63)begin
						x <= x + 1;
					end
					else if(y < 63)begin
						x <= 0;
						y <= y + 1;
					end
					else begin
						x <= 0;
						y <= 0;
					end
					
				end
				else if(maxpooling == 1)begin
					if(kernel_choose == 0)
						csel = 3;
					else 
						csel = 4;
					
					caddr_wr <= x + y * 32;
					cdata_wr <= data_1024[x + y * 32];
					if(caddr_wr == 1023)begin
						x <= 0;
						y <= 0;
					end
					if(x < 31)begin
						x <= x + 1;
					end
					else if(y < 31)begin
						x <= 0;
						y <= y + 1;
					end
					else begin
						x <= 0;
						y <= 0;
					end
				end
			end
		endcase
	end
	
	
	
endmodule