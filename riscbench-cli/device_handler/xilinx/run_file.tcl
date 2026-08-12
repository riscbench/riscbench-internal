set bit_file    "./device_handler/xilinx/top_design.bit"
set ltx_file    "./device_handler/xilinx/top_design.ltx"
set elf_file    "./device_handler/xilinx/app.elf"
set ila_out     "./result_handler/ila_captured_data.ila"
set csv_out     "./result_handler/ila_captured_data.csv"
set hw_host     "localhost"
set hw_port     "3121"

# Target the MicroBlaze V Hart core context directly
set target_proc "Hart*"

# Target probe and Verilog-formatted trigger value (e.g., 1'b1, 1'b0, 8'hFF, or _RNG for transition)
set target_probe_name "design_1_i/CUSTOM_addsub1b_0_data_in_ip"
set trigger_value      "1'b1"

puts "=================================================="
puts "1. Connecting Hardware Server & Programming FPGA"
puts "=================================================="

open_hw_manager
connect_hw_server -url ${hw_host}:${hw_port} -allow_non_jtag
open_hw_target

set my_device [lindex [get_hw_devices] 0]
current_hw_device $my_device

set_property PROGRAM.FILE $bit_file $my_device
if {[file exists $ltx_file]} {
    set_property PROBES.FILE $ltx_file $my_device
    set_property FULL_PROBES.FILE $ltx_file $my_device
}
program_hw_devices $my_device
refresh_hw_device $my_device

set ila_core [get_hw_ilas -of_objects $my_device]
if {[llength $ila_core] == 0} {
    puts "Error: No ILA debug cores found in device."
    return -code error "No ILA Core"
}
puts "Found ILA Core: $ila_core"

puts "=================================================="
puts "2. Configuring Probe Trigger Settings"
puts "=================================================="

# Retrieve handle for the target probe
set probe_obj [get_hw_probes -of_objects $ila_core -filter "NAME =~ \"*$target_probe_name*\""]

if {[llength $probe_obj] == 0} {
    puts "Error: Probe '$target_probe_name' not found in LTX file."
    puts "Available probes:"
    foreach p [get_hw_probes -of_objects $ila_core] {
        puts "  - $p"
    }
    return -code error "Probe Not Found"
}

puts "Configuring Probe: $probe_obj"

# Apply Verilog-formatted compare string (e.g., eq1'b1 or eq8'hAA)
set_property TRIGGER_COMPARE_VALUE "eq${trigger_value}" $probe_obj

# Set trigger position near middle of the trace buffer
set_property CONTROL.TRIGGER_POSITION 512 $ila_core

puts "=================================================="
puts "3. Halting Core & Flashing ELF via XSDB"
puts "=================================================="

set xsdb_setup "
connect -host $hw_host -port $hw_port
targets -set -filter {name =~ \"*$target_proc*\"}
rst -core
dow $elf_file
"
exec xsdb -eval $xsdb_setup

puts "=================================================="
puts "4. Arming ILA Core & Resuming Processor"
puts "=================================================="

# Arm the ILA to listen BEFORE releasing CPU execution
run_hw_ila $ila_core

# Resume CPU execution
set xsdb_run "
connect -host $hw_host -port $hw_port
targets -set -filter {name =~ \"*$target_proc*\"}
con
"
exec xsdb -eval $xsdb_run

puts "=================================================="
puts "5. Waiting for ILA Trigger & Saving Capture"
puts "=================================================="

# Wait for signal condition or fallback to manual trigger on timeout
if {[catch {wait_on_hw_ila $ila_core -timeout 10} err]} {
    puts "Warning: Trigger timeout! Signal did not reach $trigger_value."
    puts "Forcing immediate ILA capture..."
    run_hw_ila -trigger_now $ila_core
    wait_on_hw_ila $ila_core -timeout 2
}

set captured_data [upload_hw_ila_data $ila_core]

# Write output files
file mkdir [file dirname $ila_out]
write_hw_ila_data -force $ila_out $captured_data
write_hw_ila_data -force -csv_file $csv_out $captured_data

puts "=================================================="
puts "Execution and ILA Capture Complete!"
puts "=================================================="

close_hw_target
disconnect_hw_server
close_hw_manager
