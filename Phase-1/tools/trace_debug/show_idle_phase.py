#!/usr/bin/env python3
"""
Show instructions around the idle_phase to see what's actually there
"""
import sys
import re

if len(sys.argv) < 2:
    print("Usage: python show_idle_phase.py <spike_trace>")
    sys.exit(1)

trace_file = sys.argv[1]

# Look for the markers first
print("=== SEARCHING FOR MARKERS ===")
marker_101_count = 0
marker_102_count = 0
marker_101_lines = []
marker_102_lines = []

inst_num = 0
with open(trace_file) as f:
    for line_num, line in enumerate(f, 1):
        if 'core' in line and ':' in line:
            inst_num += 1
            
        # Look for addi x0, x0, 101/102
        if 'addi' in line.lower() and 'x0' in line.lower():
            if ', 101' in line or ',101' in line:
                marker_101_count += 1
                marker_101_lines.append((line_num, inst_num, line.strip()))
            elif ', 102' in line or ',102' in line:
                marker_102_count += 1
                marker_102_lines.append((line_num, inst_num, line.strip()))

print(f"Found {marker_101_count} RES_ON markers (101)")
for line_num, inst, line in marker_101_lines[:3]:
    print(f"  Line {line_num} (inst {inst}): {line}")

print(f"\nFound {marker_102_count} RES_OFF markers (102)")
for line_num, inst, line in marker_102_lines[:3]:
    print(f"  Line {line_num} (inst {inst}): {line}")

if marker_101_count > 0 and marker_102_count > 0:
    print("\n✓ Markers found! Now checking what's between them...")
    
    # Show 20 instructions after first RES_ON
    if marker_101_lines:
        start_line = marker_101_lines[0][0]
        print(f"\n=== 20 instructions after RES_ON (line {start_line}) ===")
        with open(trace_file) as f:
            for i, line in enumerate(f, 1):
                if i > start_line and 'core' in line:
                    print(f"  {line.strip()}")
                    if i > start_line + 20:
                        break
    
    # Show what's RIGHT BEFORE RES_OFF
    if marker_102_lines:
        end_line = marker_102_lines[0][0]
        print(f"\n=== 20 instructions before RES_OFF (line {end_line}) ===")
        with open(trace_file) as f:
            lines = []
            for i, line in enumerate(f, 1):
                if 'core' in line:
                    lines.append(line.strip())
                    if len(lines) > 20:
                        lines.pop(0)
                if i == end_line:
                    for l in lines:
                        print(f"  {l}")
                    break
else:
    print("\n❌ NO MARKERS FOUND - they're still being optimized away!")
    print("\nLet's check what instructions actually exist...")
    
    # Sample first 1000 instructions
    print("\n=== INSTRUCTION TYPES (first 1000) ===")
    inst_types = {}
    with open(trace_file) as f:
        count = 0
        for line in f:
            if 'core' in line and ':' in line:
                count += 1
                # Extract mnemonic
                parts = line.split(')')
                if len(parts) > 1:
                    tokens = parts[1].strip().split()
                    if tokens:
                        mnem = tokens[0]
                        inst_types[mnem] = inst_types.get(mnem, 0) + 1
                if count >= 1000:
                    break
    
    print("Top 20 instruction types:")
    for mnem, count in sorted(inst_types.items(), key=lambda x: -x[1])[:20]:
        print(f"  {mnem}: {count}")