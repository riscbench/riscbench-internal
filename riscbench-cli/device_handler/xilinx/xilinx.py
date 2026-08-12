import subprocess
import os
import csv
import time
import threading
from datetime import datetime
import serial

def uart_logger(port, baudrate, csv_path, stop_event):
    """
    Background thread function that continuously reads lines from UART
    and appends FLOPS/results with timestamps into a CSV file.
    """
    # Ensure the directory for CSV exists
    csv_dir = os.path.dirname(csv_path)
    if csv_dir and not os.path.exists(csv_dir):
        os.makedirs(csv_dir, exist_ok=True)

    file_exists = os.path.isfile(csv_path)

    try:
        # Open serial port
        with serial.Serial(port, baudrate, timeout=1) as ser, \
             open(csv_path, mode='w', newline='', encoding='utf-8') as csv_file:
            
            writer = csv.writer(csv_file)
            
            # Write header if creating a new file
            if not file_exists:
                writer.writerow(["timestamp", "raw_output"])
                csv_file.flush()

            print(f"[UART Logger] Listening on {port} @ {baudrate} baud...")

            while not stop_event.is_set():
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            timestamp = datetime.now().isoformat()
                            writer.writerow([timestamp, line])
                            csv_file.flush()  # Instantly write to file
                            print(f"[UART Output] {line}")
                    except Exception as e:
                        print(f"[UART Error] Error reading line: {e}")
                else:
                    time.sleep(0.01)  # Yield CPU time

    except serial.SerialException as e:
        print(f"[UART Error] Could not open/access serial port '{port}': {e}")

def run_vivado_ila(settings_path="/path/to/Xilinx/Vivado/VERSION/settings64.sh", tcl_script="run_file.tcl", cwd=None):
    # Verify settings file exists
    if not os.path.exists(settings_path):
        error_msg = f"Error: Vivado settings script not found at '{settings_path}'."
        print(error_msg)
        return False, error_msg

    # Verify TCL script exists
    tcl_path = os.path.abspath(tcl_script) if cwd is None else os.path.join(cwd, tcl_script)
    if not os.path.exists(tcl_path):
        error_msg = f"Error: TCL script not found at '{tcl_path}'."
        print(error_msg)
        return False, error_msg

    # Combine sourcing Vivado and executing in batch mode
    command = f"source {settings_path} && vivado -mode batch -source {tcl_script}"
    
    print(f"Running Vivado script:\n  Command: {command}")
    if cwd:
        print(f"  Working Directory: {cwd}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            executable='/bin/bash',
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("Vivado executed successfully!")
        return True, result.stdout
        
    except subprocess.CalledProcessError as e:
        print(f"Error running Vivado (Exit Code {e.returncode}):")
        print(f"Error output:\n{e.stderr}")
        return False, e.stderr

def xil_run_script():
    print("xil run Script")
    
    # UPDATE THE SETTINGS SCRIPT 

    VIVADO_SETTINGS = "/home/protox/Xilinx/2025.2/Vivado/settings64.sh"
    TCL_SCRIPT_PATH = "/home/protox/Projects/vibecode_playground/riscbench-dev/device_handler/xilinx/run_file.tcl"
    
    # UART & CSV configuration
    UART_PORT = "/dev/ttyUSB1"  # Update this to match your serial device (e.g., /dev/ttyUSB1, /dev/ttyACM0)
    BAUD_RATE = 9600
    CSV_OUTPUT_PATH = "./result_handler/UART_results.csv"

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
            print("Output logs:")
            print(output)

    finally:
        # Allow extra time for any residual UART bytes to transmit after Vivado finishes
        print("Waiting 20 seconds for final UART messages...")
        time.sleep(20.0)

        # Stop the background logging thread cleanly
        stop_logging.set()
        uart_thread.join()
        print(f"Finished UART logging. Results saved to {CSV_OUTPUT_PATH}")

if __name__ == "__main__":
    xil_run_script()
