## RISCBENCH MAIN PROGRAM

import common
import result_handler

from common import load_env
from front_end import front_end_handler
from device_handler import device_handler
from result_handler import rh_processor

if __name__ == "__main__":

    ## Step 1: Generate UI for configuration handling 
    config = front_end_handler()

    ## Step 2: Load necessary environment variables and paths
    load_env("env.json", config) 

    ## Step 3: Device Handler
    device_handler(config)

    ## Step 4: SIT
# ================================================================
# ALTERA / NIOS V EXTENSION — UNDER REVIEW
# Added for current RISCBench Altera backend integration.
# Keep isolated until reviewed/approved.
# ================================================================
    if config.get("v_id") and config["v_id"][0] == "altera":
        print("[Info] Altera UART results saved; result visualization is not enabled for this backend yet.")
    else:
        rh_processor()
# ================================================================
# END ALTERA / NIOS V EXTENSION — UNDER REVIEW
# ================================================================

    ## Step 5: Result handler and tools
    

