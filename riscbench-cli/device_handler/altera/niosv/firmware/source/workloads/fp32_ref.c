#include "workloads/fp32_ref.h"

/*
 * The native DSP datapaths operate on binary32 values. Volatile temporaries
 * force each helper to round to binary32 independently; callers compose MUL
 * followed by ADD, matching the non-FMA hardware sequence. Validation inputs
 * stay finite, normal, and exactly representable to avoid device-specific
 * denormal and NaN payload differences.
 */

uint32_t riscbench_fp32_mul(uint32_t a, uint32_t b)
{
    union { uint32_t bits; float value; } left = {.bits = a}, right = {.bits = b}, out;
    volatile float rounded = left.value * right.value;
    out.value = rounded;
    return out.bits;
}

uint32_t riscbench_fp32_add(uint32_t a, uint32_t b)
{
    union { uint32_t bits; float value; } left = {.bits = a}, right = {.bits = b}, out;
    volatile float rounded = left.value + right.value;
    out.value = rounded;
    return out.bits;
}

uint32_t riscbench_vecadd_fp32_reference(uint32_t a, uint32_t b)
{
    return riscbench_fp32_add(a, b);
}

uint16_t riscbench_fp16_add_reference(uint16_t a, uint16_t b)
{
    uint32_t ae = (a >> 10) & 0x1fu, be = (b >> 10) & 0x1fu;
    uint32_t a32 = ((uint32_t)(a & 0x8000u) << 16) |
                   ((ae == 0u ? 0u : ae + 112u) << 23) |
                   ((uint32_t)(a & 0x03ffu) << 13);
    uint32_t b32 = ((uint32_t)(b & 0x8000u) << 16) |
                   ((be == 0u ? 0u : be + 112u) << 23) |
                   ((uint32_t)(b & 0x03ffu) << 13);
    uint32_t q = riscbench_fp32_add(a32, b32);
    uint32_t qe = (q >> 23) & 0xffu;

    /* Step-1 behavioral contract: flush subnormals and truncate on narrowing. */
    if (qe == 0u) return (uint16_t)((q >> 16) & 0x8000u);
    if (qe >= 143u)
        return (uint16_t)(((q >> 16) & 0x8000u) | 0x7c00u);
    return (uint16_t)(((q >> 16) & 0x8000u) |
                      ((qe - 112u) << 10) | ((q >> 13) & 0x03ffu));
}

uint32_t riscbench_vecadd_fp16_reference(uint32_t a, uint32_t b)
{
    return (uint32_t)riscbench_fp16_add_reference((uint16_t)a, (uint16_t)b);
}

uint32_t riscbench_vecmul_reference(uint32_t a, uint32_t b)
{ return riscbench_fp32_mul(a, b); }

static int16_t saturate_int16(int32_t value)
{
    if (value > INT16_MAX) return INT16_MAX;
    if (value < INT16_MIN) return INT16_MIN;
    return (int16_t)value;
}

uint32_t riscbench_vecadd_int16_reference(uint32_t a, uint32_t b,
                                         bool lane1_valid)
{
    int32_t lane0 = (int32_t)(int16_t)a + (int32_t)(int16_t)b;
    int32_t lane1 = (int32_t)(int16_t)(a >> 16) +
                    (int32_t)(int16_t)(b >> 16);
    return (uint16_t)saturate_int16(lane0) |
           (lane1_valid ? ((uint32_t)(uint16_t)saturate_int16(lane1) << 16) : 0u);
}

uint32_t riscbench_vecmul_int16_reference(uint32_t a, uint32_t b,
                                         bool lane1_valid)
{
    int32_t lane0 = (int32_t)(int16_t)a * (int32_t)(int16_t)b;
    int32_t lane1 = (int32_t)(int16_t)(a >> 16) *
                    (int32_t)(int16_t)(b >> 16);
    return (uint16_t)saturate_int16(lane0) |
           (lane1_valid ? ((uint32_t)(uint16_t)saturate_int16(lane1) << 16) : 0u);
}

uint32_t riscbench_saxpy_int16_reference(int16_t alpha, uint32_t a, uint32_t b,
                                        bool lane1_valid)
{
    int32_t lane0=(int32_t)alpha*(int16_t)a+(int16_t)b;
    int32_t lane1=(int32_t)alpha*(int16_t)(a>>16)+(int16_t)(b>>16);
    return (uint16_t)saturate_int16(lane0) |
      (lane1_valid ? ((uint32_t)(uint16_t)saturate_int16(lane1)<<16) : 0u);
}

uint32_t riscbench_dot_int16_reference(const uint32_t *a, const uint32_t *b,
                                      uint32_t logical_size)
{
    int64_t sum=0;
    for(uint32_t i=0;i<logical_size;i++) {
        int16_t av=(i&1u)?(int16_t)(a[i>>1]>>16):(int16_t)a[i>>1];
        int16_t bv=(i&1u)?(int16_t)(b[i>>1]>>16):(int16_t)b[i>>1];
        sum+=(int32_t)av*(int32_t)bv;
    }
    if(sum>INT32_MAX) return 0x7fffffffu;
    if(sum<INT32_MIN) return 0x80000000u;
    return (uint32_t)(int32_t)sum;
}

static int8_t saturate_int8(int32_t v)
{
    return v > 127 ? 127 : v < -128 ? -128 : (int8_t)v;
}
uint32_t riscbench_vecadd_int8_reference(uint32_t a,uint32_t b,uint32_t lanes){
 uint32_t r=0;for(uint32_t i=0;i<lanes;i++){int32_t v=(int8_t)(a>>(8*i))+(int8_t)(b>>(8*i));r|=(uint32_t)(uint8_t)saturate_int8(v)<<(8*i);}return r;}
uint32_t riscbench_vecmul_int8_reference(uint32_t a,uint32_t b,uint32_t lanes){
 uint32_t r=0;for(uint32_t i=0;i<lanes;i++){int32_t v=(int8_t)(a>>(8*i))*(int8_t)(b>>(8*i));r|=(uint32_t)(uint8_t)saturate_int8(v)<<(8*i);}return r;}
uint32_t riscbench_saxpy_int8_reference(int8_t alpha,uint32_t a,uint32_t b,uint32_t lanes){
 uint32_t r=0;for(uint32_t i=0;i<lanes;i++){int32_t v=(int32_t)alpha*(int8_t)(a>>(8*i))+(int8_t)(b>>(8*i));r|=(uint32_t)(uint8_t)saturate_int8(v)<<(8*i);}return r;}
uint32_t riscbench_dot_int8_reference(const uint32_t*a,const uint32_t*b,uint32_t n){
 int64_t s=0;for(uint32_t i=0;i<n;i++)s+=(int32_t)(int8_t)(a[i>>2]>>(8*(i&3u)))*(int8_t)(b[i>>2]>>(8*(i&3u)));
 if(s>INT32_MAX)return 0x7fffffffu;
 if(s<INT32_MIN)return 0x80000000u;
 return(uint32_t)(int32_t)s;}

uint32_t riscbench_saxpy_reference(uint32_t alpha, uint32_t a, uint32_t b)
{ return riscbench_fp32_add(riscbench_fp32_mul(alpha, a), b); }

uint32_t riscbench_dot_reference(const uint32_t *a, const uint32_t *b, uint32_t size)
{
    uint32_t result = 0u;
    for (uint32_t i = 0; i < size; ++i)
        result = riscbench_fp32_add(result, riscbench_fp32_mul(a[i], b[i]));
    return result;
}

void riscbench_matmul_reference(const uint32_t *a, const uint32_t *b,
                               uint32_t *c, uint32_t n)
{
    for (uint32_t row = 0; row < n; ++row)
        for (uint32_t col = 0; col < n; ++col) {
            uint32_t value = 0u;
            for (uint32_t k = 0; k < n; ++k)
                value = riscbench_fp32_add(value,
                    riscbench_fp32_mul(a[(uint64_t)row*n+k], b[(uint64_t)k*n+col]));
            c[(uint64_t)row*n+col] = value;
        }
}
