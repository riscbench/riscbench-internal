# Front End Program

import argparse
import json
import os
import sys
import glob

import common
from result_handler.result_handler import rh_ui as result_handler_ui

from . import cli_handler
from . import path_handler
from .config_handler import config_flow

def parse_args():
    parser = argparse.ArgumentParser(description="RiscBench Main Program")
    parser.add_argument("-c", "--config", help="Path to config file (JSON or key-value format)")
    parser.add_argument("-v", "--vendor", help="Device Vendor Name")
    parser.add_argument("-d", "--device", help="Device to be profiled (name or index)")
    parser.add_argument("-w", "--workload", help="Workload to be profiled (name or index)")
    parser.add_argument("-p", "--precision", help="Workload precision (name or index)")
    parser.add_argument("-s", "--size", help="Workload size / vector size (name or index)")
    parser.add_argument("-r", "--result", nargs="?", help="Show the results of the previous run (if available)", const='latest') #, action='store_true'
    return parser.parse_args()

def most_recent_run(filter_name=None):
    pattern = f"./runs/*{filter_name}*" if filter_name else "./runs/*"
    return max(glob.glob(pattern), key=os.path.getmtime, default=None)

def front_end_handler():

    ## Parse Arguments
    args = parse_args()

    ## Show only results
    if args.result:
        if args.result == "latest":
            recent_run_path = most_recent_run()
            print("[Info] Result option selected, displaying results...")
            print(f"[Info] Selecting the most recent run: {recent_run_path}")
            result_handler_ui(recent_run_path)
            exit(0)
        elif args.result in device_list:
            print("[Info] Result option selected, displaying results...")
            print(f"[Info] Selecting the most recent {args.result} run")
            recent_run_path = most_recent_run(args.result)
            if recent_run_path:
                result_handler_ui(recent_run_path)
            else:
                print(f"[Error] No previous {args.result} runs found")
            exit(0)
        elif os.path.exists(args.result):
            print("[Info] Result option selected, displaying results...")
            print(f"[Info] Selected {args.result} run")
            result_handler_ui(args.result)
            exit(0)
        else:
            print(f"[Error] No {args.result} runs found")
            exit(0)

    ## Parse Config (if exists)
    config_data = config_flow(args)

    ## Override config with extra parameters (if exists)
    vendor_val = args.device if args.device is not None else config_data.get("vendor")
    device_val = args.device if args.device is not None else config_data.get("device")
    workload_val = args.workload if args.workload is not None else config_data.get("workload")
    precision_val = args.precision if args.precision is not None else config_data.get("precision")
    size_val = args.size if args.size is not None else config_data.get("size")

    ## Interactive UI for empty values
    ## and
    ## Convert Device val to Device IDs

    ## Generate Vendors List
    path_handler.gen_vend_list()

    if (not vendor_val) or (vendor_val not in path_handler.vendor_list):
        vendor_val, v_id = cli_handler.vendor_selector()
    else:
        v_id = vendor_list.index(vendor_val)

    # Generate device list
    path_handler.gen_dev_list(vendor_val)

    if (not device_val) or (device_val not in path_handler.device_list):
        device_val, d_id = cli_handler.device_selector()
    else:
        d_id = device_list.index(device_val)

    # Generate workloads list from folders
    path_handler.gen_workload_list(device_val)

    if not workload_val or (workload_val not in path_handler.workload_list):
        workload_val, w_id = cli_handler.workload_selector()
    else:
        w_id = workload_list.index(workload_val)

    # Generate precision list from folders
    path_handler.gen_precision_list(workload_val)

    if not precision_val or (precision_val.lower() not in path_handler.precision_list):
        precision_val, p_id = cli_handler.precision_selector()
    else:
        p_id = precision_list.index(precision_val.lower())

    # Generate size list from folders
    path_handler.gen_size_list(precision_val)

    if not size_val or (size_val not in path_handler.size_list):
        size_val, s_id = cli_handler.size_selector()
    else:
        s_id = size_list.index(size_val)


    return {
        "v_id": [vendor_val, s_id],
        "d_id": [device_val, d_id],
        "w_id": [workload_val, w_id],
        "p_id": [precision_val, p_id],
        "s_id": [size_val, s_id],
    }
    
if __name__ == "__main__":
    pass