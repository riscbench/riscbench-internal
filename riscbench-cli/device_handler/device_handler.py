# Device Handler Program

from .xilinx import xilinx_handle
from .altera import altera_handle
from .tenstorrent import tenstorrent_handle

def run_by_name(func_name, *args, **kwargs):
    func = globals()[func_name]
    return func(*args, **kwargs)

def device_handler(config):
    
    device_vendor = config["v_id"][0]
    run_by_name(f"{device_vendor}_handle", config)