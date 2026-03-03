#!/usr/bin/env python3
import sys
import pandas as pd

if len(sys.argv) < 3:
    print("Usage: python compare_intervals.py <state_intervals.csv> <residency_intervals.csv>")
    sys.exit(1)

state_path = sys.argv[1]
resid_path = sys.argv[2]

state_df = pd.read_csv(state_path)
resid_df = pd.read_csv(resid_path)

print("=== RESIDENCY INTERVALS ===")
print(resid_df)
resid_total = (resid_df['end_us'] - resid_df['start_us']).sum()
print(f"\nTotal residency time: {resid_total:.2f} us")

print("\n=== STATE INTERVALS ===")
print(state_df.head(10))
print(f"... ({len(state_df)} total rows)")
state_total = (state_df['end_us'] - state_df['start_us']).sum()
print(f"\nTotal state time: {state_total:.2f} us")

print("\n=== COMPARISON ===")
print(f"Residency time: {resid_total:.2f} us")
print(f"State time:     {state_total:.2f} us")
print(f"Difference:     {resid_total - state_total:.2f} us")

if resid_total > state_total:
    print(f"\n⚠️  RESIDENCY > STATE by {resid_total - state_total:.2f} us ({100*(resid_total-state_total)/resid_total:.1f}%)")
    print("This difference will be gap-filled as IDLE in the SIT engine!")
elif state_total > resid_total:
    print(f"\n⚠️  STATE > RESIDENCY by {state_total - resid_total:.2f} us")
    print("Some state time is outside residency and will be ignored!")
else:
    print("\n✓ Residency and state times match perfectly!")

# Check time ranges
print("\n=== TIME RANGES ===")
print(f"Residency: {resid_df['start_us'].min():.2f} to {resid_df['end_us'].max():.2f}")
print(f"State:     {state_df['start_us'].min():.2f} to {state_df['end_us'].max():.2f}")