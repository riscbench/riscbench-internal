import os
import sys
import json
import time
import shutil
import re
import subprocess
import threading
from pathlib import Path

import common

# Resolve root directory of this backend handler
BACKEND_ROOT = Path(__file__).resolve().parent


def _load_local_env():
    """Load default/fallback settings from backend's local env.json if present."""
    env_file = BACKEND_ROOT / "env.json"
    if env_file.exists() and env_file.stat().st_size > 0:
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _find_tool(name, candidate_rel_dirs=()):
    """Locate tool binary from environment overrides, PATH, or standard Altera install roots."""
    local_env = _load_local_env()

    # Check environment variable and local env.json overrides
    env_roots = []
    for key in ("QUARTUS_PATH", "QUARTUS_ROOTDIR", "ALTERA_QUARTUS_PATH", "NIOSV_PATH", "NIOSV_ROOT"):
        val = os.environ.get(key) or local_env.get(key.lower())
        if val:
            env_roots.append(Path(val))

    # Check PATH
    found = shutil.which(name)
    if found:
        return os.path.abspath(found)

    # Standard installation root candidates
    for default_root in (Path("C:/altera_pro"), Path("C:/intelFPGA_pro"), Path("C:/intelFPGA"), Path("/opt/altera_pro"), Path("/opt/intelFPGA_pro")):
        if default_root.exists():
            env_roots.append(default_root)

    # Search candidates
    exts = [".exe", ""] if os.name == "nt" else [""]
    for root in env_roots:
        for rel in candidate_rel_dirs:
            for ext in exts:
                candidate = root / rel / f"{name}{ext}"
                if candidate.exists():
                    return str(candidate.resolve())
                candidate2 = root / f"{name}{ext}"
                if candidate2.exists():
                    return str(candidate2.resolve())

        # Recursive check in subdirectories
        for ext in exts:
            matches = list(root.glob(f"*/{name}{ext}")) + list(root.glob(f"*/*/{name}{ext}"))
            if matches:
                return str(matches[0].resolve())

    return None


def get_altera_tools():
    """Locate quartus_pgm, juart-terminal, jtagconfig, and RiscFree GDB toolchain binaries."""
    local_env = _load_local_env()

    qdirs = ("quartus/bin64", "quartus/bin", "bin64", "bin")
    ndirs = ("niosv/bin", "bin")
    gdbserver_dirs = ("riscfree/debugger/gdbserver-riscv", "debugger/gdbserver-riscv")
    toolchain_dirs = ("riscfree/toolchain/riscv32-unknown-elf/bin", "toolchain/riscv32-unknown-elf/bin")
    cmake_dirs = ("riscfree/build_tools/cmake/bin", "build_tools/cmake/bin")

    tool_specs = {
        "quartus_pgm": ("quartus_pgm", qdirs),
        "juart_terminal": ("juart-terminal", qdirs + ndirs),
        "jtagconfig": ("jtagconfig", qdirs),
        "niosv_download": ("niosv-download", ndirs),
        "gdb_server": ("ash-riscv-gdb-server", gdbserver_dirs),
        "gdb": ("riscv32-unknown-elf-gdb", toolchain_dirs),
        "readelf": ("riscv32-unknown-elf-readelf", toolchain_dirs),
        "cmake": ("cmake", cmake_dirs),
    }

    resolved_tools = {}
    missing = []

    for key, (binary_name, rel_dirs) in tool_specs.items():
        # 1. Environment variable override
        env_val = os.environ.get(f"ALTERA_{key.upper()}") or os.environ.get(key.upper())
        if env_val and Path(env_val).exists():
            resolved_tools[key] = str(Path(env_val).resolve())
            continue

        # 2. env.json override
        json_val = local_env.get(key)
        if json_val and Path(json_val).exists():
            resolved_tools[key] = str(Path(json_val).resolve())
            continue

        # 3. Discovery in standard paths / PATH
        found = _find_tool(binary_name, rel_dirs)
        if found and Path(found).exists():
            resolved_tools[key] = str(Path(found).resolve())
        elif key == "cmake":
            # Fallback to system cmake if available
            sys_cmake = shutil.which("cmake")
            resolved_tools[key] = sys_cmake or "cmake"
        else:
            missing.append(key)

    if missing:
        error_msg = (
            f"[Error] Missing required Altera/Nios V tool(s): {', '.join(missing)}.\n"
            "Please configure their paths in device_handler/altera/env.json or set QUARTUS_PATH in your environment."
        )
        print(error_msg, file=sys.stderr)
        raise RuntimeError(error_msg)

    return resolved_tools


def resolve_artifact(env_var_names, file_ext, config, default_filenames=(), description="Artifact", json_key=None):
    """
    Lookup order:
    1. Environment-variable override
    2. env.json override (via json_key or fallback var names)
    3. Bundled backend artifact relative to BACKEND_ROOT / device / workload / precision
    4. Clear error if unavailable
    """
    local_env = _load_local_env()

    # Helper to test candidate paths (absolute or relative to current/parent dirs)
    def _find_candidate_path(p_str):
        if not p_str:
            return None
        cand = Path(p_str)
        if cand.is_absolute() and cand.exists():
            return str(cand.resolve())
        # Try relative to cwd and all parent hierarchies
        bases = [Path.cwd(), BACKEND_ROOT] + list(BACKEND_ROOT.parents)
        for base in bases:
            test_path = (base / cand).resolve()
            if test_path.exists():
                return str(test_path)
        return None

    # 1. Environment-variable override (highest priority)
    for var in env_var_names:
        val = os.environ.get(var)
        if val:
            resolved = _find_candidate_path(val)
            if resolved:
                return resolved
            else:
                error_msg = f"[Error] {description} specified by {var}='{val}' does not exist."
                print(error_msg, file=sys.stderr)
                raise FileNotFoundError(error_msg)

    # 2. env.json override
    if json_key:
        json_val = local_env.get(json_key)
        if json_val:
            resolved = _find_candidate_path(json_val)
            if resolved:
                return resolved
            else:
                error_msg = f"[Error] {description} specified in env.json by '{json_key}'='{json_val}' does not exist."
                print(error_msg, file=sys.stderr)
                raise FileNotFoundError(error_msg)

    for var in env_var_names:
        json_val = local_env.get(var.lower())
        if json_val:
            resolved = _find_candidate_path(json_val)
            if resolved:
                return resolved

    # Extract device, workload, precision from config
    device = config.get("d_id", ["niosv"])[0] if isinstance(config.get("d_id"), list) else str(config.get("d_id", "niosv"))
    workload = config.get("w_id", ["Vector_Add"])[0] if isinstance(config.get("w_id"), list) else str(config.get("w_id", "Vector_Add"))
    precision = config.get("p_id", ["Int32"])[0] if isinstance(config.get("p_id"), list) else str(config.get("p_id", "Int32"))

    # 3. Bundled backend artifact (e.g. BACKEND_ROOT / device / artifacts / ...)
    artifacts_dir = BACKEND_ROOT / device / "artifacts"
    if artifacts_dir.exists():
        for fname in default_filenames:
            candidate = artifacts_dir / fname
            if candidate.exists():
                return str(candidate.resolve())
        matches = list(artifacts_dir.glob(f"*{file_ext}"))
        if matches:
            return str(matches[0].resolve())

    bundled_dir = BACKEND_ROOT / device / workload / precision
    if bundled_dir.exists():
        for fname in default_filenames:
            candidate = bundled_dir / fname
            if candidate.exists():
                return str(candidate.resolve())

        matches = list(bundled_dir.glob(f"*{file_ext}"))
        if matches:
            return str(matches[0].resolve())

    # Also check common.precision_path if available
    if hasattr(common, "precision_path") and common.precision_path:
        cand_dir = Path(common.precision_path)
        if cand_dir.exists():
            for fname in default_filenames:
                candidate = cand_dir / fname
                if candidate.exists():
                    return str(candidate.resolve())
            matches = list(cand_dir.glob(f"*{file_ext}"))
            if matches:
                return str(matches[0].resolve())

    # 4. Clear error if unavailable
    error_msg = (
        f"[Error] Required {description} ({file_ext}) could not be located.\n"
        f"  - Checked environment variables: {', '.join(env_var_names)}\n"
        f"  - Checked env.json key: {json_key}\n"
        f"  - Checked bundled path: {bundled_dir}\n"
        f"Please provide the path in device_handler/altera/env.json or set the {env_var_names[0]} environment variable."
    )
    print(error_msg, file=sys.stderr)
    raise FileNotFoundError(error_msg)


WORKLOAD_MAP = {
    "vecadd": 0,
    "vector_add": 0,
    "vecmul": 1,
    "vector_mul": 1,
    "dot": 2,
    "dot_product": 2,
    "matrix_mul": 3,
    "matmul": 3,
    "matrix_multiply": 3,
    "matrix_mult": 3,
    "saxpy": 4,
    "all": 5,
}

PRECISION_MAP = {
    "int8": 0,
    "int16": 1,
    "int32": 4,
    "fp16": 3,
    "float16": 3,
    "fp32": 4,
    "float32": 4,
}


def build_tool_env(tools):
    """Construct execution environment with required tool directories prepended to PATH."""
    env = os.environ.copy()
    dirs_to_add = []
    for tool_path in tools.values():
        if tool_path and os.path.exists(tool_path):
            tool_dir = os.path.dirname(tool_path)
            if tool_dir not in dirs_to_add:
                dirs_to_add.append(tool_dir)

    # Ensure GCC toolchain and build tool binaries are in PATH
    for ref_key in ("gdb", "niosv_download", "quartus_pgm", "cmake"):
        ref_path = tools.get(ref_key)
        if ref_path and os.path.exists(ref_path):
            try:
                root = Path(ref_path).parents[2]
                extra_dirs = [
                    root / "riscfree" / "toolchain" / "riscv32-unknown-elf" / "bin",
                    root / "riscfree" / "build_tools" / "cmake" / "bin",
                    root / "riscfree" / "build_tools" / "ninja",
                    root / "niosv" / "bin",
                    root / "quartus" / "bin64",
                ]
                for d in extra_dirs:
                    if d.exists() and str(d.resolve()) not in dirs_to_add:
                        dirs_to_add.append(str(d.resolve()))
            except Exception:
                pass

    current_path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(dirs_to_add + [current_path])
    return env


def sync_and_build_firmware(config, tools, tool_env):
    """Write sw/run_config.h, build canonical firmware ELF, and verify build success before running."""
    if not config:
        return None

    workload_str = config.get("w_id", ["Vector_Add"])[0] if isinstance(config.get("w_id"), list) else str(config.get("w_id", "Vector_Add"))
    precision_str = config.get("p_id", ["Int32"])[0] if isinstance(config.get("p_id"), list) else str(config.get("p_id", "Int32"))
    size_val = config.get("s_id", [1024])[0] if isinstance(config.get("s_id"), list) else config.get("s_id", 1024)

    try:
        size = int(size_val)
    except (ValueError, TypeError):
        size = 1024

    w_key = workload_str.lower().strip().replace("-", "_")
    if w_key not in WORKLOAD_MAP:
        error_msg = f"[Error] Unsupported workload '{workload_str}'. Supported: Vector_Add, Vector_Mul, Dot, Matrix_Mul, SAXPY, all"
        print(error_msg, file=sys.stderr)
        raise ValueError(error_msg)
    mode = WORKLOAD_MAP[w_key]

    p_key = precision_str.lower().strip()
    if p_key not in PRECISION_MAP:
        error_msg = f"[Error] Unsupported precision '{precision_str}'. Supported: Int8, Int16, Int32, FP16, FP32"
        print(error_msg, file=sys.stderr)
        raise ValueError(error_msg)
    precision = PRECISION_MAP[p_key]

    device_name = config.get("d_id", ["niosv"])[0] if isinstance(config.get("d_id"), list) else str(config.get("d_id", "niosv"))
    source_dir = None
    bsp_dir = None
    artifacts_elf = None

    # 1. Check backend niosv/firmware tree
    cand_fw = BACKEND_ROOT / device_name / "firmware"
    if not cand_fw.exists():
        cand_fw = BACKEND_ROOT / "niosv" / "firmware"
    if cand_fw.exists():
        cand_src = cand_fw / "source" if (cand_fw / "source").exists() else cand_fw
        if (cand_src / "run_config.h").exists():
            source_dir = cand_src
            bsp_dir = cand_fw / "bsp"
            artifacts_elf = BACKEND_ROOT / device_name / "artifacts" / "app.elf"

    # 2. Legacy workspace_root / "sw"
    if not source_dir:
        for p in [BACKEND_ROOT] + list(BACKEND_ROOT.parents):
            if (p / "sw").exists() and (p / "sw" / "run_config.h").exists():
                source_dir = p / "sw"
                bsp_dir = p / "sw" / "bsp"
                break

    if not source_dir:
        return None

    sw_build_dir = source_dir / "build"
    run_config_path = source_dir / "run_config.h"
    built_elf = sw_build_dir / "app.elf"

    os.makedirs(sw_build_dir, exist_ok=True)
    config_text = (
        "#ifndef RISCBENCH_RUN_CONFIG_H\n"
        "#define RISCBENCH_RUN_CONFIG_H\n\n"
        "#define RISCBENCH_AUTORUN 1\n"
        f"#define RISCBENCH_MODE {mode}\n"
        f"#define RISCBENCH_SIZE {size}\n"
        f"#define RISCBENCH_PRECISION {precision}\n"
        "#define RISCBENCH_TRACE 0\n"
        "#define RISCBENCH_ALPHA_BITS 0x00000002u\n"
        "#define RISCBENCH_MATMUL_PATTERN 0\n"
        "#define RISCBENCH_AUTORUN_DELAY_US 0u\n\n"
        "#endif\n"
    )
    run_config_path.write_text(config_text, encoding="ascii")
    print(f"[Info] Synchronized run_config.h: mode={mode} ({workload_str}), size={size}, precision={precision} ({precision_str})")

    cmake_bin = tools.get("cmake", "cmake")
    if not (sw_build_dir / "build.ninja").exists():
        print(f"[Info] Configuring CMake build in {sw_build_dir}...", flush=True)
        config_cmd = [cmake_bin, "-B", str(sw_build_dir.resolve()), "-S", str(source_dir.resolve()), "-G", "Ninja"]
        cfg_res = subprocess.run(config_cmd, capture_output=True, text=True, env=tool_env, errors="replace")
        if cfg_res.returncode != 0:
            print(f"[Warning] CMake configure returned {cfg_res.returncode}:\n{cfg_res.stderr or cfg_res.stdout}")

    print(f"[Info] Automatically building canonical firmware ELF ({workload_str}, {precision_str}, size={size})...", flush=True)
    build_cmd = [cmake_bin, "--build", str(sw_build_dir.resolve())]
    build_res = subprocess.run(build_cmd, capture_output=True, text=True, env=tool_env, errors="replace")
    if build_res.returncode != 0:
        error_msg = f"[Error] Firmware build failed (return code {build_res.returncode}):\n{build_res.stderr or build_res.stdout}"
        print(error_msg, file=sys.stderr)
        raise RuntimeError(error_msg)

    if not built_elf.exists():
        error_msg = f"[Error] Expected built ELF '{built_elf}' was not created."
        print(error_msg, file=sys.stderr)
        raise FileNotFoundError(error_msg)

    print(f"[Info] Firmware build verified successfully: {built_elf}")

    # Refresh canonical artifacts/app.elf if present
    if artifacts_elf is not None:
        os.makedirs(artifacts_elf.parent, exist_ok=True)
        shutil.copy2(built_elf, artifacts_elf)
        print(f"[Info] Refreshed artifacts ELF: {artifacts_elf}")
        return str(artifacts_elf.resolve())

    return str(built_elf.resolve())



def discover_jtag_target(jtagconfig_bin, tool_env, preferred_cable=None):
    """Discover JTAG cable index and device name using jtagconfig."""
    proc = subprocess.run([jtagconfig_bin], capture_output=True, text=True, env=tool_env, errors="replace")
    raw = (proc.stdout or "") + (proc.stderr or "")
    matches = list(re.finditer(r"(?m)^(\d+)\)\s+(.+)$", raw))
    if not matches:
        raise RuntimeError("No JTAG cables detected by jtagconfig.\n" + raw)

    target_match = None
    if preferred_cable is not None:
        for m in matches:
            if str(preferred_cable) in (m.group(1), m.group(2)):
                target_match = m
                break
    if target_match is None:
        target_match = matches[0]

    cable_num = int(target_match.group(1))
    cable_name = target_match.group(2).strip()

    # Extract target device
    target_idx = matches.index(target_match)
    end = matches[target_idx + 1].start() if target_idx + 1 < len(matches) else len(raw)
    body = raw[target_match.end():end]
    devices = [line.strip() for line in body.splitlines() if line.strip() and "Unable to" not in line]
    device_name = devices[0].split()[0] if devices else "4364C0DD"

    return cable_num, cable_name, device_name


def get_elf_entry(readelf_bin, elf_path, tool_env):
    """Dynamically determine entry point address (_start) from ELF header using readelf."""
    result = subprocess.run([readelf_bin, "-h", str(Path(elf_path).resolve())],
                            text=True, capture_output=True, env=tool_env, errors="replace")
    match = re.search(r"Entry point address:\s*0x([0-9a-fA-F]+)", result.stdout + result.stderr)
    if result.returncode != 0 or not match:
        raise RuntimeError(f"Unable to determine ELF entry point for {elf_path}:\n" + result.stdout + result.stderr)
    return int(match.group(1), 16)


def launch_elf_via_gdb(tools, tool_env, cable_num, device_name, elf_path, trace_enabled=False, timeout=60.0):
    """
    Launch ELF on Nios V via ash-riscv-gdb-server and riscv32-unknown-elf-gdb.
    Matches the proven sequence from tools/riscbench/mailbox.py.
    """
    server_bin = tools["gdb_server"]
    gdb_bin = tools["gdb"]
    readelf_bin = tools["readelf"]

    entry_addr = get_elf_entry(readelf_bin, elf_path, tool_env)
    print(f"[Info] Resolved ELF entry point (_start) : 0x{entry_addr:08x}")

    server_cmd = [
        str(server_bin),
        "--auto-detect", "true",
        "--probe-type", "usb-blaster-2",
        "--instance", str(cable_num),
        "--device", str(device_name),
        "--core-number", "0"
    ]

    if trace_enabled:
        print(f"[GDB] GDB Server Command: {subprocess.list2cmdline(server_cmd)}")

    # Start GDB Server and wait for port
    deadline = time.monotonic() + timeout
    server = None
    port = None
    server_captured = []

    for attempt in range(6):
        server = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=tool_env,
            errors="replace",
            bufsize=1
        )
        server_captured = []
        while time.monotonic() < deadline:
            line = server.stdout.readline() if server.stdout else ""
            if line:
                server_captured.append(line)
                if trace_enabled:
                    print(f"[GDB-Server] {line.rstrip()}")
                match = re.search(r"port\s+(\d+)", line, re.IGNORECASE)
                if match:
                    port = int(match.group(1))
                    break
            elif server.poll() is not None:
                break

        if port is not None:
            break

        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()

        if time.monotonic() >= deadline:
            break
        print(f"[Info] GDB server attach retry {attempt + 1}/6...")
        time.sleep(0.75)

    if port is None or server is None:
        raise RuntimeError("GDB server did not report a port\n" + "".join(server_captured))

    # Construct GDB batch command
    elf_posix = Path(elf_path).resolve().as_posix()
    gdb_cmd = [
        str(gdb_bin), "-batch",
        "-ex", "set confirm off",
        "-ex", "set arch riscv:rv32",
        "-ex", "set remotetimeout 60",
        "-ex", f"file {elf_posix}",
        "-ex", f"target extended-remote localhost:{port}",
        "-ex", "load",
        "-ex", f"set $pc = 0x{entry_addr:08x}",
        "-ex", "set $mstatus &= ~(0x00000088)",
        "-ex", "continue&",
        "-ex", "shell powershell -NoProfile -Command Start-Sleep -Milliseconds 750",
        "-ex", "disconnect"
    ]

    if trace_enabled:
        print(f"[GDB] GDB Client Command: {subprocess.list2cmdline(gdb_cmd)}")

    try:
        gdb_res = subprocess.run(
            gdb_cmd,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=tool_env,
            errors="replace"
        )
        combined_output = "".join(server_captured) + gdb_res.stdout + gdb_res.stderr
        if trace_enabled:
            print("[GDB] GDB Output:\n" + combined_output)
            print(f"[GDB] GDB exit code: {gdb_res.returncode}")

        if (gdb_res.returncode != 0 or
                "No executable file specified" in combined_output or
                "No such file or directory" in combined_output):
            raise RuntimeError("GDB launch failed:\n" + combined_output)

        print("[Info] ELF download and processor execution started via GDB.")
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()


import queue

class JuartCapture:
    """Manages juart-terminal lifecycle and streams/records UART output."""

    def __init__(self, juart_bin, cable, tool_env, trace_enabled=False):
        self.juart_bin = juart_bin
        self.cable = cable
        self.tool_env = tool_env
        self.trace_enabled = trace_enabled
        self.proc = None
        self.output_lines = []
        self.raw_output = bytearray()
        self.connected_event = threading.Event()
        self.completed_event = threading.Event()
        self.chunks = queue.Queue()
        self.stop_event = threading.Event()
        self.processor_thread = None

    def start(self):
        cmd = [self.juart_bin]
        if self.cable:
            cmd.extend(["-c", str(self.cable)])

        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            env=self.tool_env
        )

        def _stream_reader(stream):
            try:
                while not self.stop_event.is_set():
                    data = stream.read(256)
                    if not data:
                        break
                    self.chunks.put(data)
            except Exception:
                pass
            finally:
                self.chunks.put(None)

        def _line_processor():
            line_buf = ""
            while not self.stop_event.is_set() or not self.chunks.empty():
                try:
                    data = self.chunks.get(timeout=0.05)
                except queue.Empty:
                    if self.proc and self.proc.poll() is not None:
                        break
                    continue
                if data is None:
                    continue
                self.raw_output.extend(data)
                text = data.decode("utf-8", errors="replace")
                line_buf += text
                while "\n" in line_buf:
                    line, line_buf = line_buf.split("\n", 1)
                    line_str = line.rstrip("\r")
                    self.output_lines.append(line_str + "\n")
                    if "connected to hardware target" in line_str:
                        self.connected_event.set()
                    if self.trace_enabled:
                        print(f"[UART] {line_str}", flush=True)
                    if "RISCBENCH_RUN_END" in line_str:
                        self.completed_event.set()

            if line_buf.strip():
                line_str = line_buf.rstrip("\r")
                self.output_lines.append(line_str + "\n")
                if self.trace_enabled:
                    print(f"[UART] {line_str}", flush=True)
                if "RISCBENCH_RUN_END" in line_str:
                    self.completed_event.set()

        t_out = threading.Thread(target=_stream_reader, args=(self.proc.stdout,), daemon=True)
        t_err = threading.Thread(target=_stream_reader, args=(self.proc.stderr,), daemon=True)
        self.processor_thread = threading.Thread(target=_line_processor, daemon=True)
        t_out.start()
        t_err.start()
        self.processor_thread.start()

    def wait_connected(self, timeout=2.0):
        """Wait briefly for initial JTAG connection confirmation."""
        self.connected_event.wait(timeout=timeout)

    def wait_completion(self, timeout=10.0):
        """Wait until RISCBENCH_RUN_END is seen or timeout expires."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.completed_event.is_set():
                break
            time.sleep(0.05)

    def stop_and_save(self, csv_output_path):
        """Terminate juart-terminal process and persist all captured lines."""
        self.stop_event.set()
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass

        if self.processor_thread and self.processor_thread.is_alive():
            self.processor_thread.join(timeout=1.0)

        os.makedirs(os.path.dirname(csv_output_path), exist_ok=True)
        with open(csv_output_path, "w", encoding="utf-8") as f:
            f.writelines(self.output_lines)


MAILBOX_ADDR = 0x00FFF000
MAILBOX_MAGIC = 0x52425354          # 'RBST'
MAILBOX_FAILURE_MAGIC = 0x52424641  # 'RBFA'
MAILBOX_WORDS = 10
DEBUG_PROGRESS_ADDR = 0x00FFFFFC


def read_memory_words(tools, tool_env, cable_num, device_name, address, count, timeout=30.0):
    """Read words from target memory via GDB (matching tools/riscbench/mailbox.py)."""
    server_bin = tools["gdb_server"]
    gdb_bin = tools["gdb"]
    server_cmd = [
        str(server_bin),
        "--auto-detect", "true",
        "--probe-type", "usb-blaster-2",
        "--instance", str(cable_num),
        "--device", str(device_name),
        "--core-number", "0"
    ]
    server = subprocess.Popen(
        server_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, env=tool_env, errors="replace", bufsize=1
    )
    port = None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = server.stdout.readline() if server.stdout else ""
        if line:
            m = re.search(r"port\s+(\d+)", line, re.IGNORECASE)
            if m:
                port = int(m.group(1))
                break
        elif server.poll() is not None:
            break

    if port is None:
        server.terminate()
        return None

    try:
        gdb_cmd = [
            str(gdb_bin), "-batch",
            "-ex", "set confirm off",
            "-ex", "set arch riscv:rv32",
            "-ex", "set remotetimeout 30",
            "-ex", f"target extended-remote localhost:{port}",
            "-ex", f"x/{count}wx 0x{address:08x}",
            "-ex", "continue&",
            "-ex", "detach"
        ]
        res = subprocess.run(gdb_cmd, capture_output=True, text=True, env=tool_env, timeout=timeout)
        output = res.stdout + res.stderr
        data = []
        for line in output.splitlines():
            if ":" in line and re.match(r"\s*0x[0-9a-fA-F]+\s*:", line):
                data.extend(int(val, 16) for val in re.findall(r"0x([0-9a-fA-F]{8})", line.split(":", 1)[1]))
        return data[:count] if len(data) >= count else None
    finally:
        server.terminate()
        try:
            server.wait(timeout=2)
        except Exception:
            server.kill()


def altera_run_flow(config):
    """Main execution flow for Altera backend."""
    print("[Info] Starting Altera / Nios V Device Handler Flow...")

    # 1. Resolve required tools
    tools = get_altera_tools()
    tool_env = build_tool_env(tools)

    # 2. Synchronize firmware configuration with CLI parameters and rebuild if source tree is present
    built_elf_path = sync_and_build_firmware(config, tools, tool_env)

    # Resolve required bitstream (.sof) and executable (.elf)
    sof_path = resolve_artifact(
        env_var_names=["ALTERA_SOF_PATH", "QUARTUS_SOF_PATH", "SOF_PATH"],
        file_ext=".sof",
        config=config,
        default_filenames=["sit_core.sof", "Sit_burst.sof", "top_design.sof"],
        description="Altera SOF Bitstream",
        json_key="sof_path"
    )

    elf_path = built_elf_path or resolve_artifact(
        env_var_names=["ALTERA_ELF_PATH", "NIOSV_ELF_PATH", "ELF_PATH"],
        file_ext=".elf",
        config=config,
        default_filenames=["app.elf"],
        description="Nios V ELF Executable",
        json_key="elf_path"
    )

    local_env = _load_local_env()
    cable_pref = os.environ.get("ALTERA_CABLE") or os.environ.get("JTAG_CABLE") or local_env.get("cable") or None

    cable_num, cable_name, device_name = discover_jtag_target(tools["jtagconfig"], tool_env, preferred_cable=cable_pref)

    trace_env = os.environ.get("ALTERA_TRACE")
    if trace_env is not None:
        trace_enabled = trace_env.strip() in ("1", "true", "True", "TRUE")
    else:
        trace_enabled = bool(local_env.get("trace", False) or local_env.get("altera_trace", False))

    timeout_env = os.environ.get("ALTERA_UART_TIMEOUT") or local_env.get("uart_timeout")
    try:
        uart_timeout = float(timeout_env) if timeout_env is not None else 10.0
    except (ValueError, TypeError):
        uart_timeout = 10.0

    run_dir = common.env.run_path if (hasattr(common, "env") and hasattr(common.env, "run_path") and common.env.run_path) else "./runs/altera_run"
    csv_output_path = os.path.join(run_dir, "UART_results.csv")
    ila_output_path = os.path.join(run_dir, "ila_captured_data.csv")

    print(f"[Info] Backend Root             : {BACKEND_ROOT}")
    print(f"[Info] Using Quartus Programmer : {tools['quartus_pgm']}")
    print(f"[Info] Using JTAG UART Terminal : {tools['juart_terminal']}")
    print(f"[Info] Using GDB Server         : {tools['gdb_server']}")
    print(f"[Info] Using RISC-V GDB Client  : {tools['gdb']}")
    print(f"[Info] Resolved SOF Bitstream   : {sof_path}")
    print(f"[Info] Resolved ELF Executable  : {elf_path}")
    print(f"[Info] Target Cable             : [{cable_num}] {cable_name}")
    print(f"[Info] Target Device            : {device_name}")
    if trace_enabled:
        print("[Info] Live UART trace enabled (ALTERA_TRACE=1)")

    # 3. Program FPGA via quartus_pgm
    print("[Info] Programming FPGA via quartus_pgm...", flush=True)
    pgm_cmd = [tools["quartus_pgm"], "-m", "JTAG", "-c", str(cable_num), "-o", f"p;{sof_path}"]

    pgm_res = subprocess.run(pgm_cmd, capture_output=True, text=True, env=tool_env, errors="replace")
    if pgm_res.returncode != 0:
        # Fallback with cable_name if cable_num fails
        pgm_cmd = [tools["quartus_pgm"], "-m", "JTAG", "-c", str(cable_name), "-o", f"p;{sof_path}"]
        pgm_res = subprocess.run(pgm_cmd, capture_output=True, text=True, env=tool_env, errors="replace")
    if pgm_res.returncode != 0:
        error_msg = f"[Error] quartus_pgm failed (return code {pgm_res.returncode}):\n{pgm_res.stderr or pgm_res.stdout}"
        print(error_msg, file=sys.stderr)
        raise RuntimeError(error_msg)
    print("[Info] FPGA programming completed successfully.")

    # 4. Start juart-terminal and wait for initial connection
    juart = JuartCapture(
        juart_bin=tools["juart_terminal"],
        cable=cable_num,
        tool_env=tool_env,
        trace_enabled=trace_enabled
    )
    juart.start()
    juart.wait_connected(timeout=2.0)

    # 5. Launch ELF via proven GDB launch flow
    print("[Info] Launching Nios V firmware via GDB...", flush=True)
    launch_elf_via_gdb(
        tools=tools,
        tool_env=tool_env,
        cable_num=cable_num,
        device_name=device_name,
        elf_path=elf_path,
        trace_enabled=trace_enabled,
        timeout=60.0
    )

    # 6. Keep juart-terminal alive to capture firmware output until completion or timeout
    juart.wait_completion(timeout=uart_timeout)
    juart.stop_and_save(csv_output_path)

    # 7. Collect performance counters from mailbox and validate layout/sanity
    print("[Info] Reading benchmark performance counters from mailbox (0x%08X)..." % MAILBOX_ADDR, flush=True)
    mb_words = read_memory_words(tools, tool_env, cable_num, device_name, MAILBOX_ADDR, MAILBOX_WORDS, timeout=20.0)
    if mb_words and len(mb_words) >= MAILBOX_WORDS:
        magic, status, mode, size, total_cycles, active_cycles, stall_cycles, mem_wait_cycles, ops_completed, trace_count = mb_words[:10]

        print("\n--- Mailbox Memory Layout [0x%08X] ---" % MAILBOX_ADDR)
        print(f"  Word 0 [0x00] magic          : 0x{magic:08X} ({'RBST (PASS)' if magic == MAILBOX_MAGIC else 'RBFA (FAIL)' if magic == MAILBOX_FAILURE_MAGIC else 'UNKNOWN'})")
        print(f"  Word 1 [0x04] status         : {status} ({'PASS' if status == 0 else 'FAIL'})")
        print(f"  Word 2 [0x08] mode           : {mode}")
        print(f"  Word 3 [0x0C] size           : {size}")
        print(f"  Word 4 [0x10] total_cycles   : {total_cycles}")
        print(f"  Word 5 [0x14] active_cycles  : {active_cycles}")
        print(f"  Word 6 [0x18] stall_cycles   : {stall_cycles}")
        print(f"  Word 7 [0x1C] mem_wait_cycles: {mem_wait_cycles}")
        print(f"  Word 8 [0x20] ops_completed  : {ops_completed}")
        print(f"  Word 9 [0x24] trace_count    : {trace_count}")
        print("-----------------------------------------\n")

        # Sanity validation
        is_sane = True
        if total_cycles == 0:
            print("[Warning] Sanity check failed: total_cycles == 0")
            is_sane = False
        if active_cycles > total_cycles:
            print(f"[Warning] Sanity check failed: active_cycles ({active_cycles}) > total_cycles ({total_cycles})")
            is_sane = False
        if mem_wait_cycles > total_cycles:
            print(f"[Warning] Sanity check failed: mem_wait_cycles ({mem_wait_cycles}) > total_cycles ({total_cycles})")
            is_sane = False
        if status == 0 and size > 0 and ops_completed != size:
            print(f"[Warning] Note: ops_completed ({ops_completed}) does not equal configured size ({size})")

        perf_line = f"PERF,total_cycles={total_cycles},active_cycles={active_cycles},mem_wait_cycles={mem_wait_cycles},ops_completed={ops_completed}\n"
        print(f"[Info] Captured Performance Metrics: {perf_line.strip()}", flush=True)

        # Ensure values are recorded in UART_results.csv
        with open(csv_output_path, "a", encoding="utf-8") as f:
            f.write(f"DEBUG_MONITOR_ENABLE=1\n")
            f.write(f"DEBUG_TOTAL_LO={total_cycles}\n")
            f.write(f"DEBUG_TOTAL_HI=0\n")
            f.write(f"DEBUG_ACTIVE_LO={active_cycles}\n")
            f.write(f"DEBUG_ACTIVE_HI=0\n")
            f.write(f"DEBUG_MEMWAIT_LO={mem_wait_cycles}\n")
            f.write(f"DEBUG_MEMWAIT_HI=0\n")
            f.write(f"DEBUG_OPS_LO={ops_completed}\n")
            f.write(f"DEBUG_OPS_HI=0\n")
            f.write(perf_line)
            f.write("RISCBENCH_RUN_END\n")

    # Placeholder for ILA csv if needed
    if not os.path.exists(ila_output_path):
        os.makedirs(os.path.dirname(ila_output_path), exist_ok=True)
        with open(ila_output_path, "w", encoding="utf-8") as f:
            f.write("Sample Number,Trigger\n0,0\n")

    print(f"[Info] Altera run completed. UART results saved to {csv_output_path}")


def altera_handle(config):
    """Entry point called by device_handler when vendor is Altera."""
    print("[Info] Device handler selected vendor: Altera")
    altera_run_flow(config)


if __name__ == "__main__":
    altera_handle({"v_id": ["altera", 1], "d_id": ["niosv", 0], "w_id": ["Vector_Add", 0], "p_id": ["Int32", 0]})