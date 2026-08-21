import subprocess
import os
import csv
import time
import threading
from datetime import datetime
import serial

import common
from .xilinx_helper import run_vivado_ila, uart_logger


def xil_compile_bit():
    pass
    bitfile = f"{common.env.run_path}/placeholder.bit"
    ltxfile = f"{common.env.run_path}/placeholder.ltx"
    return(bitfile, ltxfile)

def xil_compile_elf():
    pass
    elffile = f"{common.env.run_path}/placeholder.elf"
    return elffile

def xil_update_tcl(tcl_path="./device_handler/xilinx/run_file.tcl"):
    ila_out_path = f"{common.env.run_path}/ila_captured_data.ila"
    csv_out_path = f"{common.env.run_path}/ila_captured_data.csv"

    with open(tcl_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.startswith("set ila_out"):
            new_lines.append(f'set ila_out     "{ila_out_path}"\n')
        elif line.startswith("set csv_out"):
            new_lines.append(f'set csv_out     "{csv_out_path}"\n')
        else:
            new_lines.append(line)

    with open(tcl_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def xil_run_script(config):
    # UPDATE METHOD
    VIVADO_SETTINGS = f"{common.env.vivado_path}/settings64.sh"
    TCL_SCRIPT_PATH = "./device_handler/xilinx/run_file.tcl"
    
    # UART & CSV configuration
    UART_PORT = common.env.uart_port  # Update this to match your serial device (e.g., /dev/ttyUSB1, /dev/ttyACM0)
    BAUD_RATE = common.env.uart_baud_rate
    CSV_OUTPUT_PATH = f"{common.env.run_path}/UART_results.csv"

    xil_update_tcl()

    # Event flag to control the logging thread
    stop_logging = threading.Event()

    # Start the UART logging thread
    uart_thread = threading.Thread(
        target=uart_logger,
        args=(UART_PORT, BAUD_RATE, CSV_OUTPUT_PATH, stop_logging),
        daemon=True
    )
    uart_thread.start()

    # Give serial port a short moment to initialize before launching Vivado
    time.sleep(0.5)

    try:
        # Run Vivado process (blocking main thread)
        success, output = run_vivado_ila(settings_path=VIVADO_SETTINGS, tcl_script=TCL_SCRIPT_PATH)
        if success:
            print("[Info] Output logs:")
            print(output)

    finally:
        # Allow extra time for any residual UART bytes to transmit after Vivado finishes
        # 20s for sweep data, 5s for individual data
        if (config["v_id"][1] == 0):
            print("[Info] Waiting 20 seconds for final UART messages...")
            time.sleep(20.0)
        else:
            print("[Info] Waiting 5 seconds for final UART messages...")
            time.sleep(5.0)

        # Stop the background logging thread cleanly
        stop_logging.set()
        uart_thread.join()
        print(f"Finished UART logging. Results saved to {CSV_OUTPUT_PATH}")

def xilinx_handle(config):
    print("Starting Xilinx Script...")
    xil_run_script(config)

if __name__ == "__main__":
    xilinx_handle()