-- Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
-- Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
-- --------------------------------------------------------------------------------
-- Tool Version: Vivado v.2026.1 (win64) Build 6511674 Tue Jun 16 11:02:23 MDT 2026
-- Date        : Fri Jul 31 14:21:38 2026
-- Host        : Protox-PC running 64-bit major release  (build 9200)
-- Command     : write_vhdl -force -mode funcsim -rename_top decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix -prefix
--               decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_ design_1_CUSTOM_addsub1b_0_0_sim_netlist.vhdl
-- Design      : design_1_CUSTOM_addsub1b_0_0
-- Purpose     : This VHDL netlist is a functional simulation representation of the design and should not be modified or
--               synthesized. This netlist cannot be used for SDF annotated simulation.
-- Device      : xc7a35ticsg324-1L
-- --------------------------------------------------------------------------------
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
library UNISIM;
use UNISIM.VCOMPONENTS.ALL;
entity decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_CUSTOM_addsub1b_slave_lite_v1_0_S00_AXI is
  port (
    axi_awready_reg_0 : out STD_LOGIC;
    axi_arready_reg_0 : out STD_LOGIC;
    axi_rvalid_reg_0 : out STD_LOGIC;
    s00_axi_rdata : out STD_LOGIC_VECTOR ( 31 downto 0 );
    s00_axi_bvalid : out STD_LOGIC;
    data_in_ip : out STD_LOGIC;
    s00_axi_wready : out STD_LOGIC;
    s00_axi_awvalid : in STD_LOGIC;
    s00_axi_wvalid : in STD_LOGIC;
    s00_axi_aclk : in STD_LOGIC;
    s00_axi_arvalid : in STD_LOGIC;
    s00_axi_rready : in STD_LOGIC;
    s00_axi_awaddr : in STD_LOGIC_VECTOR ( 1 downto 0 );
    s00_axi_araddr : in STD_LOGIC_VECTOR ( 1 downto 0 );
    s00_axi_aresetn : in STD_LOGIC;
    s00_axi_wdata : in STD_LOGIC_VECTOR ( 31 downto 0 );
    s00_axi_wstrb : in STD_LOGIC_VECTOR ( 3 downto 0 );
    s00_axi_bready : in STD_LOGIC
  );
end decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_CUSTOM_addsub1b_slave_lite_v1_0_S00_AXI;

architecture STRUCTURE of decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_CUSTOM_addsub1b_slave_lite_v1_0_S00_AXI is
  signal \FSM_sequential_state_read[0]_i_1_n_0\ : STD_LOGIC;
  signal \FSM_sequential_state_read[1]_i_1_n_0\ : STD_LOGIC;
  signal \FSM_sequential_state_write[0]_i_1_n_0\ : STD_LOGIC;
  signal \FSM_sequential_state_write[1]_i_1_n_0\ : STD_LOGIC;
  signal \axi_araddr[2]_i_1_n_0\ : STD_LOGIC;
  signal \axi_araddr[3]_i_1_n_0\ : STD_LOGIC;
  signal \axi_arready0__0\ : STD_LOGIC;
  signal axi_arready_i_1_n_0 : STD_LOGIC;
  signal \^axi_arready_reg_0\ : STD_LOGIC;
  signal \axi_awaddr[2]_i_1_n_0\ : STD_LOGIC;
  signal \axi_awaddr[3]_i_1_n_0\ : STD_LOGIC;
  signal \axi_awaddr_reg_n_0_[2]\ : STD_LOGIC;
  signal \axi_awaddr_reg_n_0_[3]\ : STD_LOGIC;
  signal \axi_awready0__0\ : STD_LOGIC;
  signal axi_awready_i_1_n_0 : STD_LOGIC;
  signal \^axi_awready_reg_0\ : STD_LOGIC;
  signal axi_bvalid_i_1_n_0 : STD_LOGIC;
  signal axi_rvalid_i_1_n_0 : STD_LOGIC;
  signal \^axi_rvalid_reg_0\ : STD_LOGIC;
  signal axi_wready_i_1_n_0 : STD_LOGIC;
  signal \^data_in_ip\ : STD_LOGIC;
  signal data_in_ip_i_1_n_0 : STD_LOGIC;
  signal data_in_ip_i_2_n_0 : STD_LOGIC;
  signal data_in_ip_i_3_n_0 : STD_LOGIC;
  signal data_in_ip_i_4_n_0 : STD_LOGIC;
  signal p_0_in : STD_LOGIC_VECTOR ( 1 downto 0 );
  signal p_1_in : STD_LOGIC_VECTOR ( 31 downto 7 );
  signal \^s00_axi_bvalid\ : STD_LOGIC;
  signal \^s00_axi_wready\ : STD_LOGIC;
  signal slv_reg0 : STD_LOGIC_VECTOR ( 31 downto 0 );
  signal \slv_reg0[15]_i_1_n_0\ : STD_LOGIC;
  signal \slv_reg0[23]_i_1_n_0\ : STD_LOGIC;
  signal \slv_reg0[31]_i_1_n_0\ : STD_LOGIC;
  signal \slv_reg0[31]_i_2_n_0\ : STD_LOGIC;
  signal \slv_reg0[7]_i_1_n_0\ : STD_LOGIC;
  signal slv_reg1 : STD_LOGIC_VECTOR ( 31 downto 0 );
  signal \slv_reg1[15]_i_1_n_0\ : STD_LOGIC;
  signal \slv_reg1[23]_i_1_n_0\ : STD_LOGIC;
  signal \slv_reg1[31]_i_1_n_0\ : STD_LOGIC;
  signal \slv_reg1[31]_i_2_n_0\ : STD_LOGIC;
  signal \slv_reg1[7]_i_1_n_0\ : STD_LOGIC;
  signal slv_reg2_reg : STD_LOGIC_VECTOR ( 31 downto 0 );
  signal \slv_reg2_reg0_carry__0_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__0_n_1\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__0_n_2\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__0_n_3\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__0_n_4\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__0_n_5\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__0_n_6\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__0_n_7\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__1_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__1_n_1\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__1_n_2\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__1_n_3\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__1_n_4\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__1_n_5\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__1_n_6\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__1_n_7\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__2_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__2_n_1\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__2_n_2\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__2_n_3\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__2_n_4\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__2_n_5\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__2_n_6\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__2_n_7\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__3_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__3_n_1\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__3_n_2\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__3_n_3\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__3_n_4\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__3_n_5\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__3_n_6\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__3_n_7\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__4_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__4_n_1\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__4_n_2\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__4_n_3\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__4_n_4\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__4_n_5\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__4_n_6\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__4_n_7\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__5_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__5_n_1\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__5_n_2\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__5_n_3\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__5_n_4\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__5_n_5\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__5_n_6\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__5_n_7\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__6_n_1\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__6_n_2\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__6_n_3\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__6_n_4\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__6_n_5\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__6_n_6\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry__6_n_7\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_1__0_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_1__1_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_1__2_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_1__3_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_1__4_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_1__5_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_1__6_n_0\ : STD_LOGIC;
  signal slv_reg2_reg0_carry_i_1_n_0 : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_2__0_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_2__1_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_2__2_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_2__3_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_2__4_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_2__5_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_2__6_n_0\ : STD_LOGIC;
  signal slv_reg2_reg0_carry_i_2_n_0 : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_3__0_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_3__1_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_3__2_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_3__3_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_3__4_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_3__5_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_3__6_n_0\ : STD_LOGIC;
  signal slv_reg2_reg0_carry_i_3_n_0 : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_4__0_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_4__1_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_4__2_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_4__3_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_4__4_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_4__5_n_0\ : STD_LOGIC;
  signal \slv_reg2_reg0_carry_i_4__6_n_0\ : STD_LOGIC;
  signal slv_reg2_reg0_carry_i_4_n_0 : STD_LOGIC;
  signal slv_reg2_reg0_carry_n_0 : STD_LOGIC;
  signal slv_reg2_reg0_carry_n_1 : STD_LOGIC;
  signal slv_reg2_reg0_carry_n_2 : STD_LOGIC;
  signal slv_reg2_reg0_carry_n_3 : STD_LOGIC;
  signal slv_reg2_reg0_carry_n_4 : STD_LOGIC;
  signal slv_reg2_reg0_carry_n_5 : STD_LOGIC;
  signal slv_reg2_reg0_carry_n_6 : STD_LOGIC;
  signal slv_reg2_reg0_carry_n_7 : STD_LOGIC;
  signal slv_reg3 : STD_LOGIC_VECTOR ( 31 downto 0 );
  signal \slv_reg3[31]_i_2_n_0\ : STD_LOGIC;
  signal state_read : STD_LOGIC_VECTOR ( 1 downto 0 );
  signal state_write : STD_LOGIC_VECTOR ( 1 downto 0 );
  signal \NLW_slv_reg2_reg0_carry__6_CO_UNCONNECTED\ : STD_LOGIC_VECTOR ( 3 to 3 );
  attribute FSM_ENCODED_STATES : string;
  attribute FSM_ENCODED_STATES of \FSM_sequential_state_read_reg[0]\ : label is "Idle:00,Rdata:10,Raddr:01";
  attribute FSM_ENCODED_STATES of \FSM_sequential_state_read_reg[1]\ : label is "Idle:00,Rdata:10,Raddr:01";
  attribute SOFT_HLUTNM : string;
  attribute SOFT_HLUTNM of \FSM_sequential_state_write[0]_i_1\ : label is "soft_lutpair0";
  attribute SOFT_HLUTNM of \FSM_sequential_state_write[1]_i_1\ : label is "soft_lutpair0";
  attribute FSM_ENCODED_STATES of \FSM_sequential_state_write_reg[0]\ : label is "Idle:00,Wdata:10,Waddr:01";
  attribute FSM_ENCODED_STATES of \FSM_sequential_state_write_reg[1]\ : label is "Idle:00,Wdata:10,Waddr:01";
  attribute SOFT_HLUTNM of axi_awready_i_1 : label is "soft_lutpair1";
  attribute SOFT_HLUTNM of axi_bvalid_i_2 : label is "soft_lutpair1";
  attribute ADDER_THRESHOLD : integer;
  attribute ADDER_THRESHOLD of slv_reg2_reg0_carry : label is 35;
  attribute ADDER_THRESHOLD of \slv_reg2_reg0_carry__0\ : label is 35;
  attribute ADDER_THRESHOLD of \slv_reg2_reg0_carry__1\ : label is 35;
  attribute ADDER_THRESHOLD of \slv_reg2_reg0_carry__2\ : label is 35;
  attribute ADDER_THRESHOLD of \slv_reg2_reg0_carry__3\ : label is 35;
  attribute ADDER_THRESHOLD of \slv_reg2_reg0_carry__4\ : label is 35;
  attribute ADDER_THRESHOLD of \slv_reg2_reg0_carry__5\ : label is 35;
  attribute ADDER_THRESHOLD of \slv_reg2_reg0_carry__6\ : label is 35;
begin
  axi_arready_reg_0 <= \^axi_arready_reg_0\;
  axi_awready_reg_0 <= \^axi_awready_reg_0\;
  axi_rvalid_reg_0 <= \^axi_rvalid_reg_0\;
  data_in_ip <= \^data_in_ip\;
  s00_axi_bvalid <= \^s00_axi_bvalid\;
  s00_axi_wready <= \^s00_axi_wready\;
\FSM_sequential_state_read[0]_i_1\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"FFFF88880FFFFFFF"
    )
        port map (
      I0 => s00_axi_rready,
      I1 => \^axi_rvalid_reg_0\,
      I2 => s00_axi_arvalid,
      I3 => \^axi_arready_reg_0\,
      I4 => state_read(0),
      I5 => state_read(1),
      O => \FSM_sequential_state_read[0]_i_1_n_0\
    );
\FSM_sequential_state_read[1]_i_1\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"FFFF0FFF88880000"
    )
        port map (
      I0 => s00_axi_arvalid,
      I1 => \^axi_arready_reg_0\,
      I2 => s00_axi_rready,
      I3 => \^axi_rvalid_reg_0\,
      I4 => state_read(0),
      I5 => state_read(1),
      O => \FSM_sequential_state_read[1]_i_1_n_0\
    );
\FSM_sequential_state_read_reg[0]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \FSM_sequential_state_read[0]_i_1_n_0\,
      Q => state_read(0),
      R => data_in_ip_i_1_n_0
    );
\FSM_sequential_state_read_reg[1]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \FSM_sequential_state_read[1]_i_1_n_0\,
      Q => state_read(1),
      R => data_in_ip_i_1_n_0
    );
\FSM_sequential_state_write[0]_i_1\: unisim.vcomponents.LUT5
    generic map(
      INIT => X"FFF0F7FF"
    )
        port map (
      I0 => \^axi_awready_reg_0\,
      I1 => s00_axi_awvalid,
      I2 => s00_axi_wvalid,
      I3 => state_write(0),
      I4 => state_write(1),
      O => \FSM_sequential_state_write[0]_i_1_n_0\
    );
\FSM_sequential_state_write[1]_i_1\: unisim.vcomponents.LUT5
    generic map(
      INIT => X"FF0F0800"
    )
        port map (
      I0 => \^axi_awready_reg_0\,
      I1 => s00_axi_awvalid,
      I2 => s00_axi_wvalid,
      I3 => state_write(0),
      I4 => state_write(1),
      O => \FSM_sequential_state_write[1]_i_1_n_0\
    );
\FSM_sequential_state_write_reg[0]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \FSM_sequential_state_write[0]_i_1_n_0\,
      Q => state_write(0),
      R => data_in_ip_i_1_n_0
    );
\FSM_sequential_state_write_reg[1]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \FSM_sequential_state_write[1]_i_1_n_0\,
      Q => state_write(1),
      R => data_in_ip_i_1_n_0
    );
\axi_araddr[2]_i_1\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"FFBFFFFF00800000"
    )
        port map (
      I0 => s00_axi_araddr(0),
      I1 => s00_axi_aresetn,
      I2 => state_read(0),
      I3 => state_read(1),
      I4 => \axi_arready0__0\,
      I5 => p_0_in(0),
      O => \axi_araddr[2]_i_1_n_0\
    );
\axi_araddr[3]_i_1\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"FFBFFFFF00800000"
    )
        port map (
      I0 => s00_axi_araddr(1),
      I1 => s00_axi_aresetn,
      I2 => state_read(0),
      I3 => state_read(1),
      I4 => \axi_arready0__0\,
      I5 => p_0_in(1),
      O => \axi_araddr[3]_i_1_n_0\
    );
\axi_araddr[3]_i_2\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => s00_axi_arvalid,
      I1 => \^axi_arready_reg_0\,
      O => \axi_arready0__0\
    );
\axi_araddr_reg[2]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \axi_araddr[2]_i_1_n_0\,
      Q => p_0_in(0),
      R => '0'
    );
\axi_araddr_reg[3]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \axi_araddr[3]_i_1_n_0\,
      Q => p_0_in(1),
      R => '0'
    );
axi_arready_i_1: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CFCCCCCC4F4F4F4F"
    )
        port map (
      I0 => s00_axi_arvalid,
      I1 => \^axi_arready_reg_0\,
      I2 => state_read(0),
      I3 => s00_axi_rready,
      I4 => \^axi_rvalid_reg_0\,
      I5 => state_read(1),
      O => axi_arready_i_1_n_0
    );
axi_arready_reg: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => axi_arready_i_1_n_0,
      Q => \^axi_arready_reg_0\,
      R => data_in_ip_i_1_n_0
    );
\axi_awaddr[2]_i_1\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"EFFFFFFF20000000"
    )
        port map (
      I0 => s00_axi_awaddr(0),
      I1 => state_write(1),
      I2 => s00_axi_awvalid,
      I3 => \^axi_awready_reg_0\,
      I4 => state_write(0),
      I5 => \axi_awaddr_reg_n_0_[2]\,
      O => \axi_awaddr[2]_i_1_n_0\
    );
\axi_awaddr[3]_i_1\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"EFFFFFFF20000000"
    )
        port map (
      I0 => s00_axi_awaddr(1),
      I1 => state_write(1),
      I2 => s00_axi_awvalid,
      I3 => \^axi_awready_reg_0\,
      I4 => state_write(0),
      I5 => \axi_awaddr_reg_n_0_[3]\,
      O => \axi_awaddr[3]_i_1_n_0\
    );
\axi_awaddr_reg[2]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \axi_awaddr[2]_i_1_n_0\,
      Q => \axi_awaddr_reg_n_0_[2]\,
      R => data_in_ip_i_1_n_0
    );
\axi_awaddr_reg[3]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \axi_awaddr[3]_i_1_n_0\,
      Q => \axi_awaddr_reg_n_0_[3]\,
      R => data_in_ip_i_1_n_0
    );
axi_awready_i_1: unisim.vcomponents.LUT5
    generic map(
      INIT => X"CFCCCF4F"
    )
        port map (
      I0 => s00_axi_awvalid,
      I1 => \^axi_awready_reg_0\,
      I2 => state_write(0),
      I3 => s00_axi_wvalid,
      I4 => state_write(1),
      O => axi_awready_i_1_n_0
    );
axi_awready_reg: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => axi_awready_i_1_n_0,
      Q => \^axi_awready_reg_0\,
      R => data_in_ip_i_1_n_0
    );
axi_bvalid_i_1: unisim.vcomponents.LUT6
    generic map(
      INIT => X"AAF2AA22F2AAF2AA"
    )
        port map (
      I0 => \^s00_axi_bvalid\,
      I1 => s00_axi_bready,
      I2 => s00_axi_wvalid,
      I3 => state_write(1),
      I4 => \axi_awready0__0\,
      I5 => state_write(0),
      O => axi_bvalid_i_1_n_0
    );
axi_bvalid_i_2: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => s00_axi_awvalid,
      I1 => \^axi_awready_reg_0\,
      O => \axi_awready0__0\
    );
axi_bvalid_reg: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => axi_bvalid_i_1_n_0,
      Q => \^s00_axi_bvalid\,
      R => data_in_ip_i_1_n_0
    );
axi_rvalid_i_1: unisim.vcomponents.LUT6
    generic map(
      INIT => X"F0F0F8F800F0F0F0"
    )
        port map (
      I0 => \^axi_arready_reg_0\,
      I1 => s00_axi_arvalid,
      I2 => \^axi_rvalid_reg_0\,
      I3 => s00_axi_rready,
      I4 => state_read(1),
      I5 => state_read(0),
      O => axi_rvalid_i_1_n_0
    );
axi_rvalid_reg: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => axi_rvalid_i_1_n_0,
      Q => \^axi_rvalid_reg_0\,
      R => data_in_ip_i_1_n_0
    );
axi_wready_i_1: unisim.vcomponents.LUT3
    generic map(
      INIT => X"F1"
    )
        port map (
      I0 => state_write(1),
      I1 => state_write(0),
      I2 => \^s00_axi_wready\,
      O => axi_wready_i_1_n_0
    );
axi_wready_reg: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => axi_wready_i_1_n_0,
      Q => \^s00_axi_wready\,
      R => data_in_ip_i_1_n_0
    );
data_in_ip_i_1: unisim.vcomponents.LUT1
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => s00_axi_aresetn,
      O => data_in_ip_i_1_n_0
    );
data_in_ip_i_2: unisim.vcomponents.LUT6
    generic map(
      INIT => X"7FFF7F7F00FF0000"
    )
        port map (
      I0 => data_in_ip_i_3_n_0,
      I1 => \^axi_rvalid_reg_0\,
      I2 => s00_axi_rready,
      I3 => data_in_ip_i_4_n_0,
      I4 => s00_axi_wvalid,
      I5 => \^data_in_ip\,
      O => data_in_ip_i_2_n_0
    );
data_in_ip_i_3: unisim.vcomponents.LUT2
    generic map(
      INIT => X"2"
    )
        port map (
      I0 => p_0_in(1),
      I1 => p_0_in(0),
      O => data_in_ip_i_3_n_0
    );
data_in_ip_i_4: unisim.vcomponents.LUT3
    generic map(
      INIT => X"B8"
    )
        port map (
      I0 => s00_axi_awaddr(1),
      I1 => s00_axi_awvalid,
      I2 => \axi_awaddr_reg_n_0_[3]\,
      O => data_in_ip_i_4_n_0
    );
data_in_ip_reg: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => data_in_ip_i_2_n_0,
      Q => \^data_in_ip\,
      R => data_in_ip_i_1_n_0
    );
\s00_axi_rdata[0]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(0),
      I1 => slv_reg3(0),
      I2 => slv_reg0(0),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(0),
      O => s00_axi_rdata(0)
    );
\s00_axi_rdata[10]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(10),
      I1 => slv_reg3(10),
      I2 => slv_reg0(10),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(10),
      O => s00_axi_rdata(10)
    );
\s00_axi_rdata[11]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(11),
      I1 => slv_reg3(11),
      I2 => slv_reg0(11),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(11),
      O => s00_axi_rdata(11)
    );
\s00_axi_rdata[12]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(12),
      I1 => slv_reg3(12),
      I2 => slv_reg0(12),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(12),
      O => s00_axi_rdata(12)
    );
\s00_axi_rdata[13]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(13),
      I1 => slv_reg3(13),
      I2 => slv_reg0(13),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(13),
      O => s00_axi_rdata(13)
    );
\s00_axi_rdata[14]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(14),
      I1 => slv_reg3(14),
      I2 => slv_reg0(14),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(14),
      O => s00_axi_rdata(14)
    );
\s00_axi_rdata[15]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(15),
      I1 => slv_reg3(15),
      I2 => slv_reg0(15),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(15),
      O => s00_axi_rdata(15)
    );
\s00_axi_rdata[16]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(16),
      I1 => slv_reg3(16),
      I2 => slv_reg0(16),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(16),
      O => s00_axi_rdata(16)
    );
\s00_axi_rdata[17]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(17),
      I1 => slv_reg3(17),
      I2 => slv_reg0(17),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(17),
      O => s00_axi_rdata(17)
    );
\s00_axi_rdata[18]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(18),
      I1 => slv_reg3(18),
      I2 => slv_reg0(18),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(18),
      O => s00_axi_rdata(18)
    );
\s00_axi_rdata[19]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(19),
      I1 => slv_reg3(19),
      I2 => slv_reg0(19),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(19),
      O => s00_axi_rdata(19)
    );
\s00_axi_rdata[1]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(1),
      I1 => slv_reg3(1),
      I2 => slv_reg0(1),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(1),
      O => s00_axi_rdata(1)
    );
\s00_axi_rdata[20]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(20),
      I1 => slv_reg3(20),
      I2 => slv_reg0(20),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(20),
      O => s00_axi_rdata(20)
    );
\s00_axi_rdata[21]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(21),
      I1 => slv_reg3(21),
      I2 => slv_reg0(21),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(21),
      O => s00_axi_rdata(21)
    );
\s00_axi_rdata[22]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(22),
      I1 => slv_reg3(22),
      I2 => slv_reg0(22),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(22),
      O => s00_axi_rdata(22)
    );
\s00_axi_rdata[23]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(23),
      I1 => slv_reg3(23),
      I2 => slv_reg0(23),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(23),
      O => s00_axi_rdata(23)
    );
\s00_axi_rdata[24]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(24),
      I1 => slv_reg3(24),
      I2 => slv_reg0(24),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(24),
      O => s00_axi_rdata(24)
    );
\s00_axi_rdata[25]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(25),
      I1 => slv_reg3(25),
      I2 => slv_reg0(25),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(25),
      O => s00_axi_rdata(25)
    );
\s00_axi_rdata[26]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(26),
      I1 => slv_reg3(26),
      I2 => slv_reg0(26),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(26),
      O => s00_axi_rdata(26)
    );
\s00_axi_rdata[27]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(27),
      I1 => slv_reg3(27),
      I2 => slv_reg0(27),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(27),
      O => s00_axi_rdata(27)
    );
\s00_axi_rdata[28]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(28),
      I1 => slv_reg3(28),
      I2 => slv_reg0(28),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(28),
      O => s00_axi_rdata(28)
    );
\s00_axi_rdata[29]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(29),
      I1 => slv_reg3(29),
      I2 => slv_reg0(29),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(29),
      O => s00_axi_rdata(29)
    );
\s00_axi_rdata[2]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(2),
      I1 => slv_reg3(2),
      I2 => slv_reg0(2),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(2),
      O => s00_axi_rdata(2)
    );
\s00_axi_rdata[30]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(30),
      I1 => slv_reg3(30),
      I2 => slv_reg0(30),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(30),
      O => s00_axi_rdata(30)
    );
\s00_axi_rdata[31]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(31),
      I1 => slv_reg3(31),
      I2 => slv_reg0(31),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(31),
      O => s00_axi_rdata(31)
    );
\s00_axi_rdata[3]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(3),
      I1 => slv_reg3(3),
      I2 => slv_reg0(3),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(3),
      O => s00_axi_rdata(3)
    );
\s00_axi_rdata[4]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(4),
      I1 => slv_reg3(4),
      I2 => slv_reg0(4),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(4),
      O => s00_axi_rdata(4)
    );
\s00_axi_rdata[5]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(5),
      I1 => slv_reg3(5),
      I2 => slv_reg0(5),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(5),
      O => s00_axi_rdata(5)
    );
\s00_axi_rdata[6]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(6),
      I1 => slv_reg3(6),
      I2 => slv_reg0(6),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(6),
      O => s00_axi_rdata(6)
    );
\s00_axi_rdata[7]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(7),
      I1 => slv_reg3(7),
      I2 => slv_reg0(7),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(7),
      O => s00_axi_rdata(7)
    );
\s00_axi_rdata[8]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(8),
      I1 => slv_reg3(8),
      I2 => slv_reg0(8),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(8),
      O => s00_axi_rdata(8)
    );
\s00_axi_rdata[9]_INST_0\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"CCFFAAF0CC00AAF0"
    )
        port map (
      I0 => slv_reg2_reg(9),
      I1 => slv_reg3(9),
      I2 => slv_reg0(9),
      I3 => p_0_in(1),
      I4 => p_0_in(0),
      I5 => slv_reg1(9),
      O => s00_axi_rdata(9)
    );
\slv_reg0[15]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg0[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(1),
      O => \slv_reg0[15]_i_1_n_0\
    );
\slv_reg0[23]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg0[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(2),
      O => \slv_reg0[23]_i_1_n_0\
    );
\slv_reg0[31]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg0[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(3),
      O => \slv_reg0[31]_i_1_n_0\
    );
\slv_reg0[31]_i_2\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"0044034700000000"
    )
        port map (
      I0 => s00_axi_awaddr(0),
      I1 => s00_axi_awvalid,
      I2 => \axi_awaddr_reg_n_0_[2]\,
      I3 => s00_axi_awaddr(1),
      I4 => \axi_awaddr_reg_n_0_[3]\,
      I5 => s00_axi_wvalid,
      O => \slv_reg0[31]_i_2_n_0\
    );
\slv_reg0[7]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg0[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(0),
      O => \slv_reg0[7]_i_1_n_0\
    );
\slv_reg0_reg[0]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[7]_i_1_n_0\,
      D => s00_axi_wdata(0),
      Q => slv_reg0(0),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[10]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[15]_i_1_n_0\,
      D => s00_axi_wdata(10),
      Q => slv_reg0(10),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[11]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[15]_i_1_n_0\,
      D => s00_axi_wdata(11),
      Q => slv_reg0(11),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[12]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[15]_i_1_n_0\,
      D => s00_axi_wdata(12),
      Q => slv_reg0(12),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[13]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[15]_i_1_n_0\,
      D => s00_axi_wdata(13),
      Q => slv_reg0(13),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[14]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[15]_i_1_n_0\,
      D => s00_axi_wdata(14),
      Q => slv_reg0(14),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[15]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[15]_i_1_n_0\,
      D => s00_axi_wdata(15),
      Q => slv_reg0(15),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[16]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[23]_i_1_n_0\,
      D => s00_axi_wdata(16),
      Q => slv_reg0(16),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[17]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[23]_i_1_n_0\,
      D => s00_axi_wdata(17),
      Q => slv_reg0(17),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[18]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[23]_i_1_n_0\,
      D => s00_axi_wdata(18),
      Q => slv_reg0(18),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[19]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[23]_i_1_n_0\,
      D => s00_axi_wdata(19),
      Q => slv_reg0(19),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[1]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[7]_i_1_n_0\,
      D => s00_axi_wdata(1),
      Q => slv_reg0(1),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[20]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[23]_i_1_n_0\,
      D => s00_axi_wdata(20),
      Q => slv_reg0(20),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[21]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[23]_i_1_n_0\,
      D => s00_axi_wdata(21),
      Q => slv_reg0(21),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[22]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[23]_i_1_n_0\,
      D => s00_axi_wdata(22),
      Q => slv_reg0(22),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[23]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[23]_i_1_n_0\,
      D => s00_axi_wdata(23),
      Q => slv_reg0(23),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[24]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[31]_i_1_n_0\,
      D => s00_axi_wdata(24),
      Q => slv_reg0(24),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[25]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[31]_i_1_n_0\,
      D => s00_axi_wdata(25),
      Q => slv_reg0(25),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[26]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[31]_i_1_n_0\,
      D => s00_axi_wdata(26),
      Q => slv_reg0(26),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[27]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[31]_i_1_n_0\,
      D => s00_axi_wdata(27),
      Q => slv_reg0(27),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[28]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[31]_i_1_n_0\,
      D => s00_axi_wdata(28),
      Q => slv_reg0(28),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[29]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[31]_i_1_n_0\,
      D => s00_axi_wdata(29),
      Q => slv_reg0(29),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[2]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[7]_i_1_n_0\,
      D => s00_axi_wdata(2),
      Q => slv_reg0(2),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[30]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[31]_i_1_n_0\,
      D => s00_axi_wdata(30),
      Q => slv_reg0(30),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[31]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[31]_i_1_n_0\,
      D => s00_axi_wdata(31),
      Q => slv_reg0(31),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[3]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[7]_i_1_n_0\,
      D => s00_axi_wdata(3),
      Q => slv_reg0(3),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[4]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[7]_i_1_n_0\,
      D => s00_axi_wdata(4),
      Q => slv_reg0(4),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[5]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[7]_i_1_n_0\,
      D => s00_axi_wdata(5),
      Q => slv_reg0(5),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[6]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[7]_i_1_n_0\,
      D => s00_axi_wdata(6),
      Q => slv_reg0(6),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[7]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[7]_i_1_n_0\,
      D => s00_axi_wdata(7),
      Q => slv_reg0(7),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[8]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[15]_i_1_n_0\,
      D => s00_axi_wdata(8),
      Q => slv_reg0(8),
      R => data_in_ip_i_1_n_0
    );
\slv_reg0_reg[9]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg0[15]_i_1_n_0\,
      D => s00_axi_wdata(9),
      Q => slv_reg0(9),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1[15]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg1[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(1),
      O => \slv_reg1[15]_i_1_n_0\
    );
\slv_reg1[23]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg1[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(2),
      O => \slv_reg1[23]_i_1_n_0\
    );
\slv_reg1[31]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg1[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(3),
      O => \slv_reg1[31]_i_1_n_0\
    );
\slv_reg1[31]_i_2\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"000000A0888800A0"
    )
        port map (
      I0 => s00_axi_wvalid,
      I1 => s00_axi_awaddr(0),
      I2 => \axi_awaddr_reg_n_0_[2]\,
      I3 => \axi_awaddr_reg_n_0_[3]\,
      I4 => s00_axi_awvalid,
      I5 => s00_axi_awaddr(1),
      O => \slv_reg1[31]_i_2_n_0\
    );
\slv_reg1[7]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg1[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(0),
      O => \slv_reg1[7]_i_1_n_0\
    );
\slv_reg1_reg[0]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[7]_i_1_n_0\,
      D => s00_axi_wdata(0),
      Q => slv_reg1(0),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[10]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[15]_i_1_n_0\,
      D => s00_axi_wdata(10),
      Q => slv_reg1(10),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[11]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[15]_i_1_n_0\,
      D => s00_axi_wdata(11),
      Q => slv_reg1(11),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[12]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[15]_i_1_n_0\,
      D => s00_axi_wdata(12),
      Q => slv_reg1(12),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[13]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[15]_i_1_n_0\,
      D => s00_axi_wdata(13),
      Q => slv_reg1(13),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[14]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[15]_i_1_n_0\,
      D => s00_axi_wdata(14),
      Q => slv_reg1(14),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[15]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[15]_i_1_n_0\,
      D => s00_axi_wdata(15),
      Q => slv_reg1(15),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[16]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[23]_i_1_n_0\,
      D => s00_axi_wdata(16),
      Q => slv_reg1(16),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[17]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[23]_i_1_n_0\,
      D => s00_axi_wdata(17),
      Q => slv_reg1(17),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[18]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[23]_i_1_n_0\,
      D => s00_axi_wdata(18),
      Q => slv_reg1(18),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[19]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[23]_i_1_n_0\,
      D => s00_axi_wdata(19),
      Q => slv_reg1(19),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[1]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[7]_i_1_n_0\,
      D => s00_axi_wdata(1),
      Q => slv_reg1(1),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[20]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[23]_i_1_n_0\,
      D => s00_axi_wdata(20),
      Q => slv_reg1(20),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[21]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[23]_i_1_n_0\,
      D => s00_axi_wdata(21),
      Q => slv_reg1(21),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[22]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[23]_i_1_n_0\,
      D => s00_axi_wdata(22),
      Q => slv_reg1(22),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[23]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[23]_i_1_n_0\,
      D => s00_axi_wdata(23),
      Q => slv_reg1(23),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[24]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[31]_i_1_n_0\,
      D => s00_axi_wdata(24),
      Q => slv_reg1(24),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[25]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[31]_i_1_n_0\,
      D => s00_axi_wdata(25),
      Q => slv_reg1(25),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[26]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[31]_i_1_n_0\,
      D => s00_axi_wdata(26),
      Q => slv_reg1(26),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[27]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[31]_i_1_n_0\,
      D => s00_axi_wdata(27),
      Q => slv_reg1(27),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[28]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[31]_i_1_n_0\,
      D => s00_axi_wdata(28),
      Q => slv_reg1(28),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[29]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[31]_i_1_n_0\,
      D => s00_axi_wdata(29),
      Q => slv_reg1(29),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[2]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[7]_i_1_n_0\,
      D => s00_axi_wdata(2),
      Q => slv_reg1(2),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[30]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[31]_i_1_n_0\,
      D => s00_axi_wdata(30),
      Q => slv_reg1(30),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[31]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[31]_i_1_n_0\,
      D => s00_axi_wdata(31),
      Q => slv_reg1(31),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[3]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[7]_i_1_n_0\,
      D => s00_axi_wdata(3),
      Q => slv_reg1(3),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[4]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[7]_i_1_n_0\,
      D => s00_axi_wdata(4),
      Q => slv_reg1(4),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[5]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[7]_i_1_n_0\,
      D => s00_axi_wdata(5),
      Q => slv_reg1(5),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[6]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[7]_i_1_n_0\,
      D => s00_axi_wdata(6),
      Q => slv_reg1(6),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[7]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[7]_i_1_n_0\,
      D => s00_axi_wdata(7),
      Q => slv_reg1(7),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[8]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[15]_i_1_n_0\,
      D => s00_axi_wdata(8),
      Q => slv_reg1(8),
      R => data_in_ip_i_1_n_0
    );
\slv_reg1_reg[9]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => \slv_reg1[15]_i_1_n_0\,
      D => s00_axi_wdata(9),
      Q => slv_reg1(9),
      R => data_in_ip_i_1_n_0
    );
slv_reg2_reg0_carry: unisim.vcomponents.CARRY4
     port map (
      CI => '0',
      CO(3) => slv_reg2_reg0_carry_n_0,
      CO(2) => slv_reg2_reg0_carry_n_1,
      CO(1) => slv_reg2_reg0_carry_n_2,
      CO(0) => slv_reg2_reg0_carry_n_3,
      CYINIT => '0',
      DI(3 downto 0) => slv_reg0(3 downto 0),
      O(3) => slv_reg2_reg0_carry_n_4,
      O(2) => slv_reg2_reg0_carry_n_5,
      O(1) => slv_reg2_reg0_carry_n_6,
      O(0) => slv_reg2_reg0_carry_n_7,
      S(3) => \slv_reg2_reg0_carry_i_1__0_n_0\,
      S(2) => slv_reg2_reg0_carry_i_2_n_0,
      S(1) => slv_reg2_reg0_carry_i_3_n_0,
      S(0) => slv_reg2_reg0_carry_i_4_n_0
    );
\slv_reg2_reg0_carry__0\: unisim.vcomponents.CARRY4
     port map (
      CI => slv_reg2_reg0_carry_n_0,
      CO(3) => \slv_reg2_reg0_carry__0_n_0\,
      CO(2) => \slv_reg2_reg0_carry__0_n_1\,
      CO(1) => \slv_reg2_reg0_carry__0_n_2\,
      CO(0) => \slv_reg2_reg0_carry__0_n_3\,
      CYINIT => '0',
      DI(3 downto 0) => slv_reg0(7 downto 4),
      O(3) => \slv_reg2_reg0_carry__0_n_4\,
      O(2) => \slv_reg2_reg0_carry__0_n_5\,
      O(1) => \slv_reg2_reg0_carry__0_n_6\,
      O(0) => \slv_reg2_reg0_carry__0_n_7\,
      S(3) => \slv_reg2_reg0_carry_i_1__1_n_0\,
      S(2) => \slv_reg2_reg0_carry_i_2__0_n_0\,
      S(1) => \slv_reg2_reg0_carry_i_3__0_n_0\,
      S(0) => \slv_reg2_reg0_carry_i_4__0_n_0\
    );
\slv_reg2_reg0_carry__1\: unisim.vcomponents.CARRY4
     port map (
      CI => \slv_reg2_reg0_carry__0_n_0\,
      CO(3) => \slv_reg2_reg0_carry__1_n_0\,
      CO(2) => \slv_reg2_reg0_carry__1_n_1\,
      CO(1) => \slv_reg2_reg0_carry__1_n_2\,
      CO(0) => \slv_reg2_reg0_carry__1_n_3\,
      CYINIT => '0',
      DI(3 downto 0) => slv_reg0(11 downto 8),
      O(3) => \slv_reg2_reg0_carry__1_n_4\,
      O(2) => \slv_reg2_reg0_carry__1_n_5\,
      O(1) => \slv_reg2_reg0_carry__1_n_6\,
      O(0) => \slv_reg2_reg0_carry__1_n_7\,
      S(3) => \slv_reg2_reg0_carry_i_1__2_n_0\,
      S(2) => \slv_reg2_reg0_carry_i_2__1_n_0\,
      S(1) => \slv_reg2_reg0_carry_i_3__1_n_0\,
      S(0) => \slv_reg2_reg0_carry_i_4__1_n_0\
    );
\slv_reg2_reg0_carry__2\: unisim.vcomponents.CARRY4
     port map (
      CI => \slv_reg2_reg0_carry__1_n_0\,
      CO(3) => \slv_reg2_reg0_carry__2_n_0\,
      CO(2) => \slv_reg2_reg0_carry__2_n_1\,
      CO(1) => \slv_reg2_reg0_carry__2_n_2\,
      CO(0) => \slv_reg2_reg0_carry__2_n_3\,
      CYINIT => '0',
      DI(3 downto 0) => slv_reg0(15 downto 12),
      O(3) => \slv_reg2_reg0_carry__2_n_4\,
      O(2) => \slv_reg2_reg0_carry__2_n_5\,
      O(1) => \slv_reg2_reg0_carry__2_n_6\,
      O(0) => \slv_reg2_reg0_carry__2_n_7\,
      S(3) => \slv_reg2_reg0_carry_i_1__3_n_0\,
      S(2) => \slv_reg2_reg0_carry_i_2__2_n_0\,
      S(1) => \slv_reg2_reg0_carry_i_3__2_n_0\,
      S(0) => \slv_reg2_reg0_carry_i_4__2_n_0\
    );
\slv_reg2_reg0_carry__3\: unisim.vcomponents.CARRY4
     port map (
      CI => \slv_reg2_reg0_carry__2_n_0\,
      CO(3) => \slv_reg2_reg0_carry__3_n_0\,
      CO(2) => \slv_reg2_reg0_carry__3_n_1\,
      CO(1) => \slv_reg2_reg0_carry__3_n_2\,
      CO(0) => \slv_reg2_reg0_carry__3_n_3\,
      CYINIT => '0',
      DI(3 downto 0) => slv_reg0(19 downto 16),
      O(3) => \slv_reg2_reg0_carry__3_n_4\,
      O(2) => \slv_reg2_reg0_carry__3_n_5\,
      O(1) => \slv_reg2_reg0_carry__3_n_6\,
      O(0) => \slv_reg2_reg0_carry__3_n_7\,
      S(3) => \slv_reg2_reg0_carry_i_1__4_n_0\,
      S(2) => \slv_reg2_reg0_carry_i_2__3_n_0\,
      S(1) => \slv_reg2_reg0_carry_i_3__3_n_0\,
      S(0) => \slv_reg2_reg0_carry_i_4__3_n_0\
    );
\slv_reg2_reg0_carry__4\: unisim.vcomponents.CARRY4
     port map (
      CI => \slv_reg2_reg0_carry__3_n_0\,
      CO(3) => \slv_reg2_reg0_carry__4_n_0\,
      CO(2) => \slv_reg2_reg0_carry__4_n_1\,
      CO(1) => \slv_reg2_reg0_carry__4_n_2\,
      CO(0) => \slv_reg2_reg0_carry__4_n_3\,
      CYINIT => '0',
      DI(3 downto 0) => slv_reg0(23 downto 20),
      O(3) => \slv_reg2_reg0_carry__4_n_4\,
      O(2) => \slv_reg2_reg0_carry__4_n_5\,
      O(1) => \slv_reg2_reg0_carry__4_n_6\,
      O(0) => \slv_reg2_reg0_carry__4_n_7\,
      S(3) => \slv_reg2_reg0_carry_i_1__5_n_0\,
      S(2) => \slv_reg2_reg0_carry_i_2__4_n_0\,
      S(1) => \slv_reg2_reg0_carry_i_3__4_n_0\,
      S(0) => \slv_reg2_reg0_carry_i_4__4_n_0\
    );
\slv_reg2_reg0_carry__5\: unisim.vcomponents.CARRY4
     port map (
      CI => \slv_reg2_reg0_carry__4_n_0\,
      CO(3) => \slv_reg2_reg0_carry__5_n_0\,
      CO(2) => \slv_reg2_reg0_carry__5_n_1\,
      CO(1) => \slv_reg2_reg0_carry__5_n_2\,
      CO(0) => \slv_reg2_reg0_carry__5_n_3\,
      CYINIT => '0',
      DI(3 downto 0) => slv_reg0(27 downto 24),
      O(3) => \slv_reg2_reg0_carry__5_n_4\,
      O(2) => \slv_reg2_reg0_carry__5_n_5\,
      O(1) => \slv_reg2_reg0_carry__5_n_6\,
      O(0) => \slv_reg2_reg0_carry__5_n_7\,
      S(3) => \slv_reg2_reg0_carry_i_1__6_n_0\,
      S(2) => \slv_reg2_reg0_carry_i_2__5_n_0\,
      S(1) => \slv_reg2_reg0_carry_i_3__5_n_0\,
      S(0) => \slv_reg2_reg0_carry_i_4__5_n_0\
    );
\slv_reg2_reg0_carry__6\: unisim.vcomponents.CARRY4
     port map (
      CI => \slv_reg2_reg0_carry__5_n_0\,
      CO(3) => \NLW_slv_reg2_reg0_carry__6_CO_UNCONNECTED\(3),
      CO(2) => \slv_reg2_reg0_carry__6_n_1\,
      CO(1) => \slv_reg2_reg0_carry__6_n_2\,
      CO(0) => \slv_reg2_reg0_carry__6_n_3\,
      CYINIT => '0',
      DI(3) => '0',
      DI(2 downto 0) => slv_reg0(30 downto 28),
      O(3) => \slv_reg2_reg0_carry__6_n_4\,
      O(2) => \slv_reg2_reg0_carry__6_n_5\,
      O(1) => \slv_reg2_reg0_carry__6_n_6\,
      O(0) => \slv_reg2_reg0_carry__6_n_7\,
      S(3) => slv_reg2_reg0_carry_i_1_n_0,
      S(2) => \slv_reg2_reg0_carry_i_2__6_n_0\,
      S(1) => \slv_reg2_reg0_carry_i_3__6_n_0\,
      S(0) => \slv_reg2_reg0_carry_i_4__6_n_0\
    );
slv_reg2_reg0_carry_i_1: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(31),
      I1 => slv_reg1(31),
      O => slv_reg2_reg0_carry_i_1_n_0
    );
\slv_reg2_reg0_carry_i_1__0\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(3),
      I1 => slv_reg1(3),
      O => \slv_reg2_reg0_carry_i_1__0_n_0\
    );
\slv_reg2_reg0_carry_i_1__1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(7),
      I1 => slv_reg1(7),
      O => \slv_reg2_reg0_carry_i_1__1_n_0\
    );
\slv_reg2_reg0_carry_i_1__2\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(11),
      I1 => slv_reg1(11),
      O => \slv_reg2_reg0_carry_i_1__2_n_0\
    );
\slv_reg2_reg0_carry_i_1__3\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(15),
      I1 => slv_reg1(15),
      O => \slv_reg2_reg0_carry_i_1__3_n_0\
    );
\slv_reg2_reg0_carry_i_1__4\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(19),
      I1 => slv_reg1(19),
      O => \slv_reg2_reg0_carry_i_1__4_n_0\
    );
\slv_reg2_reg0_carry_i_1__5\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(23),
      I1 => slv_reg1(23),
      O => \slv_reg2_reg0_carry_i_1__5_n_0\
    );
\slv_reg2_reg0_carry_i_1__6\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(27),
      I1 => slv_reg1(27),
      O => \slv_reg2_reg0_carry_i_1__6_n_0\
    );
slv_reg2_reg0_carry_i_2: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(2),
      I1 => slv_reg1(2),
      O => slv_reg2_reg0_carry_i_2_n_0
    );
\slv_reg2_reg0_carry_i_2__0\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(6),
      I1 => slv_reg1(6),
      O => \slv_reg2_reg0_carry_i_2__0_n_0\
    );
\slv_reg2_reg0_carry_i_2__1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(10),
      I1 => slv_reg1(10),
      O => \slv_reg2_reg0_carry_i_2__1_n_0\
    );
\slv_reg2_reg0_carry_i_2__2\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(14),
      I1 => slv_reg1(14),
      O => \slv_reg2_reg0_carry_i_2__2_n_0\
    );
\slv_reg2_reg0_carry_i_2__3\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(18),
      I1 => slv_reg1(18),
      O => \slv_reg2_reg0_carry_i_2__3_n_0\
    );
\slv_reg2_reg0_carry_i_2__4\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(22),
      I1 => slv_reg1(22),
      O => \slv_reg2_reg0_carry_i_2__4_n_0\
    );
\slv_reg2_reg0_carry_i_2__5\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(26),
      I1 => slv_reg1(26),
      O => \slv_reg2_reg0_carry_i_2__5_n_0\
    );
\slv_reg2_reg0_carry_i_2__6\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(30),
      I1 => slv_reg1(30),
      O => \slv_reg2_reg0_carry_i_2__6_n_0\
    );
slv_reg2_reg0_carry_i_3: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(1),
      I1 => slv_reg1(1),
      O => slv_reg2_reg0_carry_i_3_n_0
    );
\slv_reg2_reg0_carry_i_3__0\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(5),
      I1 => slv_reg1(5),
      O => \slv_reg2_reg0_carry_i_3__0_n_0\
    );
\slv_reg2_reg0_carry_i_3__1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(9),
      I1 => slv_reg1(9),
      O => \slv_reg2_reg0_carry_i_3__1_n_0\
    );
\slv_reg2_reg0_carry_i_3__2\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(13),
      I1 => slv_reg1(13),
      O => \slv_reg2_reg0_carry_i_3__2_n_0\
    );
\slv_reg2_reg0_carry_i_3__3\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(17),
      I1 => slv_reg1(17),
      O => \slv_reg2_reg0_carry_i_3__3_n_0\
    );
\slv_reg2_reg0_carry_i_3__4\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(21),
      I1 => slv_reg1(21),
      O => \slv_reg2_reg0_carry_i_3__4_n_0\
    );
\slv_reg2_reg0_carry_i_3__5\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(25),
      I1 => slv_reg1(25),
      O => \slv_reg2_reg0_carry_i_3__5_n_0\
    );
\slv_reg2_reg0_carry_i_3__6\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(29),
      I1 => slv_reg1(29),
      O => \slv_reg2_reg0_carry_i_3__6_n_0\
    );
slv_reg2_reg0_carry_i_4: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(0),
      I1 => slv_reg1(0),
      O => slv_reg2_reg0_carry_i_4_n_0
    );
\slv_reg2_reg0_carry_i_4__0\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(4),
      I1 => slv_reg1(4),
      O => \slv_reg2_reg0_carry_i_4__0_n_0\
    );
\slv_reg2_reg0_carry_i_4__1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(8),
      I1 => slv_reg1(8),
      O => \slv_reg2_reg0_carry_i_4__1_n_0\
    );
\slv_reg2_reg0_carry_i_4__2\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(12),
      I1 => slv_reg1(12),
      O => \slv_reg2_reg0_carry_i_4__2_n_0\
    );
\slv_reg2_reg0_carry_i_4__3\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(16),
      I1 => slv_reg1(16),
      O => \slv_reg2_reg0_carry_i_4__3_n_0\
    );
\slv_reg2_reg0_carry_i_4__4\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(20),
      I1 => slv_reg1(20),
      O => \slv_reg2_reg0_carry_i_4__4_n_0\
    );
\slv_reg2_reg0_carry_i_4__5\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(24),
      I1 => slv_reg1(24),
      O => \slv_reg2_reg0_carry_i_4__5_n_0\
    );
\slv_reg2_reg0_carry_i_4__6\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => slv_reg0(28),
      I1 => slv_reg1(28),
      O => \slv_reg2_reg0_carry_i_4__6_n_0\
    );
\slv_reg2_reg[0]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => slv_reg2_reg0_carry_n_7,
      Q => slv_reg2_reg(0),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[10]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__1_n_5\,
      Q => slv_reg2_reg(10),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[11]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__1_n_4\,
      Q => slv_reg2_reg(11),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[12]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__2_n_7\,
      Q => slv_reg2_reg(12),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[13]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__2_n_6\,
      Q => slv_reg2_reg(13),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[14]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__2_n_5\,
      Q => slv_reg2_reg(14),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[15]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__2_n_4\,
      Q => slv_reg2_reg(15),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[16]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__3_n_7\,
      Q => slv_reg2_reg(16),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[17]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__3_n_6\,
      Q => slv_reg2_reg(17),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[18]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__3_n_5\,
      Q => slv_reg2_reg(18),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[19]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__3_n_4\,
      Q => slv_reg2_reg(19),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[1]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => slv_reg2_reg0_carry_n_6,
      Q => slv_reg2_reg(1),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[20]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__4_n_7\,
      Q => slv_reg2_reg(20),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[21]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__4_n_6\,
      Q => slv_reg2_reg(21),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[22]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__4_n_5\,
      Q => slv_reg2_reg(22),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[23]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__4_n_4\,
      Q => slv_reg2_reg(23),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[24]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__5_n_7\,
      Q => slv_reg2_reg(24),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[25]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__5_n_6\,
      Q => slv_reg2_reg(25),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[26]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__5_n_5\,
      Q => slv_reg2_reg(26),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[27]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__5_n_4\,
      Q => slv_reg2_reg(27),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[28]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__6_n_7\,
      Q => slv_reg2_reg(28),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[29]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__6_n_6\,
      Q => slv_reg2_reg(29),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[2]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => slv_reg2_reg0_carry_n_5,
      Q => slv_reg2_reg(2),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[30]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__6_n_5\,
      Q => slv_reg2_reg(30),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[31]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__6_n_4\,
      Q => slv_reg2_reg(31),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[3]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => slv_reg2_reg0_carry_n_4,
      Q => slv_reg2_reg(3),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[4]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__0_n_7\,
      Q => slv_reg2_reg(4),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[5]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__0_n_6\,
      Q => slv_reg2_reg(5),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[6]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__0_n_5\,
      Q => slv_reg2_reg(6),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[7]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__0_n_4\,
      Q => slv_reg2_reg(7),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[8]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__1_n_7\,
      Q => slv_reg2_reg(8),
      R => data_in_ip_i_1_n_0
    );
\slv_reg2_reg[9]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => '1',
      D => \slv_reg2_reg0_carry__1_n_6\,
      Q => slv_reg2_reg(9),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3[15]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg3[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(1),
      O => p_1_in(15)
    );
\slv_reg3[23]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg3[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(2),
      O => p_1_in(23)
    );
\slv_reg3[31]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg3[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(3),
      O => p_1_in(31)
    );
\slv_reg3[31]_i_2\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"8888A0000000A000"
    )
        port map (
      I0 => s00_axi_wvalid,
      I1 => s00_axi_awaddr(0),
      I2 => \axi_awaddr_reg_n_0_[2]\,
      I3 => \axi_awaddr_reg_n_0_[3]\,
      I4 => s00_axi_awvalid,
      I5 => s00_axi_awaddr(1),
      O => \slv_reg3[31]_i_2_n_0\
    );
\slv_reg3[7]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => \slv_reg3[31]_i_2_n_0\,
      I1 => s00_axi_wstrb(0),
      O => p_1_in(7)
    );
\slv_reg3_reg[0]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(7),
      D => s00_axi_wdata(0),
      Q => slv_reg3(0),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[10]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(15),
      D => s00_axi_wdata(10),
      Q => slv_reg3(10),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[11]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(15),
      D => s00_axi_wdata(11),
      Q => slv_reg3(11),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[12]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(15),
      D => s00_axi_wdata(12),
      Q => slv_reg3(12),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[13]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(15),
      D => s00_axi_wdata(13),
      Q => slv_reg3(13),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[14]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(15),
      D => s00_axi_wdata(14),
      Q => slv_reg3(14),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[15]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(15),
      D => s00_axi_wdata(15),
      Q => slv_reg3(15),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[16]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(23),
      D => s00_axi_wdata(16),
      Q => slv_reg3(16),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[17]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(23),
      D => s00_axi_wdata(17),
      Q => slv_reg3(17),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[18]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(23),
      D => s00_axi_wdata(18),
      Q => slv_reg3(18),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[19]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(23),
      D => s00_axi_wdata(19),
      Q => slv_reg3(19),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[1]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(7),
      D => s00_axi_wdata(1),
      Q => slv_reg3(1),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[20]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(23),
      D => s00_axi_wdata(20),
      Q => slv_reg3(20),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[21]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(23),
      D => s00_axi_wdata(21),
      Q => slv_reg3(21),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[22]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(23),
      D => s00_axi_wdata(22),
      Q => slv_reg3(22),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[23]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(23),
      D => s00_axi_wdata(23),
      Q => slv_reg3(23),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[24]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(31),
      D => s00_axi_wdata(24),
      Q => slv_reg3(24),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[25]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(31),
      D => s00_axi_wdata(25),
      Q => slv_reg3(25),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[26]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(31),
      D => s00_axi_wdata(26),
      Q => slv_reg3(26),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[27]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(31),
      D => s00_axi_wdata(27),
      Q => slv_reg3(27),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[28]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(31),
      D => s00_axi_wdata(28),
      Q => slv_reg3(28),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[29]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(31),
      D => s00_axi_wdata(29),
      Q => slv_reg3(29),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[2]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(7),
      D => s00_axi_wdata(2),
      Q => slv_reg3(2),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[30]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(31),
      D => s00_axi_wdata(30),
      Q => slv_reg3(30),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[31]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(31),
      D => s00_axi_wdata(31),
      Q => slv_reg3(31),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[3]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(7),
      D => s00_axi_wdata(3),
      Q => slv_reg3(3),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[4]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(7),
      D => s00_axi_wdata(4),
      Q => slv_reg3(4),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[5]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(7),
      D => s00_axi_wdata(5),
      Q => slv_reg3(5),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[6]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(7),
      D => s00_axi_wdata(6),
      Q => slv_reg3(6),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[7]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(7),
      D => s00_axi_wdata(7),
      Q => slv_reg3(7),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[8]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(15),
      D => s00_axi_wdata(8),
      Q => slv_reg3(8),
      R => data_in_ip_i_1_n_0
    );
\slv_reg3_reg[9]\: unisim.vcomponents.FDRE
     port map (
      C => s00_axi_aclk,
      CE => p_1_in(15),
      D => s00_axi_wdata(9),
      Q => slv_reg3(9),
      R => data_in_ip_i_1_n_0
    );
end STRUCTURE;
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
library UNISIM;
use UNISIM.VCOMPONENTS.ALL;
entity decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_CUSTOM_addsub1b is
  port (
    axi_awready_reg : out STD_LOGIC;
    axi_arready_reg : out STD_LOGIC;
    axi_rvalid_reg : out STD_LOGIC;
    s00_axi_rdata : out STD_LOGIC_VECTOR ( 31 downto 0 );
    s00_axi_bvalid : out STD_LOGIC;
    data_in_ip : out STD_LOGIC;
    s00_axi_wready : out STD_LOGIC;
    s00_axi_awvalid : in STD_LOGIC;
    s00_axi_wvalid : in STD_LOGIC;
    s00_axi_aclk : in STD_LOGIC;
    s00_axi_arvalid : in STD_LOGIC;
    s00_axi_rready : in STD_LOGIC;
    s00_axi_awaddr : in STD_LOGIC_VECTOR ( 1 downto 0 );
    s00_axi_araddr : in STD_LOGIC_VECTOR ( 1 downto 0 );
    s00_axi_aresetn : in STD_LOGIC;
    s00_axi_wdata : in STD_LOGIC_VECTOR ( 31 downto 0 );
    s00_axi_wstrb : in STD_LOGIC_VECTOR ( 3 downto 0 );
    s00_axi_bready : in STD_LOGIC
  );
end decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_CUSTOM_addsub1b;

architecture STRUCTURE of decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_CUSTOM_addsub1b is
begin
CUSTOM_addsub1b_slave_lite_v1_0_S00_AXI_inst: entity work.decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_CUSTOM_addsub1b_slave_lite_v1_0_S00_AXI
     port map (
      axi_arready_reg_0 => axi_arready_reg,
      axi_awready_reg_0 => axi_awready_reg,
      axi_rvalid_reg_0 => axi_rvalid_reg,
      data_in_ip => data_in_ip,
      s00_axi_aclk => s00_axi_aclk,
      s00_axi_araddr(1 downto 0) => s00_axi_araddr(1 downto 0),
      s00_axi_aresetn => s00_axi_aresetn,
      s00_axi_arvalid => s00_axi_arvalid,
      s00_axi_awaddr(1 downto 0) => s00_axi_awaddr(1 downto 0),
      s00_axi_awvalid => s00_axi_awvalid,
      s00_axi_bready => s00_axi_bready,
      s00_axi_bvalid => s00_axi_bvalid,
      s00_axi_rdata(31 downto 0) => s00_axi_rdata(31 downto 0),
      s00_axi_rready => s00_axi_rready,
      s00_axi_wdata(31 downto 0) => s00_axi_wdata(31 downto 0),
      s00_axi_wready => s00_axi_wready,
      s00_axi_wstrb(3 downto 0) => s00_axi_wstrb(3 downto 0),
      s00_axi_wvalid => s00_axi_wvalid
    );
end STRUCTURE;
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
library UNISIM;
use UNISIM.VCOMPONENTS.ALL;
entity decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix is
  port (
    data_in_ip : out STD_LOGIC;
    s00_axi_aclk : in STD_LOGIC;
    s00_axi_aresetn : in STD_LOGIC;
    s00_axi_awaddr : in STD_LOGIC_VECTOR ( 3 downto 0 );
    s00_axi_awprot : in STD_LOGIC_VECTOR ( 2 downto 0 );
    s00_axi_awvalid : in STD_LOGIC;
    s00_axi_awready : out STD_LOGIC;
    s00_axi_wdata : in STD_LOGIC_VECTOR ( 31 downto 0 );
    s00_axi_wstrb : in STD_LOGIC_VECTOR ( 3 downto 0 );
    s00_axi_wvalid : in STD_LOGIC;
    s00_axi_wready : out STD_LOGIC;
    s00_axi_bresp : out STD_LOGIC_VECTOR ( 1 downto 0 );
    s00_axi_bvalid : out STD_LOGIC;
    s00_axi_bready : in STD_LOGIC;
    s00_axi_araddr : in STD_LOGIC_VECTOR ( 3 downto 0 );
    s00_axi_arprot : in STD_LOGIC_VECTOR ( 2 downto 0 );
    s00_axi_arvalid : in STD_LOGIC;
    s00_axi_arready : out STD_LOGIC;
    s00_axi_rdata : out STD_LOGIC_VECTOR ( 31 downto 0 );
    s00_axi_rresp : out STD_LOGIC_VECTOR ( 1 downto 0 );
    s00_axi_rvalid : out STD_LOGIC;
    s00_axi_rready : in STD_LOGIC
  );
  attribute NotValidForBitStream : boolean;
  attribute NotValidForBitStream of decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix : entity is true;
  attribute CHECK_LICENSE_TYPE : string;
  attribute CHECK_LICENSE_TYPE of decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix : entity is "design_1_CUSTOM_addsub1b_0_0,CUSTOM_addsub1b,{}";
  attribute DowngradeIPIdentifiedWarnings : string;
  attribute DowngradeIPIdentifiedWarnings of decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix : entity is "yes";
  attribute X_CORE_INFO : string;
  attribute X_CORE_INFO of decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix : entity is "CUSTOM_addsub1b,Vivado 2026.1";
end decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix;

architecture STRUCTURE of decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix is
  signal \<const0>\ : STD_LOGIC;
  attribute X_INTERFACE_INFO : string;
  attribute X_INTERFACE_INFO of s00_axi_aclk : signal is "xilinx.com:signal:clock:1.0 S00_AXI_CLK CLK";
  attribute X_INTERFACE_MODE : string;
  attribute X_INTERFACE_MODE of s00_axi_aclk : signal is "slave";
  attribute X_INTERFACE_PARAMETER : string;
  attribute X_INTERFACE_PARAMETER of s00_axi_aclk : signal is "XIL_INTERFACENAME S00_AXI_CLK, ASSOCIATED_BUSIF S00_AXI, ASSOCIATED_RESET s00_axi_aresetn, FREQ_HZ 200000000, FREQ_TOLERANCE_HZ 0, PHASE 0.0, CLK_DOMAIN /clk_wiz_1_clk_out1, INSERT_VIP 0";
  attribute X_INTERFACE_INFO of s00_axi_aresetn : signal is "xilinx.com:signal:reset:1.0 S00_AXI_RST RST";
  attribute X_INTERFACE_MODE of s00_axi_aresetn : signal is "slave";
  attribute X_INTERFACE_PARAMETER of s00_axi_aresetn : signal is "XIL_INTERFACENAME S00_AXI_RST, POLARITY ACTIVE_LOW, INSERT_VIP 0";
  attribute X_INTERFACE_INFO of s00_axi_arready : signal is "xilinx.com:interface:aximm:1.0 S00_AXI ARREADY";
  attribute X_INTERFACE_INFO of s00_axi_arvalid : signal is "xilinx.com:interface:aximm:1.0 S00_AXI ARVALID";
  attribute X_INTERFACE_INFO of s00_axi_awready : signal is "xilinx.com:interface:aximm:1.0 S00_AXI AWREADY";
  attribute X_INTERFACE_INFO of s00_axi_awvalid : signal is "xilinx.com:interface:aximm:1.0 S00_AXI AWVALID";
  attribute X_INTERFACE_INFO of s00_axi_bready : signal is "xilinx.com:interface:aximm:1.0 S00_AXI BREADY";
  attribute X_INTERFACE_INFO of s00_axi_bvalid : signal is "xilinx.com:interface:aximm:1.0 S00_AXI BVALID";
  attribute X_INTERFACE_INFO of s00_axi_rready : signal is "xilinx.com:interface:aximm:1.0 S00_AXI RREADY";
  attribute X_INTERFACE_INFO of s00_axi_rvalid : signal is "xilinx.com:interface:aximm:1.0 S00_AXI RVALID";
  attribute X_INTERFACE_INFO of s00_axi_wready : signal is "xilinx.com:interface:aximm:1.0 S00_AXI WREADY";
  attribute X_INTERFACE_INFO of s00_axi_wvalid : signal is "xilinx.com:interface:aximm:1.0 S00_AXI WVALID";
  attribute X_INTERFACE_INFO of s00_axi_araddr : signal is "xilinx.com:interface:aximm:1.0 S00_AXI ARADDR";
  attribute X_INTERFACE_INFO of s00_axi_arprot : signal is "xilinx.com:interface:aximm:1.0 S00_AXI ARPROT";
  attribute X_INTERFACE_INFO of s00_axi_awaddr : signal is "xilinx.com:interface:aximm:1.0 S00_AXI AWADDR";
  attribute X_INTERFACE_MODE of s00_axi_awaddr : signal is "slave";
  attribute X_INTERFACE_PARAMETER of s00_axi_awaddr : signal is "XIL_INTERFACENAME S00_AXI, WIZ_DATA_WIDTH 32, WIZ_NUM_REG 4, SUPPORTS_NARROW_BURST 0, DATA_WIDTH 32, PROTOCOL AXI4LITE, FREQ_HZ 200000000, ID_WIDTH 0, ADDR_WIDTH 4, AWUSER_WIDTH 0, ARUSER_WIDTH 0, WUSER_WIDTH 0, RUSER_WIDTH 0, BUSER_WIDTH 0, READ_WRITE_MODE READ_WRITE, HAS_BURST 0, HAS_LOCK 0, HAS_PROT 1, HAS_CACHE 0, HAS_QOS 0, HAS_REGION 0, HAS_WSTRB 1, HAS_BRESP 1, HAS_RRESP 1, NUM_READ_OUTSTANDING 1, NUM_WRITE_OUTSTANDING 1, MAX_BURST_LENGTH 1, PHASE 0.0, CLK_DOMAIN /clk_wiz_1_clk_out1, NUM_READ_THREADS 1, NUM_WRITE_THREADS 1, RUSER_BITS_PER_BYTE 0, WUSER_BITS_PER_BYTE 0, INSERT_VIP 0";
  attribute X_INTERFACE_INFO of s00_axi_awprot : signal is "xilinx.com:interface:aximm:1.0 S00_AXI AWPROT";
  attribute X_INTERFACE_INFO of s00_axi_bresp : signal is "xilinx.com:interface:aximm:1.0 S00_AXI BRESP";
  attribute X_INTERFACE_INFO of s00_axi_rdata : signal is "xilinx.com:interface:aximm:1.0 S00_AXI RDATA";
  attribute X_INTERFACE_INFO of s00_axi_rresp : signal is "xilinx.com:interface:aximm:1.0 S00_AXI RRESP";
  attribute X_INTERFACE_INFO of s00_axi_wdata : signal is "xilinx.com:interface:aximm:1.0 S00_AXI WDATA";
  attribute X_INTERFACE_INFO of s00_axi_wstrb : signal is "xilinx.com:interface:aximm:1.0 S00_AXI WSTRB";
begin
  s00_axi_bresp(1) <= \<const0>\;
  s00_axi_bresp(0) <= \<const0>\;
  s00_axi_rresp(1) <= \<const0>\;
  s00_axi_rresp(0) <= \<const0>\;
GND: unisim.vcomponents.GND
     port map (
      G => \<const0>\
    );
inst: entity work.decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_CUSTOM_addsub1b
     port map (
      axi_arready_reg => s00_axi_arready,
      axi_awready_reg => s00_axi_awready,
      axi_rvalid_reg => s00_axi_rvalid,
      data_in_ip => data_in_ip,
      s00_axi_aclk => s00_axi_aclk,
      s00_axi_araddr(1 downto 0) => s00_axi_araddr(3 downto 2),
      s00_axi_aresetn => s00_axi_aresetn,
      s00_axi_arvalid => s00_axi_arvalid,
      s00_axi_awaddr(1 downto 0) => s00_axi_awaddr(3 downto 2),
      s00_axi_awvalid => s00_axi_awvalid,
      s00_axi_bready => s00_axi_bready,
      s00_axi_bvalid => s00_axi_bvalid,
      s00_axi_rdata(31 downto 0) => s00_axi_rdata(31 downto 0),
      s00_axi_rready => s00_axi_rready,
      s00_axi_wdata(31 downto 0) => s00_axi_wdata(31 downto 0),
      s00_axi_wready => s00_axi_wready,
      s00_axi_wstrb(3 downto 0) => s00_axi_wstrb(3 downto 0),
      s00_axi_wvalid => s00_axi_wvalid
    );
end STRUCTURE;
