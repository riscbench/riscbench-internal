import os
import common

vendor_list = []
device_list = []
workload_list = []
precision_list = []
size_list = []

def get_folder_names(path):
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
    device_list = get_folder_names(common.vendor_path)

def gen_workload_list(device_name):
    global workload_list
    common.device_path = common.vendor_path + "/" + device_name
    workload_list = get_folder_names(common.device_path)

def gen_precision_list(workload_name):
    global precision_list
    common.workload_path = common.device_path + "/" + workload_name
    precision_list = get_folder_names(common.workload_path)
    

def gen_size_list(precision_name):
    global size_list
    common.precision_path = common.workload_path + "/" + precision_name
    size_list = common.full_size_list
