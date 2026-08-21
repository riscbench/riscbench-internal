# Note: This python file loads the environment variables and uses it to run dependent scripts
import json
import os
import sys
from datetime import datetime

vivado_path = ""
vitis_path = ""
uart_port = ""
uart_baud_rate = "9600" #default
run_path = ""

def load_env(env_file, config):
    global vivado_path, vitis_path, uart_port, uart_baud_rate, run_path

    print("[Info] Loading Environment Paths and Variables...")

    current_time = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    run_path = (f"./runs/{current_time}-{config['d_id'][0]}")

    # Check if the file exists
    if not os.path.exists(env_file):
        print(f"[Error] Environment file '{env_file}' does not exist.")
        return -1

    # Check if the file is empty
    if os.path.getsize(env_file) == 0:
        print(f"[Warning] Environment file '{env_file}' is empty.")
        return -1

    try:
        with open(env_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        vivado_path = data.get("vivado_path", vivado_path)
        vitis_path = data.get("vitis_path", vitis_path)
        uart_port = data.get("uart_port", uart_port)
        uart_baud_rate = data.get("uart_baud_rate", uart_baud_rate)

        return env_check(config)


    except json.JSONDecodeError as e:
        print(f"[Error] Failed to parse '{env_file}': Invalid JSON format ({e}).")
        return -1
    except Exception as e:
        print(f"[Error] Error reading '{env_file}': {e}")
        return -1



def env_check(config):
    global vivado_path, vitis_path, uart_port, uart_baud_rate, run_path

    print("[Info] Checking for missing environment paths or variables...")

    err_flag = 0

    if (config["d_id"][1] == 0): #Xilinx
        if (vivado_path == "") or (vivado_path == None):
            print("[Error] Vivado Path is missing, update env.json")
            err_flag = -1
        if (vitis_path == "") or (vitis_path == None):
            print("[Error] Vitis Path is missing, update env.json")
            err_flag = -1
        if (uart_port == "") or (uart_port == None):
            print("[Error] UART Port is missing, update env.json")
            err_flag = -1
        if (uart_baud_rate == "") or (uart_baud_rate == None):
            print("[Error] UART baud rate is missing, update env.json")
            err_flag = -1

    if (err_flag == -1):

        print("")
        print("[Error] Environment loading failed...")
        print("[Error] Exiting RISCBench...")

        sys.exit()

    if (err_flag == 0):
        os.makedirs(run_path, exist_ok=True)
        print(f"[Info] Runtime Folder created: {run_path}")

    return err_flag
