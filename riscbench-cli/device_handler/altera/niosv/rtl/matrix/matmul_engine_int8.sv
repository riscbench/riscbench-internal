module matmul_engine_int8 (
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
        S_WAIT_REDUCE_L1,
        S_WAIT_REDUCE_L2,
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
    logic mul_valid, r1_valid[0:1], r2_valid, acc_valid;
    logic signed [15:0] p[0:3];
    logic signed [64:0] r1[0:1], r2, acc_result;
    logic [2:0] k_lanes;
    logic [31:0] masked_a, masked_b;
    wire last_k = kword + 1 >= row_words;
    // Tail / extent and saturation helpers.
    function automatic logic [31:0] mask_word(input logic [31:0] v, input logic [2:0] lanes);
        logic [31:0] q;
        begin
            q = 0;
            for (integer i = 0; i < 4; i++) if (i < lanes) q[8*i+:8] = v[8*i+:8];
            mask_word = q;
        end
    endfunction
    function automatic logic signed [63:0] sat65_64(input logic signed [64:0] v);
        if (v[64:63] == 2'b01) sat65_64 = 64'sh7fff_ffff_ffff_ffff;
        else if (v[64:63] == 2'b10) sat65_64 = 64'sh8000_0000_0000_0000;
        else sat65_64 = v[63:0];
    endfunction
    function automatic logic [7:0] sat65_8(input logic signed [64:0] v);
        if (v > 65'sd127) sat65_8 = 8'h7f;
        else if (v < -65'sd128) sat65_8 = 8'h80;
        else sat65_8 = v[7:0];
    endfunction
    always_comb begin
        k_lanes  = (!last_k || size[1:0] == 0) ? 4 : size[1:0];
        masked_a = mask_word(a_word, k_lanes);
        masked_b = mask_word(b_word, k_lanes);
    end
    // Arithmetic IP: retain every start condition and result-valid dependency.
    int8_mul_wide_wrapper mu (
        .clk,
        .reset,
        .start(state == S_COMPUTE),
        .packed_a(masked_a),
        .packed_b(masked_b),
        .busy(),
        .result_valid(mul_valid),
        .product0(p[0]),
        .product1(p[1]),
        .product2(p[2]),
        .product3(p[3])
    );
    int64_add_wrapper r10 (
        .clk,
        .reset,
        .start(state == S_WAIT_MUL && mul_valid),
        .operand_a({{48{p[0][15]}}, p[0]}),
        .operand_b({{48{p[1][15]}}, p[1]}),
        .busy(),
        .result_valid(r1_valid[0]),
        .result(r1[0])
    );
    int64_add_wrapper r11 (
        .clk,
        .reset,
        .start(state == S_WAIT_MUL && mul_valid),
        .operand_a({{48{p[2][15]}}, p[2]}),
        .operand_b({{48{p[3][15]}}, p[3]}),
        .busy(),
        .result_valid(r1_valid[1]),
        .result(r1[1])
    );
    int64_add_wrapper r20 (
        .clk,
        .reset,
        .start(state == S_WAIT_REDUCE_L1 && r1_valid[0] && r1_valid[1]),
        .operand_a(r1[0][63:0]),
        .operand_b(r1[1][63:0]),
        .busy(),
        .result_valid(r2_valid),
        .result(r2)
    );
    int64_add_wrapper ac (
        .clk,
        .reset,
        .start(state == S_WAIT_REDUCE_L2 && r2_valid),
        .operand_a(accum),
        .operand_b(r2[63:0]),
        .busy(),
        .result_valid(acc_valid),
        .result(acc_result)
    );
    // Status and memory requests.
    always_comb begin
        busy = (state != S_IDLE) && (state != S_DONE);
        done = state == S_DONE;
        phase = (state == S_LOAD_A || state == S_WAIT_LOAD_A) ? 1 :
                (state == S_LOAD_B || state == S_WAIT_LOAD_B) ? 2 :
                (state == S_WRITE_LOCAL_RESULT || state == S_WRITE_RESULT || state == S_WAIT_WRITE_RESULT) ? 4 :
                (state == S_DONE) ? 5 : (state == S_IDLE) ? 0 : 3;
        word_req = '0;
        word_req.read_valid = word_path && (state == S_LOAD_A || state == S_LOAD_B);
        word_req.write_valid = word_path && (state == S_WRITE_RESULT);
        if (state == S_LOAD_A) word_req.address = a_base + (((row * row_words) + kword) << 2);
        else if (state == S_LOAD_B) word_req.address = b_base + (((col * row_words) + kword) << 2);
        else if (state == S_WRITE_RESULT)
            word_req.address = c_base + (((row * row_words) + (col >> 2)) << 2);
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
        operation_complete  = state == S_PACK_RESULT;
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
            a_word <= 0;
            b_word <= 0;
            out_word <= 0;
            accum <= 0;
        end else
            case (state)
                // Idle / command initialization.
                S_IDLE:
                if (start) begin
                    row <= 0;
                    col <= 0;
                    kword <= 0;
                    row_words <= (size + 3) >> 2;
                    out_word <= 0;
                    accum <= 0;
                    state <= size ? S_LOAD_A : S_DONE;
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
                S_WAIT_MUL: if (mul_valid) state <= S_WAIT_REDUCE_L1;
                S_WAIT_REDUCE_L1: if (r1_valid[0] && r1_valid[1]) state <= S_WAIT_REDUCE_L2;
                S_WAIT_REDUCE_L2: if (r2_valid) state <= S_ACCUMULATE;
                // Accumulate: commit the 64-bit sum, then advance kword or pack the output.
                S_ACCUMULATE:
                if (acc_valid) begin
                    accum <= sat65_64(acc_result);
                    if (last_k) state <= S_PACK_RESULT;
                    else begin
                        kword <= kword + 1;
                        state <= S_LOAD_A;
                    end
                end
                // Write: pack one output lane; flush a full word or row tail.
                S_PACK_RESULT: begin
                    out_word[8*(col[1:0])+:8] <= sat65_8(acc_result);
                    if (col[1:0] == 3 || col + 1 >= size) state <= word_path ? S_WRITE_RESULT : S_WRITE_LOCAL_RESULT;
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
