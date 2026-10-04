module sit_engine_pd #(
    parameter bit ENABLE_PERF_MONITOR = 1'b1
) (
    input  logic        clk,
    input  logic        reset,
    input  logic [4:0]  avs_address,
    input  logic        avs_read,
    input  logic        avs_write,
    input  logic [31:0] avs_writedata,
    input  logic [3:0]  avs_byteenable,
    output logic [31:0] avs_readdata,
    output logic        avs_waitrequest,
    output logic [31:0] avm_address,
    output logic        avm_read,
    output logic        avm_write,
    output logic [31:0] avm_writedata,
    output logic [3:0]  avm_byteenable,
    output logic [7:0]  avm_burstcount,
    input  logic        avm_waitrequest,
    input  logic [31:0] avm_readdata,
    input  logic        avm_readdatavalid
);
    logic monitor_enable;
    logic [63:0] total_cycles, active_cycles, mem_wait_cycles, ops_completed;
    logic start, busy, done, operation_complete, mem_stall;
    logic [2:0] mode, control_state;
    logic [3:0] selected_slot;
    logic [31:0] size, a_base, b_base, c_base, alpha;
    logic [2:0] precision;
    logic [1:0] memory_policy;

    sit_csr csr (
        .clk, .reset,
        .avs_address, .avs_read, .avs_write, .avs_writedata,
        .avs_byteenable, .avs_readdata, .avs_waitrequest,
        .start, .mode, .size, .a_base, .b_base, .c_base, .alpha, .precision,
        .memory_policy, .monitor_enable,
        .total_cycles, .active_cycles, .mem_wait_cycles, .ops_completed,
        .busy, .done, .selected_slot, .control_state, .operation_complete, .mem_stall
    );

    sit_engine #(.ENABLE_PERF_MONITOR(ENABLE_PERF_MONITOR)) engine (
        .monitor_enable,
        .total_cycles, .active_cycles, .mem_wait_cycles, .ops_completed,
        .clk, .reset, .start, .mode, .size,
        .precision, .memory_policy, .burst_len(8'd16),
        .a_base, .b_base, .c_base, .saxpy_scalar(alpha),
        .load_a_write_enable(1'b0), .load_a_write_address('0),
        .load_a_write_data(32'd0),
        .load_b_write_enable(1'b0), .load_b_write_address('0),
        .load_b_write_data(32'd0),
        .busy, .done, .selected_slot, .control_state, .operation_complete, .mem_stall,
        .avm_address, .avm_read, .avm_write, .avm_writedata,
        .avm_byteenable, .avm_burstcount, .avm_waitrequest,
        .avm_readdata, .avm_readdatavalid
    );

endmodule
