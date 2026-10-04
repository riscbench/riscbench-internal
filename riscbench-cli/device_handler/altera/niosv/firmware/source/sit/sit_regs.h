#ifndef SIT_REGS_H
#define SIT_REGS_H

#define SIT_CSR_BASE                 0x400A0000u

#define SIT_CTRL_OFFSET              0x00u
#define SIT_STATUS_OFFSET            0x04u
#define SIT_MODE_OFFSET              0x08u
#define SIT_SIZE_OFFSET              0x0Cu
#define SIT_A_BASE_OFFSET            0x10u
#define SIT_B_BASE_OFFSET            0x14u
#define SIT_C_BASE_OFFSET            0x18u
#define SIT_MONITOR_CTRL_OFFSET      0x1Cu
#define SIT_TOTAL_CYCLES_OFFSET      0x60u
#define SIT_TOTAL_CYCLES_LO_OFFSET   0x60u
#define SIT_TOTAL_CYCLES_HI_OFFSET   0x64u
#define SIT_ACTIVE_CYCLES_OFFSET     0x68u
#define SIT_ACTIVE_CYCLES_LO_OFFSET  0x68u
#define SIT_ACTIVE_CYCLES_HI_OFFSET  0x6Cu
#define SIT_MEM_WAIT_CYCLES_OFFSET   0x70u
#define SIT_MEM_WAIT_CYCLES_LO_OFFSET 0x70u
#define SIT_MEM_WAIT_CYCLES_HI_OFFSET 0x74u
#define SIT_OPS_DONE_OFFSET          0x78u
#define SIT_OPS_COMPLETED_LO_OFFSET  0x78u
#define SIT_OPS_COMPLETED_HI_OFFSET  0x7Cu
#define SIT_ALPHA_OFFSET             0x30u
#define SIT_TRACE_COUNT_OFFSET       0x34u
#define SIT_TRACE_OVERFLOW_OFFSET    0x38u
#define SIT_TRACE_EVENT_INDEX_OFFSET 0x3Cu
#define SIT_TRACE_EVENT_LO_OFFSET    0x40u
#define SIT_TRACE_EVENT_HI_OFFSET    0x44u
#define SIT_TRACE_CLEAR_OFFSET       0x48u
#define SIT_PRECISION_OFFSET         0x4Cu
#define SIT_TRACE_BUCKET_CYCLES      1024u

#define SIT_CTRL_START               (1u << 0)
#define SIT_STATUS_BUSY              (1u << 0)
#define SIT_STATUS_DONE              (1u << 1)

#define SIT_MODE_VECADD              0u
#define SIT_MODE_VECMUL              1u
#define SIT_MODE_DOT                 2u
#define SIT_MODE_MATMUL              3u
#define SIT_MODE_SAXPY               4u

#define SIT_PRECISION_INT8           0u
#define SIT_PRECISION_INT16          1u
#define SIT_PRECISION_INT32          2u
#define SIT_PRECISION_FP16           3u
#define SIT_PRECISION_FP32           4u

#endif
