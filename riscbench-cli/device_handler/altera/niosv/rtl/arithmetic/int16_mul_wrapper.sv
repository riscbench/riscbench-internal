module int16_mul_wrapper (
    input  logic        clk,
    input  logic        reset,
    input  logic        start,
    input  logic [31:0] operand_a,
    input  logic [31:0] operand_b,
    output logic        busy,
    output logic        result_valid,
    output logic [31:0] result
);
    localparam integer LATENCY = 4;
    logic [LATENCY-1:0] valid_pipe;
    logic enable;
    logic [31:0] lane0_product, lane1_product;

    function automatic logic [15:0] saturate32(input logic signed [31:0] value);
        begin
            if (value > 32'sd32767)       saturate32 = 16'h7fff;
            else if (value < -32'sd32768) saturate32 = 16'h8000;
            else                          saturate32 = value[15:0];
        end
    endfunction

    assign enable = start || (|valid_pipe);
    riscbench_int16_mul packed_mul (
        .ax(operand_a[15:0]), .ay(operand_b[15:0]),
        .bx(operand_a[31:16]), .by(operand_b[31:16]),
        .clk(clk), .ena({2'b00,enable}),
        .resulta(lane0_product), .resultb(lane1_product));

    always_ff @(posedge clk) begin
        if (reset) valid_pipe <= '0;
        else if (enable) begin
            valid_pipe[0] <= start;
            for (integer i=1; i<LATENCY; i=i+1)
                valid_pipe[i] <= valid_pipe[i-1];
        end
    end
    assign busy = |valid_pipe;
    assign result_valid = valid_pipe[LATENCY-1];
    assign result = {saturate32($signed(lane1_product)),
                     saturate32($signed(lane0_product))};
endmodule
