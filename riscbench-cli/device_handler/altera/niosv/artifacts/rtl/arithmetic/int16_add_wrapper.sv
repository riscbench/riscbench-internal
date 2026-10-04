module int16_add_wrapper (
    input  logic        clk,
    input  logic        reset,
    input  logic        start,
    input  logic [31:0] operand_a,
    input  logic [31:0] operand_b,
    output logic        busy,
    output logic        result_valid,
    output logic [31:0] result
);
    logic [16:0] lane0_sum, lane1_sum;

    function automatic logic [15:0] saturate17(input logic signed [16:0] value);
        begin
            if (value > 17'sd32767)       saturate17 = 16'h7fff;
            else if (value < -17'sd32768) saturate17 = 16'h8000;
            else                          saturate17 = value[15:0];
        end
    endfunction

    riscbench_int16_add lane0_add (
        .data0x(operand_a[15:0]), .data1x(operand_b[15:0]),
        .clock(clk), .result(lane0_sum));
    riscbench_int16_add lane1_add (
        .data0x(operand_a[31:16]), .data1x(operand_b[31:16]),
        .clock(clk), .result(lane1_sum));

    always_ff @(posedge clk) begin
        if (reset) result_valid <= 1'b0;
        else       result_valid <= start;
    end
    assign busy = result_valid;
    assign result = {saturate17($signed(lane1_sum)),
                     saturate17($signed(lane0_sum))};
endmodule
