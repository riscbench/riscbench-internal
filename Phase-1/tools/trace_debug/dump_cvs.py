#!/usr/bin/env python3
"""
Run this from your Phase-1 directory:
python3 dump_csvs.py runs/spike/fm_mm/small/inputs
"""
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python dump_csvs.py <inputs_dir>")
    sys.exit(1)

inputs_dir = Path(sys.argv[1])
state_csv = inputs_dir / "state_intervals.csv"
resid_csv = inputs_dir / "residency_intervals.csv"

print("=== STATE INTERVALS ===")
with open(state_csv) as f:
    lines = f.readlines()
    print(f"Total lines: {len(lines)}")
    print("First 15 lines:")
    for line in lines[:15]:
        print(f"  {line.rstrip()}")
    if len(lines) > 15:
        print(f"  ... {len(lines) - 15} more lines")

print("\n=== RESIDENCY INTERVALS ===")
with open(resid_csv) as f:
    lines = f.readlines()
    print(f"Total lines: {len(lines)}")
    print("All lines:")
    for line in lines:
        print(f"  {line.rstrip()}")

# Parse and analyze
print("\n=== QUICK ANALYSIS ===")
import csv

with open(state_csv) as f:
    reader = csv.DictReader(f)
    state_rows = list(reader)
    state_active = [r for r in state_rows if r['state'] == 'active']
    state_idle = [r for r in state_rows if r['state'] == 'idle']
    
    total_active = sum(float(r['end_us']) - float(r['start_us']) for r in state_active)
    total_idle = sum(float(r['end_us']) - float(r['start_us']) for r in state_idle)
    total_state = total_active + total_idle
    
    print(f"State intervals: {len(state_rows)} rows")
    print(f"  Active: {len(state_active)} intervals, {total_active:.2f} us ({100*total_active/total_state:.1f}%)")
    print(f"  Idle:   {len(state_idle)} intervals, {total_idle:.2f} us ({100*total_idle/total_state:.1f}%)")

with open(resid_csv) as f:
    reader = csv.DictReader(f)
    resid_rows = list(reader)
    
    total_resid = sum(float(r['end_us']) - float(r['start_us']) for r in resid_rows)
    
    print(f"\nResidency intervals: {len(resid_rows)} rows")
    print(f"  Total residency time: {total_resid:.2f} us")
    
    if len(resid_rows) > 1:
        print(f"  ⚠️  WARNING: {len(resid_rows)} separate residency intervals!")
        print(f"  Expected 1 interval from RES_ON to RES_OFF")
        print(f"  This suggests markers are not being detected properly")

print(f"\n=== RESIDENCY VS STATE ===")
print(f"Residency covers: {total_resid:.2f} us")
print(f"State covers:     {total_state:.2f} us")
if abs(total_resid - total_state) > 1.0:
    print(f"❌ MISMATCH: {abs(total_resid - total_state):.2f} us difference!")
    if total_state > total_resid:
        print(f"   State time > Residency time")
        print(f"   {100*(total_state-total_resid)/total_state:.1f}% of state will be ignored!")
else:
    print("✓ Times match!")