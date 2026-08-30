#from .utils import run_command, run_executable

HOME = "../tt-metal"
VPATH = HOME + "/python_env"

def tt_compile_program():
    run_executable("build_metal.sh --build-programming-examples", shared.HOME, shared.VPATH)
    # Needs to be updated

def tt_execute_program(workload):
    run_executable(workload.exec_path, shared.HOME, shared.VPATH, ["TT_METAL_DEVICE_PROFILER=1"])
    # Needs to be updated

def tenstorrent_handle():
    #tt_compile_program()
    #tt_execute_program(workload)

    pass