#!/usr/bin/env python3
import sys
import re

if len(sys.argv) < 2:
    print("Usage: python find_marker_encodings.py <spike_trace_file>")
    sys.exit(1)

trace_file = sys.argv[1]

# RISC-V encodings:
# addi x0, x0, 101 = 0x06500013
# addi x0, x0, 102 = 0x06600013
MARKER_101_ENCODING = "0x06500013"
MARKER_102_ENCODING = "0x06600013"

markers_101 = []
markers_102 = []
inst_count = 0

with open(trace_file, 'r', errors='ignore') as f:
    for line_num, line in enumerate(f, 1):
        if re.search(r'core\s+\d+:', line):
            inst_count += 1
            
            # Look for the instruction encodings
            if MARKER_101_ENCODING in line.lower():
                markers_101.append((line_num, inst_count, line.strip()))
            elif MARKER_102_ENCODING in line.lower():
                markers_102.append((line_num, inst_count, line.strip()))

print(f"=== SEARCHING BY INSTRUCTION ENCODING ===")
print(f"Looking for:")
print(f"  RES_ON  (101): {MARKER_101_ENCODING}")
print(f"  RES_OFF (102): {MARKER_102_ENCODING}")

print(f"\n=== MARKER 101 (RES_ON) - Found {len(markers_101)} ===")
for line_num, inst, line in markers_101:
    print(f"Line {line_num} (inst #{inst}): {line}")

print(f"\n=== MARKER 102 (RES_OFF) - Found {len(markers_102)} ===")
for line_num, inst, line in markers_102:
    print(f"Line {line_num} (inst #{inst}): {line}")

print(f"\n=== SUMMARY ===")
print(f"Total instructions: {inst_count}")
print(f"RES_ON markers (101): {len(markers_101)}")
print(f"RES_OFF markers (102): {len(markers_102)}")

if len(markers_101) == 0 and len(markers_102) == 0:
    print("\n❌ NO MARKERS FOUND!")
    print("\nPossible reasons:")
    print("1. Compiler optimized them away (writes to x0 have no effect)")
    print("2. The trace doesn't include these instructions")
    print("3. The workload didn't execute the marker code")
    print("\nTry checking the disassembly:")
    print("  riscv64-unknown-elf-objdump -d <binary> | grep -A2 -B2 'addi.*x0.*x0'")