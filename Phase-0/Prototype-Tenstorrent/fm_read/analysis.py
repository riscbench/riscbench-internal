import os
import pandas as pd
import re

col_names = [
    'PCIe slot', 'core_x', 'core_y', 'proctype', 'timer_id',
    'time[cycles since reset]', 'data', 'run host ID', 'zone name', 'type',
    'source line', 'source file', 'meta data'
]

PROFILE_DIR = os.path.expanduser(".")
results = []

def natural_sort_key(s):
    # Extract integer from filename before '.csv' for sorting
    return int(re.findall(r'\d+', s)[0]) if re.findall(r'\d+', s) else s

files = [f for f in os.listdir(PROFILE_DIR) if f.endswith(".csv")]
files = sorted(files, key=natural_sort_key)

for filename in files:
    if filename.endswith(".csv"):
        path = os.path.join(PROFILE_DIR, filename)
        tilesize = int(os.path.splitext(filename)[0])
        # Read with no header, then apply our header after dropping top 2 lines

        df = pd.read_csv(path, skiprows=2, header=None, names=col_names, skipinitialspace=True)

        #df = pd.read_csv(path, header=None)
        print(f"Loaded {filename}:")
        print(df)
        print("\n---\n")

        # Now continue analysis as before
        zone_df = df[df["zone name"] == "RD_SECTION"]
        start_time = float(zone_df[zone_df["type"] == "ZONE_START"]["time[cycles since reset]"].iloc[0])
        end_time = float(zone_df[zone_df["type"] == "ZONE_END"]["time[cycles since reset]"].iloc[0])
        readcycles = end_time - start_time
        bytes_ = 32 * 32 * 2 * tilesize
        gflops = bytes_ / readcycles if readcycles != 0 else 0.0
        results.append({
            "tilesize": tilesize,
            "readcycles": readcycles,
            "bytes": bytes_,
            "GFLOPS": gflops
        })

results_df = pd.DataFrame(results)
print("Summary DataFrame:")
print(results_df)

results_df.to_csv(os.path.join(PROFILE_DIR, "summary_results.csv"), index=False)
print(f"Results saved to {os.path.join(PROFILE_DIR, 'summary_results.csv')}")
