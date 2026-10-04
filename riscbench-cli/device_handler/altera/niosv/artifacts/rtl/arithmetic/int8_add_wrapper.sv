module int8_add_wrapper(
 input logic clk,reset,start, input logic[31:0] operand_a,operand_b,
 output logic busy,result_valid, output logic[31:0] result);
 logic signed[8:0] sums[0:3];
 function automatic logic[7:0] sat9(input logic signed[8:0] v);
   if(v>9'sd127) sat9=8'h7f; else if(v< -9'sd128) sat9=8'h80; else sat9=v[7:0];
 endfunction
 for(genvar i=0;i<4;i++) begin:g_add
   riscbench_int8_add u(.data0x(operand_a[8*i+:8]),.data1x(operand_b[8*i+:8]),
                         .clock(clk),.result(sums[i]));
 end
 always_ff @(posedge clk) if(reset) result_valid<=0; else result_valid<=start;
 assign busy=result_valid;
 always_comb for(integer i=0;i<4;i++) result[8*i+:8]=sat9(sums[i]);
endmodule
