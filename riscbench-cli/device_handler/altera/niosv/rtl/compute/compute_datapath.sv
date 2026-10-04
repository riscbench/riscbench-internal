// Dedicated compute engines. Each slot is a real engine path; no compatibility fallback.
//
// Slot mapping:
//   0-2   VECADD  FP32, INT16, INT8
//   3-5   VECMUL  FP32, INT16, INT8
//   6-8   SAXPY   FP32, INT16, INT8
//   9-11  DOT     FP32, INT16, INT8
//   12-14 MATMUL  FP32, INT16, INT8
//
// MATMUL INT16/INT8 remain direct-word by default. VECADD, VECMUL, and SAXPY
// use the controller's effective path selector, including AUTO defaults.
module compute_datapath #(
    parameter BUFFER_DEPTH = 1024,
    parameter BUFFER_ADDR_WIDTH = $clog2(BUFFER_DEPTH)
) (
    input logic clk, reset,
    input logic [14:0] engine_start,
    input logic word_path,
    input logic [31:0] size, a_base, b_base, c_base, saxpy_scalar,
    input logic [7:0] burst_len,
    output data_mover_pkg::buffered_request_t dma_requests [0:14],
    input data_mover_pkg::buffered_response_t dma_response,
    output data_mover_pkg::local_buffer_request_t buffer_requests [0:14],
    input data_mover_pkg::local_buffer_response_t buffer_response,
    output data_mover_pkg::word_request_t word_requests [0:14],
    input data_mover_pkg::word_response_t word_response,
    output logic engine_busy [0:14],
    output logic engine_done [0:14],
    output logic engine_complete [0:14],
    output logic [2:0] engine_phase [0:14]
);
    // Slot 0: VECADD / FP32 (buffered)
    vecadd_engine_fp32 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) vecadd_engine_fp32_inst (
        // Control / start
        .clk, .reset, .start(engine_start[0]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .alpha(saxpy_scalar), .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[0]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[0]), .buffer_rsp(buffer_response),
        .word_req(word_requests[0]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[0]), .done(engine_done[0]), .phase(engine_phase[0]),
        .operation_complete(engine_complete[0]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 1: VECADD / INT16 (buffered)
    vecadd_engine_int16 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) vecadd_engine_int16_inst (
        // Control / start
        .clk, .reset, .start(engine_start[1]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .alpha(saxpy_scalar), .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[1]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[1]), .buffer_rsp(buffer_response),
        .word_req(word_requests[1]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[1]), .done(engine_done[1]), .phase(engine_phase[1]),
        .operation_complete(engine_complete[1]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 2: VECADD / INT8 (direct-word)
    vecadd_engine_int8 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) vecadd_engine_int8_inst (
        // Control / start
        .clk, .reset, .start(engine_start[2]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .alpha(saxpy_scalar), .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[2]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[2]), .buffer_rsp(buffer_response),
        .word_req(word_requests[2]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[2]), .done(engine_done[2]), .phase(engine_phase[2]),
        .operation_complete(engine_complete[2]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 3: VECMUL / FP32
    vecmul_engine_fp32 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) vecmul_engine_fp32_inst (
        // Control / start
        .clk, .reset, .start(engine_start[3]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .alpha(saxpy_scalar), .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[3]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[3]), .buffer_rsp(buffer_response),
        .word_req(word_requests[3]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[3]), .done(engine_done[3]), .phase(engine_phase[3]),
        .operation_complete(engine_complete[3]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 4: VECMUL / INT16
    vecmul_engine_int16 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) vecmul_engine_int16_inst (
        // Control / start
        .clk, .reset, .start(engine_start[4]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .alpha(saxpy_scalar), .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[4]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[4]), .buffer_rsp(buffer_response),
        .word_req(word_requests[4]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[4]), .done(engine_done[4]), .phase(engine_phase[4]),
        .operation_complete(engine_complete[4]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 5: VECMUL / INT8
    vecmul_engine_int8 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) vecmul_engine_int8_inst (
        // Control / start
        .clk, .reset, .start(engine_start[5]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .alpha(saxpy_scalar), .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[5]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[5]), .buffer_rsp(buffer_response),
        .word_req(word_requests[5]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[5]), .done(engine_done[5]), .phase(engine_phase[5]),
        .operation_complete(engine_complete[5]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 6: SAXPY / FP32 (buffered)
    saxpy_engine_fp32 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) saxpy_engine_fp32_inst (
        // Control / start
        .clk, .reset, .start(engine_start[6]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .alpha(saxpy_scalar), .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[6]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[6]), .buffer_rsp(buffer_response),
        .word_req(word_requests[6]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[6]), .done(engine_done[6]), .phase(engine_phase[6]),
        .operation_complete(engine_complete[6]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 7: SAXPY / INT16 (buffered)
    saxpy_engine_int16 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) saxpy_engine_int16_inst (
        // Control / start
        .clk, .reset, .start(engine_start[7]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .alpha(saxpy_scalar), .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[7]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[7]), .buffer_rsp(buffer_response),
        .word_req(word_requests[7]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[7]), .done(engine_done[7]), .phase(engine_phase[7]),
        .operation_complete(engine_complete[7]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 8: SAXPY / INT8 (buffered)
    saxpy_engine_int8 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) saxpy_engine_int8_inst (
        // Control / start
        .clk, .reset, .start(engine_start[8]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .alpha(saxpy_scalar), .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[8]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[8]), .buffer_rsp(buffer_response),
        .word_req(word_requests[8]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[8]), .done(engine_done[8]), .phase(engine_phase[8]),
        .operation_complete(engine_complete[8]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 9: DOT / FP32 (buffered)
    dot_engine_fp32 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) dot_engine_fp32_inst (
        // Control / start
        .clk, .reset, .start(engine_start[9]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[9]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[9]), .buffer_rsp(buffer_response),
        .word_req(word_requests[9]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[9]), .done(engine_done[9]), .phase(engine_phase[9]),
        .operation_complete(engine_complete[9]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 10: DOT / INT16 (buffered)
    dot_engine_int16 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) dot_engine_int16_inst (
        // Control / start
        .clk, .reset, .start(engine_start[10]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[10]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[10]), .buffer_rsp(buffer_response),
        .word_req(word_requests[10]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[10]), .done(engine_done[10]), .phase(engine_phase[10]),
        .operation_complete(engine_complete[10]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 11: DOT / INT8 (buffered)
    dot_engine_int8 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) dot_engine_int8_inst (
        // Control / start
        .clk, .reset, .start(engine_start[11]),
        .word_path,
        // Configuration
        .size, .a_base, .b_base, .c_base, .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[11]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[11]), .buffer_rsp(buffer_response),
        .word_req(word_requests[11]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[11]), .done(engine_done[11]), .phase(engine_phase[11]),
        .operation_complete(engine_complete[11]),
        .arithmetic_progress(), .trace_ops_progress()
    );

    // Slot 12: MATMUL / FP32 (dual-memory)
    matmul_engine_fp32 #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) matmul_engine_fp32_inst (
        // Control / start
        .clk, .reset, .start(engine_start[12]),
        // Configuration
        .word_path, .size, .a_base, .b_base, .c_base, .burst_len,
        // Memory interfaces
        .word_req(word_requests[12]), .word_rsp(word_response),
        .dma_req(dma_requests[12]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[12]), .buffer_rsp(buffer_response),
        // Status outputs
        .busy(engine_busy[12]), .done(engine_done[12]), .phase(engine_phase[12]),
        .operation_complete(engine_complete[12]),
        .arithmetic_progress()
    );

    // Slot 13: MATMUL / INT16 (dual-memory)
    matmul_engine_int16 matmul_engine_int16_inst (
        // Control / start
        .clk, .reset, .start(engine_start[13]),
        // Configuration
        .word_path, .size, .a_base, .b_base, .c_base, .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[13]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[13]), .buffer_rsp(buffer_response),
        .word_req(word_requests[13]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[13]), .done(engine_done[13]), .phase(engine_phase[13]),
        .operation_complete(engine_complete[13]),
        .arithmetic_progress()
    );

    // Slot 14: MATMUL / INT8 (dual-memory)
    matmul_engine_int8 matmul_engine_int8_inst (
        // Control / start
        .clk, .reset, .start(engine_start[14]),
        // Configuration
        .word_path, .size, .a_base, .b_base, .c_base, .burst_len,
        // Memory interfaces
        .dma_req(dma_requests[14]), .dma_rsp(dma_response),
        .buffer_req(buffer_requests[14]), .buffer_rsp(buffer_response),
        .word_req(word_requests[14]), .word_rsp(word_response),
        // Status outputs
        .busy(engine_busy[14]), .done(engine_done[14]), .phase(engine_phase[14]),
        .operation_complete(engine_complete[14]),
        .arithmetic_progress()
    );

    // Each engine exclusively drives its DMA, local-buffer, and word requests.
endmodule
