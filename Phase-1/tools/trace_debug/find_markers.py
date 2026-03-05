#!/usr/bin/env python3
import sys
import re

if len(sys.argv) < 2:
    print("Usage: python find_markers.py <spike_trace_file>")
    sys.exit(1)

trace_file = sys.argv[1]

ADDI_ZERO_IMM_RE = re.compile(
    r"\baddi\s+(?:x0|zero)\s*,\s*(?:x0|zero)\s*,\s*(?P<imm>-?(?:0x[0-9a-fA-F]+|\d+))\b",
    re.IGNORECASE,
)

markers_101 = []
markers_102 = []
inst_count = 0

with open(trace_file, 'r', errors='ignore') as f:
    for line_num, line in enumerate(f, 1):
        if re.search(r'core\s+\d+:', line):
            inst_count += 1
            
        if 'addi' in line.lower():
            m = ADDI_ZERO_IMM_RE.search(line)
            if m:
                try:
                    imm = int(m.group('imm'), 0)
                    if imm == 101:
                        markers_101.append((line_num, inst_count, line.strip()))
                    elif imm == 102:
                        markers_102.append((line_num, inst_count, line.strip()))
                except ValueError:
                    pass

print(f"=== MARKER 101 (RES_ON) - Found {len(markers_101)} ===")
for line_num, inst, line in markers_101[:10]:  # First 10
    print(f"Line {line_num} (inst #{inst}): {line}")
if len(markers_101) > 10:
    print(f"... and {len(markers_101) - 10} more")

print(f"\n=== MARKER 102 (RES_OFF) - Found {len(markers_102)} ===")
for line_num, inst, line in markers_102[:10]:  # First 10
    print(f"Line {line_num} (inst #{inst}): {line}")
if len(markers_102) > 10:
    print(f"... and {len(markers_102) - 10} more")

print(f"\n=== SUMMARY ===")
print(f"Total instructions: {inst_count}")
print(f"RES_ON markers (101): {len(markers_101)}")
print(f"RES_OFF markers (102): {len(markers_102)}")
print(f"Pairs: {min(len(markers_101), len(markers_102))}")

if len(markers_101) != len(markers_102):
    print(f"\n⚠️  MISMATCH: {len(markers_101)} RES_ON but {len(markers_102)} RES_OFF")
elif len(markers_101) > 1:
    print(f"\n⚠️  Multiple marker pairs detected! Expected 1, found {len(markers_101)}")