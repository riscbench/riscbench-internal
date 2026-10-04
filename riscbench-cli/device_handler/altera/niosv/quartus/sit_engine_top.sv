// sit_engine_top.sv
module sit_engine_top (
    input  wire        CLK_50,
    input  wire        RESET,

    output wire [16:0] DDR4_A,
    output wire [1:0]  DDR4_BA,
    output wire        DDR4_BG,
    output wire        DDR4_ACT_N,
    output wire        DDR4_CKE,
    output wire        DDR4_CS_N,
    output wire        DDR4_ODT,
    output wire        DDR4_PAR,
    input  wire        DDR4_ALERT_N,

    inout  wire [31:0] DDR4_DQ,
    inout  wire [3:0]  DDR4_DQS_P,
    inout  wire [3:0]  DDR4_DQS_N,

    output wire        DDR4_CK_P,
    output wire        DDR4_CK_N,
    output wire        DDR4_RESET_N,

    input  wire        DDR4_RZQ,
    input  wire        DDR4_REFCLK_P,

    output wire        DDR4_CTRL_READY
);

    wire        axi4lite_awready_unused;
    wire        axi4lite_arready_unused;
    wire        axi4lite_wready_unused;
    wire [1:0]  axi4lite_bresp_unused;
    wire        axi4lite_bvalid_unused;
    wire [31:0] axi4lite_rdata_unused;
    wire [1:0]  axi4lite_rresp_unused;
    wire        axi4lite_rvalid_unused;

    niosv_bringup u_niosv_bringup (
        .clk_clk                                   (CLK_50),
        .reset_reset                               (RESET),

        .ddr4_ctrl_ready_reset_n                   (DDR4_CTRL_READY),

        .ddr4_mem_mem_cke                          (DDR4_CKE),
        .ddr4_mem_mem_odt                          (DDR4_ODT),
        .ddr4_mem_mem_cs_n                         (DDR4_CS_N),
        .ddr4_mem_mem_a                            (DDR4_A),
        .ddr4_mem_mem_ba                           (DDR4_BA),
        .ddr4_mem_mem_bg                           (DDR4_BG),
        .ddr4_mem_mem_act_n                        (DDR4_ACT_N),
        .ddr4_mem_mem_par                          (DDR4_PAR),
        .ddr4_mem_mem_dq                           (DDR4_DQ),
        .ddr4_mem_mem_dqs_t                        (DDR4_DQS_P),
        .ddr4_mem_mem_dqs_c                        (DDR4_DQS_N),
        .ddr4_mem_mem_alert_n                      (DDR4_ALERT_N),

        .ddr4_ck_mem_ck_t                          (DDR4_CK_P),
        .ddr4_ck_mem_ck_c                          (DDR4_CK_N),
        .ddr4_reset_n_mem_reset_n                  (DDR4_RESET_N),
        .ddr4_oct_oct_rzqin                        (DDR4_RZQ),
        .ddr4_ref_clk_clk                          (DDR4_REFCLK_P),

        // AXI4-Lite control port unused for initial DDR bring-up.
        .emif_io96b_ddr4comp_0_s0_axi4lite_awaddr  (27'b0),
        .emif_io96b_ddr4comp_0_s0_axi4lite_awprot  (3'b0),
        .emif_io96b_ddr4comp_0_s0_axi4lite_awvalid (1'b0),
        .emif_io96b_ddr4comp_0_s0_axi4lite_awready (axi4lite_awready_unused),

        .emif_io96b_ddr4comp_0_s0_axi4lite_araddr  (27'b0),
        .emif_io96b_ddr4comp_0_s0_axi4lite_arprot  (3'b0),
        .emif_io96b_ddr4comp_0_s0_axi4lite_arvalid (1'b0),
        .emif_io96b_ddr4comp_0_s0_axi4lite_arready (axi4lite_arready_unused),

        .emif_io96b_ddr4comp_0_s0_axi4lite_wdata   (32'b0),
        .emif_io96b_ddr4comp_0_s0_axi4lite_wstrb   (4'b0),
        .emif_io96b_ddr4comp_0_s0_axi4lite_wvalid  (1'b0),
        .emif_io96b_ddr4comp_0_s0_axi4lite_wready  (axi4lite_wready_unused),

        .emif_io96b_ddr4comp_0_s0_axi4lite_bready  (1'b1),
        .emif_io96b_ddr4comp_0_s0_axi4lite_bresp   (axi4lite_bresp_unused),
        .emif_io96b_ddr4comp_0_s0_axi4lite_bvalid  (axi4lite_bvalid_unused),

        .emif_io96b_ddr4comp_0_s0_axi4lite_rready  (1'b1),
        .emif_io96b_ddr4comp_0_s0_axi4lite_rdata   (axi4lite_rdata_unused),
        .emif_io96b_ddr4comp_0_s0_axi4lite_rresp   (axi4lite_rresp_unused),
        .emif_io96b_ddr4comp_0_s0_axi4lite_rvalid  (axi4lite_rvalid_unused)
    );

endmodule
