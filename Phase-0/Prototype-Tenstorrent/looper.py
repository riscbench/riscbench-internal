import os
import shutil
import subprocess
import re

# Path settings - adjust as needed
LOOPBACK_CPP = "tt_metal/programming_examples/fm_loopback/loopback.cpp"
BUILD_SCRIPT = "./build_metal.sh --enable-profiler --build-programming-examples"
EXE_PATH = "./build/programming_examples/fm_loopback"
PROFILE_LOG = "generated/profiler/.logs/profile_log_device.csv"
PROFILE_DST_DIR = os.path.expanduser("~/fm_profiles/WRITE")

# The tile values to test
tile_values = [1, 2, 4] #, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576, 2097152]

def patch_num_tiles(val):
    with open(LOOPBACK_CPP, 'r') as f:
        lines = f.readlines()
    # Replace the line that declares num_tiles
    for i, l in enumerate(lines):
        if re.match(r'\s*constexpr\s+uint32_t\s+num_tiles\s*=', l):
            lines[i] = f'constexpr uint32_t num_tiles = {val};\n'
            break
    with open(LOOPBACK_CPP, 'w') as f:
        f.writelines(lines)

def build_project():
    subprocess.check_call(BUILD_SCRIPT, shell=True)

def run_loopback():
    env = os.environ.copy()
    env["TT_METAL_DEVICE_PROFILER"] = "1"
    subprocess.check_call(EXE_PATH, shell=True, env=env)

def copy_profile(num_tiles):
    dst_file = os.path.join(PROFILE_DST_DIR, f"{num_tiles}.csv")
    if not os.path.exists(PROFILE_DST_DIR):
        os.makedirs(PROFILE_DST_DIR)
    shutil.copyfile(PROFILE_LOG, dst_file)

for val in tile_values:
    print(f"Running for num_tiles = {val}")
    patch_num_tiles(val)
    build_project()
    run_loopback()
    copy_profile(val)
    print(f"Profile for {val} saved.\n")
