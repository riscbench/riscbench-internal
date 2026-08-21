#include <stdio.h>
#include <stdint.h>
#include "platform.h"
#include "xil_printf.h"
#include "xil_io.h"
#include "xil_cache.h"

// Set this to your MIG's DDR3 Base Address (check Address Editor in Vivado)
#define DDR3_BASE_ADDR   0x80000000 
#define MAX_VECTOR_SIZE  1048576  // 2^20 elements (1 M elements)

// Include xparameters.h to check for CPU clock frequencies
#if __has_include("xparameters.h")
    #include "xparameters.h"
#endif

#ifndef XPAR_CPU_CORE_CLOCK_FREQ_HZ
    #define XPAR_CPU_CORE_CLOCK_FREQ_HZ 100000000 // Default 100 MHz if undefined
#endif

// Lightweight LCG Pseudo-Random Number Generator to keep code size small (no stdlib.h required)
uint32_t lcg_rand(void) {
    static uint32_t seed = 123456789;
    seed = seed * 1664525 + 1013904223;
    return seed;
}

// Inline assembly helper to read RISC-V cycles directly
static inline uint32_t get_cycle_count(void) {
    uint32_t cycles;
    // RISC-V "rdcycle" reads the 32-bit clock cycle counter
    asm volatile ("rdcycle %0" : "=r" (cycles));
    return cycles;
}

//#define XPAR_CUSTOM_ADDSUB1B_0_BASEADDR 0x44a00000
uint32_t axi_hardware_add(uint32_t a, uint32_t b) {
    
    Xil_Out32(XPAR_CUSTOM_ADDSUB1B_0_BASEADDR + 0x0, a);
    Xil_Out32(XPAR_CUSTOM_ADDSUB1B_0_BASEADDR + 0x4, b);
    
    return Xil_In32(XPAR_CUSTOM_ADDSUB1B_0_BASEADDR + 0x8);
}

int main()
{
    init_platform();

    xil_printf("\n\r--- DDR3 Vector Addition Benchmark (Integer OPs) ---\n\r");
    xil_printf("Sweeping vector sizes from 1024 to %d elements...\n\r", MAX_VECTOR_SIZE);

    // Map uint32_t pointers to DDR3 memory spaces
    // A, B, and C each take MAX_VECTOR_SIZE * sizeof(uint32_t) bytes (4 MB each, total 12 MB)
    volatile uint32_t *A = (volatile uint32_t *)(DDR3_BASE_ADDR);
    volatile uint32_t *B = (volatile uint32_t *)(DDR3_BASE_ADDR + MAX_VECTOR_SIZE * sizeof(uint32_t));
    volatile uint32_t *C = (volatile uint32_t *)(DDR3_BASE_ADDR + 2 * MAX_VECTOR_SIZE * sizeof(uint32_t));

    // Ensure L1/L2 caches are enabled for realistic embedded performance
    Xil_DCacheEnable();

    // Print table header
    xil_printf("\n\r%-12s | %-16s | %-16s | %-12s\n\r", "Vector Size", "Cycles", "Time (us)", "MOPS");
    xil_printf("-------------------------------------------------------------------------\n\r");

    for (uint32_t N = 1024; N <= MAX_VECTOR_SIZE; N *= 2) {
        // 1. Initialize input vectors A and B with random numbers
        for (uint32_t i = 0; i < N; i++) {
            A[i] = lcg_rand() % 1000;
            B[i] = lcg_rand() % 1000;
        }

        // Flush cache to ensure written input data moves out of cache to DDR3
        Xil_DCacheFlush();

        // 2. Perform addition and measure execution time in CPU cycles
        uint32_t tStart = get_cycle_count();

        for (uint32_t i = 0; i < N; i++) {
            //C[i] = A[i] + B[i];
            C[i] = axi_hardware_add(A[i], B[i]);
        }

        uint32_t tEnd = get_cycle_count();

        // 3. Flush cache for output vector C to ensure writes are committed to DDR3
        Xil_DCacheFlush();

        // 4. Calculate timing metrics
        uint32_t elapsed_cycles = tEnd - tStart;
        
        // Time in microseconds = (Cycles * 1,000,000) / Frequency
        uint64_t elapsed_us_64 = ((uint64_t)elapsed_cycles * 1000000) / XPAR_CPU_CORE_CLOCK_FREQ_HZ;
        uint32_t elapsed_us = (uint32_t)elapsed_us_64;

        // Calculate MOPS (Mega Operations Per Second) using clock cycle scaling:
        // MOPS = (N * (Freq / 1M)) / Cycles
        uint32_t cpu_freq_mhz = XPAR_CPU_CORE_CLOCK_FREQ_HZ / 1000000;
        uint64_t mops_scaled = ((uint64_t)N * cpu_freq_mhz * 100) / elapsed_cycles;
        uint32_t mops_int = (uint32_t)(mops_scaled / 100);
        uint32_t mops_frac = (uint32_t)(mops_scaled % 100);

        // Print results cleanly
        xil_printf("%-12d | %-16d | %-16d | %d.%02d\n\r", N, elapsed_cycles, elapsed_us, mops_int, mops_frac);
    }

    xil_printf("-------------------------------------------------------------------------\n\r");
    xil_printf("Benchmark complete.\n\r");

    cleanup_platform();
    return 0;
}