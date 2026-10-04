package require -exact qsys 26.1

set_module_property NAME sit_engine_pd
set_module_property VERSION 1.2
set_module_property DISPLAY_NAME "SIT Engine DDR Manager"
set_module_property DESCRIPTION "SIT engine with one 32-bit Avalon-MM DDR manager"
set_module_property INTERNAL false
set_module_property OPAQUE_ADDRESS_MAP true
set_module_property INSTANTIATE_IN_SYSTEM_MODULE true
set_module_property EDITABLE false

add_fileset QUARTUS_SYNTH QUARTUS_SYNTH {} {}
set_fileset_property QUARTUS_SYNTH TOP_LEVEL sit_engine_pd
add_fileset_file ../hardware/rtl/compute/fp32_pkg.sv SYSTEM_VERILOG PATH ../hardware/rtl/compute/fp32_pkg.sv
add_fileset_file ../hardware/rtl/memory/data_mover_pkg.sv SYSTEM_VERILOG PATH ../hardware/rtl/memory/data_mover_pkg.sv
add_fileset_file ../hardware/rtl/compute/fp_add_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/compute/fp_add_wrapper.sv
add_fileset_file ../hardware/rtl/compute/fp_mul_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/compute/fp_mul_wrapper.sv
add_fileset_file ../hardware/rtl/compute/int16_add_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/compute/int16_add_wrapper.sv
add_fileset_file ../hardware/rtl/compute/int16_mul_wide_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/compute/int16_mul_wide_wrapper.sv
add_fileset_file ../hardware/rtl/compute/int16_mul_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/compute/int16_mul_wrapper.sv
add_fileset_file ../hardware/rtl/compute/int64_add_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/compute/int64_add_wrapper.sv
add_fileset_file ../hardware/rtl/compute/int8_add_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/compute/int8_add_wrapper.sv
add_fileset_file ../hardware/rtl/compute/int8_mul_wide_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/compute/int8_mul_wide_wrapper.sv
add_fileset_file ../hardware/rtl/compute/int8_mul_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/compute/int8_mul_wrapper.sv
add_fileset_file ../hardware/rtl/control/sit_csr.sv SYSTEM_VERILOG PATH ../hardware/rtl/control/sit_csr.sv
add_fileset_file ../hardware/rtl/control/workload_dispatch.sv SYSTEM_VERILOG PATH ../hardware/rtl/control/workload_dispatch.sv
add_fileset_file ../hardware/rtl/legacy/dot.sv SYSTEM_VERILOG PATH ../hardware/rtl/legacy/dot.sv
add_fileset_file ../hardware/rtl/legacy/matmul.sv SYSTEM_VERILOG PATH ../hardware/rtl/legacy/matmul.sv
add_fileset_file ../hardware/rtl/legacy/saxpy.sv SYSTEM_VERILOG PATH ../hardware/rtl/legacy/saxpy.sv
add_fileset_file ../hardware/rtl/legacy/sit_control.sv SYSTEM_VERILOG PATH ../hardware/rtl/legacy/sit_control.sv
add_fileset_file ../hardware/rtl/legacy/sit_engine_compat.sv SYSTEM_VERILOG PATH ../hardware/rtl/legacy/sit_engine_compat.sv
add_fileset_file ../hardware/rtl/legacy/vecadd.sv SYSTEM_VERILOG PATH ../hardware/rtl/legacy/vecadd.sv
add_fileset_file ../hardware/rtl/legacy/vecmul.sv SYSTEM_VERILOG PATH ../hardware/rtl/legacy/vecmul.sv
add_fileset_file ../hardware/rtl/matrix/matmul_engine_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/matrix/matmul_engine_wrapper.sv
add_fileset_file ../hardware/rtl/matrix/matmul_int16_packed.sv SYSTEM_VERILOG PATH ../hardware/rtl/matrix/matmul_int16_packed.sv
add_fileset_file ../hardware/rtl/matrix/matmul_int8_packed.sv SYSTEM_VERILOG PATH ../hardware/rtl/matrix/matmul_int8_packed.sv
add_fileset_file ../hardware/rtl/matrix/matmul_tiled.sv SYSTEM_VERILOG PATH ../hardware/rtl/matrix/matmul_tiled.sv
add_fileset_file ../hardware/rtl/memory/ddr_reader.sv SYSTEM_VERILOG PATH ../hardware/rtl/memory/ddr_reader.sv
add_fileset_file ../hardware/rtl/memory/ddr_writer.sv SYSTEM_VERILOG PATH ../hardware/rtl/memory/ddr_writer.sv
add_fileset_file ../hardware/rtl/memory/local_buffer.sv SYSTEM_VERILOG PATH ../hardware/rtl/memory/local_buffer.sv
add_fileset_file ../hardware/rtl/memory/shared_data_mover.sv SYSTEM_VERILOG PATH ../hardware/rtl/memory/shared_data_mover.sv
add_fileset_file ../hardware/rtl/monitoring/sit_counters.sv SYSTEM_VERILOG PATH ../hardware/rtl/monitoring/sit_counters.sv
add_fileset_file ../hardware/rtl/monitoring/sit_trace.sv SYSTEM_VERILOG PATH ../hardware/rtl/monitoring/sit_trace.sv
add_fileset_file ../hardware/rtl/top/sit_engine.sv SYSTEM_VERILOG PATH ../hardware/rtl/top/sit_engine.sv
add_fileset_file ../hardware/rtl/top/sit_engine_pd.sv SYSTEM_VERILOG PATH ../hardware/rtl/top/sit_engine_pd.sv TOP_LEVEL_FILE
add_fileset_file ../hardware/rtl/vector/saxpy_engine_fp32.sv SYSTEM_VERILOG PATH ../hardware/rtl/vector/saxpy_engine_fp32.sv
add_fileset_file ../hardware/rtl/vector/vecadd_engine_fp32.sv SYSTEM_VERILOG PATH ../hardware/rtl/vector/vecadd_engine_fp32.sv
add_fileset_file ../hardware/rtl/vector/vecadd_engine_int16.sv SYSTEM_VERILOG PATH ../hardware/rtl/vector/vecadd_engine_int16.sv
add_fileset_file ../hardware/rtl/vector/vecadd_engine_int8.sv SYSTEM_VERILOG PATH ../hardware/rtl/vector/vecadd_engine_int8.sv
add_fileset_file ../hardware/rtl/vector/vecmul_engine_fp32.sv SYSTEM_VERILOG PATH ../hardware/rtl/vector/vecmul_engine_fp32.sv
add_fileset_file ../hardware/rtl/vector/vecmul_engine_int16.sv SYSTEM_VERILOG PATH ../hardware/rtl/vector/vecmul_engine_int16.sv
add_fileset_file ../hardware/rtl/vector/vecmul_engine_int8.sv SYSTEM_VERILOG PATH ../hardware/rtl/vector/vecmul_engine_int8.sv
add_fileset_file ../hardware/rtl/vector/vector_chunked.sv SYSTEM_VERILOG PATH ../hardware/rtl/vector/vector_chunked.sv
add_fileset_file ../hardware/rtl/vector/vector_engine_wrapper.sv SYSTEM_VERILOG PATH ../hardware/rtl/vector/vector_engine_wrapper.sv
add_fileset_file ../hardware/rtl/vector/vector_int8_packed.sv SYSTEM_VERILOG PATH ../hardware/rtl/vector/vector_int8_packed.sv
add_fileset_file riscbench_fp32_add.v VERILOG PATH ../hardware/ip/native_fp/riscbench_fp32_add/synth/riscbench_fp32_add.v
add_fileset_file riscbench_fp32_add_agilex_native_floating_point_dsp_100_m5fvifq.v VERILOG PATH ../hardware/ip/native_fp/riscbench_fp32_add/agilex_native_floating_point_dsp_100/synth/riscbench_fp32_add_agilex_native_floating_point_dsp_100_m5fvifq.v
add_fileset_file riscbench_fp32_mul.v VERILOG PATH ../hardware/ip/native_fp/riscbench_fp32_mul/synth/riscbench_fp32_mul.v
add_fileset_file riscbench_fp32_mul_agilex_native_floating_point_dsp_100_m5tk52i.v VERILOG PATH ../hardware/ip/native_fp/riscbench_fp32_mul/agilex_native_floating_point_dsp_100/synth/riscbench_fp32_mul_agilex_native_floating_point_dsp_100_m5tk52i.v

add_interface clock clock end
set_interface_property clock clockRate 0
add_interface_port clock clk clk Input 1

add_interface reset reset end
set_interface_property reset associatedClock clock
set_interface_property reset synchronousEdges DEASSERT
add_interface_port reset reset reset Input 1

add_interface avalon_master avalon start
set_interface_property avalon_master addressUnits SYMBOLS
set_interface_property avalon_master associatedClock clock
set_interface_property avalon_master associatedReset reset
set_interface_property avalon_master bitsPerSymbol 8
set_interface_property avalon_master burstOnBurstBoundariesOnly false
set_interface_property avalon_master burstcountUnits WORDS
set_interface_property avalon_master linewrapBursts false
set_interface_property avalon_master maximumPendingReadTransactions 1
set_interface_property avalon_master maximumPendingWriteTransactions 0
set_interface_property avalon_master readLatency 0
set_interface_property avalon_master waitrequestAllowance 0
add_interface_port avalon_master avm_address address Output 32
add_interface_port avalon_master avm_read read Output 1
add_interface_port avalon_master avm_write write Output 1
add_interface_port avalon_master avm_writedata writedata Output 32
add_interface_port avalon_master avm_byteenable byteenable Output 4
add_interface_port avalon_master avm_burstcount burstcount Output 8
add_interface_port avalon_master avm_waitrequest waitrequest Input 1
add_interface_port avalon_master avm_readdata readdata Input 32
add_interface_port avalon_master avm_readdatavalid readdatavalid Input 1

add_interface csr avalon end
set_interface_property csr addressUnits WORDS
set_interface_property csr associatedClock clock
set_interface_property csr associatedReset reset
set_interface_property csr bitsPerSymbol 8
set_interface_property csr explicitAddressSpan 128
set_interface_property csr maximumPendingReadTransactions 0
set_interface_property csr maximumPendingWriteTransactions 0
set_interface_property csr readLatency 0
set_interface_property csr waitrequestAllowance 0
add_interface_port csr avs_address address Input 5
add_interface_port csr avs_read read Input 1
add_interface_port csr avs_write write Input 1
add_interface_port csr avs_writedata writedata Input 32
add_interface_port csr avs_byteenable byteenable Input 4
add_interface_port csr avs_readdata readdata Output 32
add_interface_port csr avs_waitrequest waitrequest Output 1
set_interface_assignment csr embeddedsw.configuration.isFlash 0
set_interface_assignment csr embeddedsw.configuration.isMemoryDevice 0
set_interface_assignment csr embeddedsw.configuration.isNonVolatileStorage 0
set_interface_assignment csr embeddedsw.configuration.isPrintableDevice 0
