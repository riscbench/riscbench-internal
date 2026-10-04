module workload_controller (
    input  logic        clk, reset, start,
    input  logic [2:0]  mode, precision,
    input  logic [1:0]  memory_policy,
    input  logic        busy,

    output logic [3:0]  selected_slot,
    output logic        word_path,
    output logic [14:0] compute_start
);

    logic [2:0] active_mode, active_precision;
    logic active_word_path;
    logic [3:0] request_slot;

    localparam logic [3:0] INVALID_SLOT = 4'd15;

    function automatic logic [3:0] decode_slot(
        input logic [2:0] m,
        input logic [2:0] p
    );
        case ({m,p})
            {3'd0,3'd4}: decode_slot = 4'd0;
            {3'd0,3'd1}: decode_slot = 4'd1;
            {3'd0,3'd0}: decode_slot = 4'd2;

            {3'd1,3'd4}: decode_slot = 4'd3;
            {3'd1,3'd1}: decode_slot = 4'd4;
            {3'd1,3'd0}: decode_slot = 4'd5;

            {3'd4,3'd4}: decode_slot = 4'd6;
            {3'd4,3'd1}: decode_slot = 4'd7;
            {3'd4,3'd0}: decode_slot = 4'd8;

            {3'd2,3'd4}: decode_slot = 4'd9;
            {3'd2,3'd1}: decode_slot = 4'd10;
            {3'd2,3'd0}: decode_slot = 4'd11;

            {3'd3,3'd4}: decode_slot = 4'd12;
            {3'd3,3'd1}: decode_slot = 4'd13;
            {3'd3,3'd0}: decode_slot = 4'd14;

            default:     decode_slot = INVALID_SLOT;
        endcase
    endfunction

    function automatic logic resolve_word_path(
        input logic [2:0] m,
        input logic [2:0] p,
        input logic [1:0] policy
    );
        logic [3:0] slot;
        begin
            slot = decode_slot(m, p);
            if (((m == 3'd0 || m == 3'd1) && slot < 4'd6) ||
                (m == 3'd4 && slot >= 4'd6 && slot < 4'd9) ||
                (m == 3'd2 && slot >= 4'd9 && slot < 4'd12) ||
                (m == 3'd3 && slot >= 4'd12 && slot < 4'd15)) begin
                case (policy)
                    2'b01: resolve_word_path = 1'b0;
                    2'b10: resolve_word_path = 1'b1;
                    default: resolve_word_path =
                        ((m == 3'd0 || m == 3'd1) && p == 3'd0) ||
                        (m == 3'd3 && (p == 3'd1 || p == 3'd0));
                endcase
            end else begin
                resolve_word_path = (slot == 4'd2)  ||
                                    (slot == 4'd5)  ||
                                    (slot == 4'd13) ||
                                    (slot == 4'd14);
            end
        end
    endfunction

    assign request_slot = decode_slot(mode, precision);
    assign selected_slot = decode_slot(active_mode, active_precision);

    always_ff @(posedge clk) begin
        if (reset) begin
            active_mode      <= 3'd0;
            active_precision <= 3'd4;
            active_word_path <= 1'b0;
        end
        else if (start && !busy && request_slot != INVALID_SLOT) begin
            active_mode      <= mode;
            active_precision <= precision;
            active_word_path <= resolve_word_path(mode, precision, memory_policy);
        end
    end

    always_comb begin
        compute_start = '0;

        if (start && !busy && request_slot != INVALID_SLOT)
            compute_start[request_slot] = 1'b1;
    end

    assign word_path = active_word_path;

endmodule
