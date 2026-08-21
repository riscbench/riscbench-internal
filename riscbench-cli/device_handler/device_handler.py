# Device Handler Program

from .xilinx import xilinx_handle
from .altera import altera_handle
from .tenstorrent import tenstorrent_handle

def device_handler(config):
    
    device_id = config["d_id"][1]

    if device_id == 0:
        xilinx_handle(config)
        pass
    elif device_id == 1:
        altera_handle()
        pass
    elif device_id == 2:
        tenstorrent_handle()
        pass
    else:
        #out_of_scope_error()
        print("Oops")