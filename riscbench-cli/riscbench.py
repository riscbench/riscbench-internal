## RISCBENCH MAIN PROGRAM

from front_end import frontend_qa, parse_args, load_config, resolve_option
import common
from device_handler.device_handler import device_handler
from result_handler import rh_ui as result_handler_ui
from result_handler import rh_processor

if __name__ == "__main__":
    args = parse_args()

    if args.result:
        print("Result option selected, displaying results...")
        result_handler_ui()
        exit(0)

    config_data = {}
    if args.config:
        config_data = load_config(args.config)
    else:
        print("Config file not selected, checking other inputs...")

    device_val = args.device if args.device is not None else config_data.get("device")
    workload_val = args.workload if args.workload is not None else config_data.get("workload")
    precision_val = args.precision if args.precision is not None else config_data.get("precision")
    vectorsize_val = args.vectorsize if args.vectorsize is not None else config_data.get("vectorsize")

    d_id = 0
    w_id = 0
    p_id = 0
    v_id = 0

    if not any([device_val, workload_val, precision_val, vectorsize_val]):
        print("No input switches detected, Switching to Interactive mode...")
        d_id, w_id, p_id, v_id = frontend_qa()

    outcome = device_handler(d_id)
    rh_processor()



