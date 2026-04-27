#!/usr/bin/env python3
"""IEEE-style workload visualization for Tenstorrent TT runs.

Generates four publication-ready figures from run_summary.json data:
  fig1_tt_residency.pdf  — TT-Wormhole hardware residency breakdown
  fig2_sit_scaling.pdf   — QEMU SIT vs tile count (scaling analysis)
  fig3_qemu_vs_tt.pdf    — QEMU vs TT-Wormhole SIT comparison
  fig4_ops_per_zone.pdf  — Ops-per-zone compute intensity reference

Usage:
  python tools/tt_ieee_plots.py [--outdir PATH]
"""
from __future__ import annotations

import argparse
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ── IEEE single/double column dimensions ──────────────────────────────────────
COL1 = (3.5, 2.4)   # single column
COL2 = (7.16, 2.6)  # double column

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "savefig.dpi": 300,
    "axes.linewidth": 0.8,
    "grid.linewidth": 0.4,
    "lines.linewidth": 1.4,
    "patch.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

SCRIPT_DIR = pathlib.Path(__file__).parent
BUNDLE_ROOT = SCRIPT_DIR.parent

OPS_PER_ZONE: dict[str, int] = {
    "eltwise_sfpu":          1024,
    "custom_sfpi_add":       1024,
    "eltwise_binary":        1024,
    "custom_sfpi_smoothstep": 6144,
    "sfpu_chain":            3072,
    "matmul_single":        65536,
}

WORKLOAD_LABEL: dict[str, str] = {
    "custom_sfpi_add":        "SFPI Add",
    "custom_sfpi_smoothstep": "SFPI Smoothstep",
    "eltwise_binary":         "Eltwise Binary",
    "eltwise_sfpu":           "Eltwise SFPU",
    "loopback":               "Loopback",
    "matmul_multi":           "MatMul Multi",
    "matmul_single":          "MatMul Single",
    "noc_transfer":           "NOC Transfer",
    "sfpu_chain":             "SFPU Chain",
    "vecadd":                 "VecAdd",
    "matmul_multicore":       "MatMul (mc)",
    "tt_matmul_multi":        "MatMul Multi*",
}

TILE_SIZES  = ["tt_1tile", "tt_4tile", "tt_64tile", "tt_256tile", "tt_1024tile"]
TILE_COUNTS = [1, 4, 64, 256, 1024]

PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
           "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]


# ── data loading ──────────────────────────────────────────────────────────────

def load_adapter(adapter: str) -> dict[str, dict[str, dict]]:
    root = BUNDLE_ROOT / "runs" / adapter
    if not root.exists():
        return {}
    data: dict[str, dict[str, dict]] = {}
    for wdir in sorted(root.iterdir()):
        if not wdir.is_dir():
            continue
        for sdir in sorted(wdir.iterdir()):
            p = sdir / "run_summary.json"
            if p.exists():
                data.setdefault(wdir.name, {})[sdir.name] = json.loads(p.read_text())
    return data


# ── figure helpers ─────────────────────────────────────────────────────────────

def _save(fig: plt.Figure, outdir: pathlib.Path, stem: str) -> pathlib.Path:
    pdf = outdir / f"{stem}.pdf"
    png = outdir / f"{stem}.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, bbox_inches="tight", dpi=300)
    plt.close(fig)
    return pdf


def _residency_triple(summary: dict) -> tuple[float, float, float]:
    a = float(summary.get("residency_active_avg", 0.0))
    s = float(summary.get("residency_stall_avg", 0.0))
    i = float(summary.get("residency_idle_avg", 0.0))
    total = a + s + i
    if total <= 0:
        return 0.0, 0.0, 0.0
    return a / total, s / total, i / total


# ── Figure 1: TT-Wormhole hardware residency breakdown ────────────────────────

def fig_tt_residency(tt: dict[str, dict[str, dict]], outdir: pathlib.Path) -> pathlib.Path:
    SIZE = "tt_64tile"
    rows = []
    for w, sizes in tt.items():
        size = SIZE if SIZE in sizes else next(iter(sizes), None)
        if size is None:
            continue
        d = sizes[size]
        a, s, i = _residency_triple(d)
        sit = float(d.get("sit_median", float("nan")))
        rows.append((WORKLOAD_LABEL.get(w, w), a, s, i, sit))

    rows.sort(key=lambda r: r[1])  # sort by active fraction ascending

    labels = [r[0] for r in rows]
    actives = np.array([r[1] * 100 for r in rows])
    stalls  = np.array([r[2] * 100 for r in rows])
    idles   = np.array([r[3] * 100 for r in rows])
    sits    = np.array([r[4] for r in rows])

    fig, (ax_bar, ax_sit) = plt.subplots(
        1, 2, figsize=(7.16, 0.45 * len(rows) + 0.9),
        gridspec_kw={"width_ratios": [3, 1]},
    )

    y = np.arange(len(rows))
    bh = 0.6
    ax_bar.barh(y, actives, height=bh, color="#2ca02c", label="Active")
    ax_bar.barh(y, stalls,  height=bh, left=actives, color="#ff7f0e", label="Stall")
    ax_bar.barh(y, idles,   height=bh, left=actives + stalls, color="#aec7e8", label="Idle")
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(labels)
    ax_bar.set_xlabel("Residency (%)")
    ax_bar.set_xlim(0, 102)
    ax_bar.grid(axis="x", linestyle="--", alpha=0.35)
    ax_bar.legend(frameon=False, loc="lower right", ncol=3, fontsize=7.5)

    valid = np.isfinite(sits)
    ax_sit.barh(y[valid], sits[valid], height=bh, color="#1f77b4")
    ax_sit.set_yticks(y)
    ax_sit.set_yticklabels([])
    ax_sit.set_xlabel("SIT Median")
    ax_sit.set_xlim(0, 1.05)
    ax_sit.grid(axis="x", linestyle="--", alpha=0.35)

    fig.suptitle("TT-Wormhole Workload Residency and SIT (64 Tiles)", y=1.01, fontsize=9)
    fig.tight_layout(pad=0.5)
    return _save(fig, outdir, "fig1_tt_residency")


# ── Figure 2: QEMU SIT scaling with tile count ────────────────────────────────

def fig_sit_scaling(qemu: dict[str, dict[str, dict]], outdir: pathlib.Path) -> pathlib.Path:
    fig, ax = plt.subplots(figsize=COL1)

    workloads = [w for w in qemu if any(s in qemu[w] for s in TILE_SIZES)]
    for idx, w in enumerate(sorted(workloads)):
        xs, ys = [], []
        for tc, size in zip(TILE_COUNTS, TILE_SIZES):
            if size in qemu[w]:
                xs.append(tc)
                ys.append(qemu[w][size]["sit_median"])
        if xs:
            ax.semilogx(xs, ys, marker="o", markersize=3.5,
                        color=PALETTE[idx % len(PALETTE)],
                        label=WORKLOAD_LABEL.get(w, w))

    ax.set_xlabel("Tile Count")
    ax.set_ylabel("SIT Median")
    ax.set_xticks(TILE_COUNTS)
    ax.get_xaxis().set_major_formatter(ticker.ScalarFormatter())
    ax.set_ylim(0.998, 1.0005)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.4f"))
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout(pad=0.4)
    return _save(fig, outdir, "fig2_sit_scaling")


# ── Figure 3: QEMU vs TT-Wormhole stall fraction comparison ──────────────────

def fig_qemu_vs_tt(qemu: dict, tt: dict, outdir: pathlib.Path) -> pathlib.Path:
    """Stall fraction comparison: reveals simulator fidelity gap."""
    SIZE = "tt_64tile"
    common = sorted(set(qemu) & set(tt))

    rows = []
    for w in common:
        qs = qemu[w].get(SIZE) or qemu[w].get(next(iter(qemu[w]), ""), {})
        ts = tt[w].get(SIZE)   or tt[w].get(next(iter(tt[w]),   ""), {})
        q_stall = float(qs.get("residency_stall_avg", float("nan"))) * 100 if qs else float("nan")
        t_stall = float(ts.get("residency_stall_avg", float("nan"))) * 100 if ts else float("nan")
        if np.isfinite(q_stall) and np.isfinite(t_stall):
            rows.append((WORKLOAD_LABEL.get(w, w), q_stall, t_stall))

    if not rows:
        return outdir / "fig3_qemu_vs_tt.pdf"

    rows.sort(key=lambda r: r[2], reverse=True)
    labels      = [r[0] for r in rows]
    qemu_stalls = np.array([r[1] for r in rows])
    tt_stalls   = np.array([r[2] for r in rows])

    x  = np.arange(len(labels))
    bw = 0.35
    fig, ax = plt.subplots(figsize=COL2)
    ax.bar(x - bw / 2, qemu_stalls, width=bw, label="QEMU",        color="#1f77b4")
    ax.bar(x + bw / 2, tt_stalls,   width=bw, label="TT-Wormhole", color="#d62728")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Stall Fraction (%)")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend(frameon=False)
    fig.tight_layout(pad=0.4)
    return _save(fig, outdir, "fig3_qemu_vs_tt")


# ── Figure 4: Ops-per-zone compute intensity reference ───────────────────────

def fig_ops_per_zone(outdir: pathlib.Path) -> pathlib.Path:
    items   = sorted(OPS_PER_ZONE.items(), key=lambda kv: kv[1])
    labels  = [WORKLOAD_LABEL.get(k, k) for k, _ in items]
    values  = [v for _, v in items]

    fig, ax = plt.subplots(figsize=COL1)
    y   = np.arange(len(labels))
    bh  = 0.55
    bars = ax.barh(y, values, height=bh, color=PALETTE[:len(labels)])
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() * 1.02, bar.get_y() + bar.get_height() / 2,
                f"{v:,}", va="center", ha="left", fontsize=7.5)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Ops per Zone (--tt-ops-per-zone)")
    ax.set_xlim(0, max(values) * 1.3)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    fig.tight_layout(pad=0.4)
    return _save(fig, outdir, "fig4_ops_per_zone")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Generate IEEE-style TT workload plots.")
    ap.add_argument("--outdir", default=None, help="Output directory (default: results/ieee_plots)")
    args = ap.parse_args()

    outdir = pathlib.Path(args.outdir).resolve() if args.outdir else (BUNDLE_ROOT / "results" / "ieee_plots")
    outdir.mkdir(parents=True, exist_ok=True)

    qemu = load_adapter("qemu")
    tt   = load_adapter("tt_wormhole")

    p1 = fig_tt_residency(tt,           outdir)
    p2 = fig_sit_scaling(qemu,          outdir)
    p3 = fig_qemu_vs_tt(qemu, tt,       outdir)
    p4 = fig_ops_per_zone(              outdir)

    print(f"fig1 TT residency:    {p1}")
    print(f"fig2 SIT scaling:     {p2}")
    print(f"fig3 QEMU vs TT SIT:  {p3}")
    print(f"fig4 ops/zone:        {p4}")
    print(f"\nAll figures written to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
