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
    parser.add_argument("-r", "--result", nargs="?", help="Show the results of the previous run (if available)", const='latest')
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
        elif os.path.exists(args.result):
            print("[Info] Result option selected, displaying results...")
            print(f"[Info] Selected {args.result} run")
            result_handler_ui(args.result)
            exit(0)
        else:
            recent_run_path = most_recent_run(args.result)
            if recent_run_path:
                print("[Info] Result option selected, displaying results...")
                print(f"[Info] Selecting the most recent {args.result} run")
                result_handler_ui(recent_run_path)
                exit(0)
            else:
                print(f"[Error] No {args.result} runs found")
            exit(0)

    ## Parse Config (if exists)
    config_data = config_flow(args)

    ## Override config with extra parameters (if exists)
    vendor_val = args.vendor if args.vendor is not None else config_data.get("vendor")
    device_val = args.device if args.device is not None else config_data.get("device")
    workload_val = args.workload if args.workload is not None else config_data.get("workload")
    precision_val = args.precision if args.precision is not None else config_data.get("precision")
    size_val = args.size if args.size is not None else config_data.get("size")

    ## Interactive UI for empty values
    ## and
    ## Convert Device val to Device IDs

    ## Generate Vendors List
    path_handler.gen_vend_list()

    if vendor_val is not None:
        vendor_matches = [v for v in path_handler.vendor_list if v.lower() == vendor_val.lower()]
        if not vendor_matches:
            print(f"[Error] Unsupported vendor '{vendor_val}'. Supported vendors: {', '.join(path_handler.vendor_list)}", file=sys.stderr)
            sys.exit(1)
        vendor_val = vendor_matches[0]
        v_id = path_handler.vendor_list.index(vendor_val)
    else:
        vendor_val, v_id = cli_handler.vendor_selector()

    # Generate device list
    path_handler.gen_dev_list(vendor_val)

    if device_val is not None:
        device_matches = [d for d in path_handler.device_list if d.lower() == device_val.lower()]
        if not device_matches:
            print(f"[Error] Unsupported device '{device_val}'. Supported devices: {', '.join(path_handler.device_list)}", file=sys.stderr)
            sys.exit(1)
        device_val = device_matches[0]
        d_id = path_handler.device_list.index(device_val)
    else:
        device_val, d_id = cli_handler.device_selector()

    # Generate workloads list from folders
    path_handler.gen_workload_list(device_val)

    if workload_val is not None:
        workload_matches = [w for w in path_handler.workload_list if w.lower().replace("-", "_") == workload_val.lower().replace("-", "_")]
        if not workload_matches:
            print(f"[Error] Unsupported workload '{workload_val}'. Supported workloads: {', '.join(path_handler.workload_list)}", file=sys.stderr)
            sys.exit(1)
        workload_val = workload_matches[0]
        w_id = path_handler.workload_list.index(workload_val)
    else:
        workload_val, w_id = cli_handler.workload_selector()

    # Generate precision list from folders
    path_handler.gen_precision_list(workload_val)

    if precision_val is not None:
        precision_matches = [p for p in path_handler.precision_list if p.lower() == precision_val.lower()]
        if not precision_matches:
            print(f"[Error] Unsupported precision '{precision_val}'. Supported precisions: {', '.join(path_handler.precision_list)}", file=sys.stderr)
            sys.exit(1)
        precision_val = precision_matches[0]
        p_id = path_handler.precision_list.index(precision_val)
    else:
        precision_val, p_id = cli_handler.precision_selector()

    # Generate size list from folders
    path_handler.gen_size_list(precision_val)

    if size_val is not None:
        size_matches = [s for s in path_handler.size_list if str(s).lower() == str(size_val).lower()]
        if not size_matches:
            # Allow custom integer sizes directly
            try:
                int(size_val)
                s_id = 0
            except ValueError:
                print(f"[Error] Invalid size '{size_val}'.", file=sys.stderr)
                sys.exit(1)
        else:
            size_val = size_matches[0]
            s_id = path_handler.size_list.index(size_val)
    else:
        size_val, s_id = cli_handler.size_selector()

    return {
        "v_id": [vendor_val, v_id],
        "d_id": [device_val, d_id],
        "w_id": [workload_val, w_id],
        "p_id": [precision_val, p_id],
        "s_id": [size_val, s_id],
    }
    
if __name__ == "__main__":
    pass