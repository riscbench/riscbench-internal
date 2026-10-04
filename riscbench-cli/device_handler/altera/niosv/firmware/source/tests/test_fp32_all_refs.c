#include <stdint.h>
#include <stdio.h>

#include "workloads/fp32_ref.h"

#define MAX_VECTOR 1025u
#define MAX_MATRIX 20u

typedef union { uint32_t bits; float value; } fp32_t;

static uint32_t bits(float value)
{
    fp32_t number;
    number.value = value;
    return number.bits;
}

static uint32_t safe_value(uint32_t index, uint32_t salt)
{
    static const uint32_t values[] = {
        UINT32_C(0x3f000000), UINT32_C(0x3f800000),
        UINT32_C(0x3fc00000), UINT32_C(0x40000000),
        UINT32_C(0x40400000)
    };
    return values[(index + salt) % 5u];
}

static uint32_t host_mul(uint32_t a, uint32_t b)
{
    fp32_t left = {.bits = a}, right = {.bits = b}, out;
    volatile float rounded = left.value * right.value;
    out.value = rounded;
    return out.bits;
}

static uint32_t host_add(uint32_t a, uint32_t b)
{
    fp32_t left = {.bits = a}, right = {.bits = b}, out;
    volatile float rounded = left.value + right.value;
    out.value = rounded;
    return out.bits;
}

int main(void)
{
    static const uint32_t vector_sizes[] = {1u,16u,20u,1024u,1025u};
    static const uint32_t matrix_sizes[] = {2u,4u,16u,20u};
    static uint32_t a[MAX_VECTOR], b[MAX_VECTOR];
    static uint32_t ma[MAX_MATRIX*MAX_MATRIX];
    static uint32_t mb[MAX_MATRIX*MAX_MATRIX];
    static uint32_t mc[MAX_MATRIX*MAX_MATRIX];
    const uint32_t alpha = bits(2.0f);

    for (uint32_t i=0; i<MAX_VECTOR; ++i) {
        a[i] = safe_value(i,0u);
        b[i] = safe_value(i,2u);
    }
    for (uint32_t s=0; s<sizeof(vector_sizes)/sizeof(vector_sizes[0]); ++s) {
        uint32_t n=vector_sizes[s], dot=0u, expected_dot=0u;
        for (uint32_t i=0; i<n; ++i) {
            uint32_t product=host_mul(a[i],b[i]);
            if (riscbench_vecadd_fp32_reference(a[i],b[i]) != host_add(a[i],b[i])) return 10;
            if (riscbench_vecmul_reference(a[i],b[i]) != product) return 11;
            if (riscbench_saxpy_reference(alpha,a[i],b[i]) != host_add(host_mul(alpha,a[i]),b[i])) return 12;
            expected_dot=host_add(expected_dot,product);
        }
        dot=riscbench_dot_reference(a,b,n);
        if (dot != expected_dot) return 13;
        if (n == 0u || (n == 1u ? 1u : n) == 0u) return 14;
    }

    for (uint32_t s=0; s<sizeof(matrix_sizes)/sizeof(matrix_sizes[0]); ++s) {
        uint32_t n=matrix_sizes[s];
        for (uint32_t row=0; row<n; ++row)
            for (uint32_t col=0; col<n; ++col) {
                ma[row*n+col]=safe_value(row*3u+col,0u);
                mb[row*n+col]=safe_value(row*n+col,1u);
            }
        riscbench_matmul_reference(ma,mb,mc,n);
        for (uint32_t row=0; row<n; ++row)
            for (uint32_t col=0; col<n; ++col) {
                uint32_t expected=0u;
                for (uint32_t k=0; k<n; ++k) {
                    uint32_t product=host_mul(ma[row*n+k],mb[k*n+col]);
                    expected=host_add(expected,product);
                }
                if (mc[row*n+col] != expected) return 20;
            }
        if (n*n == 0u) return 21;
    }

    puts("FP32_ALL_REFERENCE_TEST_PASS");
    return 0;
}
