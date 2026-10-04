module int8_mul_wrapper(
 input logic clk,reset,start, input logic[31:0] operand_a,operand_b,
 output logic busy,result_valid, output logic[31:0] result);
 logic signed[15:0] p0,p1,p2,p3;
 function automatic logic[7:0] sat16(input logic signed[15:0] v);
   if(v>16'sd127) sat16=8'h7f; else if(v< -16'sd128) sat16=8'h80; else sat16=v[7:0];
 endfunction
 int8_mul_wide_wrapper u(.clk,.reset,.start,.packed_a(operand_a),.packed_b(operand_b),
   .busy,.result_valid,.product0(p0),.product1(p1),.product2(p2),.product3(p3));
 assign result={sat16(p3),sat16(p2),sat16(p1),sat16(p0)};
endmodule
