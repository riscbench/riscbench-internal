module sit_engine #(
    parameter BUFFER_DEPTH = 1024,
    parameter BUFFER_ADDR_WIDTH = $clog2(BUFFER_DEPTH),
    parameter bit ENABLE_PERF_MONITOR = 1'b1
) (
    input logic clk, reset, start,
    input logic monitor_enable,
    output logic [63:0] total_cycles, active_cycles, mem_wait_cycles, ops_completed,
    input logic [2:0] mode,
    input logic [31:0] size,
    input logic [2:0] precision,
    input logic [1:0] memory_policy,
    input logic [7:0] burst_len,
    input logic [31:0] a_base, b_base, c_base, saxpy_scalar,
    input logic load_a_write_enable,
    input logic [BUFFER_ADDR_WIDTH-1:0] load_a_write_address,
    input logic [31:0] load_a_write_data,
    input logic load_b_write_enable,
    input logic [BUFFER_ADDR_WIDTH-1:0] load_b_write_address,
    input logic [31:0] load_b_write_data,
    output logic busy, done,
    output logic [3:0] selected_slot,
    output logic [2:0] control_state,
    output logic operation_complete,
    output logic mem_stall,
    output logic [31:0] avm_address,
    output logic avm_read, avm_write,
    output logic [31:0] avm_writedata,
    output logic [3:0] avm_byteenable,
    output logic [7:0] avm_burstcount,
    input logic avm_waitrequest,
    input logic [31:0] avm_readdata,
    input logic avm_readdatavalid
);
    import data_mover_pkg::*;

    // ---------------------------------------------------------------------
    // Controller / datapath signals
    // ---------------------------------------------------------------------
    logic slot_valid, word_path;
    logic [14:0] compute_start;
    logic compute_busy [0:14], compute_done [0:14], compute_complete [0:14];
    logic [2:0] compute_phase [0:14];

    buffered_request_t compute_dma_requests [0:14];
    local_buffer_request_t compute_buffer_requests [0:14];
    word_request_t compute_word_requests [0:14];

    buffered_response_t dma_response;
    word_response_t word_response;
    local_buffer_response_t local_buffer_response;

    buffered_request_t dma_request;
    local_buffer_request_t active_buffer_request;
    word_request_t word_request;

    logic [31:0] buffer_a_data, buffer_b_data, buffer_c_data;
    logic reader_buffer_write_enable, writer_buffer_active;
    logic [BUFFER_ADDR_WIDTH-1:0] reader_buffer_write_address;
    logic [BUFFER_ADDR_WIDTH-1:0] writer_buffer_read_address;
    logic [31:0] reader_buffer_write_data;

    // Observation only: counter outputs go to CSR readback, never execution.
    generate
        if (ENABLE_PERF_MONITOR) begin : g_perf_monitor
            perf_monitor monitor (
                .clk, .reset, .monitor_enable,
                .start(|compute_start), .busy,
                .compute_active(busy && (control_state == 3'd3)),
                .mem_wait(busy && ((control_state == 3'd1) ||
                                  (control_state == 3'd2) ||
                                  (control_state == 3'd4))),
                .operation_complete,
                .total_cycles, .active_cycles, .mem_wait_cycles, .ops_completed
            );
        end else begin : g_no_perf_monitor
            assign total_cycles = 64'd0;
            assign active_cycles = 64'd0;
            assign mem_wait_cycles = 64'd0;
            assign ops_completed = 64'd0;
        end
    endgenerate

    assign slot_valid = (selected_slot < 4'd15);

    workload_controller controller (
        .clk, .reset, .start, .mode, .precision,
        .memory_policy,
        .busy, .selected_slot, .word_path, .compute_start
    );

    compute_datapath #(
        .BUFFER_DEPTH(BUFFER_DEPTH),
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) compute (
        .clk, .reset,
        .engine_start(compute_start),
        .word_path,
        .size, .a_base, .b_base, .c_base, .saxpy_scalar, .burst_len,
        .dma_requests(compute_dma_requests), .dma_response,
        .buffer_requests(compute_buffer_requests),
        .buffer_response(local_buffer_response),
        .word_requests(compute_word_requests), .word_response,
        .engine_busy(compute_busy), .engine_done(compute_done),
        .engine_complete(compute_complete), .engine_phase(compute_phase)
    );

    // ---------------------------------------------------------------------
    // Selected-slot request / status muxing
    // ---------------------------------------------------------------------
    always_comb begin
        dma_request = '0;
        active_buffer_request = '0;
        word_request = '0;
        busy = 1'b0;
        done = 1'b0;
        control_state = '0;
        operation_complete = 1'b0;

        if (slot_valid) begin
            dma_request = compute_dma_requests[selected_slot];
            active_buffer_request = compute_buffer_requests[selected_slot];
            word_request = compute_word_requests[selected_slot];

            busy = compute_busy[selected_slot];
            done = compute_done[selected_slot];
            control_state = compute_phase[selected_slot];
            operation_complete = compute_complete[selected_slot];
        end
    end

    // ---------------------------------------------------------------------
    // Local-buffer integration
    // ---------------------------------------------------------------------
    assign local_buffer_response.a_data = buffer_a_data;
    assign local_buffer_response.b_data = buffer_b_data;
    assign local_buffer_response.c_data = buffer_c_data;

    local_buffer #(.DEPTH(BUFFER_DEPTH)) buffer_a (
        .clk,
        .write_enable(slot_valid && !word_path && reader_buffer_write_enable &&
                      active_buffer_request.load_a),
        .write_address(reader_buffer_write_address),
        .write_data(reader_buffer_write_data),
        .read_address(active_buffer_request.a_read_address[BUFFER_ADDR_WIDTH-1:0]),
        .read_data(buffer_a_data)
    );

    local_buffer #(.DEPTH(BUFFER_DEPTH)) buffer_b (
        .clk,
        .write_enable(slot_valid && !word_path && reader_buffer_write_enable &&
                      active_buffer_request.load_b),
        .write_address(reader_buffer_write_address),
        .write_data(reader_buffer_write_data),
        .read_address(active_buffer_request.b_read_address[BUFFER_ADDR_WIDTH-1:0]),
        .read_data(buffer_b_data)
    );

    local_buffer #(.DEPTH(BUFFER_DEPTH)) buffer_c (
        .clk,
        .write_enable(slot_valid && !word_path && active_buffer_request.c_write_enable),
        .write_address(active_buffer_request.c_write_address[BUFFER_ADDR_WIDTH-1:0]),
        .write_data(active_buffer_request.c_write_data),
        .read_address(writer_buffer_active ?
                      writer_buffer_read_address :
                      active_buffer_request.c_read_address[BUFFER_ADDR_WIDTH-1:0]),
        .read_data(buffer_c_data)
    );

    // ---------------------------------------------------------------------
    // Data mover connection
    // ---------------------------------------------------------------------
    data_mover #(
        .BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)
    ) mover (
        .clk, .reset, .owner_valid(slot_valid), .word_path,
        .dma_req(dma_request), .dma_rsp(dma_response),
        .read_buffer_offset(active_buffer_request.read_offset[BUFFER_ADDR_WIDTH-1:0]),
        .write_buffer_offset(active_buffer_request.write_offset[BUFFER_ADDR_WIDTH-1:0]),
        .reader_buffer_write_enable, .reader_buffer_write_address,
        .reader_buffer_write_data, .writer_buffer_active,
        .writer_buffer_read_address, .writer_buffer_read_data(buffer_c_data),
        .word_req(word_request), .word_rsp(word_response),
        .avm_address, .avm_read, .avm_write, .avm_writedata,
        .avm_byteenable, .avm_burstcount,
        .avm_waitrequest, .avm_readdata, .avm_readdatavalid
    );

    // ---------------------------------------------------------------------
    // Avalon output routing / status outputs
    // ---------------------------------------------------------------------
    assign mem_stall = (avm_read || avm_write) && avm_waitrequest;
endmodule
