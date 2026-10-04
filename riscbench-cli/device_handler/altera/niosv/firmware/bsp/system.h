/*
 * system.h - SOPC Builder system and BSP software package information
 *
 * Machine generated for CPU 'intel_niosv_m_0' in SOPC Builder design 'niosv_bringup'
 *
 * Generated: Sun Oct 04 18:32:15 EDT 2026
 */

/*
 * DO NOT MODIFY THIS FILE
 *
 * Changing this file will have subtle consequences
 * which will almost certainly lead to a nonfunctioning
 * system. If you do modify this file, be aware that your
 * changes will be overwritten and lost when this file
 * is generated again.
 *
 * DO NOT MODIFY THIS FILE
 */

/*
 * License Agreement
 *
 * Copyright (c) 2008
 * Altera Corporation, San Jose, California, USA.
 * All rights reserved.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 * DEALINGS IN THE SOFTWARE.
 *
 * This agreement shall be governed in all respects by the laws of the State
 * of California and by the laws of the United States of America.
 */

#ifndef __SYSTEM_H_
#define __SYSTEM_H_

/* Include definitions from linker script generator */
#include "linker.h"


/*
 * CPU configuration
 *
 */

#define ALT_CPU_ARCHITECTURE "intel_niosv_m"
#define ALT_CPU_CPU_FREQ 50000000u
#define ALT_CPU_DATA_ADDR_WIDTH 0x20
#define ALT_CPU_DCACHE_LINE_SIZE 0
#define ALT_CPU_DCACHE_LINE_SIZE_LOG2 0
#define ALT_CPU_DCACHE_SIZE 0
#define ALT_CPU_FREQ 50000000
#define ALT_CPU_HAS_CSR_SUPPORT 1
#define ALT_CPU_HAS_DEBUG_STUB
#define ALT_CPU_ICACHE_LINE_SIZE 0
#define ALT_CPU_ICACHE_LINE_SIZE_LOG2 0
#define ALT_CPU_ICACHE_SIZE 0
#define ALT_CPU_INST_ADDR_WIDTH 0x20
#define ALT_CPU_INT_MODE 0
#define ALT_CPU_MTIME_OFFSET 0x400a0080
#define ALT_CPU_NAME "intel_niosv_m_0"
#define ALT_CPU_NIOSV_CORE_VARIANT 2
#define ALT_CPU_NUM_GPR 32
#define ALT_CPU_RESET_ADDR 0x40040000
#define ALT_CPU_TICKS_PER_SEC NIOSV_INTERNAL_TIMER_TICKS_PER_SECOND
#define ALT_CPU_TIMER_DEVICE_TYPE 2


/*
 * CPU configuration (with legacy prefix - don't use these anymore)
 *
 */

#define ABBOTTSLAKE_CPU_FREQ 50000000u
#define ABBOTTSLAKE_DATA_ADDR_WIDTH 0x20
#define ABBOTTSLAKE_DCACHE_LINE_SIZE 0
#define ABBOTTSLAKE_DCACHE_LINE_SIZE_LOG2 0
#define ABBOTTSLAKE_DCACHE_SIZE 0
#define ABBOTTSLAKE_HAS_CSR_SUPPORT 1
#define ABBOTTSLAKE_HAS_DEBUG_STUB
#define ABBOTTSLAKE_ICACHE_LINE_SIZE 0
#define ABBOTTSLAKE_ICACHE_LINE_SIZE_LOG2 0
#define ABBOTTSLAKE_ICACHE_SIZE 0
#define ABBOTTSLAKE_INST_ADDR_WIDTH 0x20
#define ABBOTTSLAKE_INT_MODE 0
#define ABBOTTSLAKE_MTIME_OFFSET 0x400a0080
#define ABBOTTSLAKE_NIOSV_CORE_VARIANT 2
#define ABBOTTSLAKE_NUM_GPR 32
#define ABBOTTSLAKE_RESET_ADDR 0x40040000
#define ABBOTTSLAKE_TICKS_PER_SEC NIOSV_INTERNAL_TIMER_TICKS_PER_SECOND
#define ABBOTTSLAKE_TIMER_DEVICE_TYPE 2


/*
 * Define for each module class mastered by the CPU
 *
 */

#define __ALTERA_AVALON_JTAG_UART
#define __EMIF_IO96B_DDR4COMP
#define __INTEL_NIOSV_M
#define __INTEL_ONCHIP_MEMORY_0
#define __SIT_0


/*
 * System configuration
 *
 */

#define ALT_DEVICE_FAMILY "AGILEX5"
#define ALT_ENHANCED_INTERRUPT_API_PRESENT
#define ALT_IRQ_BASE NULL
#define ALT_LOG_PORT "/dev/null"
#define ALT_LOG_PORT_BASE 0x0
#define ALT_LOG_PORT_DEV null
#define ALT_LOG_PORT_TYPE ""
#define ALT_NUM_EXTERNAL_INTERRUPT_CONTROLLERS 0
#define ALT_NUM_INTERNAL_INTERRUPT_CONTROLLERS 1
#define ALT_NUM_INTERRUPT_CONTROLLERS 1
#define ALT_STDERR "/dev/jtag_uart_0"
#define ALT_STDERR_BASE 0x400a00c0
#define ALT_STDERR_DEV jtag_uart_0
#define ALT_STDERR_IS_JTAG_UART
#define ALT_STDERR_PRESENT
#define ALT_STDERR_TYPE "altera_avalon_jtag_uart"
#define ALT_STDIN "/dev/jtag_uart_0"
#define ALT_STDIN_BASE 0x400a00c0
#define ALT_STDIN_DEV jtag_uart_0
#define ALT_STDIN_IS_JTAG_UART
#define ALT_STDIN_PRESENT
#define ALT_STDIN_TYPE "altera_avalon_jtag_uart"
#define ALT_STDOUT "/dev/jtag_uart_0"
#define ALT_STDOUT_BASE 0x400a00c0
#define ALT_STDOUT_DEV jtag_uart_0
#define ALT_STDOUT_IS_JTAG_UART
#define ALT_STDOUT_PRESENT
#define ALT_STDOUT_TYPE "altera_avalon_jtag_uart"
#define ALT_SYSTEM_NAME "niosv_bringup"
#define ALT_SYS_CLK_TICKS_PER_SEC ALT_CPU_TICKS_PER_SEC
#define ALT_TIMESTAMP_CLK_TIMER_DEVICE_TYPE ALT_CPU_TIMER_DEVICE_TYPE


/*
 * emif_io96b_ddr4comp_0 configuration
 *
 */

#define ALT_MODULE_CLASS_emif_io96b_ddr4comp_0 emif_io96b_ddr4comp
#define EMIF_IO96B_DDR4COMP_0_BASE 0x0
#define EMIF_IO96B_DDR4COMP_0_IRQ -1
#define EMIF_IO96B_DDR4COMP_0_IRQ_INTERRUPT_CONTROLLER_ID -1
#define EMIF_IO96B_DDR4COMP_0_NAME "/dev/emif_io96b_ddr4comp_0"
#define EMIF_IO96B_DDR4COMP_0_SPAN 1073741824
#define EMIF_IO96B_DDR4COMP_0_TYPE "emif_io96b_ddr4comp"


/*
 * hal2 configuration
 *
 */

#define ALT_MAX_FD 32
#define ALT_SYS_CLK INTEL_NIOSV_M_0
#define ALT_TIMESTAMP_CLK INTEL_NIOSV_M_0
#define INTEL_FPGA_DFL_START_ADDRESS 0xffffffffffffffff
#define INTEL_FPGA_USE_DFL_WALKER 0


/*
 * intel_niosv_m_0_dm_agent configuration
 *
 */

#define ALT_MODULE_CLASS_intel_niosv_m_0_dm_agent intel_niosv_m
#define INTEL_NIOSV_M_0_DM_AGENT_BASE 0x40090000
#define INTEL_NIOSV_M_0_DM_AGENT_CPU_FREQ 50000000u
#define INTEL_NIOSV_M_0_DM_AGENT_DATA_ADDR_WIDTH 0x20
#define INTEL_NIOSV_M_0_DM_AGENT_DCACHE_LINE_SIZE 0
#define INTEL_NIOSV_M_0_DM_AGENT_DCACHE_LINE_SIZE_LOG2 0
#define INTEL_NIOSV_M_0_DM_AGENT_DCACHE_SIZE 0
#define INTEL_NIOSV_M_0_DM_AGENT_HAS_CSR_SUPPORT 1
#define INTEL_NIOSV_M_0_DM_AGENT_HAS_DEBUG_STUB
#define INTEL_NIOSV_M_0_DM_AGENT_ICACHE_LINE_SIZE 0
#define INTEL_NIOSV_M_0_DM_AGENT_ICACHE_LINE_SIZE_LOG2 0
#define INTEL_NIOSV_M_0_DM_AGENT_ICACHE_SIZE 0
#define INTEL_NIOSV_M_0_DM_AGENT_INST_ADDR_WIDTH 0x20
#define INTEL_NIOSV_M_0_DM_AGENT_INT_MODE 0
#define INTEL_NIOSV_M_0_DM_AGENT_IRQ -1
#define INTEL_NIOSV_M_0_DM_AGENT_IRQ_INTERRUPT_CONTROLLER_ID -1
#define INTEL_NIOSV_M_0_DM_AGENT_MTIME_OFFSET 0x400a0080
#define INTEL_NIOSV_M_0_DM_AGENT_NAME "/dev/intel_niosv_m_0_dm_agent"
#define INTEL_NIOSV_M_0_DM_AGENT_NIOSV_CORE_VARIANT 2
#define INTEL_NIOSV_M_0_DM_AGENT_NUM_GPR 32
#define INTEL_NIOSV_M_0_DM_AGENT_RESET_ADDR 0x40040000
#define INTEL_NIOSV_M_0_DM_AGENT_SPAN 65536
#define INTEL_NIOSV_M_0_DM_AGENT_TICKS_PER_SEC NIOSV_INTERNAL_TIMER_TICKS_PER_SECOND
#define INTEL_NIOSV_M_0_DM_AGENT_TIMER_DEVICE_TYPE 2
#define INTEL_NIOSV_M_0_DM_AGENT_TYPE "intel_niosv_m"


/*
 * intel_niosv_m_0_timer_sw_agent configuration
 *
 */

#define ALT_MODULE_CLASS_intel_niosv_m_0_timer_sw_agent intel_niosv_m
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_BASE 0x400a0080
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_CPU_FREQ 50000000u
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_DATA_ADDR_WIDTH 0x20
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_DCACHE_LINE_SIZE 0
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_DCACHE_LINE_SIZE_LOG2 0
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_DCACHE_SIZE 0
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_HAS_CSR_SUPPORT 1
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_HAS_DEBUG_STUB
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_ICACHE_LINE_SIZE 0
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_ICACHE_LINE_SIZE_LOG2 0
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_ICACHE_SIZE 0
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_INST_ADDR_WIDTH 0x20
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_INT_MODE 0
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_IRQ -1
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_IRQ_INTERRUPT_CONTROLLER_ID -1
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_MTIME_OFFSET 0x400a0080
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_NAME "/dev/intel_niosv_m_0_timer_sw_agent"
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_NIOSV_CORE_VARIANT 2
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_NUM_GPR 32
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_RESET_ADDR 0x40040000
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_SPAN 64
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_TICKS_PER_SEC NIOSV_INTERNAL_TIMER_TICKS_PER_SECOND
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_TIMER_DEVICE_TYPE 2
#define INTEL_NIOSV_M_0_TIMER_SW_AGENT_TYPE "intel_niosv_m"


/*
 * intel_niosv_m_hal_driver configuration
 *
 */

#define NIOSV_INTERNAL_TIMER_TICKS_PER_SECOND 1000


/*
 * intel_onchip_memory_0 configuration
 *
 */

#define ALT_MODULE_CLASS_intel_onchip_memory_0 intel_onchip_memory_0
#define INTEL_ONCHIP_MEMORY_0_ALLOW_IN_SYSTEM_MEMORY_CONTENT_EDITOR 1
#define INTEL_ONCHIP_MEMORY_0_BASE 0x40040000
#define INTEL_ONCHIP_MEMORY_0_CONTENTS_INFO ""
#define INTEL_ONCHIP_MEMORY_0_DUAL_PORT 0
#define INTEL_ONCHIP_MEMORY_0_GUI_RAM_BLOCK_TYPE "AUTO"
#define INTEL_ONCHIP_MEMORY_0_INIT_CONTENTS_FILE "app"
#define INTEL_ONCHIP_MEMORY_0_INIT_MEM_CONTENT 1
#define INTEL_ONCHIP_MEMORY_0_INSTANCE_ID "NONE"
#define INTEL_ONCHIP_MEMORY_0_IRQ -1
#define INTEL_ONCHIP_MEMORY_0_IRQ_INTERRUPT_CONTROLLER_ID -1
#define INTEL_ONCHIP_MEMORY_0_NAME "/dev/intel_onchip_memory_0"
#define INTEL_ONCHIP_MEMORY_0_NON_DEFAULT_INIT_FILE_ENABLED 1
#define INTEL_ONCHIP_MEMORY_0_RAM_BLOCK_TYPE "AUTO"
#define INTEL_ONCHIP_MEMORY_0_READ_DURING_WRITE_MODE "DONT_CARE"
#define INTEL_ONCHIP_MEMORY_0_SINGLE_CLOCK_OP 0
#define INTEL_ONCHIP_MEMORY_0_SIZE_MULTIPLE 1
#define INTEL_ONCHIP_MEMORY_0_SIZE_VALUE 262144
#define INTEL_ONCHIP_MEMORY_0_SPAN 262144
#define INTEL_ONCHIP_MEMORY_0_TYPE "intel_onchip_memory_0"
#define INTEL_ONCHIP_MEMORY_0_WRITABLE 1


/*
 * jtag_uart_0 configuration
 *
 */

#define ALT_MODULE_CLASS_jtag_uart_0 altera_avalon_jtag_uart
#define JTAG_UART_0_BASE 0x400a00c0
#define JTAG_UART_0_IRQ 0
#define JTAG_UART_0_IRQ_INTERRUPT_CONTROLLER_ID 0
#define JTAG_UART_0_NAME "/dev/jtag_uart_0"
#define JTAG_UART_0_READ_DEPTH 64
#define JTAG_UART_0_READ_THRESHOLD 8
#define JTAG_UART_0_SPAN 8
#define JTAG_UART_0_TYPE "altera_avalon_jtag_uart"
#define JTAG_UART_0_WRITE_DEPTH 64
#define JTAG_UART_0_WRITE_THRESHOLD 8


/*
 * sit_0 configuration
 *
 */

#define ALT_MODULE_CLASS_sit_0 sit_0
#define SIT_0_BASE 0x400a0000
#define SIT_0_IRQ -1
#define SIT_0_IRQ_INTERRUPT_CONTROLLER_ID -1
#define SIT_0_NAME "/dev/sit_0"
#define SIT_0_SPAN 128
#define SIT_0_TYPE "sit_0"

#endif /* __SYSTEM_H_ */
