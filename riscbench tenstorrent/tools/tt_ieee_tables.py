#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

TT_MATMUL_SIZE_RE = re.compile(r"^tt_m(\d+)_n(\d+)_k(\d+)$")
TT_TILE_SIZE_RE = re.compile(r"^tt_(\d+)tile$")

WORKLOAD_LABELS = {
    "tt_matmul_single": "MatMul Single",
    "tt_matmul_multi": "MatMul Multi",
    "tt_sfpu_chain": "SFPU Chain",
    "tt_eltwise_sfpu": "Eltwise SFPU",
    "tt_eltwise_binary": "Eltwise Binary",
    "tt_custom_sfpi_add": "SFPI Add",
    "tt_custom_sfpi_smoothstep": "SFPI Smoothstep",
}

FULL_TABLE_ORDER = [
    "tt_matmul_single",
    "tt_matmul_multi",
    "tt_sfpu_chain",
    "tt_eltwise_sfpu",
    "tt_eltwise_binary",
    "tt_custom_sfpi_add",
    "tt_custom_sfpi_smoothstep",
]


def parse_float(value: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return float("nan")


def case_sort_key(size: str) -> tuple[int, int]:
    raw = str(size).strip()
    match = TT_MATMUL_SIZE_RE.match(raw)
    if match:
        return (0, int(match.group(1)))
    match = TT_TILE_SIZE_RE.match(raw)
    if match:
        return (1, int(match.group(1)))
    if raw == "tt_1tile":
        return (2, 1)
    return (9, 0)


def workload_sort_key(name: str) -> tuple[int, str]:
    if name in FULL_TABLE_ORDER:
        return (FULL_TABLE_ORDER.index(name), name)
    return (len(FULL_TABLE_ORDER), name)


def pretty_case(workload_size: str) -> str:
    raw = str(workload_size).strip()
    match = TT_MATMUL_SIZE_RE.match(raw)
    if match:
        return f"M{match.group(1)}"
    match = TT_TILE_SIZE_RE.match(raw)
    if match:
        return f"{match.group(1)}t"
    if raw == "tt_1tile":
        return "1t"
    return raw


def pretty_workload(workload: str) -> str:
    return WORKLOAD_LABELS.get(workload, workload.replace("tt_", "").replace("_", " ").title())


def tex_escape(text: str) -> str:
    return (
        str(text)
        .replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace("#", "\\#")
    )


def fmt_value(value: float, digits: int = 1) -> str:
    if value != value:
        return "--"
    return f"{value:.{digits}f}"


def fmt_ratio(value: float) -> str:
    if value != value:
        return "--"
    return f"{value:.3f}"


def fmt_pct(value: float) -> str:
    if value != value:
        return "--"
    return f"{100.0 * value:.1f}"


def load_rows(metrics_csv: Path) -> list[dict]:
    with metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "workload": str(row.get("workload", "")).strip(),
                    "workload_size": str(row.get("workload_size", "")).strip(),
                    "case": pretty_case(row.get("workload_size", "")),
                    "observed": parse_float(row.get("observed_flops_per_us", "")),
                    "expected": parse_float(row.get("expected_work_rate", "")),
                    "obs_exp": parse_float(row.get("observed_vs_expected", "")),
                    "sit": parse_float(row.get("sit_median", "")),
                    "active": parse_float(row.get("active", "")),
                    "stall": parse_float(row.get("stall", "")),
                    "idle": parse_float(row.get("idle", "")),
                    "res_win": parse_float(row.get("resident_windows", "")),
                }
            )
    rows.sort(key=lambda row: (workload_sort_key(row["workload"]), case_sort_key(row["workload_size"])))
    return rows


def build_table_block(rows: list[dict], *, caption: str, label: str, wide: bool) -> str:
    env = "table*" if wide else "table"
    lines = [
        f"\\begin{{{env}}}[t]",
        "\\caption{" + caption + "}",
        "\\label{" + label + "}",
        "\\centering",
        "\\footnotesize",
        "\\setlength{\\tabcolsep}{4pt}",
        "\\renewcommand{\\arraystretch}{1.08}",
        "\\begin{tabular}{llrrrrrr}",
        "\\toprule",
        "Workload & Case & Obs. & Exp. & Obs./Exp. & SIT & Active (\\%) & Stall (\\%) \\\\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(
            "{} & {} & {} & {} & {} & {} & {} & {} \\\\".format(
                tex_escape(pretty_workload(row["workload"])),
                tex_escape(row["case"]),
                fmt_value(row["observed"], 1),
                fmt_value(row["expected"], 1),
                fmt_ratio(row["obs_exp"]),
                fmt_ratio(row["sit"]),
                fmt_pct(row["active"]),
                fmt_pct(row["stall"]),
            )
        )
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{" + env + "}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_full_table(rows: list[dict]) -> str:
    return build_table_block(
        rows,
        caption="Tenstorrent TT sweep summary using formula-based expected work rate and kernel-envelope residency.",
        label="tab:tt_full_sweep_summary",
        wide=True,
    )


def build_tile_table(rows: list[dict]) -> str:
    tile_rows = [row for row in rows if row["workload"] in {
        "tt_sfpu_chain",
        "tt_eltwise_sfpu",
        "tt_eltwise_binary",
        "tt_custom_sfpi_add",
        "tt_custom_sfpi_smoothstep",
    }]
    return build_table_block(
        tile_rows,
        caption="Tile-oriented TT workloads. Cases are grouped by workload and tile count.",
        label="tab:tt_tile_workloads",
        wide=False,
    )


def build_matmul_table(rows: list[dict]) -> str:
    matmul_rows = [row for row in rows if row["workload"] in {"tt_matmul_single", "tt_matmul_multi"}]
    return build_table_block(
        matmul_rows,
        caption="TT matmul sweeps across square matrix sizes.",
        label="tab:tt_matmul_workloads",
        wide=False,
    )


def build_adapter_classification_table() -> str:
    rows = [
        {
            "adapter": "Spike",
            "input": "Commit log",
            "time_base": "Committed instruction count $\\times$ inst\\_us",
            "residency": "Marker-driven; else PC threshold",
            "state_rules": "Control/nop/fence/CSR $\\rightarrow$ idle; loads/stores/atomics $\\rightarrow$ stall; else active",
            "granularity": "Per committed instruction",
        },
        {
            "adapter": "QEMU",
            "input": "Instruction trace / translated blocks",
            "time_base": "Executed TB count $\\times$ inst\\_us",
            "residency": "Marker-driven; else PC threshold",
            "state_rules": "TB summarized as idle/stall/active from contained instructions; markers override",
            "granularity": "Per executed translated block",
        },
        {
            "adapter": "gem5 Exec",
            "input": "Exec debug trace",
            "time_base": "Executed instruction count $\\times$ inst\\_us",
            "residency": "Marker-driven; else PC threshold",
            "state_rules": "Control-like ops $\\rightarrow$ idle; memory/atomics $\\rightarrow$ stall; else active",
            "granularity": "Per executed instruction",
        },
        {
            "adapter": "gem5 Stats",
            "input": "Periodic stats blocks",
            "time_base": "finalTick/simTicks scaled by simFreq",
            "residency": "Cache-locality and memory-pressure thresholds",
            "state_rules": "IPC threshold $\\rightarrow$ active; committed-inst threshold $\\rightarrow$ idle; miss/memory pressure $\\rightarrow$ stall",
            "granularity": "Per stats interval",
        },
    ]

    lines = [
        "\\begin{table*}[t]",
        "\\caption{Platform-specific simulator adapter classification rules used to derive residency and state intervals for SIT analysis.}",
        "\\label{tab:sim_adapter_classification}",
        "\\centering",
        "\\footnotesize",
        "\\setlength{\\tabcolsep}{3.5pt}",
        "\\renewcommand{\\arraystretch}{1.1}",
        "\\begin{tabular}{llllll}",
        "\\toprule",
        "Adapter & Input & Time Base & Residency Rule & State Rule & Granularity \\\\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(
            "{} & {} & {} & {} & {} & {} \\\\".format(
                tex_escape(row["adapter"]),
                tex_escape(row["input"]),
                row["time_base"],
                row["residency"],
                row["state_rules"],
                row["granularity"],
            )
        )
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table*}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate IEEE-style LaTeX tables from TT sweep metrics.")
    ap.add_argument("--metrics-csv", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--adapter-only", action="store_true")
    args = ap.parse_args()

    metrics_csv = Path(args.metrics_csv).expanduser().resolve() if args.metrics_csv else None
    if not args.adapter_only:
        if metrics_csv is None or not metrics_csv.exists():
            raise SystemExit(f"metrics csv not found: {metrics_csv}")
    if args.out_dir:
        out_dir = Path(args.out_dir).expanduser().resolve()
    elif metrics_csv is not None:
        out_dir = (metrics_csv.parent / "tables_ieee").resolve()
    else:
        out_dir = (Path(__file__).resolve().parents[1] / "results" / "tables_ieee").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    adapter_path = out_dir / "sim_adapter_classification.tex"
    adapter_path.write_text(build_adapter_classification_table(), encoding="utf-8")
    print(f"wrote tex: {adapter_path}")
    if not args.adapter_only:
        rows = load_rows(metrics_csv)
        full_path = out_dir / "tt_full_sweep_summary.tex"
        tile_path = out_dir / "tt_tile_workloads.tex"
        matmul_path = out_dir / "tt_matmul_workloads.tex"
        full_path.write_text(build_full_table(rows), encoding="utf-8")
        tile_path.write_text(build_tile_table(rows), encoding="utf-8")
        matmul_path.write_text(build_matmul_table(rows), encoding="utf-8")
        print(f"wrote tex: {full_path}")
        print(f"wrote tex: {tile_path}")
        print(f"wrote tex: {matmul_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
