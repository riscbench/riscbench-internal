module dot_engine_fp32 #(
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
    localparam logic [2:0] PRECISION_FP32 = 3'd4;
    typedef enum logic [3:0] {
        S_IDLE, S_LOAD_A_START, S_LOAD_A_WAIT, S_LOAD_B_START, S_LOAD_B_WAIT,
        S_PREFETCH, S_EXECUTE, S_MUL_WAIT, S_ADD_WAIT, S_DOT_FINAL,
        S_STORE_START, S_STORE_WAIT, S_DONE
    } state_t;

    state_t state;
    logic [31:0] chunk_offset, chunk_length, chunk_words, local_index;
    logic reader_target_a, last_word;
    logic [BUFFER_ADDR_WIDTH-1:0] local_address;
    logic [31:0] reader_base, direct_address, dot_accumulator;
    logic [31:0] direct_operand_a, direct_operand_b;
    logic [31:0] operand_a, operand_b;
    logic fp_mul_start, fp_mul_result_valid;
    logic fp_add_start, fp_add_result_valid;
    logic [31:0] fp_mul_result, fp_add_result;

    always_comb begin
        if (word_path) chunk_length = size - chunk_offset;
        else if (size - chunk_offset > CHUNK_SIZE) chunk_length = CHUNK_SIZE;
        else chunk_length = size - chunk_offset;
        chunk_words = chunk_length;
        reader_base = (reader_target_a ? a_base : b_base) + (chunk_offset << 2);
        direct_address = (reader_target_a ? a_base : b_base) +
                         ((chunk_offset + local_index) << 2);
        operand_a = word_path ? direct_operand_a : buffer_rsp.a_data;
        operand_b = word_path ? direct_operand_b : buffer_rsp.b_data;
        last_word = local_index + 1 >= chunk_words;
    end

    assign local_address = local_index[BUFFER_ADDR_WIDTH-1:0];
    assign busy = (state != S_IDLE) && (state != S_DONE);
    assign done = (state == S_DONE);
    always_comb case (state)
        S_LOAD_A_START, S_LOAD_A_WAIT: phase = 3'd1;
        S_LOAD_B_START, S_LOAD_B_WAIT: phase = 3'd2;
        S_PREFETCH, S_EXECUTE, S_MUL_WAIT, S_ADD_WAIT, S_DOT_FINAL: phase = 3'd3;
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
        buffer_req.c_write_data = dot_accumulator;
        buffer_req.c_read_address = 32'(local_address);
        word_req = '0;
        word_req.read_valid = word_path &&
                              ((state == S_LOAD_A_START) || (state == S_LOAD_B_START));
        word_req.write_valid = word_path && (state == S_STORE_START);
        word_req.address = (state == S_LOAD_A_START || state == S_LOAD_A_WAIT) ?
                           direct_address :
                           (state == S_LOAD_B_START || state == S_LOAD_B_WAIT) ?
                           b_base + ((chunk_offset + local_index) << 2) : c_base;
        word_req.write_data = dot_accumulator;
    end

    assign fp_mul_start = (state == S_EXECUTE);
    assign fp_add_start = (state == S_MUL_WAIT) && fp_mul_result_valid;
    fp32_mul_wrapper mul_unit (
        .clk, .reset, .start(fp_mul_start), .precision(PRECISION_FP32),
        .operand_a(operand_a), .operand_b(operand_b),
        .busy(), .result_valid(fp_mul_result_valid), .result(fp_mul_result)
    );
    fp32_add_wrapper add_unit (
        .clk, .reset, .start(fp_add_start), .precision(PRECISION_FP32),
        .operand_a(dot_accumulator), .operand_b(fp_mul_result),
        .busy(), .result_valid(fp_add_result_valid), .result(fp_add_result)
    );

    assign operation_complete = (state == S_DOT_FINAL);
    assign arithmetic_progress = operation_complete ? 32'd1 : 32'd0;
    assign trace_ops_progress =
        (state == S_ADD_WAIT && fp_add_result_valid) ? 32'd1 : 32'd0;

    always_ff @(posedge clk) begin
        if (reset) begin
            state <= S_IDLE; chunk_offset <= 0; local_index <= 0;
            reader_target_a <= 1; dot_accumulator <= 0;
            direct_operand_a <= 0; direct_operand_b <= 0;
        end else case (state)
            S_IDLE: if (start) begin
                chunk_offset <= 0; local_index <= 0; reader_target_a <= 1;
                dot_accumulator <= 0;
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
            S_MUL_WAIT: if (fp_mul_result_valid) state <= S_ADD_WAIT;
            S_ADD_WAIT: if (fp_add_result_valid) begin
                dot_accumulator <= fp_add_result;
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
