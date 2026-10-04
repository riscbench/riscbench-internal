module dot_engine_int16 #(
    parameter integer BUFFER_DEPTH = 1024,
    parameter integer BUFFER_ADDR_WIDTH = $clog2(BUFFER_DEPTH),
    parameter integer CHUNK_SIZE = 1024
) (
    input logic clk, reset, start, word_path,
    input logic [31:0] size, a_base, b_base, c_base,
    input logic [7:0] burst_len,
    output data_mover_pkg::buffered_request_t dma_req,
    input data_mover_pkg::buffered_response_t dma_rsp,
    output data_mover_pkg::local_buffer_request_t buffer_req,
    input data_mover_pkg::local_buffer_response_t buffer_rsp,
    output data_mover_pkg::word_request_t word_req,
    input data_mover_pkg::word_response_t word_rsp,
    output logic busy, done,
    output logic [2:0] phase,
    output logic operation_complete,
    output logic [31:0] arithmetic_progress,
    output logic [31:0] trace_ops_progress
);
    typedef enum logic [3:0] {
        S_IDLE, S_LOAD_A_START, S_LOAD_A_WAIT, S_LOAD_B_START, S_LOAD_B_WAIT,
        S_PREFETCH, S_EXECUTE, S_MUL_WAIT, S_REDUCE_WAIT, S_ACCUM_WAIT,
        S_DOT_FINAL, S_STORE_START, S_STORE_WAIT, S_DONE
    } state_t;

    state_t state;
    logic [31:0] chunk_offset, chunk_length, chunk_words, local_index;
    logic reader_target_a, int16_tail_word, last_word;
    logic [BUFFER_ADDR_WIDTH-1:0] local_address;
    logic [31:0] reader_base, direct_address;
    logic [31:0] direct_operand_a, direct_operand_b;
    logic [31:0] operand_a, operand_b;
    logic signed [63:0] int_dot_accumulator;
    logic wide_mul_valid, reduce_valid, accum_valid;
    logic signed [31:0] wide_product0, wide_product1;
    logic signed [64:0] reduce_sum, accum_sum;
    logic [31:0] packed_a, packed_b;

    function automatic logic signed [63:0] saturate65_to64(
        input logic signed [64:0] value
    );
        if (value[64:63] == 2'b01) saturate65_to64 = 64'sh7fff_ffff_ffff_ffff;
        else if (value[64:63] == 2'b10) saturate65_to64 = 64'sh8000_0000_0000_0000;
        else saturate65_to64 = value[63:0];
    endfunction

    function automatic logic [31:0] saturate64_to32(
        input logic signed [63:0] value
    );
        if (value > 64'sd2147483647) saturate64_to32 = 32'h7fff_ffff;
        else if (value < -64'sd2147483648) saturate64_to32 = 32'h8000_0000;
        else saturate64_to32 = value[31:0];
    endfunction

    always_comb begin
        if (word_path) chunk_length = size - chunk_offset;
        else if (size - chunk_offset > CHUNK_SIZE * 2) chunk_length = CHUNK_SIZE * 2;
        else chunk_length = size - chunk_offset;
        chunk_words = (chunk_length + 1) >> 1;
        reader_base = (reader_target_a ? a_base : b_base) + (chunk_offset << 1);
        direct_address = (reader_target_a ? a_base : b_base) +
                         (chunk_offset << 1) + (local_index << 2);
        operand_a = word_path ? direct_operand_a : buffer_rsp.a_data;
        operand_b = word_path ? direct_operand_b : buffer_rsp.b_data;
        int16_tail_word = chunk_length[0] && (local_index + 1 >= chunk_words);
        packed_a = int16_tail_word ? {16'd0, operand_a[15:0]} : operand_a;
        packed_b = int16_tail_word ? {16'd0, operand_b[15:0]} : operand_b;
        last_word = local_index + 1 >= chunk_words;
    end

    assign local_address = local_index[BUFFER_ADDR_WIDTH-1:0];
    assign busy = (state != S_IDLE) && (state != S_DONE);
    assign done = (state == S_DONE);
    always_comb case (state)
        S_LOAD_A_START, S_LOAD_A_WAIT: phase = 3'd1;
        S_LOAD_B_START, S_LOAD_B_WAIT: phase = 3'd2;
        S_PREFETCH, S_EXECUTE, S_MUL_WAIT, S_REDUCE_WAIT,
        S_ACCUM_WAIT, S_DOT_FINAL: phase = 3'd3;
        S_STORE_START, S_STORE_WAIT: phase = 3'd4;
        S_DONE: phase = 3'd5;
        default: phase = 3'd0;
    endcase

    always_comb begin
        dma_req = '0;
        dma_req.read_valid = !word_path &&
                             ((state == S_LOAD_A_START) || (state == S_LOAD_B_START));
        dma_req.write_valid = !word_path && (state == S_STORE_START);
        dma_req.read_address = reader_base;
        dma_req.read_words = chunk_words;
        dma_req.write_address = c_base;
        dma_req.write_words = 32'd1;
        dma_req.burst_len = burst_len;

        buffer_req = '0;
        buffer_req.load_a = !word_path && reader_target_a;
        buffer_req.load_b = !word_path && !reader_target_a;
        buffer_req.a_read_address = 32'(local_address);
        buffer_req.b_read_address = 32'(local_address);
        buffer_req.c_write_enable = !word_path && (state == S_DOT_FINAL);
        buffer_req.c_write_address = 32'd0;
        buffer_req.c_write_data = saturate64_to32(int_dot_accumulator);
        buffer_req.c_read_address = 32'(local_address);
        word_req = '0;
        word_req.read_valid = word_path &&
                              ((state == S_LOAD_A_START) || (state == S_LOAD_B_START));
        word_req.write_valid = word_path && (state == S_STORE_START);
        word_req.address = (state == S_LOAD_A_START || state == S_LOAD_A_WAIT) ?
                           direct_address :
                           (state == S_LOAD_B_START || state == S_LOAD_B_WAIT) ?
                           b_base + (chunk_offset << 1) + (local_index << 2) : c_base;
        word_req.write_data = saturate64_to32(int_dot_accumulator);
    end

    int16_mul_wide_wrapper wide_mul_unit (
        .clk, .reset, .start(state == S_EXECUTE),
        .packed_a, .packed_b, .busy(), .result_valid(wide_mul_valid),
        .product0(wide_product0), .product1(wide_product1)
    );
    int64_add_wrapper dot_reduce (
        .clk, .reset, .start(state == S_MUL_WAIT && wide_mul_valid),
        .operand_a({{32{wide_product0[31]}}, wide_product0}),
        .operand_b({{32{wide_product1[31]}}, wide_product1}),
        .busy(), .result_valid(reduce_valid), .result(reduce_sum)
    );
    int64_add_wrapper dot_accum (
        .clk, .reset, .start(state == S_REDUCE_WAIT && reduce_valid),
        .operand_a(int_dot_accumulator), .operand_b(reduce_sum[63:0]),
        .busy(), .result_valid(accum_valid), .result(accum_sum)
    );

    assign operation_complete = (state == S_DOT_FINAL);
    assign arithmetic_progress = operation_complete ? 32'd1 : 32'd0;
    assign trace_ops_progress = (state == S_ACCUM_WAIT && accum_valid) ?
                                (int16_tail_word ? 32'd1 : 32'd2) : 32'd0;

    always_ff @(posedge clk) begin
        if (reset) begin
            state <= S_IDLE; chunk_offset <= 0; local_index <= 0;
            reader_target_a <= 1; int_dot_accumulator <= 0;
            direct_operand_a <= 0; direct_operand_b <= 0;
        end else case (state)
            S_IDLE: if (start) begin
                chunk_offset <= 0; local_index <= 0; reader_target_a <= 1;
                int_dot_accumulator <= 0;
                state <= (size == 0) ? S_DONE : S_LOAD_A_START;
            end
            S_LOAD_A_START: if (!word_path || word_rsp.ready) state <= S_LOAD_A_WAIT;
            S_LOAD_A_WAIT: begin
                if (word_path && word_rsp.read_valid) begin
                    direct_operand_a <= word_rsp.read_data;
                    reader_target_a <= 0; state <= S_LOAD_B_START;
                end else if (!word_path && dma_rsp.read_done) begin
                    reader_target_a <= 0; state <= S_LOAD_B_START;
                end
            end
            S_LOAD_B_START: if (!word_path || word_rsp.ready) state <= S_LOAD_B_WAIT;
            S_LOAD_B_WAIT: begin
                if (word_path && word_rsp.read_valid) begin
                    direct_operand_b <= word_rsp.read_data; state <= S_EXECUTE;
                end else if (!word_path && dma_rsp.read_done) begin
                    local_index <= 0; state <= S_PREFETCH;
                end
            end
            S_PREFETCH: state <= S_EXECUTE;
            S_EXECUTE: state <= S_MUL_WAIT;
            S_MUL_WAIT: if (wide_mul_valid) state <= S_REDUCE_WAIT;
            S_REDUCE_WAIT: if (reduce_valid) state <= S_ACCUM_WAIT;
            S_ACCUM_WAIT: if (accum_valid) begin
                int_dot_accumulator <= saturate65_to64(accum_sum);
                if (last_word) begin
                    local_index <= 0;
                    if (word_path || chunk_offset + chunk_length >= size)
                        state <= S_DOT_FINAL;
                    else begin
                        chunk_offset <= chunk_offset + chunk_length;
                        reader_target_a <= 1; state <= S_LOAD_A_START;
                    end
                end else begin
                    local_index <= local_index + 1;
                    if (word_path) begin
                        reader_target_a <= 1; state <= S_LOAD_A_START;
                    end else state <= S_PREFETCH;
                end
            end
            S_DOT_FINAL: state <= S_STORE_START;
            S_STORE_START: begin
                if (word_path) begin
                    if (word_rsp.ready) state <= S_DONE;
                end else state <= S_STORE_WAIT;
            end
            S_STORE_WAIT: if (dma_rsp.write_done) state <= S_DONE;
            S_DONE: if (!start) state <= S_IDLE;
            default: state <= S_IDLE;
        endcase
    end

endmodule
