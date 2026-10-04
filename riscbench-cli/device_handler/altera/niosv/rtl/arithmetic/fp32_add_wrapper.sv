module fp32_add_wrapper (
    input  logic clk, reset, start,
    input  logic [2:0] precision,
    input  logic [31:0] operand_a, operand_b,
    output logic busy, result_valid,
    output logic [31:0] result
);
    localparam integer FP32_HARDWARE_LATENCY = 3;
    logic [FP32_HARDWARE_LATENCY-1:0] fp32_valid_pipe;
    logic [31:0] fp32_ip_result;
    logic fp32_enable;

    // The generated native DSP uses ena[0] for its input, internal adder, and
    // output registers. Keep that clock enable asserted until the request has
    // traversed all three registered stages.
    assign fp32_enable = (precision == 3'd4) && (start || (|fp32_valid_pipe));
    riscbench_fp32_add fp32_add_ip (
        .clk(clk),
        .ena({2'b00,fp32_enable}),
        .fp32_adder_a(operand_a),
        .fp32_adder_b(operand_b),
        .fp32_result(fp32_ip_result)
    );

    always_ff @(posedge clk) begin
        if (reset) fp32_valid_pipe <= '0;
        else begin
            fp32_valid_pipe[0] <= start && (precision == 3'd4);
            for (integer i=1; i<FP32_HARDWARE_LATENCY; i=i+1)
                fp32_valid_pipe[i] <= fp32_valid_pipe[i-1];
        end
    end
    assign busy = |fp32_valid_pipe;
    assign result_valid = fp32_valid_pipe[FP32_HARDWARE_LATENCY-1];
    assign result = fp32_ip_result;
endmodule
