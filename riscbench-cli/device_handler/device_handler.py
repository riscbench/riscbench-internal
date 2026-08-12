# Device Handler Program

from .xilinx import xil_run_script

def xilinx_handle():
    print("Starting Xilinx Script...")
    xil_run_script()

def altera_handle():
    pass

def tenstorrent_handle():
    pass


def device_handler(device_id):
    
    if device_id == 0:
        xilinx_handle()
        pass
    elif device_id == 1:
        #altera_handle()
        pass
    elif device_id == 2:
        #tenstorrent_handle()
        pass
    else:
        #out_of_scope_error()
        print("Oops")