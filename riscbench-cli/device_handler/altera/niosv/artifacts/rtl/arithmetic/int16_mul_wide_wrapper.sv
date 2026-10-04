module int16_mul_wide_wrapper (
    input  logic clk, reset, start,
    input  logic [31:0] packed_a, packed_b,
    output logic busy, result_valid,
    output logic signed [31:0] product0, product1
);
    localparam integer LATENCY = 4;
    logic [LATENCY-1:0] valid_pipe;
    logic enable;
    assign enable = start || (|valid_pipe);
    riscbench_int16_mul packed_mul (
        .ax(packed_a[15:0]), .ay(packed_b[15:0]),
        .bx(packed_a[31:16]), .by(packed_b[31:16]),
        .clk(clk), .ena({2'b00,enable}), .resulta(product0), .resultb(product1));
    always_ff @(posedge clk) begin
        if (reset) valid_pipe <= '0;
        else if (enable) begin
            valid_pipe[0] <= start;
            for (integer i=1; i<LATENCY; i++) valid_pipe[i] <= valid_pipe[i-1];
        end
    end
    assign busy=|valid_pipe; assign result_valid=valid_pipe[LATENCY-1];
endmodule
