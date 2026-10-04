module local_buffer #(
    parameter DATA_WIDTH = 32,
    parameter DEPTH      = 1024,
    parameter ADDR_WIDTH = $clog2(DEPTH)
) (
    input  logic                  clk,
    input  logic                  write_enable,
    input  logic [ADDR_WIDTH-1:0] write_address,
    input  logic [DATA_WIDTH-1:0] write_data,
    input  logic [ADDR_WIDTH-1:0] read_address,
    output logic [DATA_WIDTH-1:0] read_data
);
    // Synchronous read and registered write infer FPGA block RAM.
    logic [DATA_WIDTH-1:0] memory [0:DEPTH-1];

    always_ff @(posedge clk) begin
        if (write_enable)
            memory[write_address] <= write_data;
        read_data <= memory[read_address];
    end
endmodule
