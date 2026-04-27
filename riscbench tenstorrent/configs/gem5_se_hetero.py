#!/usr/bin/env python3
"""
Phase-2 gem5 SE config with heterogeneous per-CPU type support.

Use this only when a run needs different gem5 CPU models across CPUs, e.g.
`--phase2-cpu-types=TimingSimpleCPU,MinorCPU`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import m5
from m5.objects import *
from m5.util import addToPath, fatal

from gem5.isas import ISA

_bootstrap = argparse.ArgumentParser(add_help=False)
_bootstrap.add_argument("--phase2-base-se-script", required=True)
_bootstrap_args, _ = _bootstrap.parse_known_args(sys.argv[1:])
_base_se_script = Path(_bootstrap_args.phase2_base_se_script).expanduser().resolve()
if not _base_se_script.exists():
    raise SystemExit(f"Base gem5 se.py not found: {_base_se_script}")

_configs_root = _base_se_script.parents[2]
if str(_configs_root) not in sys.path:
    sys.path.insert(0, str(_configs_root))
addToPath(str(_configs_root))

from common import CacheConfig, MemConfig, ObjectList, Options, Simulation
from common.FileSystemConfig import config_filesystem
from ruby import Ruby


def get_processes(args):
    multiprocesses = []
    inputs = []
    outputs = []
    errouts = []
    pargs = []

    workloads = args.cmd.split(";")
    if args.input != "":
        inputs = args.input.split(";")
    if args.output != "":
        outputs = args.output.split(";")
    if args.errout != "":
        errouts = args.errout.split(";")
    if args.options != "":
        pargs = args.options.split(";")

    idx = 0
    for wrkld in workloads:
        process = Process(pid=100 + idx)
        process.executable = wrkld
        process.cwd = os.getcwd()
        process.gid = os.getgid()

        if args.env:
            with open(args.env, "r", encoding="utf-8") as f:
                process.env = [line.rstrip() for line in f]

        if len(pargs) > idx:
            process.cmd = [wrkld] + pargs[idx].split()
        else:
            process.cmd = [wrkld]

        if len(inputs) > idx:
            process.input = inputs[idx]
        if len(outputs) > idx:
            process.output = outputs[idx]
        if len(errouts) > idx:
            process.errout = errouts[idx]

        multiprocesses.append(process)
        idx += 1

    if args.smt:
        fatal("Phase-2 heterogeneous config does not support SMT")

    return multiprocesses, 1


def parse_phase2_cpu_types(spec: str, num_cpus: int, options):
    cpu_type_names = [tok.strip() for tok in str(spec).split(",") if tok.strip()]
    if not cpu_type_names:
        fatal("--phase2-cpu-types must contain at least one CPU type")
    if len(cpu_type_names) != num_cpus:
        fatal(
            "--phase2-cpu-types count (%d) must match --num-cpus (%d)",
            len(cpu_type_names),
            num_cpus,
        )

    cpu_classes = []
    mem_mode = None
    isa = None
    for cpu_type in cpu_type_names:
        cpu_cls = ObjectList.cpu_list.get(cpu_type)
        cpu_mem_mode = cpu_cls.memory_mode()
        cpu_isa = ObjectList.cpu_list.get_isa(cpu_type)

        if cpu_isa != ISA.RISCV:
            fatal(
                "Phase-2 heterogeneous SE config currently supports only RISC-V CPU types; got %s (%s)",
                cpu_type,
                cpu_isa,
            )

        if mem_mode is None:
            mem_mode = cpu_mem_mode
            isa = cpu_isa
        else:
            if cpu_mem_mode != mem_mode:
                fatal(
                    "All --phase2-cpu-types must share the same memory mode; saw %s then %s",
                    mem_mode,
                    cpu_mem_mode,
                )
            if cpu_isa != isa:
                fatal(
                    "All --phase2-cpu-types must share the same ISA; saw %s then %s",
                    isa,
                    cpu_isa,
                )

        if cpu_cls.require_caches() and not options.caches and not options.ruby:
            fatal("%s must be used with caches", cpu_type)

        if ObjectList.is_kvm_cpu(cpu_cls):
            fatal("Phase-2 heterogeneous SE config does not support KVM CPUs")

        cpu_classes.append(cpu_cls)

    return cpu_type_names, cpu_classes, mem_mode


def reject_unsupported_options(args):
    if args.fast_forward:
        fatal("Phase-2 heterogeneous SE config does not support --fast-forward")
    if args.checkpoint_restore is not None:
        fatal("Phase-2 heterogeneous SE config does not support --checkpoint-restore")
    if args.repeat_switch:
        fatal("Phase-2 heterogeneous SE config does not support --repeat-switch")
    if args.standard_switch:
        fatal("Phase-2 heterogeneous SE config does not support --standard-switch")
    if args.elastic_trace_en:
        fatal("Phase-2 heterogeneous SE config does not support elastic tracing")
    if args.simpoint_profile:
        fatal("Phase-2 heterogeneous SE config does not support SimPoint profiling")


parser = argparse.ArgumentParser()
Options.addCommonOptions(parser)
Options.addSEOptions(parser)
parser.add_argument(
    "--phase2-cpu-types",
    required=True,
    help="Comma-separated per-CPU gem5 CPU types, e.g. TimingSimpleCPU,MinorCPU",
)
parser.add_argument(
    "--phase2-base-se-script",
    required=True,
    help="Path to the real gem5 se.py used to bootstrap gem5 config imports",
)

if "--ruby" in sys.argv:
    Ruby.define_options(parser)

args = parser.parse_args()
reject_unsupported_options(args)

if not args.cmd:
    fatal("Phase-2 heterogeneous SE config requires --cmd")

multiprocesses, num_threads = get_processes(args)
if num_threads > 1:
    fatal("Phase-2 heterogeneous SE config does not support SMT-style threads")

cpu_type_names, cpu_classes, test_mem_mode = parse_phase2_cpu_types(
    args.phase2_cpu_types,
    args.num_cpus,
    args,
)
args.cpu_type = cpu_type_names[0]

np = args.num_cpus
if len(multiprocesses) not in (1, np):
    fatal(
        "Workload count (%d) must be 1 or equal to --num-cpus (%d)",
        len(multiprocesses),
        np,
    )

mp0_path = multiprocesses[0].executable
system = System(
    cpu=[cpu_classes[i](cpu_id=i) for i in range(np)],
    mem_mode=test_mem_mode,
    mem_ranges=[AddrRange(args.mem_size)],
    cache_line_size=args.cacheline_size,
)

system.voltage_domain = VoltageDomain(voltage=args.sys_voltage)
system.clk_domain = SrcClockDomain(
    clock=args.sys_clock, voltage_domain=system.voltage_domain
)
system.cpu_voltage_domain = VoltageDomain()
system.cpu_clk_domain = SrcClockDomain(
    clock=args.cpu_clock, voltage_domain=system.cpu_voltage_domain
)

for cpu in system.cpu:
    cpu.clk_domain = system.cpu_clk_domain

for i in range(np):
    if len(multiprocesses) == 1:
        system.cpu[i].workload = multiprocesses[0]
    else:
        system.cpu[i].workload = multiprocesses[i]

    if args.checker:
        system.cpu[i].addCheckerCpu()

    if args.bp_type:
        bp_class = ObjectList.bp_list.get(args.bp_type)
        system.cpu[i].branchPred = bp_class()

    if args.indirect_bp_type:
        indirect_bp_class = ObjectList.indirect_bp_list.get(args.indirect_bp_type)
        system.cpu[i].branchPred.indirectBranchPred = indirect_bp_class()

    system.cpu[i].createThreads()

if args.ruby:
    Ruby.create_system(args, False, system)
    assert args.num_cpus == len(system.ruby._cpu_ports)

    system.ruby.clk_domain = SrcClockDomain(
        clock=args.ruby_clock, voltage_domain=system.voltage_domain
    )
    for i in range(np):
        ruby_port = system.ruby._cpu_ports[i]
        system.cpu[i].createInterruptController()
        ruby_port.connectCpuPorts(system.cpu[i])
else:
    MemClass = Simulation.setMemClass(args)
    system.membus = SystemXBar()
    system.system_port = system.membus.cpu_side_ports
    CacheConfig.config_cache(args, system)
    MemConfig.config_mem(args, system)
    config_filesystem(system, args)

system.workload = SEWorkload.init_compatible(mp0_path)
if args.wait_gdb:
    system.workload.wait_for_remote_gdb = True

root = Root(full_system=False, system=system)
Simulation.run(args, root, system, None)
