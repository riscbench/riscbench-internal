#!/bin/bash
# Manual test to verify markers work with memory writes

echo "=== STEP 1: Compile test program with -O0 ==="
riscv64-unknown-elf-gcc -O0 -static -march=rv64gc -mabi=lp64d test_markers.c -o test_markers
echo "✓ Compiled"

echo ""
echo "=== STEP 2: Check for __sit_marker variable ==="
riscv64-unknown-elf-nm test_markers | grep __sit_marker && echo "✓ Marker variable found!" || echo "❌ Marker variable not found"

echo ""
echo "=== STEP 3: Check disassembly for li/addi with 101/102 ==="
echo "Looking for 'li' or 'addi' with immediate 101 or 102..."
riscv64-unknown-elf-objdump -d test_markers | grep -E "(li|addi).*(101|102)" | head -10

echo ""
echo "=== STEP 4: Run with spike and generate trace ==="
spike -l --isa=RV64GC $HOME/opt/riscv/riscv64-unknown-elf/bin/pk test_markers > test_markers.trace 2>&1
echo "✓ Trace generated ($(wc -l < test_markers.trace) lines)"

echo ""
echo "=== STEP 5: Search trace for marker values ==="
echo "Looking for instructions with immediate 101..."
grep -E "(li|addi).*(101|0x65)" test_markers.trace | head -5 && echo "✓ Found 101!" || echo "❌ 101 not found"

echo ""
echo "Looking for instructions with immediate 102..."
grep -E "(li|addi).*(102|0x66)" test_markers.trace | head -5 && echo "✓ Found 102!" || echo "❌ 102 not found"

echo ""
echo "=== STEP 6: Count nop instructions ==="
nop_count=$(grep -c "nop" test_markers.trace)
echo "Found $nop_count nop instructions"

echo ""
echo "=== STEP 7: Show context around marker stores ==="
echo "Instructions around value 101:"
grep -B3 -A3 -E "(li|addi).*(101|0x65)" test_markers.trace | head -20