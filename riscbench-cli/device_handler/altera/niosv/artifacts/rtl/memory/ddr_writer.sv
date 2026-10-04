module ddr_writer #(
    parameter BUFFER_ADDR_WIDTH = 10
) (
    input  logic                         clk,
    input  logic                         reset,
    input  logic                         start,
    input  logic [31:0]                  base_address,
    input  logic [31:0]                  transfer_words,
    input  logic [BUFFER_ADDR_WIDTH-1:0] buffer_base_address,
    input  logic [7:0]                   burst_len,
    output logic                         busy,
    output logic                         done,
    output logic [BUFFER_ADDR_WIDTH-1:0] buffer_read_address,
    input  logic [31:0]                  buffer_read_data,
    output logic [31:0]                  m_address,
    output logic                         m_write,
    output logic [31:0]                  m_writedata,
    output logic [3:0]                   m_byteenable,
    output logic [7:0]                   m_burstcount,
    input  logic                         m_waitrequest
);
    typedef enum logic [2:0] {IDLE, PREFETCH, CAPTURE, WRITE} state_t;

    state_t state;
    logic [31:0] next_address;
    logic [31:0] words_remaining;
    logic [31:0] buffer_index;
    logic [8:0]  beats_remaining;
    logic [7:0]  configured_burst_len;

    function automatic logic [7:0] choose_burst(
        input logic [31:0] address,
        input logic [31:0] remaining,
        input logic [7:0]  requested
    );
        logic [31:0] candidate;
        logic [31:0] words_to_4k;
        begin
            candidate = (requested == 0) ? 32'd1 : {24'd0, requested};
            if (candidate > remaining)
                candidate = remaining;
            words_to_4k = (32'h0000_1000 - {20'd0, address[11:0]}) >> 2;
            if (candidate > words_to_4k)
                candidate = words_to_4k;
            choose_burst = candidate[7:0];
        end
    endfunction

    assign busy                = (state != IDLE);
    assign buffer_read_address = buffer_base_address +
                                 buffer_index[BUFFER_ADDR_WIDTH-1:0];
    assign m_address           = next_address;
    assign m_write             = (state == WRITE);
    assign m_byteenable        = 4'hf;

    always_ff @(posedge clk) begin
        if (reset) begin
            state                <= IDLE;
            done                 <= 1'b0;
            m_writedata          <= '0;
            m_burstcount         <= 8'd1;
            next_address         <= '0;
            words_remaining      <= '0;
            buffer_index         <= '0;
            beats_remaining      <= '0;
            configured_burst_len <= 8'd1;
        end else begin
            done <= 1'b0;

            case (state)
                IDLE: begin
                    if (start) begin
                        if (transfer_words == 0) begin
                            done <= 1'b1;
                        end else begin
                            next_address         <= base_address;
                            words_remaining      <= transfer_words;
                            buffer_index         <= 32'd0;
                            configured_burst_len <= (burst_len == 0) ? 8'd1 : burst_len;
                            m_burstcount         <= choose_burst(
                                base_address, transfer_words, burst_len
                            );
                            state <= PREFETCH;
                        end
                    end
                end

                // local_buffer has a synchronous read port. PREFETCH presents
                // the address for one clock; CAPTURE registers its result.
                PREFETCH: state <= CAPTURE;

                CAPTURE: begin
                    m_writedata <= buffer_read_data;
                    if (beats_remaining == 0)
                        beats_remaining <= {1'b0, m_burstcount};
                    state <= WRITE;
                end

                WRITE: begin
                    if (!m_waitrequest) begin
                        buffer_index    <= buffer_index + 1'b1;
                        words_remaining <= words_remaining - 1'b1;
                        beats_remaining <= beats_remaining - 1'b1;

                        if (words_remaining == 1) begin
                            done  <= 1'b1;
                            state <= IDLE;
                        end else if (beats_remaining == 1) begin
                            next_address <= next_address +
                                            ({24'd0, m_burstcount} << 2);
                            m_burstcount <= choose_burst(
                                next_address + ({24'd0, m_burstcount} << 2),
                                words_remaining - 1'b1,
                                configured_burst_len
                            );
                            beats_remaining <= '0;
                            state <= PREFETCH;
                        end else begin
                            state <= PREFETCH;
                        end
                    end
                end

                default: state <= IDLE;
            endcase
        end
    end
endmodule
