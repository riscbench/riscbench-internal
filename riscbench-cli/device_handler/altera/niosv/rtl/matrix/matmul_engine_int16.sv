module matmul_engine_int16 (
    input logic clk, reset, start,
    input logic word_path,
    input logic [7:0] burst_len,
    output data_mover_pkg::buffered_request_t dma_req,
    input data_mover_pkg::buffered_response_t dma_rsp,
    output data_mover_pkg::local_buffer_request_t buffer_req,
    input data_mover_pkg::local_buffer_response_t buffer_rsp,
    input logic [31:0] size, a_base, b_base, c_base,
    output logic busy, done,
    output logic [2:0] phase,
    output logic operation_complete,
    output logic [31:0] arithmetic_progress,
    output data_mover_pkg::word_request_t word_req,
    input data_mover_pkg::word_response_t word_rsp
);
    typedef enum logic [4:0] {
        // Idle / command initialization.
        S_IDLE,
        // Load: issue requests and wait for data / DMA completion.
        S_LOAD_A,
        S_WAIT_LOAD_A,
        S_PREFETCH_A,
        S_CAPTURE_A,
        S_LOAD_B,
        S_WAIT_LOAD_B,
        S_PREFETCH_B,
        S_CAPTURE_B,
        // Compute: launch multiply; WAIT_MUL also launches the first reduction.
        S_COMPUTE,
        S_WAIT_MUL,
        S_WAIT_REDUCE,
        // Accumulate: commit the 64-bit sum, then advance kword or pack the output.
        S_ACCUMULATE,
        // Write: pack one output lane; flush a full word or row tail.
        S_PACK_RESULT,
        // Write: DDR handshake; advance row/column/tile only on completion.
        S_WRITE_LOCAL_RESULT,
        S_WRITE_RESULT,
        S_WAIT_WRITE_RESULT,
        // Done: hold completion until start is released.
        S_DONE
    } state_t;
    // Traversal, operand storage, and arithmetic status.
    state_t state;
    logic [31:0] row, col, kword, row_words, a_word, b_word, out_word;
    logic signed [63:0] accum;
    logic mul_valid, reduce_valid, accum_valid;
    logic signed [31:0] p0, p1;
    logic signed [64:0] reduce_result, accum_result;
    wire last_k = (kword + 1 >= row_words);
    wire odd_k_tail = size[0] && last_k;
    // Tail / extent and saturation helpers.
    function automatic logic signed [63:0] sat65_64(input logic signed [64:0] v);
        if (v[64:63] == 2'b01) sat65_64 = 64'sh7fff_ffff_ffff_ffff;
        else if (v[64:63] == 2'b10) sat65_64 = 64'sh8000_0000_0000_0000;
        else sat65_64 = v[63:0];
    endfunction
    function automatic logic [15:0] sat64_16(input logic signed [63:0] v);
        if (v > 64'sd32767) sat64_16 = 16'h7fff;
        else if (v < -64'sd32768) sat64_16 = 16'h8000;
        else sat64_16 = v[15:0];
    endfunction
    // Arithmetic IP: retain every start condition and result-valid dependency.
    int16_mul_wide_wrapper mul_i (
        .clk,
        .reset,
        .start(state == S_COMPUTE),
        .packed_a(odd_k_tail ? {16'd0, a_word[15:0]} : a_word),
        .packed_b(odd_k_tail ? {16'd0, b_word[15:0]} : b_word),
        .busy(),
        .result_valid(mul_valid),
        .product0(p0),
        .product1(p1)
    );
    int64_add_wrapper reduce_i (
        .clk,
        .reset,
        .start(state == S_WAIT_MUL && mul_valid),
        .operand_a({{32{p0[31]}}, p0}),
        .operand_b({{32{p1[31]}}, p1}),
        .busy(),
        .result_valid(reduce_valid),
        .result(reduce_result)
    );
    int64_add_wrapper accum_i (
        .clk,
        .reset,
        .start(state == S_WAIT_REDUCE && reduce_valid),
        .operand_a(accum),
        .operand_b(reduce_result[63:0]),
        .busy(),
        .result_valid(accum_valid),
        .result(accum_result)
    );
    // Status and memory requests.
    always_comb begin
        busy = (state != S_IDLE) && (state != S_DONE);
        done = (state == S_DONE);
        phase=(state==S_LOAD_A||state==S_WAIT_LOAD_A)?3'd1:(state==S_LOAD_B||state==S_WAIT_LOAD_B)?3'd2:
         (state==S_WRITE_LOCAL_RESULT||state==S_WRITE_RESULT||state==S_WAIT_WRITE_RESULT)?3'd4:(state==S_DONE)?3'd5:(state==S_IDLE)?3'd0:3'd3;
        word_req = '0;
        word_req.read_valid = word_path && ((state == S_LOAD_A) || (state == S_LOAD_B));
        word_req.write_valid = word_path && (state == S_WRITE_RESULT);
        if (state == S_LOAD_A) word_req.address = a_base + (((row * row_words) + kword) << 2);
        else if (state == S_LOAD_B) word_req.address = b_base + (((col * row_words) + kword) << 2);
        else if (state == S_WRITE_RESULT)
            word_req.address = c_base + (((row * row_words) + (col >> 1)) << 2);
        word_req.write_data = out_word;
        // One packed word per DMA keeps the existing traversal independent of
        // local-buffer capacity. A, B and packed C each use local address zero.
        dma_req = '0;
        dma_req.read_valid = !word_path && (state == S_LOAD_A || state == S_LOAD_B);
        dma_req.read_address = word_req.address;
        dma_req.read_words = 1;
        dma_req.write_valid = !word_path && state == S_WRITE_RESULT;
        dma_req.write_address = word_req.address;
        dma_req.write_words = 1;
        dma_req.burst_len = burst_len;
        buffer_req = '0;
        buffer_req.load_a = !word_path && (state == S_LOAD_A || state == S_WAIT_LOAD_A);
        buffer_req.load_b = !word_path && (state == S_LOAD_B || state == S_WAIT_LOAD_B);
        buffer_req.c_write_enable = !word_path && state == S_WRITE_LOCAL_RESULT;
        buffer_req.c_write_data = out_word;
        operation_complete  = (state == S_PACK_RESULT);
        arithmetic_progress = operation_complete ? 1 : 0;
    end
    // State transitions: loop updates stay on their original completion cycles.
    always_ff @(posedge clk) begin
        if (reset) begin
            state <= S_IDLE;
            row <= 0;
            col <= 0;
            kword <= 0;
            row_words <= 0;
            accum <= 0;
            a_word <= 0;
            b_word <= 0;
            out_word <= 0;
        end else
            case (state)
                // Idle / command initialization.
                S_IDLE:
                if (start) begin
                    row <= 0;
                    col <= 0;
                    kword <= 0;
                    accum <= 0;
                    out_word <= 0;
                    row_words <= (size + 1) >> 1;
                    state <= size == 0 ? S_DONE : S_LOAD_A;
                end
                // Load: issue requests and wait for data / DMA completion.
                S_LOAD_A:
                if (word_path ? word_rsp.ready : dma_rsp.read_ready)
                    state <= S_WAIT_LOAD_A;
                S_WAIT_LOAD_A:
                if (word_path) begin
                    if (word_rsp.read_valid) begin
                        a_word <= word_rsp.read_data;
                        state <= S_LOAD_B;
                    end
                end else if (dma_rsp.read_done) state <= S_PREFETCH_A;
                S_PREFETCH_A: state <= S_CAPTURE_A;
                S_CAPTURE_A: begin
                    a_word <= buffer_rsp.a_data;
                    state <= S_LOAD_B;
                end
                S_LOAD_B:
                if (word_path ? word_rsp.ready : dma_rsp.read_ready)
                    state <= S_WAIT_LOAD_B;
                S_WAIT_LOAD_B:
                if (word_path) begin
                    if (word_rsp.read_valid) begin
                        b_word <= word_rsp.read_data;
                        state <= S_COMPUTE;
                    end
                end else if (dma_rsp.read_done) state <= S_PREFETCH_B;
                S_PREFETCH_B: state <= S_CAPTURE_B;
                S_CAPTURE_B: begin
                    b_word <= buffer_rsp.b_data;
                    state <= S_COMPUTE;
                end
                // Compute: launch multiply; WAIT_MUL also launches the first reduction.
                S_COMPUTE: state <= S_WAIT_MUL;
                S_WAIT_MUL: if (mul_valid) state <= S_WAIT_REDUCE;
                S_WAIT_REDUCE: if (reduce_valid) state <= S_ACCUMULATE;
                // Accumulate: commit the 64-bit sum, then advance kword or pack the output.
                S_ACCUMULATE:
                if (accum_valid) begin
                    accum <= sat65_64(accum_result);
                    if (last_k) state <= S_PACK_RESULT;
                    else begin
                        kword <= kword + 1;
                        state <= S_LOAD_A;
                    end
                end
                // Write: pack one output lane; flush a full word or row tail.
                S_PACK_RESULT: begin
                    if (!col[0]) out_word <= {16'd0, sat64_16(accum)};
                    else out_word[31:16] <= sat64_16(accum);
                    if (col[0] || col + 1 >= size) state <= word_path ? S_WRITE_RESULT : S_WRITE_LOCAL_RESULT;
                    else begin
                        col   <= col + 1;
                        kword <= 0;
                        accum <= 0;
                        state <= S_LOAD_A;
                    end
                end
                // Write: DDR handshake; advance row/column/tile only on completion.
                S_WRITE_LOCAL_RESULT: state <= S_WRITE_RESULT;
                S_WRITE_RESULT:
                if (!word_path) begin
                    if (dma_rsp.write_ready) state <= S_WAIT_WRITE_RESULT;
                end else if (word_rsp.ready) begin
                    out_word <= 0;
                    kword <= 0;
                    accum <= 0;
                    if (col + 1 < size) begin
                        col   <= col + 1;
                        state <= S_LOAD_A;
                    end else if (row + 1 < size) begin
                        row   <= row + 1;
                        col   <= 0;
                        state <= S_LOAD_A;
                    end else state <= S_DONE;
                end
                S_WAIT_WRITE_RESULT:
                if (dma_rsp.write_done) begin
                    out_word <= 0;
                    kword <= 0;
                    accum <= 0;
                    if (col + 1 < size) begin
                        col   <= col + 1;
                        state <= S_LOAD_A;
                    end else if (row + 1 < size) begin
                        row   <= row + 1;
                        col   <= 0;
                        state <= S_LOAD_A;
                    end else state <= S_DONE;
                end
                // Done: hold completion until start is released.
                S_DONE: if (!start) state <= S_IDLE;
                default: state <= S_IDLE;
            endcase
    end
endmodule
