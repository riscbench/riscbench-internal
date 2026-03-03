#!/usr/bin/env python3
import sys
import pandas as pd

if len(sys.argv) < 2:
    print("Usage: python debug_state.py <path_to_state_intervals.csv>")
    sys.exit(1)

csv_path = sys.argv[1]
df = pd.read_csv(csv_path)

print("=== STATE INTERVALS ===")
print(df.head(20))
print(f"\nTotal rows: {len(df)}")
print("\n=== STATE BREAKDOWN ===")
print(df.groupby('state').agg({
    'start_us': 'count',
    'end_us': lambda x: (df.loc[x.index, 'end_us'] - df.loc[x.index, 'start_us']).sum()
}).rename(columns={'start_us': 'count', 'end_us': 'total_duration_us'}))

# Calculate percentages
total_time = (df['end_us'] - df['start_us']).sum()
for state in df['state'].unique():
    state_time = (df[df['state'] == state]['end_us'] - df[df['state'] == state]['start_us']).sum()
    pct = (state_time / total_time) * 100 if total_time > 0 else 0
    print(f"\n{state}: {state_time:.2f} us ({pct:.2f}%)")