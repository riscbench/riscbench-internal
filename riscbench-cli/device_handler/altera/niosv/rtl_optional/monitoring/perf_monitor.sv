// Passive observer: start must be an accepted-workload pulse (SIT: |compute_start).
// Reset is synchronous and active high. Reset/start clear even while disabled.
// Event inputs must be qualified for the selected workload; completion need not
// coincide with busy. Outputs must never drive execution logic.
module perf_monitor (
    input logic clk, reset, monitor_enable, start, busy,
    input logic compute_active, mem_wait, operation_complete,
    output logic [63:0] total_cycles, active_cycles, mem_wait_cycles, ops_completed
);
    localparam logic [63:0] COUNTER_MAX = 64'hFFFF_FFFF_FFFF_FFFF;
    always_ff @(posedge clk) begin
        if (reset || start) begin
            total_cycles <= 64'd0;
            active_cycles <= 64'd0;
            mem_wait_cycles <= 64'd0;
            ops_completed <= 64'd0;
        end else if (monitor_enable) begin
            if (busy && total_cycles != COUNTER_MAX)
                total_cycles <= total_cycles + 64'd1;
            if (compute_active && active_cycles != COUNTER_MAX)
                active_cycles <= active_cycles + 64'd1;
            if (mem_wait && mem_wait_cycles != COUNTER_MAX)
                mem_wait_cycles <= mem_wait_cycles + 64'd1;
            if (operation_complete && ops_completed != COUNTER_MAX)
                ops_completed <= ops_completed + 64'd1;
        end
    end
endmodule
