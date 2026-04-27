#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolchainSettings:
    root_dir: Path
    auto_install: bool = False
    dry_run: bool = False
    show_commands: bool = False
    gem5_ref: str = ""
    spike_ref: str = ""
    pk_ref: str = ""


@dataclass
class ToolchainResult:
    resolved_args: dict[str, Any]
    errors: list[str]
    install_actions: list[str]


def _home_dir() -> Path:
    return Path.home()


def _common_riscv_roots(settings: ToolchainSettings) -> list[Path]:
    home = _home_dir()
    return [
        settings.root_dir / "opt" / "riscv",
        home / "opt" / "riscv",
        Path("/opt/riscv"),
    ]


def _common_gem5_roots(settings: ToolchainSettings) -> list[Path]:
    home = _home_dir()
    return [
        settings.root_dir / "src" / "gem5",
        home / "opt" / "gem5",
        home / "gem5",
        Path("/opt/gem5"),
    ]


def _as_path(value: Any) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _resolve_executable(value: Any, env_key: str, candidates: list[Path] | None = None) -> str | None:
    candidates = list(candidates or [])
    explicit = str(value or "").strip()
    env_value = str(os.environ.get(env_key, "")).strip()

    for raw in (explicit, env_value):
        if not raw:
            continue
        found = shutil.which(raw)
        if found:
            return str(Path(found).resolve())
        path = Path(raw).expanduser()
        if path.exists():
            return str(path.resolve())

    for path in candidates:
        resolved = Path(path).expanduser()
        if resolved.exists():
            return str(resolved.resolve())

    return None


def _resolve_file(value: Any, env_key: str, candidates: list[Path] | None = None) -> str | None:
    candidates = list(candidates or [])
    explicit = _as_path(value)
    env_value = _as_path(os.environ.get(env_key, ""))

    for path in (explicit, env_value):
        if path is not None and path.exists():
            return str(path.resolve())

    for path in candidates:
        resolved = Path(path).expanduser()
        if resolved.exists():
            return str(resolved.resolve())

    return None


def _run_install_action(command: str, cwd: Path | None, settings: ToolchainSettings) -> tuple[bool, str]:
    display = command if cwd is None else f"(cd {cwd} && {command})"
    if settings.show_commands:
        print(f"$ {display}")
    if settings.dry_run:
        return True, display
    proc = subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        shell=True,
        executable="/bin/bash",
    )
    return proc.returncode == 0, display


def _git_clone_or_fetch(repo_url: str, dest: Path, ref: str) -> str:
    clone = (
        f"if [ ! -d {shlex_quote(dest)} ]; then "
        f"git clone {shlex_quote(repo_url)} {shlex_quote(dest)}; "
        "fi"
    )
    checkout = ""
    if ref:
        checkout = (
            f" && cd {shlex_quote(dest)}"
            f" && git fetch --all --tags"
            f" && git checkout {shlex_quote(ref)}"
        )
    return clone + checkout


def shlex_quote(value: Path | str) -> str:
    raw = str(value)
    return "'" + raw.replace("'", "'\"'\"'") + "'"


def _qemu_install_plan() -> list[tuple[str, Path | None]]:
    return [
        ("sudo apt-get update", None),
        ("sudo apt-get install -y qemu-user gcc-riscv64-linux-gnu", None),
    ]


def _spike_install_plan(settings: ToolchainSettings) -> list[tuple[str, Path | None]]:
    root = settings.root_dir.resolve()
    src_root = root / "src"
    install_root = root / "opt" / "riscv"
    spike_src = src_root / "riscv-isa-sim"
    pk_src = src_root / "riscv-pk"
    spike_ref = settings.spike_ref.strip()
    pk_ref = settings.pk_ref.strip()
    return [
        ("sudo apt-get update", None),
        (
            "sudo apt-get install -y "
            "git build-essential device-tree-compiler "
            "libboost-regex-dev libboost-system-dev libboost-filesystem-dev "
            "libexpat1-dev zlib1g-dev gcc-riscv64-unknown-elf",
            None,
        ),
        (f"mkdir -p {shlex_quote(src_root)} {shlex_quote(install_root)}", None),
        (_git_clone_or_fetch("https://github.com/riscv-software-src/riscv-isa-sim.git", spike_src, spike_ref), None),
        (f"mkdir -p build && ../configure --prefix={shlex_quote(install_root)} && make -j\"$(nproc)\" && make install", spike_src),
        (_git_clone_or_fetch("https://github.com/riscv-software-src/riscv-pk.git", pk_src, pk_ref), None),
        (
            "mkdir -p build"
            f" && ../configure --prefix={shlex_quote(install_root)} --host=riscv64-unknown-elf"
            " && make -j\"$(nproc)\" && make install",
            pk_src,
        ),
    ]


def _gem5_install_plan(settings: ToolchainSettings) -> list[tuple[str, Path | None]]:
    root = settings.root_dir.resolve()
    src_root = root / "src"
    gem5_src = src_root / "gem5"
    gem5_ref = settings.gem5_ref.strip()
    return [
        ("sudo apt-get update", None),
        (
            "sudo apt-get install -y "
            "git build-essential scons m4 zlib1g zlib1g-dev "
            "libprotobuf-dev protobuf-compiler libprotoc-dev "
            "libgoogle-perftools-dev python3-dev pkg-config "
            "libboost-all-dev gcc-riscv64-linux-gnu",
            None,
        ),
        (f"mkdir -p {shlex_quote(src_root)}", None),
        (_git_clone_or_fetch("https://github.com/gem5/gem5.git", gem5_src, gem5_ref), None),
        ("scons build/RISCV/gem5.opt -j\"$(nproc)\"", gem5_src),
    ]


def _install_backend(target_name: str, settings: ToolchainSettings) -> tuple[list[str], list[str]]:
    if target_name == "qemu":
        plan = _qemu_install_plan()
    elif target_name == "spike":
        plan = _spike_install_plan(settings)
    elif target_name == "gem5":
        plan = _gem5_install_plan(settings)
    else:
        return [], []

    actions: list[str] = []
    errors: list[str] = []
    for command, cwd in plan:
        ok, display = _run_install_action(command, cwd, settings)
        actions.append(display)
        if not ok:
            errors.append(f"tool install step failed: {display}")
            break
    return actions, errors


def _resolve_qemu(args: dict[str, Any], settings: ToolchainSettings) -> ToolchainResult:
    updated = dict(args)
    errors: list[str] = []
    actions: list[str] = []
    qemu_candidates = [
        settings.root_dir / "bin" / "qemu-riscv64",
        Path("/usr/bin/qemu-riscv64"),
        Path("/usr/local/bin/qemu-riscv64"),
    ]
    cc_candidates = [
        settings.root_dir / "bin" / "riscv64-linux-gnu-gcc",
        Path("/usr/bin/riscv64-linux-gnu-gcc"),
        Path("/usr/local/bin/riscv64-linux-gnu-gcc"),
    ]

    updated["qemu_bin"] = _resolve_executable(updated.get("qemu_bin"), "QEMU_BIN", qemu_candidates) or updated.get("qemu_bin")
    updated["qemu_cc"] = _resolve_executable(updated.get("qemu_cc"), "QEMU_CC", cc_candidates) or updated.get("qemu_cc")

    missing = []
    if _resolve_executable(updated.get("qemu_bin"), "QEMU_BIN", qemu_candidates) is None:
        missing.append("qemu")
    if _resolve_executable(updated.get("qemu_cc"), "QEMU_CC", cc_candidates) is None:
        missing.append("qemu_cc")

    if missing and settings.auto_install:
        actions, errors = _install_backend("qemu", settings)
        updated["qemu_bin"] = _resolve_executable(updated.get("qemu_bin"), "QEMU_BIN", qemu_candidates) or updated.get("qemu_bin")
        updated["qemu_cc"] = _resolve_executable(updated.get("qemu_cc"), "QEMU_CC", cc_candidates) or updated.get("qemu_cc")
        missing = []
        if _resolve_executable(updated.get("qemu_bin"), "QEMU_BIN", qemu_candidates) is None:
            missing.append("qemu")
        if _resolve_executable(updated.get("qemu_cc"), "QEMU_CC", cc_candidates) is None:
            missing.append("qemu_cc")

    if missing and not errors:
        errors = [f"missing qemu toolchain pieces: {', '.join(missing)}"]
    return ToolchainResult(updated, errors, actions)


def _resolve_spike(args: dict[str, Any], settings: ToolchainSettings) -> ToolchainResult:
    updated = dict(args)
    errors: list[str] = []
    actions: list[str] = []
    riscv_roots = _common_riscv_roots(settings)
    spike_candidates = [root / "bin" / "spike" for root in riscv_roots]
    spike_cc_candidates = [root / "bin" / "riscv64-unknown-elf-gcc" for root in riscv_roots]
    pk_candidates: list[Path] = []
    for root in riscv_roots:
        pk_candidates.extend(
            [
                root / "riscv64-unknown-elf" / "bin" / "pk",
                root / "bin" / "pk",
            ]
        )

    updated["spike_bin"] = _resolve_executable(updated.get("spike_bin"), "SPIKE_BIN", spike_candidates) or updated.get("spike_bin")
    updated["spike_cc"] = _resolve_executable(updated.get("spike_cc"), "SPIKE_CC", spike_cc_candidates) or updated.get("spike_cc")
    updated["pk"] = _resolve_file(updated.get("pk"), "PK", pk_candidates) or updated.get("pk")

    missing = []
    if _resolve_executable(updated.get("spike_bin"), "SPIKE_BIN", spike_candidates) is None:
        missing.append("spike")
    if _resolve_executable(updated.get("spike_cc"), "SPIKE_CC", spike_cc_candidates) is None:
        missing.append("spike_cc")
    if _resolve_file(updated.get("pk"), "PK", pk_candidates) is None:
        missing.append("pk")

    if missing and settings.auto_install:
        actions, errors = _install_backend("spike", settings)
        updated["spike_bin"] = _resolve_executable(updated.get("spike_bin"), "SPIKE_BIN", spike_candidates) or updated.get("spike_bin")
        updated["spike_cc"] = _resolve_executable(updated.get("spike_cc"), "SPIKE_CC", spike_cc_candidates) or updated.get("spike_cc")
        updated["pk"] = _resolve_file(updated.get("pk"), "PK", pk_candidates) or updated.get("pk")
        missing = []
        if _resolve_executable(updated.get("spike_bin"), "SPIKE_BIN", spike_candidates) is None:
            missing.append("spike")
        if _resolve_executable(updated.get("spike_cc"), "SPIKE_CC", spike_cc_candidates) is None:
            missing.append("spike_cc")
        if _resolve_file(updated.get("pk"), "PK", pk_candidates) is None:
            missing.append("pk")

    if missing and not errors:
        errors = [f"missing spike toolchain pieces: {', '.join(missing)}"]
    return ToolchainResult(updated, errors, actions)


def _resolve_gem5(args: dict[str, Any], settings: ToolchainSettings) -> ToolchainResult:
    updated = dict(args)
    errors: list[str] = []
    actions: list[str] = []
    gem5_root_candidates = _common_gem5_roots(settings)
    gem5_bin_candidates = [root / "build" / "RISCV" / "gem5.opt" for root in gem5_root_candidates]
    gem5_cc_candidates = [
        settings.root_dir / "bin" / "riscv64-linux-gnu-gcc",
        Path("/usr/bin/riscv64-linux-gnu-gcc"),
        Path("/usr/local/bin/riscv64-linux-gnu-gcc"),
    ]

    updated["gem5_bin"] = _resolve_executable(updated.get("gem5_bin"), "GEM5_BIN", gem5_bin_candidates) or updated.get("gem5_bin")
    updated["gem5_cc"] = _resolve_executable(updated.get("gem5_cc"), "GEM5_CC", gem5_cc_candidates) or updated.get("gem5_cc")
    gem5_root = _resolve_file(updated.get("gem5_root"), "GEM5_ROOT", gem5_root_candidates)
    if gem5_root:
        updated["gem5_root"] = gem5_root
    else:
        gem5_bin_path = _as_path(updated.get("gem5_bin"))
        if gem5_bin_path is not None and gem5_bin_path.exists():
            updated["gem5_root"] = str(gem5_bin_path.resolve().parent.parent.parent)

    missing = []
    if _resolve_executable(updated.get("gem5_bin"), "GEM5_BIN", gem5_bin_candidates) is None:
        missing.append("gem5")
    if _resolve_executable(updated.get("gem5_cc"), "GEM5_CC", gem5_cc_candidates) is None:
        missing.append("gem5_cc")
    if not str(updated.get("gem5_root", "")).strip():
        missing.append("gem5_root")

    if missing and settings.auto_install:
        actions, errors = _install_backend("gem5", settings)
        updated["gem5_bin"] = _resolve_executable(updated.get("gem5_bin"), "GEM5_BIN", gem5_bin_candidates) or updated.get("gem5_bin")
        updated["gem5_cc"] = _resolve_executable(updated.get("gem5_cc"), "GEM5_CC", gem5_cc_candidates) or updated.get("gem5_cc")
        gem5_root = _resolve_file(updated.get("gem5_root"), "GEM5_ROOT", gem5_root_candidates)
        if gem5_root:
            updated["gem5_root"] = gem5_root
        elif _resolve_executable(updated.get("gem5_bin"), "GEM5_BIN", gem5_bin_candidates):
            updated["gem5_root"] = str((settings.root_dir / "src" / "gem5").resolve())
        missing = []
        if _resolve_executable(updated.get("gem5_bin"), "GEM5_BIN", gem5_bin_candidates) is None:
            missing.append("gem5")
        if _resolve_executable(updated.get("gem5_cc"), "GEM5_CC", gem5_cc_candidates) is None:
            missing.append("gem5_cc")
        if not str(updated.get("gem5_root", "")).strip():
            missing.append("gem5_root")

    if missing and not errors:
        errors = [f"missing gem5 toolchain pieces: {', '.join(missing)}"]
    return ToolchainResult(updated, errors, actions)


def prepare_backend_toolchain(
    target_name: str,
    merged_args: dict[str, Any],
    settings: ToolchainSettings,
) -> ToolchainResult:
    if target_name == "qemu":
        return _resolve_qemu(merged_args, settings)
    if target_name == "spike":
        return _resolve_spike(merged_args, settings)
    if target_name == "gem5":
        return _resolve_gem5(merged_args, settings)
    return ToolchainResult(dict(merged_args), [], [])
