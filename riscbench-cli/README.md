# RISCBench — How to Run

> **RISCBench** is a CLI-based hardware benchmarking tool that profiles arithmetic workloads (vector add, vector multiply, matrix multiply) across different compute devices — Xilinx FPGAs, Altera FPGAs, and Tenstorrent accelerators.  
> It automates FPGA programming, ILA waveform capture, UART data logging, and result visualization into a single end-to-end flow.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)  
2. [Python Dependencies](#2-python-dependencies)  
3. [Environment Configuration (`env.json`)](#3-environment-configuration-envjson)  
4. [Running RISCBench](#4-running-riscbench)  
   - [Interactive Mode](#interactive-mode)  
   - [Config File Mode](#config-file-mode)  
   - [CLI Argument Mode](#cli-argument-mode)  
   - [Mixed Mode](#mixed-mode)  
5. [Viewing Results](#5-viewing-results)  
6. [Pipeline Overview](#6-pipeline-overview)  
7. [Xilinx-Specific Setup](#7-xilinx-specific-setup)  
8. [Project Structure](#8-project-structure)  
9. [Troubleshooting](#9-troubleshooting)  

---

## 1. Prerequisites

### System Requirements

| Requirement | Details |
|---|---|
| **OS** | Linux (tested on Ubuntu/Debian) or Windows (partial — interactive CLI supports both) |
| **Python** | Python 3.10+ |
| **Vivado** | Xilinx Vivado 2025.2 (or compatible) — required for Xilinx FPGA targets |
| **Vitis** | Xilinx Vitis 2025.2 (or compatible) — required for ELF compilation/download on Xilinx |
| **XSDB** | Comes with Vitis; must be on `PATH` after sourcing `settings64.sh` |
| **hw_server** | Xilinx Hardware Server must be running on `localhost:3121` (default) |
| **FPGA Board** | Xilinx Arty A7-35T (for Xilinx target), connected via USB/JTAG |
| **UART** | USB-to-UART cable connected (e.g., `/dev/ttyUSB1`) |

> **Note:** Tenstorrent and Altera device handlers are currently stubs (under development). Only the **Xilinx** target is fully functional.

---

## 2. Python Dependencies

Install all required Python packages:

```bash
pip install pyserial matplotlib pandas numpy
```

To use the **Results Viewer GUI** (optional — only needed for `--result` mode):

```bash
pip install PyQt5
```

### Summary of Dependencies

| Package | Purpose |
|---|---|
| `pyserial` | UART serial communication with the FPGA board |
| `matplotlib` | Generating waveform and benchmark plots |
| `pandas` | Parsing ILA CSV data exports |
| `numpy` | Numerical processing for waveform analysis |
| `PyQt5` | Results Viewer GUI (optional, for `-r` / `--result` flag) |

---

## 3. Environment Configuration (`env.json`)

Before running, edit the `env.json` file in the project root to match your local system paths and hardware setup:

```json
{
    "vivado_path": "/path/to/Xilinx/2025.2/Vivado",
    "vitis_path": "/path/to/Xilinx/2025.2/Vitis",
    "uart_port": "/dev/ttyUSB1",
    "uart_baud_rate": "9600",
    "tt_metal_home": ""
}
```

| Field | Description |
|---|---|
| `vivado_path` | Absolute path to the Vivado installation directory (contains `settings64.sh`) |
| `vitis_path` | Absolute path to the Vitis installation directory |
| `uart_port` | Serial port for UART communication (e.g., `/dev/ttyUSB1`, `/dev/ttyACM0`) |
| `uart_baud_rate` | Baud rate for UART (default: `9600`) |
| `tt_metal_home` | Path to Tenstorrent Metal SDK (leave empty if not using Tenstorrent) |

### Finding Your UART Port

```bash
# List available serial ports on Linux
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# Or use dmesg to find recently plugged-in devices
dmesg | grep tty
```

---

## 4. Running RISCBench

All commands are run from the **project root directory**.

### Interactive Mode

Run with no arguments to get an interactive CLI menu for selecting each parameter:

```bash
python riscbench.py
```

You will be guided through 4 selection menus:
1. **Device** — Xilinx Arty A7-35T FPGA, Altera Nano DE25 FPGA, or Tenstorrent Wormhole
2. **Workload** — Vector Addition, Vector Multiplication, or Matrix Multiplication
3. **Precision** — `int8`, `int16`, `int32` (FPGA devices); also `fp16`, `fp32`, `bf16` (Tenstorrent only)
4. **Vector Size** — `Sweep` (all sizes), or a specific power-of-2 from `1024` to `1048576`

Use **↑/↓ arrow keys** (or `j`/`k`) to navigate, **Enter** to select.

### Config File Mode

Provide a JSON config file to skip interactive menus:

```bash
python riscbench.py --config config.json
```

**Example `config.json`:**

```json
{
    "device": "xilinx",
    "workload": "vector_add",
    "precision": "int32",
    "vectorsize": "1024"
}
```

#### Valid Config Values

| Field | Valid Values |
|---|---|
| `device` | `xilinx`, `altera`, `tenstorrent` |
| `workload` | `vector_add`, `vector_mul`, `matrix_mul` |
| `precision` | `int8`, `int16`, `int32`, `fp16`, `fp32`, `bf16` |
| `vectorsize` | `Sweep`, `1024`, `2048`, `4096`, `8192`, `16384`, `32768`, `65536`, `131072`, `262144`, `524288`, `1048576` |

> **Note:** FPGA devices (Xilinx, Altera) only support integer precisions (`int8`, `int16`, `int32`). Floating-point precisions are only available for Tenstorrent.

### CLI Argument Mode

Pass individual parameters directly:

```bash
python riscbench.py -d xilinx -w vector_add -p int32 -v 1024
```

#### Available Flags

| Flag | Long Form | Description |
|---|---|---|
| `-c` | `--config` | Path to a JSON config file |
| `-d` | `--device` | Device name (`xilinx`, `altera`, `tenstorrent`) |
| `-w` | `--workload` | Workload name (`vector_add`, `vector_mul`, `matrix_mul`) |
| `-p` | `--precision` | Precision (`int8`, `int16`, `int32`, `fp16`, `fp32`, `bf16`) |
| `-v` | `--vectorsize` | Vector size (`Sweep`, `1024`, ..., `1048576`) |
| `-r` | `--result` | View results from a previous run (see [Viewing Results](#5-viewing-results)) |

### Mixed Mode

You can combine a config file with CLI overrides. CLI arguments take priority:

```bash
python riscbench.py --config config.json -v Sweep
```

Any values not provided via config or CLI will prompt the interactive menu.

---

## 5. Viewing Results

After a successful run, output data is saved to a timestamped folder under `./runs/`:

```
runs/
└── DD-MM-YYYY-HH-MM-SS-xilinx/
    ├── ila_captured_data.ila    # Raw ILA capture (Vivado native format)
    ├── ila_captured_data.csv    # ILA waveform data in CSV
    └── UART_results.csv         # Benchmark results from UART output
```

### View Results with the GUI

Launch the PyQt5-based Results Viewer:

```bash
# View the most recent run
python riscbench.py -r

# View the most recent run for a specific device
python riscbench.py -r xilinx

# View a specific run folder
python riscbench.py -r ./runs/21-08-2026-15-56-48-xilinx
```

The viewer displays:
- **Waveform View #1** — Zoomed ILA waveform capture (sample range 1)
- **Waveform View #2** — Zoomed ILA waveform capture (sample range 2)
- **SIT Calculation** — Signal Integrity Timing analysis
- **FLOPs Profile** — *(disabled in v0.1)*
- **Sweep Analysis** — *(disabled in v0.1)*

> **Requires:** `pip install PyQt5`

---

## 6. Pipeline Overview

When you run `python riscbench.py`, the following steps execute in order:

```
┌─────────────────────────────────────────────────────────┐
│  Step 1: Front End Handler                              │
│  • Parse CLI args and/or config file                    │
│  • Interactive selection for missing parameters         │
│  • Returns config dict with device/workload/precision   │
├─────────────────────────────────────────────────────────┤
│  Step 2: Load Environment                               │
│  • Read env.json (Vivado/Vitis paths, UART settings)    │
│  • Validate all required paths exist                    │
│  • Create timestamped run folder under ./runs/          │
├─────────────────────────────────────────────────────────┤
│  Step 3: Device Handler (Xilinx)                        │
│  • Update TCL script with output paths                  │
│  • Start UART logger thread (background)                │
│  • Source Vivado settings64.sh                          │
│  • Run Vivado in batch mode with run_file.tcl:          │
│    1. Connect to hw_server, program FPGA bitstream      │
│    2. Configure ILA trigger on target probe             │
│    3. Download ELF to MicroBlaze via XSDB               │
│    4. Arm ILA, resume processor execution               │
│    5. Wait for trigger, capture & export ILA data       │
│  • Stop UART logger, save results                       │
├─────────────────────────────────────────────────────────┤
│  Step 4: SIT Calculation (under construction)           │
├─────────────────────────────────────────────────────────┤
│  Step 5: Result Handler (under construction)            │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Xilinx-Specific Setup

The Xilinx flow requires several hardware and software components to be in place.

### Hardware Server

Before running, ensure the Xilinx Hardware Server (`hw_server`) is running:

```bash
# Source Vivado environment
source /path/to/Xilinx/2025.2/Vivado/settings64.sh

# Start hardware server (runs on localhost:3121 by default)
hw_server &
```

### Required Files

The following pre-built files must exist in `device_handler/xilinx/`:

| File | Description |
|---|---|
| `top_design.bit` | FPGA bitstream (generated from Vivado synthesis + implementation) |
| `top_design.ltx` | ILA probe definitions (generated with the bitstream) |
| `app.elf` | Software application ELF for MicroBlaze RISC-V core |
| `run_file.tcl` | TCL automation script for Vivado batch mode |

### Artifacts

The `device_handler/xilinx/artifacts/` directory contains supporting Vivado IP and project files:

- `CUSTOM_addsub1b_1_0/` — Custom AXI peripheral IP (add/subtract operations)
- `mig/` — Vitis Project files
- `MIIGTEST/` — Complete Vivado project with block design, IPs, and synthesis runs

### UART Permissions

Ensure your user has permission to access the serial port:

```bash
# Add your user to the dialout group
sudo usermod -a -G dialout $USER

# Log out and back in for changes to take effect
# Or temporarily change permissions:
sudo chmod 666 /dev/ttyUSB1
```

---

## 8. Project Structure

```
riscbench-dev/
├── riscbench.py                  # Main entry point
├── config.json                   # Default run configuration
├── env.json                      # Environment paths & UART settings
├── copy_to_repo.sh               # Script to sync files to internal repo
│
├── common/                       # Shared utilities
│   ├── __init__.py
│   ├── common.py                 # Device/workload/precision definitions
│   └── env.py                    # Environment loader & validator
│
├── front_end/                    # CLI front-end & argument parsing
│   ├── __init__.py
│   ├── frontend.py               # Main front-end handler with argparse
│   ├── front_end_helper.py       # Interactive TUI menu (arrow-key selection)
│   └── config_handler.py         # JSON config file loader
│
├── device_handler/               # Per-device execution handlers
│   ├── __init__.py
│   ├── device_handler.py         # Router — dispatches to correct device
│   ├── xilinx/                   # Xilinx FPGA handler (fully functional)
│   │   ├── xilinx.py             # Orchestrates Vivado + UART flow
│   │   ├── xilinx_helper.py      # Vivado runner & UART logger
│   │   ├── run_file.tcl          # Vivado batch TCL script
│   │   ├── top_design.bit        # FPGA bitstream
│   │   ├── top_design.ltx        # ILA probe file
│   │   ├── app.elf               # MicroBlaze application binary
│   │   └── artifacts/            # Vivado IP cores & project files
│   ├── altera/                   # Altera handler (stub)
│   └── tenstorrent/              # Tenstorrent handler (stub)
│
├── result_handler/               # Result processing & visualization
│   ├── __init__.py
│   ├── result_handler.py         # PyQt5 Results Viewer GUI
│   ├── ila_handler.py            # ILA CSV waveform parser & plot exporter
│   └── image[1-4].png            # Pre-generated visualization assets
│
└── runs/                         # Timestamped output directories
    └── DD-MM-YYYY-HH-MM-SS-{device}/
        ├── ila_captured_data.ila
        ├── ila_captured_data.csv
        └── UART_results.csv
```

---

## 9. Troubleshooting

### `[Error] Vivado Path is missing, update env.json`

Your `env.json` is missing or has an empty `vivado_path`. Set it to your Vivado installation directory, e.g.:
```json
"vivado_path": "/home/user/Xilinx/2025.2/Vivado"
```

### `[Error] Vivado settings script not found`

The path in `env.json` doesn't point to a valid Vivado installation. Verify that `settings64.sh` exists:
```bash
ls /path/to/Xilinx/2025.2/Vivado/settings64.sh
```

### `[UART Error] Could not open/access serial port`

- Check the device is connected: `ls /dev/ttyUSB*`
- Check permissions: `sudo chmod 666 /dev/ttyUSB1` or add yourself to the `dialout` group
- Verify the correct port in `env.json`

### `ERROR: PyQt5 is not installed`

Install PyQt5 for the results viewer:
```bash
pip install PyQt5
```
This is only required when using the `-r` / `--result` flag.

### `No ILA debug cores found in device`

The bitstream (`top_design.bit`) does not contain an ILA debug core, or the FPGA was not programmed correctly. Re-generate the bitstream in Vivado with ILA cores enabled.

### `Probe 'X' not found in LTX file`

The ILA probe name in `run_file.tcl` does not match any probe in `top_design.ltx`. Check available probes in Vivado Hardware Manager or update the `target_probe_name` variable in the TCL script.

### `Trigger timeout! Signal did not reach value`

The ILA trigger condition was not met within 10 seconds. The tool will force an immediate capture as a fallback. This may indicate the workload did not execute as expected on the MicroBlaze core.

---

*RISCBench v0.1 — Under Active Development*
