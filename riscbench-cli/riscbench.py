## RISCBENCH MAIN PROGRAM

import common
import result_handler

from front_end import front_end_handler
from device_handler import device_handler

if __name__ == "__main__":

    ## Step 1: Generate UI for configuration handling 
    config = front_end_handler()
    #print(config)

    ## Step 2: Device Handler
    device_handler(config)


