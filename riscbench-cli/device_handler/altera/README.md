# RISCBench Altera / Nios V Backend

> **Status: UNDER REVIEW**  
> This Altera/Nios V backend is currently being evaluated before integration into the main RISCBench frontend/common flow.  
> Altera-specific additions in shared frontend files are intentionally kept minimal and clearly marked for review.

Self-contained Altera / Intel FPGA backend for the RISCBench benchmark framework.

## Overview
This backend connects RISCBench CLI workflows to Altera Quartus Prime and Nios V tools for:
1. Dynamic workload compilation (`CMake` + `riscv32-unknown-elf-gcc`)
2. FPGA bitstream programming (`quartus_pgm`)
3. GDB-based firmware download & target execution (`ash-riscv-gdb-server` + GDB)
4. JTAG UART output capture & hardware mailbox verification (`juart-terminal`)

## Path Resolution Order
1. **Environment Variable Override** (highest priority)
   - `ALTERA_SOF_PATH`
   - `ALTERA_ELF_PATH`
2. **`env.json` Configuration**
   - Relative or absolute paths configured in `env.json`:
     - `"sof_path": "niosv/artifacts/sit_core.sof"`
     - `"elf_path": "niosv/artifacts/app.elf"`
3. **Auto-Discovery**
   - Automatically searches for bitstream (`sit_core.sof`) and firmware (`app.elf`) in `niosv/artifacts/` and standard project subdirectories.

## Tool Requirements
- **Quartus Prime Pro / Standard** (provides `quartus_pgm` and `juart-terminal`)
- **Ashling RiscFree / Nios V Toolchain** (provides GDB server and `riscv32-unknown-elf-gdb`)

Tools are auto-discovered from `PATH` or standard installation directories (`C:/altera_pro`, `C:/intelFPGA_pro`, etc.). Use `QUARTUS_PATH` or `env.json` to configure paths.

## Supported Environment Variables
| Variable | Description |
| :--- | :--- |
| `QUARTUS_PATH` / `QUARTUS_ROOTDIR` | Quartus Prime installation path |
| `ALTERA_SOF_PATH` | Path override for `.sof` FPGA bitstream |
| `ALTERA_ELF_PATH` | Path override for `.elf` software binary |
| `ALTERA_TRACE` | Set to `1` to enable live real-time `[UART]` console output streaming |
| `ALTERA_UART_TIMEOUT` | Timeout in seconds for post-download UART capture (default: 15) |
| `ALTERA_CABLE` / `JTAG_CABLE` | Specific JTAG cable index or name (optional) |

## Example CLI Usage
Run the default workload:
```bash
python riscbench.py -v altera -d niosv -w Vector_Add -p Int32 -s 1024
```

Run with optional overrides:
```powershell
$env:ALTERA_SOF_PATH = "niosv/artifacts/sit_core.sof"
$env:ALTERA_ELF_PATH = "niosv/artifacts/app.elf"
python riscbench.py -v altera -d niosv -w Vector_Add -p Int32 -s 1024
```
