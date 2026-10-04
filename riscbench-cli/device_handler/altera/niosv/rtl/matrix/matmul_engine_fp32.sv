module matmul_engine_fp32 #(
    parameter integer BUFFER_DEPTH = 1024,
    parameter integer BUFFER_ADDR_WIDTH = $clog2(BUFFER_DEPTH)
) (
    input logic clk, reset, start,
    input logic word_path,
    output data_mover_pkg::word_request_t word_req,
    input data_mover_pkg::word_response_t word_rsp,
    input logic [31:0] size, a_base, b_base, c_base,
    input logic [7:0] burst_len,
    output data_mover_pkg::buffered_request_t dma_req,
    input data_mover_pkg::buffered_response_t dma_rsp,
    output data_mover_pkg::local_buffer_request_t buffer_req,
    input data_mover_pkg::local_buffer_response_t buffer_rsp,
    output logic busy, done,
    output logic [2:0] phase,
    output logic operation_complete,
    output logic [31:0] arithmetic_progress
);
    // Configuration and traversal / operand / arithmetic registers.
    localparam integer TILE_SIZE = 16;
    typedef enum logic [4:0] {
        // Idle / command initialization.
        S_IDLE,
        // Prepare: clear the C tile before its first K tile.
        S_CLEAR_RESULT,
        // Load: issue requests and wait for data / DMA completion.
        S_LOAD_A,
        S_WAIT_LOAD_A,
        S_LOAD_B,
        S_WAIT_LOAD_B,
        // Prepare: synchronous C read, accumulator capture, then A/B prefetch.
        S_PREFETCH_RESULT,
        S_PREPARE_ACCUMULATOR,
        S_PREFETCH_OPERANDS,
        // Compute: launch multiply; WAIT_MUL also launches the FP32 add.
        S_COMPUTE,
        S_WAIT_MUL,
        // Accumulate: wait for the final add and commit the accumulator.
        S_ACCUMULATE,
        // Write: retain the partial C result and advance the output element.
        S_WRITE_LOCAL_RESULT,
        // Loop / next: advance the reduction tile or begin DDR stores.
        S_NEXT_TILE_K,
        // Write: DDR handshake; advance row/column/tile only on completion.
        S_PREFETCH_WRITE_RESULT,
        S_WRITE_RESULT,
        S_WAIT_WRITE_RESULT,
        // Done: hold completion until start is released.
        S_DONE
    } state_t;
    // Traversal, operand storage, and arithmetic status.
    state_t state;
    logic [31:0] tile_i, tile_j, tile_k, load_row, store_row;
    logic [31:0] clear_row, clear_col, comp_row, comp_col, comp_k;
    logic [31:0] tile_rows, tile_cols, tile_depth;
    logic reader_start, reader_done;
    logic writer_start, writer_done;
    logic [31:0] reader_base, writer_base;
    logic [31:0] reader_words, writer_words;
    logic [BUFFER_ADDR_WIDTH-1:0] reader_buffer_base, writer_buffer_base;
    logic [BUFFER_ADDR_WIDTH-1:0] a_ra, b_ra, c_addr;
    logic [31:0] a_data, b_data, c_data;
    logic c_we, mul_start, mul_result_valid;
    logic add_start, add_result_valid;
    logic [31:0] accumulator, mul_result, add_result;
    logic [63:0] byte_address;
    logic [31:0] direct_a, direct_b, store_col;
    // Private synchronous C tile retains exactly the buffered path's K-tile
    // partial sums. It is cleared per (tile_i,tile_j), never per tile_k.
    logic [31:0] direct_c_tile [0:TILE_SIZE*TILE_SIZE-1];
    logic [31:0] direct_c_data;
    logic [7:0] direct_c_address;
    assign direct_c_address = (state == S_PREFETCH_WRITE_RESULT ||
                               state == S_WRITE_RESULT || state == S_WAIT_WRITE_RESULT) ?
                              8'(store_row * TILE_SIZE + store_col) :
                              (state == S_CLEAR_RESULT) ? 8'(clear_row * TILE_SIZE + clear_col) :
                              8'(comp_row * TILE_SIZE + comp_col);
    always_ff @(posedge clk) begin
        direct_c_data <= direct_c_tile[direct_c_address];
        if (word_path && c_we)
            direct_c_tile[direct_c_address] <= (state == S_CLEAR_RESULT) ? 32'd0 : accumulator;
    end

    // Tail / extent and saturation helpers.
    function automatic logic [31:0] tile_extent(input logic [31:0] origin);
        logic [31:0] remaining;
        begin
            remaining   = size - origin;
            tile_extent = (remaining > TILE_SIZE) ? TILE_SIZE : remaining;
        end
    endfunction

    always_comb begin
        tile_rows  = tile_extent(tile_i);
        tile_cols  = tile_extent(tile_j);
        tile_depth = tile_extent(tile_k);
    end

    // Status and memory requests.
    assign busy = (state != S_IDLE) && (state != S_DONE);
    assign done = (state == S_DONE);
    always_comb begin
        case (state)
            S_LOAD_A, S_WAIT_LOAD_A: phase = 3'd1;
            S_LOAD_B, S_WAIT_LOAD_B: phase = 3'd2;
            S_PREFETCH_WRITE_RESULT, S_WRITE_RESULT, S_WAIT_WRITE_RESULT: phase = 3'd4;
            S_IDLE: phase = 3'd0;
            S_DONE: phase = 3'd5;
            default: phase = 3'd3;
        endcase
    end

    assign reader_start = !word_path && ((state == S_LOAD_A) || (state == S_LOAD_B));
    assign writer_start = !word_path && (state == S_WRITE_RESULT);
    always_comb begin
        reader_words = (state == S_LOAD_A) ? tile_depth : tile_cols;
        reader_buffer_base = (state == S_LOAD_A) ? (load_row * TILE_SIZE) : (load_row * TILE_SIZE);
        if (state == S_LOAD_A)
            byte_address = {32'd0, a_base} +
                           (((({32'd0, tile_i} + load_row) * size) + tile_k) << 2);
        else
            byte_address = {32'd0, b_base} +
                           (((({32'd0, tile_k} + load_row) * size) + tile_j) << 2);
        reader_base = byte_address[31:0];

        writer_words = tile_cols;
        writer_buffer_base = store_row * TILE_SIZE;
        byte_address = {32'd0, c_base} + (((({32'd0, tile_i} + store_row) * size) + tile_j) << 2);
        writer_base = byte_address[31:0];
    end

    assign reader_done = dma_rsp.read_done;
    assign writer_done = dma_rsp.write_done;
    assign a_data = word_path ? direct_a : buffer_rsp.a_data;
    assign b_data = word_path ? direct_b : buffer_rsp.b_data;
    assign c_data = word_path ? direct_c_data : buffer_rsp.c_data;
    always_comb begin
        word_req = '0;
        word_req.read_valid = word_path && (state == S_LOAD_A || state == S_LOAD_B);
        word_req.write_valid = word_path && state == S_WRITE_RESULT;
        if (state == S_LOAD_A)
            word_req.address = a_base + (((tile_i + comp_row) * size + tile_k + comp_k) << 2);
        else if (state == S_LOAD_B)
            word_req.address = b_base + (((tile_k + comp_k) * size + tile_j + comp_col) << 2);
        else
            word_req.address = c_base + (((tile_i + store_row) * size + tile_j + store_col) << 2);
        word_req.write_data = direct_c_data;
        dma_req = '0;
        buffer_req = '0;
        dma_req.read_valid = reader_start;
        dma_req.write_valid = writer_start;
        dma_req.read_address = reader_base;
        dma_req.read_words = reader_words;
        dma_req.write_address = writer_base;
        dma_req.write_words = writer_words;
        dma_req.burst_len = burst_len;
        buffer_req.read_offset = 32'(reader_buffer_base);
        buffer_req.write_offset = 32'(writer_buffer_base);
        buffer_req.load_a = (state == S_LOAD_A) || (state == S_WAIT_LOAD_A) || (state == S_LOAD_B);
        buffer_req.load_b = (state == S_LOAD_B) || (state == S_WAIT_LOAD_B) ||
                            (state == S_PREFETCH_RESULT);
        buffer_req.a_read_address = 32'(a_ra);
        buffer_req.b_read_address = 32'(b_ra);
        buffer_req.c_write_enable = !word_path && c_we;
        buffer_req.c_write_address = 32'(c_addr);
        buffer_req.c_write_data = (state == S_CLEAR_RESULT) ? 32'd0 : accumulator;
        buffer_req.c_read_address = 32'(c_addr);
    end

    assign a_ra = comp_row * TILE_SIZE + comp_k;
    assign b_ra = comp_k * TILE_SIZE + comp_col;
    assign c_addr = (state == S_CLEAR_RESULT) ?
                    (clear_row * TILE_SIZE + clear_col) :
                    (comp_row * TILE_SIZE + comp_col);
    assign c_we = (state == S_CLEAR_RESULT) || (state == S_WRITE_LOCAL_RESULT);
    assign mul_start = (state == S_COMPUTE);
    assign add_start = (state == S_WAIT_MUL) && mul_result_valid;
    // Arithmetic IP: retain every start condition and result-valid dependency.
    fp32_mul_wrapper mul_unit (
        .clk,
        .reset,
        .start(mul_start),
        .precision(3'd4),
        .operand_a(a_data),
        .operand_b(b_data),
        .busy(),
        .result_valid(mul_result_valid),
        .result(mul_result)
    );
    fp32_add_wrapper add_unit (
        .clk,
        .reset,
        .start(add_start),
        .precision(3'd4),
        .operand_a(accumulator),
        .operand_b(mul_result),
        .busy(),
        .result_valid(add_result_valid),
        .result(add_result)
    );
    assign operation_complete  = (state == S_WRITE_LOCAL_RESULT) && (tile_k + tile_depth >= size);
    assign arithmetic_progress = add_result_valid ? 32'd1 : 32'd0;

    // State transitions: loop updates stay on their original completion cycles.
    always_ff @(posedge clk) begin
        if (reset) begin
            state <= S_IDLE;
            tile_i <= 0;
            tile_j <= 0;
            tile_k <= 0;
            load_row <= 0;
            store_row <= 0;
            clear_row <= 0;
            clear_col <= 0;
            comp_row <= 0;
            comp_col <= 0;
            comp_k <= 0;
            accumulator <= 0;
            direct_a <= 0;
            direct_b <= 0;
            store_col <= 0;
        end else
            case (state)
                // Idle / command initialization.
                S_IDLE:
                if (start) begin
                    tile_i <= 0;
                    tile_j <= 0;
                    tile_k <= 0;
                    clear_row <= 0;
                    clear_col <= 0;
                    state <= (size == 0) ? S_DONE : S_CLEAR_RESULT;
                end
                // Prepare: clear the C tile before its first K tile.
                S_CLEAR_RESULT:
                if ((clear_row + 1 >= tile_rows) && (clear_col + 1 >= tile_cols)) begin
                    load_row <= 0;
                    comp_row <= 0;
                    comp_col <= 0;
                    comp_k <= 0;
                    state <= word_path ? S_PREFETCH_RESULT : S_LOAD_A;
                end else if (clear_col + 1 >= tile_cols) begin
                    clear_col <= 0;
                    clear_row <= clear_row + 1;
                end else clear_col <= clear_col + 1;
                // Load: issue requests and wait for data / DMA completion.
                S_LOAD_A: if (word_path ? word_rsp.ready : dma_rsp.read_ready) state <= S_WAIT_LOAD_A;
                S_WAIT_LOAD_A:
                if (word_path) begin
                    if (word_rsp.read_valid) begin
                        direct_a <= word_rsp.read_data;
                        state <= S_LOAD_B;
                    end
                end else if (reader_done) begin
                    if (load_row + 1 >= tile_rows) begin
                        load_row <= 0;
                        state <= S_LOAD_B;
                    end else begin
                        load_row <= load_row + 1;
                        state <= S_LOAD_A;
                    end
                end
                S_LOAD_B: if (word_path ? word_rsp.ready : dma_rsp.read_ready) state <= S_WAIT_LOAD_B;
                S_WAIT_LOAD_B:
                if (word_path) begin
                    if (word_rsp.read_valid) begin
                        direct_b <= word_rsp.read_data;
                        state <= S_COMPUTE;
                    end
                end else if (reader_done) begin
                    if (load_row + 1 >= tile_depth) begin
                        load_row <= 0;
                        comp_row <= 0;
                        comp_col <= 0;
                        comp_k <= 0;
                        state <= S_PREFETCH_RESULT;
                    end else begin
                        load_row <= load_row + 1;
                        state <= S_LOAD_B;
                    end
                end
                // Prepare: synchronous C read, accumulator capture, then A/B prefetch.
                S_PREFETCH_RESULT: state <= S_PREPARE_ACCUMULATOR;
                S_PREPARE_ACCUMULATOR: begin
                    accumulator <= c_data;
                    state <= S_PREFETCH_OPERANDS;
                end
                S_PREFETCH_OPERANDS: state <= word_path ? S_LOAD_A : S_COMPUTE;
                // Compute: launch multiply; WAIT_MUL also launches the FP32 add.
                S_COMPUTE: state <= S_WAIT_MUL;
                S_WAIT_MUL: if (mul_result_valid) state <= S_ACCUMULATE;
                // Accumulate: wait for the final add and commit the accumulator.
                S_ACCUMULATE:
                if (add_result_valid) begin
                    accumulator <= add_result;
                    if (comp_k + 1 >= tile_depth) state <= S_WRITE_LOCAL_RESULT;
                    else begin
                        comp_k <= comp_k + 1;
                        state  <= S_PREFETCH_OPERANDS;
                    end
                end
                // Write: retain the partial C result and advance the output element.
                S_WRITE_LOCAL_RESULT: begin
                    comp_k <= 0;
                    if (comp_col + 1 < tile_cols) begin
                        comp_col <= comp_col + 1;
                        state <= S_PREFETCH_RESULT;
                    end else if (comp_row + 1 < tile_rows) begin
                        comp_col <= 0;
                        comp_row <= comp_row + 1;
                        state <= S_PREFETCH_RESULT;
                    end else state <= S_NEXT_TILE_K;
                end
                // Loop / next: advance the reduction tile or begin DDR stores.
                S_NEXT_TILE_K: begin
                    if (tile_k + tile_depth < size) begin
                        tile_k <= tile_k + tile_depth;
                        load_row <= 0;
                        comp_row <= 0;
                        comp_col <= 0;
                        comp_k <= 0;
                        state <= word_path ? S_PREFETCH_RESULT : S_LOAD_A;
                    end else begin
                        store_row <= 0;
                        store_col <= 0;
                        state <= word_path ? S_PREFETCH_WRITE_RESULT : S_WRITE_RESULT;
                    end
                end
                // Write: DDR handshake; advance row/column/tile only on completion.
                S_PREFETCH_WRITE_RESULT: state <= S_WRITE_RESULT;
                S_WRITE_RESULT:
                if (word_path ? word_rsp.ready : dma_rsp.write_ready) state <= S_WAIT_WRITE_RESULT;
                S_WAIT_WRITE_RESULT:
                if (word_path || writer_done) begin
                    if (word_path && store_col + 1 < tile_cols) begin
                        store_col <= store_col + 1;
                        state <= S_PREFETCH_WRITE_RESULT;
                    end else if (store_row + 1 < tile_rows) begin
                        store_col <= 0;
                        store_row <= store_row + 1;
                        state <= word_path ? S_PREFETCH_WRITE_RESULT : S_WRITE_RESULT;
                    end else if (tile_j + tile_cols < size) begin
                        tile_j <= tile_j + tile_cols;
                        tile_k <= 0;
                        clear_row <= 0;
                        clear_col <= 0;
                        state <= S_CLEAR_RESULT;
                    end else if (tile_i + tile_rows < size) begin
                        tile_i <= tile_i + tile_rows;
                        tile_j <= 0;
                        tile_k <= 0;
                        clear_row <= 0;
                        clear_col <= 0;
                        state <= S_CLEAR_RESULT;
                    end else state <= S_DONE;
                end
                // Done: hold completion until start is released.
                S_DONE: if (!start) state <= S_IDLE;
                default: state <= S_IDLE;
            endcase
    end
endmodule
