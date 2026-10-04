// Coordinates buffered DDR transactions, direct-word requests, and the shared
// Avalon master. Compute-side local buffers are owned by sit_engine.
module data_mover #(
    parameter BUFFER_ADDR_WIDTH = 10
) (
    input logic clk, reset, owner_valid, word_path,
    input data_mover_pkg::buffered_request_t dma_req,
    output data_mover_pkg::buffered_response_t dma_rsp,
    input logic [BUFFER_ADDR_WIDTH-1:0] read_buffer_offset,
    input logic [BUFFER_ADDR_WIDTH-1:0] write_buffer_offset,
    output logic reader_buffer_write_enable,
    output logic [BUFFER_ADDR_WIDTH-1:0] reader_buffer_write_address,
    output logic [31:0] reader_buffer_write_data,
    output logic writer_buffer_active,
    output logic [BUFFER_ADDR_WIDTH-1:0] writer_buffer_read_address,
    input logic [31:0] writer_buffer_read_data,
    input data_mover_pkg::word_request_t word_req,
    output data_mover_pkg::word_response_t word_rsp,
    output logic [31:0] avm_address, avm_writedata,
    output logic avm_read, avm_write,
    output logic [3:0] avm_byteenable,
    output logic [7:0] avm_burstcount,
    input logic avm_waitrequest,
    input logic [31:0] avm_readdata,
    input logic avm_readdatavalid
);
    logic buffered_owner;

    // ---------------------------------------------------------------------
    // Control / path selection
    // ---------------------------------------------------------------------
    assign buffered_owner = owner_valid && !word_path;

    // ---------------------------------------------------------------------
    // Buffered DDR transactions
    // ---------------------------------------------------------------------
    logic [31:0] read_address, write_address, write_data;
    logic read_request, write_request;
    logic [7:0] read_burstcount, write_burstcount;
    logic [3:0] write_byteenable;
    logic read_busy, write_busy, read_done, write_done;

    assign dma_rsp.read_ready = buffered_owner && !read_busy;
    assign dma_rsp.write_ready = buffered_owner && !write_busy;
    assign dma_rsp.read_busy = read_busy;
    assign dma_rsp.write_busy = write_busy;
    assign dma_rsp.read_done = read_done;
    assign dma_rsp.write_done = write_done;

    ddr_reader #(.BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)) reader (
        .clk, .reset,
        .start(dma_req.read_valid && buffered_owner && !read_busy),
        .base_address(dma_req.read_address),
        .transfer_words(dma_req.read_words),
        .buffer_base_address(read_buffer_offset),
        .burst_len(dma_req.burst_len),
        .busy(read_busy), .done(read_done),
        .buffer_write_enable(reader_buffer_write_enable),
        .buffer_write_address(reader_buffer_write_address),
        .buffer_write_data(reader_buffer_write_data),
        .m_address(read_address), .m_read(read_request),
        .m_burstcount(read_burstcount),
        .m_waitrequest(avm_waitrequest),
        .m_readdata(avm_readdata), .m_readdatavalid(avm_readdatavalid)
    );

    ddr_writer #(.BUFFER_ADDR_WIDTH(BUFFER_ADDR_WIDTH)) writer (
        .clk, .reset,
        .start(dma_req.write_valid && buffered_owner && !write_busy),
        .base_address(dma_req.write_address),
        .transfer_words(dma_req.write_words),
        .buffer_base_address(write_buffer_offset),
        .burst_len(dma_req.burst_len),
        .busy(write_busy), .done(write_done),
        .buffer_read_address(writer_buffer_read_address),
        .buffer_read_data(writer_buffer_read_data),
        .m_address(write_address), .m_write(write_request),
        .m_writedata(write_data), .m_byteenable(write_byteenable),
        .m_burstcount(write_burstcount), .m_waitrequest(avm_waitrequest)
    );

    // Include the request and completion cycles to preserve the synchronous
    // C-buffer address selection across the writer's full start/wait window.
    assign writer_buffer_active = buffered_owner &&
                                  (write_busy || dma_req.write_valid || write_done);

    // ---------------------------------------------------------------------
    // Direct-word interface
    // ---------------------------------------------------------------------
    assign word_rsp.ready = owner_valid && word_path && !avm_waitrequest;
    assign word_rsp.read_valid = owner_valid && word_path && avm_readdatavalid;
    assign word_rsp.read_data = avm_readdata;

    // ---------------------------------------------------------------------
    // Single Avalon-MM master routing
    // ---------------------------------------------------------------------
    always_comb begin
        avm_address = '0;
        avm_read = 1'b0;
        avm_write = 1'b0;
        avm_writedata = '0;
        avm_byteenable = '0;
        avm_burstcount = '0;

        if (buffered_owner) begin
            avm_address = read_address;
            avm_read = read_request;
            avm_byteenable = 4'hf;
            avm_burstcount = read_burstcount;
        end

        if (buffered_owner && writer_buffer_active) begin
            avm_address = write_address;
            avm_read = 1'b0;
            avm_write = write_request;
            avm_writedata = write_data;
            avm_byteenable = write_byteenable;
            avm_burstcount = write_burstcount;
        end

        if (owner_valid && word_path) begin
            avm_address = word_req.address;
            avm_writedata = word_req.write_data;
            avm_read = word_req.read_valid;
            avm_write = word_req.write_valid;
            avm_byteenable = 4'hf;
            avm_burstcount = 8'd1;
        end
    end

    // ---------------------------------------------------------------------
    // Assertions
    // ---------------------------------------------------------------------
`ifndef SYNTHESIS
    always_ff @(posedge clk) if (!reset && owner_valid) begin
        assert (!(dma_req.read_valid && dma_req.write_valid));
        assert (!(word_req.read_valid && word_req.write_valid));
    end
`endif
endmodule
