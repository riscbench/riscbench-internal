#include <stdint.h>
#include <stdio.h>
#include "workloads/fp32_ref.h"

int main(void)
{
    if (riscbench_vecadd_fp32_reference(UINT32_C(0x3f800000), UINT32_C(0x40000000)) != UINT32_C(0x40400000)) return 1;
    if (riscbench_vecadd_fp32_reference(UINT32_C(0xbf800000), UINT32_C(0x40000000)) != UINT32_C(0x3f800000)) return 2;
    if (riscbench_vecadd_fp16_reference(UINT32_C(0x00003c00), UINT32_C(0x00004000)) != UINT32_C(0x00004200)) return 3;
    if (riscbench_vecadd_fp16_reference(UINT32_C(0x0000bc00), UINT32_C(0x00004000)) != UINT32_C(0x00003c00)) return 4;
    if (riscbench_vecadd_fp16_reference(UINT32_C(0xffff3c00), UINT32_C(0xaaaa4000)) & UINT32_C(0xffff0000)) return 5;
    if (riscbench_vecadd_int16_reference(UINT32_C(0x8ad07530), UINT32_C(0xd8f02710), true) != UINT32_C(0x80007fff)) return 6;
    if (riscbench_vecadd_int16_reference(UINT32_C(0x12347530), UINT32_C(0x56782710), false) != UINT32_C(0x00007fff)) return 7;
    if (riscbench_vecmul_int16_reference(UINT32_C(0xfed4012c), UINT32_C(0x00c800c8), true) != UINT32_C(0x80007fff)) return 8;
    if (riscbench_vecmul_int16_reference(UINT32_C(0x1234012c), UINT32_C(0x567800c8), false) != UINT32_C(0x00007fff)) return 9;
    if (riscbench_saxpy_int16_reference(2, UINT32_C(0x8ad07530),
        UINT32_C(0xd8f02710), true) != UINT32_C(0x80007fff)) return 10;
    { const uint32_t a[]={UINT32_C(0xfffe0003),UINT32_C(0x00000004)};
      const uint32_t b[]={UINT32_C(0x00060005),UINT32_C(0x00000007)};
      if(riscbench_dot_int16_reference(a,b,3)!=UINT32_C(31)) return 11; }
    if(riscbench_vecadd_int8_reference(UINT32_C(0x7f80f001),UINT32_C(0x0280f07f),4)!=UINT32_C(0x7f80e07f))return 12;
    if(riscbench_vecmul_int8_reference(UINT32_C(0x7f80fe03),UINT32_C(0x02800605),4)!=UINT32_C(0x7f7ff40f))return 13;
    if(riscbench_saxpy_int8_reference(-3,UINT32_C(0x7f80fe03),UINT32_C(0x02800605),3)!=UINT32_C(0x007f0cfc))return 14;
    {const uint32_t a[]={UINT32_C(0x04fdfe03)};const uint32_t b[]={UINT32_C(0x07fa0605)};
     if(riscbench_dot_int8_reference(a,b,3)!=UINT32_C(21))return 15;}
    puts("PRECISION_REFERENCE_TEST_PASS");
    return 0;
}
