/* Minimal test to verify markers appear in trace */
#include <stdint.h>

#ifdef __riscv
// Use volatile memory writes - these CANNOT be optimized away
volatile uint64_t __attribute__((section(".data"))) __sit_marker = 0;
#define SIT_RES_ON()  do { __sit_marker = 101; } while(0)
#define SIT_RES_OFF() do { __sit_marker = 102; } while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

int main() {
    volatile int sum = 0;
    
    SIT_RES_ON();
    
    // Some work
    for (int i = 0; i < 100; i++) {
        sum += i;
    }
    
    // Idle phase
    for (int i = 0; i < 50; i++) {
        asm volatile("nop");
    }
    
    SIT_RES_OFF();
    
    return sum;
}