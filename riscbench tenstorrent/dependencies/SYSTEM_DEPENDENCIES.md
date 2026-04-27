# System Dependencies

This bundle keeps Python dependencies local, but the simulator and hardware backends still need their own system tools.

## Python

- Python 3.9+
- `venv`
- `pip`

Use:

```bash
bash bootstrap.sh
```

## Automatic Simulator Toolchain Management

The orchestrator now includes `device_handler/simulator_toolchain_manager.py`.

It can:

- resolve installed paths for `qemu`, `spike`, `pk`, and `gem5`
- optionally install missing simulator tools when you pass `--auto-install-simulator-tools`
- place locally managed source builds under `--simulator-toolchain-root`

Example:

```bash
python3 device_handler/orchestrator.py \
  --workload tt_eltwise_binary \
  --target tenstorrent \
  --workload-size tt_128tile \
  --time-us 256 \
  --auto-install-simulator-tools \
  --simulator-toolchain-root .toolchains
```

By default, nothing is auto-installed unless you opt in.

If you want to avoid repeated `sudo` prompts during setup, use the one-time system package bootstrap:

```bash
bash dependencies/install_simulator_system_deps.sh
```

That script:

- asks for `sudo` once with `sudo -v`
- keeps the sudo ticket alive while package installation runs
- installs the shared apt packages needed by QEMU, Spike/pk builds, and gem5 builds

It does not store your password anywhere in the repo or shell history.

## QEMU Backend

Required:

- `qemu-riscv64`
- `riscv64-linux-gnu-gcc`

Typical Ubuntu install:

```bash
sudo apt-get update
sudo apt-get install -y qemu-user gcc-riscv64-linux-gnu
```

## Spike Backend

Required:

- `spike`
- `riscv64-unknown-elf-gcc`
- a valid `pk` binary path

The config passes `pk` as a path, so make sure it exists on disk.

When `--auto-install-simulator-tools` is enabled, the simulator toolchain manager will try to:

- install `gcc-riscv64-unknown-elf` and build dependencies with `apt`
- clone and build `riscv-isa-sim`
- clone and build `riscv-pk`
- resolve `spike`, `spike_cc`, and `pk` paths automatically

## gem5 Backend

Required:

- a built `gem5.opt`
- `riscv64-linux-gnu-gcc`
- a valid `gem5_root` or `gem5_config`

Typical flow:

```bash
git clone https://github.com/gem5/gem5.git
cd gem5
scons build/RISCV/gem5.opt -j"$(nproc)"
```

When `--auto-install-simulator-tools` is enabled, the simulator toolchain manager will try to:

- install gem5 build dependencies with `apt`
- clone `gem5` under the local toolchain root
- build `build/RISCV/gem5.opt`
- feed `gem5_bin` and `gem5_root` back into the orchestrator

## Tenstorrent Hardware Side

The `tt_wormhole` path in this bundle ingests profiler logs.

Required inputs:

- `profile_log_device.csv`
- `zone_src_locations.log`

Optional automation:

- set `pre_run_cmd` in the config if you want the orchestrator to trigger your TT workflow before ingest
- that command can call your local `tt-metal` or other internal runner, as long as it leaves the profiler files at the configured paths

## What This Bundle Does Not Install By Default

- `tt-metal`
- Tenstorrent SDK/toolchains
- `spike` unless `--auto-install-simulator-tools` is enabled
- `pk` unless `--auto-install-simulator-tools` is enabled
- `gem5` unless `--auto-install-simulator-tools` is enabled
- system cross-compilers

Those remain external system dependencies and should be installed on the machine according to your environment.

## Recommended Permission Model

Do not hardcode a sudo password into scripts, config, or environment variables.

Prefer one of these:

1. Run `bash dependencies/install_simulator_system_deps.sh` once, then use normal orchestrator runs afterward.
2. Use `sudo -v` before a long install session so sudo caches credentials temporarily.
3. If your environment allows it, add a tightly scoped `NOPASSWD` rule in `/etc/sudoers.d/` for only the package-management commands you trust.

Example idea for a scoped sudoers rule:

```text
your_username ALL=(root) NOPASSWD: /usr/bin/apt-get, /usr/bin/apt
```

Only do that if you are comfortable with the security tradeoff on that machine.
