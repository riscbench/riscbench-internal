# Front End Program

import argparse
import json
import os
import sys

from .frontend_helper import select_menu
from common.common import device_list, workload_list, precision_list, vecsize_list

def device_selector():
    print("=========================================================================")
    print("                        RiscBench Device Selector                        ")
    print("=========================================================================")
    print("                                                                         ")

    #device_list = ["Xilinx FPGA - Arty A7","Altera FPGA - Terasic DE25","Tenstorrent Wormhole N300D"]
    device, d_id = select_menu("Select device to be profiled", device_list)

    print("                                                                         ")
    print("=========================================================================")
    print("                                                                         ")

    print(f"{device} device was chosen")
    return device, d_id

def workload_selector(d_id):
    print("=========================================================================")
    print("                       RiscBench Workload Selector                       ")
    print("=========================================================================")
    print("                                                                         ")
     
    workload, w_id = select_menu("Choose workload to be profiled", workload_list)
    
    if (d_id < 2):
        precision, p_id = select_menu("Choose workload precision", precision_list[:-3])
    else:
        precision, p_id = select_menu("Choose workload precision", precision_list)

    vecsize, v_id = select_menu("Choose workload size", vecsize_list)

    print("                                                                         ")
    print("=========================================================================")
    print("                                                                         ")

    return (w_id, p_id, v_id)

def frontend_qa():
    device, d_id = device_selector()
    w_id, p_id, v_id = workload_selector(d_id)
    
    return(d_id, w_id, p_id, v_id)


def parse_args():
    parser = argparse.ArgumentParser(description="RiscBench Main Program")
    parser.add_argument("-c", "--config", help="Path to config file (JSON or key-value format)")
    parser.add_argument("-d", "--device", help="Device to be profiled (name or index)")
    parser.add_argument("-w", "--workload", help="Workload to be profiled (name or index)")
    parser.add_argument("-p", "--precision", help="Workload precision (name or index)")
    parser.add_argument("-v", "--vectorsize", help="Workload size / vector size (name or index)")
    parser.add_argument("-r", "--result", help="Show the results of the previous run (if available)", action='store_true')
    return parser.parse_args()


def load_config(config_path):
    if not os.path.exists(config_path):
        print(f"Error: Config file '{config_path}' not found.")
        sys.exit(1)
    
    with open(config_path, "r") as f:
        content = f.read().strip()
    
    if not content:
        return {}

    # Try JSON first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Try simple key-value format (e.g. device=2 or device: 2)
    config = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith(';'):
            continue
        delimiter = '=' if '=' in line else ':' if ':' in line else None
        if delimiter:
            k, v = line.split(delimiter, 1)
            config[k.strip().lower()] = v.strip()
    return config


def resolve_option(value, choices, name):
    if value is None:
        return None, None
    # Try to convert to int index
    try:
        idx = int(value)
        if 0 <= idx < len(choices):
            return choices[idx], idx
    except ValueError:
        pass

    # Try case-insensitive string match
    val_str = str(value).strip().lower()
    for idx, choice in enumerate(choices):
        if choice.strip().lower() == val_str:
            return choice, idx

    # If invalid, print error and exit
    print(f"Error: Invalid {name} '{value}'. Must be one of index/name in {choices}")
    sys.exit(1)


if __name__ == "__main__":
    pass
    