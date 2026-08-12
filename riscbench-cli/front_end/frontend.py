# Front End Program

import argparse
import json
import os
import sys

from common.common import *
from result_handler.result_handler import rh_ui as result_handler_ui

from .front_end_helper import select_menu, print_heading_cli
from .config_handler import config_flow


def device_selector():
    print_heading_cli("Device Selector CLI")
    return select_menu("Select device to be profiled", device_list, device_names) 

def workload_selector():
    print_heading_cli("Workload Selector CLI")
    return select_menu("Choose workload to be profiled", workload_list, workload_names)

def precision_selector(d_id): 
    print_heading_cli("Precision Selector CLI")
    if (d_id < 2):
        return select_menu("Choose workload precision", precision_list[:-3])
    else:
        return select_menu("Choose workload precision", precision_list)

def vectorsize_selector():
    print_heading_cli("Vector Size Selector CLI")
    return select_menu("Choose workload size", vectorsize_list)

def parse_args():
    parser = argparse.ArgumentParser(description="RiscBench Main Program")
    parser.add_argument("-c", "--config", help="Path to config file (JSON or key-value format)")
    parser.add_argument("-d", "--device", help="Device to be profiled (name or index)")
    parser.add_argument("-w", "--workload", help="Workload to be profiled (name or index)")
    parser.add_argument("-p", "--precision", help="Workload precision (name or index)")
    parser.add_argument("-v", "--vectorsize", help="Workload size / vector size (name or index)")
    parser.add_argument("-r", "--result", help="Show the results of the previous run (if available)", action='store_true')
    return parser.parse_args()



def front_end_handler():
    ## Parse Arguments
    args = parse_args()

    ## Show only results
    if args.result:
        print("Result option selected, displaying results...")
        result_handler_ui()
        exit(0)

    ## Parse Config (if exists)
    config_data = config_flow(args)

    ## Override config with extra parameters (if exists)
    device_val = args.device if args.device is not None else config_data.get("device")
    workload_val = args.workload if args.workload is not None else config_data.get("workload")
    precision_val = args.precision if args.precision is not None else config_data.get("precision")
    vectorsize_val = args.vectorsize if args.vectorsize is not None else config_data.get("vectorsize")

    ## Interactive UI for empty values
    ## and
    ## Convert Device val to Device IDs

    if (not device_val) or (device_val not in device_list):
        device_val, d_id = device_selector()
    else:
        d_id = device_list.index(device_val)

    if not workload_val or (workload_val not in workload_list):
        workload_val, w_id = workload_selector()
    else:
        w_id = workload_list.index(workload_val)

    if not precision_val or (precision_val.lower() not in precision_list):
        precision_val, p_id = precision_selector(d_id)
    else:
        p_id = precision_list.index(precision_val.lower())
        if (p_id>2) and (d_id<2):
            print("precision mismatch (Alpha doesnt allow FP on FPGA)...")
            precision_val, p_id = precision_selector(d_id)

    if not vectorsize_val or (vectorsize_val not in vectorsize_list):
        vectorsize_val, v_id = vectorsize_selector()
    else:
        v_id = vectorsize_list.index(vectorsize_val)

    # print(f"d: {d_id} : {device_val}")
    # print(f"w: {w_id} : {workload_val}")
    # print(f"p: {p_id} : {precision_val}")
    # print(f"v: {v_id} : {vectorsize_val}")
    # print("")
    # print("")

    return {
        "d_id": [device_val, d_id],
        "w_id": [workload_val, w_id],
        "p_id": [precision_val, p_id],
        "v_id": [vectorsize_val, v_id],
    }
    
if __name__ == "__main__":
    pass