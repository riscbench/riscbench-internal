module sit_csr (
    input  logic        clk,
    input  logic        reset,
    input  logic [4:0]  avs_address,
    input  logic        avs_read,
    input  logic        avs_write,
    input  logic [31:0] avs_writedata,
    input  logic [3:0]  avs_byteenable,
    output logic [31:0] avs_readdata,
    output logic        avs_waitrequest,
    output logic        start,
    output logic [2:0]  mode,
    output logic [31:0] size,
    output logic [31:0] a_base,
    output logic [31:0] b_base,
    output logic [31:0] c_base,
    output logic [31:0] alpha,
    output logic [2:0]  precision,
    output logic [1:0]  memory_policy,
    output logic        monitor_enable,
    input  logic [63:0] total_cycles, active_cycles, mem_wait_cycles, ops_completed,
    input  logic        busy,
    input  logic        done,
    input  logic [3:0]  selected_slot,
    input  logic [2:0]  control_state,
    input  logic        operation_complete,
    input  logic        mem_stall
);
    localparam logic [4:0] ADDR_CTRL=5'h0, ADDR_STATUS=5'h1, ADDR_MODE=5'h2;
    localparam logic [4:0] ADDR_SIZE=5'h3, ADDR_A_BASE=5'h4, ADDR_B_BASE=5'h5;
    localparam logic [4:0] ADDR_C_BASE=5'h6, ADDR_ALPHA=5'hc;
    localparam logic [4:0] ADDR_PRECISION=5'h13;
    localparam logic [4:0] ADDR_MEMORY_POLICY=5'h8;
    localparam logic [4:0] ADDR_SELECTED_SLOT=5'h14, ADDR_CONTROL_STATE=5'h15;
    localparam logic [4:0] ADDR_OPERATION_COMPLETE=5'h16, ADDR_MEM_STALL=5'h17;

    // Word addresses (byte offset = word address * 4).
    localparam logic [4:0] ADDR_MONITOR_CTRL=5'h07;
    localparam logic [4:0] ADDR_TOTAL_CYCLES_LO=5'h18, ADDR_TOTAL_CYCLES_HI=5'h19;
    localparam logic [4:0] ADDR_ACTIVE_CYCLES_LO=5'h1a, ADDR_ACTIVE_CYCLES_HI=5'h1b;
    localparam logic [4:0] ADDR_MEM_WAIT_CYCLES_LO=5'h1c, ADDR_MEM_WAIT_CYCLES_HI=5'h1d;
    localparam logic [4:0] ADDR_OPS_COMPLETED_LO=5'h1e, ADDR_OPS_COMPLETED_HI=5'h1f;

    logic done_sticky;

    assign avs_waitrequest = 1'b0;

    always_ff @(posedge clk) begin
        if (reset) begin
            start       <= 1'b0;
            mode        <= 3'd0;
            size        <= 32'd0;
            a_base      <= 32'd0;
            b_base      <= 32'd0;
            c_base      <= 32'd0;
            alpha       <= 32'd0;
            precision   <= 3'd4;
            memory_policy <= 2'b00;
            monitor_enable <= 1'b0;
            done_sticky <= 1'b0;
        end else begin
            start <= 1'b0;

            if (done)
                done_sticky <= 1'b1;

            if (avs_write) begin
                case (avs_address)
                    ADDR_CTRL: begin
                        if (avs_byteenable[0] && avs_writedata[0] && !busy) begin
                            start       <= 1'b1;
                            done_sticky <= 1'b0;
                        end
                    end
                    ADDR_MODE: begin
                        if (avs_byteenable[0])
                            mode <= avs_writedata[2:0];
                    end
                    ADDR_SIZE: begin
                        if (avs_byteenable[0]) size[7:0]   <= avs_writedata[7:0];
                        if (avs_byteenable[1]) size[15:8]  <= avs_writedata[15:8];
                        if (avs_byteenable[2]) size[23:16] <= avs_writedata[23:16];
                        if (avs_byteenable[3]) size[31:24] <= avs_writedata[31:24];
                    end
                    ADDR_A_BASE: begin
                        if (avs_byteenable[0]) a_base[7:0]   <= avs_writedata[7:0];
                        if (avs_byteenable[1]) a_base[15:8]  <= avs_writedata[15:8];
                        if (avs_byteenable[2]) a_base[23:16] <= avs_writedata[23:16];
                        if (avs_byteenable[3]) a_base[31:24] <= avs_writedata[31:24];
                    end
                    ADDR_B_BASE: begin
                        if (avs_byteenable[0]) b_base[7:0]   <= avs_writedata[7:0];
                        if (avs_byteenable[1]) b_base[15:8]  <= avs_writedata[15:8];
                        if (avs_byteenable[2]) b_base[23:16] <= avs_writedata[23:16];
                        if (avs_byteenable[3]) b_base[31:24] <= avs_writedata[31:24];
                    end
                    ADDR_C_BASE: begin
                        if (avs_byteenable[0]) c_base[7:0]   <= avs_writedata[7:0];
                        if (avs_byteenable[1]) c_base[15:8]  <= avs_writedata[15:8];
                        if (avs_byteenable[2]) c_base[23:16] <= avs_writedata[23:16];
                        if (avs_byteenable[3]) c_base[31:24] <= avs_writedata[31:24];
                    end
                    ADDR_ALPHA: begin
                        if (avs_byteenable[0]) alpha[7:0]   <= avs_writedata[7:0];
                        if (avs_byteenable[1]) alpha[15:8]  <= avs_writedata[15:8];
                        if (avs_byteenable[2]) alpha[23:16] <= avs_writedata[23:16];
                        if (avs_byteenable[3]) alpha[31:24] <= avs_writedata[31:24];
                    end
                    ADDR_PRECISION: if (avs_byteenable[0])
                        precision <= avs_writedata[2:0];
                    ADDR_MONITOR_CTRL: if (avs_byteenable[0])
                        monitor_enable <= avs_writedata[0];
                    // Counter addresses deliberately have no write cases.
                    ADDR_MEMORY_POLICY: if (avs_byteenable[0] &&
                                            avs_writedata[1:0] != 2'b11)
                        memory_policy <= avs_writedata[1:0];
                    default: ;
                endcase
            end
        end
    end

    always_comb begin
        avs_readdata = 32'd0;
        if (avs_read) begin
            case (avs_address)
                ADDR_MONITOR_CTRL: avs_readdata = {31'd0, monitor_enable};
                ADDR_TOTAL_CYCLES_LO: avs_readdata = total_cycles[31:0];
                ADDR_TOTAL_CYCLES_HI: avs_readdata = total_cycles[63:32];
                ADDR_ACTIVE_CYCLES_LO: avs_readdata = active_cycles[31:0];
                ADDR_ACTIVE_CYCLES_HI: avs_readdata = active_cycles[63:32];
                ADDR_MEM_WAIT_CYCLES_LO: avs_readdata = mem_wait_cycles[31:0];
                ADDR_MEM_WAIT_CYCLES_HI: avs_readdata = mem_wait_cycles[63:32];
                ADDR_OPS_COMPLETED_LO: avs_readdata = ops_completed[31:0];
                ADDR_OPS_COMPLETED_HI: avs_readdata = ops_completed[63:32];
                ADDR_CTRL:            avs_readdata = 32'd0;
                ADDR_STATUS:          avs_readdata = {30'd0, done_sticky, busy};
                ADDR_MODE:            avs_readdata = {29'd0, mode};
                ADDR_SIZE:            avs_readdata = size;
                ADDR_A_BASE:          avs_readdata = a_base;
                ADDR_B_BASE:          avs_readdata = b_base;
                ADDR_C_BASE:          avs_readdata = c_base;
                ADDR_ALPHA:           avs_readdata = alpha;
                ADDR_PRECISION:       avs_readdata = {29'd0,precision};
                ADDR_MEMORY_POLICY:   avs_readdata = {30'd0,memory_policy};
                ADDR_SELECTED_SLOT:   avs_readdata = {28'd0,selected_slot};
                ADDR_CONTROL_STATE:   avs_readdata = {29'd0,control_state};
                ADDR_OPERATION_COMPLETE: avs_readdata = {31'd0,operation_complete};
                ADDR_MEM_STALL:       avs_readdata = {31'd0,mem_stall};
                default:              avs_readdata = 32'd0;
            endcase
        end
    end
endmodule
