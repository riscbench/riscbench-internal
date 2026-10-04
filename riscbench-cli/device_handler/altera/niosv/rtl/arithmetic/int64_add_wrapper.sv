module int64_add_wrapper (
    input logic clk, reset, start,
    input logic signed [63:0] operand_a, operand_b,
    output logic busy, result_valid,
    output logic signed [64:0] result
);
    riscbench_int64_add add_ip(.data0x(operand_a), .data1x(operand_b),
                               .clock(clk), .result(result));
    always_ff @(posedge clk) begin
        if (reset) result_valid <= 1'b0;
        else result_valid <= start;
    end
    assign busy=result_valid;
endmodule
