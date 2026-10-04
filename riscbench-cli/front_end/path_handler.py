import os
import common

vendor_list = []
device_list = []
workload_list = []
precision_list = []
size_list = []

ALTERA_DEVICES = ["niosv"]
ALTERA_WORKLOADS = ["Vector_Add", "Vector_Mul", "Dot", "Matrix_Mul", "SAXPY"]
ALTERA_PRECISIONS = ["Int8", "Int16", "Int32", "FP16", "FP32"]

def get_folder_names(path):
    if not os.path.exists(path):
        return []
    return [
        name for name in os.listdir(path)
        if os.path.isdir(os.path.join(path, name))
        and not name.startswith("__")
        and name != "__pycache__"
        and name != "artifacts"
    ]

def gen_vend_list():
    global vendor_list
    vendor_list = get_folder_names(common.vendor_path)

def gen_dev_list(vendor_name):
    global device_list
    common.vendor_path = common.vendor_path + "/" + vendor_name
    folders = get_folder_names(common.vendor_path)
    if "altera" in common.vendor_path.lower():
        device_list = ALTERA_DEVICES if not folders else (ALTERA_DEVICES + [f for f in folders if f not in ALTERA_DEVICES])
    else:
        device_list = folders

def gen_workload_list(device_name):
    global workload_list
    common.device_path = common.vendor_path + "/" + device_name
    folders = get_folder_names(common.device_path)
    if "altera" in common.vendor_path.lower():
        workload_list = ALTERA_WORKLOADS
    else:
        workload_list = folders

def gen_precision_list(workload_name):
    global precision_list
    common.workload_path = common.device_path + "/" + workload_name
    folders = get_folder_names(common.workload_path)
    if "altera" in common.vendor_path.lower():
        precision_list = ALTERA_PRECISIONS
    else:
        precision_list = folders

def gen_size_list(precision_name):
    global size_list
    common.precision_path = common.workload_path + "/" + precision_name
    size_list = common.full_size_list
