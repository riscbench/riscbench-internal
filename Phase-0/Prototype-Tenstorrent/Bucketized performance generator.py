import pandas as pd
import numpy as np
import argparse

parser = argparse.ArgumentParser(description="Analyze performance data from a CSV file.")
parser.add_argument('filepath', type=str, help='The path to the input CSV file.')
args = parser.parse_args()

try:
    col_names = [
        'PCIe slot', 'core_x', 'core_y', 'proctype', 'timer_id',
        'time[cycles since reset]', 'data', 'run host ID', 'zone name', 'type',
        'source line', 'source file', 'meta data'
    ]
    df = pd.read_csv(args.filepath, skiprows=2, header=None, names=col_names, skipinitialspace=True)
    print("✅ CSV file loaded successfully.")
except FileNotFoundError:
    print(f"❌ Error: The file '{args.filepath}' was not found. Please ensure the file is in the same directory.")
    exit()

columns_to_drop = [
    'PCIe slot', 'core_x', 'core_y', 'data', 'run host ID',
    'source line', 'source file', 'meta data'
]
df.drop(columns=columns_to_drop, inplace=True, errors='ignore')

# Ensure time column is numeric before sorting
df['time[cycles since reset]'] = pd.to_numeric(df['time[cycles since reset]'])
df.sort_values(by='time[cycles since reset]', inplace=True)
df.reset_index(drop=True, inplace=True)
print("\n✅ Sorted all rows in ascending order based on time.")

# Create the 'runtime' column
min_time_cycle = df['time[cycles since reset]'].min()
df['runtime'] = df['time[cycles since reset]'] - min_time_cycle
print("\n✅ Created 'runtime' column.")

# --- MODIFICATION 1: Calculate a new, specific runtime for bucket analysis ---
# Find the maximum runtime specifically for SRAM ZONE_END events.
sram_end_events = df[(df['zone name'] == 'SRAM THROUGHPUT_SECTION') & (df['type'] == 'ZONE_END')]
if not sram_end_events.empty:
    # This is the new runtime limit for our buckets.
    sram_max_runtime = sram_end_events['runtime'].max()
    print(f"\n✅ Max runtime for SRAM analysis set to: {sram_max_runtime} cycles")
else:
    # Fallback in case no such events are found.
    print("\n⚠️ Warning: No 'SRAM THROUGHPUT_SECTION' ZONE_END events found. Using overall max runtime.")
    sram_max_runtime = df['runtime'].max()


# --- MODIFICATION 2: Use the new sram_max_runtime for bucket creation ---
num_buckets = 100
# The buckets will now only go up to the last SRAM ZONE_END event.
buckets = np.linspace(0, sram_max_runtime, num_buckets + 1)
print(f"\n✅ Generated {num_buckets} buckets for the SRAM analysis.")

# (The rest of the script for pairing zones remains the same)
# ...
# --- Zone Start, End, and Duration Times (in cycles) ---
starts_df = df[df['type'] == 'ZONE_START'].copy()
ends_df = df[df['type'] == 'ZONE_END'].copy()
group_cols = ['proctype', 'zone name']
starts_df['instance'] = starts_df.groupby(group_cols).cumcount()
ends_df['instance'] = ends_df.groupby(group_cols).cumcount()
starts_df.rename(columns={'runtime': 'start_time'}, inplace=True)
ends_df.rename(columns={'runtime': 'end_time'}, inplace=True)
paired_zones = pd.merge(
    starts_df,
    ends_df[group_cols + ['instance', 'end_time']],
    on=group_cols + ['instance'],
    how='inner'
)
paired_zones['duration'] = paired_zones['end_time'] - paired_zones['start_time']

# --- Bucket-Centric SRAM Zone and Ops Analysis ---
# (This section now uses the correctly scaled buckets)
print("\n--- Bucket-Centric SRAM Zone and Ops Analysis ---")

sram_zones = paired_zones[paired_zones['zone name'] == 'SRAM THROUGHPUT_SECTION'].copy()
ops = 2097152
bucket_summary_data = []

if not sram_zones.empty:
    for i in range(num_buckets):
        bucket_start = buckets[i]
        bucket_end = buckets[i+1]
        
        total_percentage_in_bucket = 0.0
        zone_details_for_print = []

        for zone_index, zone in sram_zones.iterrows():
            overlap_duration = max(0, min(bucket_end, zone['end_time']) - max(bucket_start, zone['start_time']))
            
            if overlap_duration > 0:
                zone_total_duration = zone['duration']
                if zone_total_duration > 0:
                    percentage_of_zone_in_bucket = (overlap_duration / zone_total_duration) * 100
                else:
                    percentage_of_zone_in_bucket = 0 if overlap_duration == 0 else 100.0
                
                total_percentage_in_bucket += percentage_of_zone_in_bucket
                zone_details_for_print.append({ "start_time": zone['start_time'], "percentage": percentage_of_zone_in_bucket })

        ops_for_bucket = (total_percentage_in_bucket / 100) * ops
        
        bucket_summary_data.append({
            'bucket_number': i,
            'aggregate_percentage': total_percentage_in_bucket,
            'ops_for_bucket': ops_for_bucket
        })

        if zone_details_for_print:
            print(f"\n▼ Bucket {i} ({bucket_start:.0f} to {bucket_end:.0f} cycles):")
            for zone_info in zone_details_for_print:
                print(f"  - Zone starting at {zone_info['start_time']:.0f} contributes: {zone_info['percentage']:.2f}%")
            print(f"  --------------------------------------------------")
            print(f"  TOTAL AGGREGATED PERCENTAGE FOR BUCKET: {total_percentage_in_bucket:.2f}%")
            print(f"  OPS FOR THIS BUCKET: {ops_for_bucket:,.2f}")

else:
    print("No zones named 'SRAM THROUGHPUT_SECTION' were found to analyze.")


# --- Create and Save Summary CSV ---
print("\n--- Saving Summary ---")

summary_df = pd.DataFrame(bucket_summary_data)
output_filename = 'bucket_analysis_summary.csv'

try:
    summary_df.to_csv(output_filename, index=False)
    print(f"✅ Successfully saved the summary data to '{output_filename}'")
except Exception as e:
    print(f"❌ Error saving file: {e}")