// Fixed-function packed INT8 VECADD with buffered and direct-word memory paths.
module vecadd_engine_int8 #(
    parameter integer BUFFER_DEPTH = 1024,
    parameter integer BUFFER_ADDR_WIDTH = $clog2(BUFFER_DEPTH),
    parameter integer CHUNK_SIZE = 1024,
    parameter integer TILE_SIZE = 16
) (
    input logic clk, reset, start,
    input logic word_path,
    input logic [31:0] size, a_base, b_base, c_base, alpha,
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
    output logic [31:0] arithmetic_progress, trace_ops_progress
);
    localparam integer CHUNK_WORD_CAPACITY =
        (CHUNK_SIZE < BUFFER_DEPTH) ? CHUNK_SIZE : BUFFER_DEPTH;

    typedef enum logic [3:0] {
        IDLE, LOAD_A, WAIT_A, LOAD_B, WAIT_B, PREFETCH,
        EXECUTE, WAIT_RESULT, WRITE_RESULT, WAIT_WRITE, DONE
    } state_t;

    state_t state;
    logic [31:0] chunk_offset, chunk_length, word_index, word_count;
    logic reader_target_a;
    logic [31:0] byte_offset, reader_base, direct_address;
    logic [BUFFER_ADDR_WIDTH-1:0] local_address;
    logic [31:0] operand_a, operand_b, masked_a, masked_b;
    logic [31:0] direct_operand_a, direct_operand_b, add_result, direct_result;
    logic [2:0] valid_lanes;
    logic result_valid, c_write_enable, last_word;

    function automatic logic [31:0] mask_word(
        input logic [31:0] value,
        input logic [2:0] lanes
    );
        logic [31:0] masked;
        begin
            masked = '0;
            for (integer lane = 0; lane < 4; lane++)
                if (lane < lanes)
                    masked[8*lane +: 8] = value[8*lane +: 8];
            return masked;
        end
    endfunction

    int8_add_wrapper add_unit (
        .clk,
        .reset,
        .start(state == EXECUTE),
        .operand_a(masked_a),
        .operand_b(masked_b),
        .busy(),
        .result_valid(result_valid),
        .result(add_result)
    );

    always_comb begin
        if (word_path)
            chunk_length = size - chunk_offset;
        else if (size - chunk_offset > (CHUNK_WORD_CAPACITY << 2))
            chunk_length = CHUNK_WORD_CAPACITY << 2;
        else
            chunk_length = size - chunk_offset;

        word_count = (chunk_length + 3) >> 2;
        valid_lanes = (chunk_length - (word_index << 2) >= 4) ?
                      3'd4 : (chunk_length - (word_index << 2));
        byte_offset = chunk_offset;
        reader_base = (reader_target_a ? a_base : b_base) + byte_offset;
        direct_address = (reader_target_a ? a_base : b_base) +
                         chunk_offset + (word_index << 2);
        local_address = word_index[BUFFER_ADDR_WIDTH-1:0];
        operand_a = word_path ? direct_operand_a : buffer_rsp.a_data;
        operand_b = word_path ? direct_operand_b : buffer_rsp.b_data;
        masked_a = mask_word(operand_a, valid_lanes);
        masked_b = mask_word(operand_b, valid_lanes);
        c_write_enable = !word_path && (state == WAIT_RESULT) && result_valid;
        last_word = word_index + 1 >= word_count;
    end

    always_comb begin
        busy = (state != IDLE) && (state != DONE);
        done = (state == DONE);
        operation_complete = (state == WAIT_RESULT) && result_valid;
        arithmetic_progress = operation_complete ? {29'd0, valid_lanes} : 32'd0;
        trace_ops_progress = arithmetic_progress;

        case (state)
            LOAD_A, WAIT_A: phase = 3'd1;
            LOAD_B, WAIT_B: phase = 3'd2;
            PREFETCH, EXECUTE, WAIT_RESULT: phase = 3'd3;
            WRITE_RESULT, WAIT_WRITE: phase = 3'd4;
            DONE: phase = 3'd5;
            default: phase = 3'd0;
        endcase

        dma_req = '0;
        dma_req.read_valid = !word_path &&
                             ((state == LOAD_A) || (state == LOAD_B));
        dma_req.read_address = reader_base;
        dma_req.read_words = word_count;
        dma_req.write_valid = !word_path && (state == WRITE_RESULT);
        dma_req.write_address = c_base + byte_offset;
        dma_req.write_words = word_count;
        dma_req.burst_len = burst_len;

        buffer_req = '0;
        buffer_req.load_a = !word_path && reader_target_a;
        buffer_req.load_b = !word_path && !reader_target_a;
        buffer_req.read_offset = '0;
        buffer_req.write_offset = '0;
        buffer_req.a_read_address = 32'(local_address);
        buffer_req.b_read_address = 32'(local_address);
        buffer_req.c_write_enable = c_write_enable;
        buffer_req.c_write_address = 32'(local_address);
        buffer_req.c_write_data = add_result;
        buffer_req.c_read_address = 32'(local_address);

        word_req = '0;
        word_req.read_valid = word_path &&
                              ((state == LOAD_A) || (state == LOAD_B));
        word_req.write_valid = word_path && (state == WRITE_RESULT);
        word_req.address = (state == LOAD_A || state == WAIT_A) ?
                           direct_address :
                           (state == LOAD_B || state == WAIT_B) ?
                           b_base + chunk_offset + (word_index << 2) :
                           c_base + chunk_offset + (word_index << 2);
        word_req.write_data = direct_result;
    end

    always_ff @(posedge clk) begin
        if (reset) begin
            state <= IDLE;
            chunk_offset <= '0;
            word_index <= '0;
            reader_target_a <= 1'b1;
            direct_operand_a <= '0;
            direct_operand_b <= '0;
            direct_result <= '0;
        end else begin
            case (state)
                IDLE: if (start) begin
                    chunk_offset <= '0;
                    word_index <= '0;
                    reader_target_a <= 1'b1;
                    state <= (size == 0) ? DONE : LOAD_A;
                end
                LOAD_A: if (word_path ? word_rsp.ready : dma_rsp.read_ready)
                    state <= WAIT_A;
                WAIT_A: begin
                    if (word_path && word_rsp.read_valid) begin
                        direct_operand_a <= word_rsp.read_data;
                        reader_target_a <= 1'b0;
                        state <= LOAD_B;
                    end else if (!word_path && dma_rsp.read_done) begin
                        reader_target_a <= 1'b0;
                        state <= LOAD_B;
                    end
                end
                LOAD_B: if (word_path ? word_rsp.ready : dma_rsp.read_ready)
                    state <= WAIT_B;
                WAIT_B: begin
                    if (word_path && word_rsp.read_valid) begin
                        direct_operand_b <= word_rsp.read_data;
                        state <= EXECUTE;
                    end else if (!word_path && dma_rsp.read_done) begin
                        state <= PREFETCH;
                    end
                end
                PREFETCH: state <= EXECUTE;
                EXECUTE: state <= WAIT_RESULT;
                WAIT_RESULT: if (result_valid) begin
                    if (word_path) begin
                        direct_result <= add_result;
                        state <= WRITE_RESULT;
                    end else if (last_word) begin
                        word_index <= '0;
                        state <= WRITE_RESULT;
                    end else begin
                        word_index <= word_index + 1'b1;
                        state <= PREFETCH;
                    end
                end
                WRITE_RESULT: begin
                    if (word_path) begin
                        if (word_rsp.ready) begin
                            if (last_word) state <= DONE;
                            else begin
                                word_index <= word_index + 1'b1;
                                reader_target_a <= 1'b1;
                                state <= LOAD_A;
                            end
                        end
                    end else if (dma_rsp.write_ready) begin
                        state <= WAIT_WRITE;
                    end
                end
                WAIT_WRITE: if (dma_rsp.write_done) begin
                    if (chunk_offset + chunk_length < size) begin
                        chunk_offset <= chunk_offset + chunk_length;
                        word_index <= '0;
                        reader_target_a <= 1'b1;
                        state <= LOAD_A;
                    end else begin
                        state <= DONE;
                    end
                end
                DONE: if (!start) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule
