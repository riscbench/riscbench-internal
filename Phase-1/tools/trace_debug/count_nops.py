#!/usr/bin/env python3
import sys
import re

if len(sys.argv) < 2:
    print("Usage: python count_nops.py <spike_trace_file>")
    sys.exit(1)

trace_file = sys.argv[1]

total_insns = 0
nop_insns = 0
in_residency = False
resident_total = 0
resident_nops = 0

with open(trace_file, 'r', errors='ignore') as f:
    for line in f:
        # Check for residency markers
        if 'addi' in line.lower():
            if ', 101' in line or ',101' in line:
                in_residency = True
                print(f">>> RES_ON at line: {line.strip()}")
                continue
            elif ', 102' in line or ',102' in line:
                in_residency = False
                print(f">>> RES_OFF at line: {line.strip()}")
                continue
        
        # Count instructions (lines with core and PC)
        if re.search(r'core\s+\d+:', line):
            total_insns += 1
            
            # Check if it's a nop (addi x0, x0, 0 or explicit nop)
            is_nop = False
            if 'nop' in line.lower():
                is_nop = True
            elif 'addi' in line.lower():
                # Check for addi x0, x0, 0 pattern
                if re.search(r'addi\s+(x0|zero)\s*,\s*(x0|zero)\s*,\s*0\b', line, re.IGNORECASE):
                    is_nop = True
            
            if is_nop:
                nop_insns += 1
            
            if in_residency:
                resident_total += 1
                if is_nop:
                    resident_nops += 1

print(f"\n=== INSTRUCTION COUNTS ===")
print(f"Total instructions: {total_insns}")
print(f"NOP instructions: {nop_insns} ({100*nop_insns/total_insns if total_insns else 0:.1f}%)")
print(f"\nWithin residency markers:")
print(f"Total instructions: {resident_total}")
print(f"NOP instructions: {resident_nops} ({100*resident_nops/resident_total if resident_total else 0:.1f}%)")
print(f"Active instructions: {resident_total - resident_nops} ({100*(resident_total-resident_nops)/resident_total if resident_total else 0:.1f}%)")
