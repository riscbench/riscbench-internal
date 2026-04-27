#!/usr/bin/env python3.9
"""
RISCBench IEEE figure generator — clean version.
No in-plot titles.  Legends placed outside axes.  Lines clearly distinguishable.
Output: ../results/ieee_plots/
"""

import json, math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
RUNS_DIR   = SCRIPT_DIR.parent / "runs"
OUT_DIR    = SCRIPT_DIR.parent / "results" / "ieee_plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── IEEE rcParams ─────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":        "serif",
    "font.serif":         ["Times New Roman", "DejaVu Serif"],
    "font.size":          8,
    "axes.labelsize":     8,
    "xtick.labelsize":    7,
    "ytick.labelsize":    7,
    "legend.fontsize":    7,
    "legend.framealpha":  0.95,
    "legend.edgecolor":   "0.7",
    "legend.borderpad":   0.4,
    "lines.linewidth":    1.8,
    "lines.markersize":   5,
    "axes.linewidth":     0.8,
    "axes.grid":          True,
    "axes.axisbelow":     True,
    "grid.linestyle":     "--",
    "grid.linewidth":     0.4,
    "grid.alpha":         0.5,
    "figure.dpi":         300,
    "savefig.dpi":        300,
    "savefig.bbox":       "tight",
    "savefig.pad_inches": 0.04,
    "pdf.fonttype":       42,
    "ps.fonttype":        42,
})

COL1 = 3.5
COL2 = 7.16

# Colourblind-safe palette (IBM / Wong 2011)
C_TT    = "#648FFF"
C_QEMU  = "#FE6100"
C_GEM5  = "#DC267F"
C_SPIKE = "#785EF0"
C_EXEC  = "#009E73"
C_STATS = "#E69F00"

PAL = {"TT Wormhole": C_TT, "QEMU": C_QEMU, "gem5": C_GEM5, "Spike": C_SPIKE}
HATCHES = {"TT Wormhole": "", "QEMU": "//", "gem5": "xx", "Spike": ".."}

# Distinct line styles for line plots
LINE_STYLES = {
    "TT Wormhole": (C_TT,    "-",  "o"),
    "QEMU":        (C_QEMU,  "--", "s"),
    "gem5":        (C_GEM5,  "-.", "^"),
    "Spike":       (C_SPIKE, ":",  "D"),
}

# ─── Data helpers ─────────────────────────────────────────────────────────────

def _nan(v):
    if v is None: return float("nan")
    if isinstance(v, float) and math.isnan(v): return float("nan")
    return v

def load_summary(p):
    raw = p.read_text().replace(": NaN", ": null")
    return json.loads(raw)

def collect_all_runs():
    rows = []
    for pl_dir in sorted(RUNS_DIR.iterdir()):
        if not pl_dir.is_dir(): continue
        for wl_dir in sorted(pl_dir.iterdir()):
            if not wl_dir.is_dir(): continue
            for cfg_dir in sorted(wl_dir.iterdir()):
                if not cfg_dir.is_dir(): continue
                sf = cfg_dir / "summary.json"
                mf = cfg_dir / "adapter_meta.json"
                if not sf.exists(): continue
                s = load_summary(sf)
                meta = json.loads(mf.read_text()) if mf.exists() else {}
                rows.append({
                    "platform":    pl_dir.name,
                    "workload":    wl_dir.name,
                    "config":      cfg_dir.name,
                    "sit_median":  _nan(s.get("sit_median")),
                    "active":      _nan(s.get("residency_active_avg")),
                    "stall":       _nan(s.get("residency_stall_avg")),
                    "idle":        _nan(s.get("residency_idle_avg")),
                    "adapter_mode":   meta.get("adapter_mode", ""),
                    "windows_file":   cfg_dir / "windows.csv",
                })
    return pd.DataFrame(rows)

def canon_wl(raw):
    m = {
        "tt_matmul_single": "MatMul (single)", "matmul": "MatMul (single)",
        "tt_matmul_multi":  "MatMul (multi)",  "matmul_multicore": "MatMul (multi)",
        "tt_eltwise_binary":"Eltwise Bin",      "eltwise_binary":  "Eltwise Bin",
        "tt_eltwise_sfpu":  "Eltwise SFPU",     "eltwise_sfpu":    "Eltwise SFPU",
        "tt_custom_sfpi_add":"SFPI Add",         "custom_sfpi_add": "SFPI Add",
        "tt_custom_sfpi_smoothstep":"Smoothstep","custom_sfpi_smoothstep":"Smoothstep",
        "tt_sfpu_chain":    "SFPU Chain",
    }
    return m.get(raw, raw)

def canon_pl(raw):
    return {"tt_wormhole":"TT Wormhole","qemu":"QEMU","gem5":"gem5","spike":"Spike"}.get(raw, raw)

REPR = {
    "matmul":"tt_m640_n640_k640", "tt_matmul_single":"tt_m640_n640_k640",
    "matmul_multicore":"tt_m640_n640_k640", "tt_matmul_multi":"tt_m640_n640_k640",
    "eltwise_binary":"tt_64tile",  "tt_eltwise_binary":"tt_64tile",
    "eltwise_sfpu":"tt_64tile",    "tt_eltwise_sfpu":"tt_64tile",
    "custom_sfpi_add":"tt_64tile", "tt_custom_sfpi_add":"tt_64tile",
    "custom_sfpi_smoothstep":"tt_64tile", "tt_custom_sfpi_smoothstep":"tt_64tile",
}

WL_ORDER = ["MatMul (single)", "MatMul (multi)", "Eltwise Bin",
            "Eltwise SFPU", "SFPI Add", "Smoothstep"]

def build_repr_df(df):
    rows = []
    for _, r in df.iterrows():
        want = REPR.get(r["workload"])
        if want is None or r["config"] != want: continue
        rows.append({
            "platform": canon_pl(r["platform"]),
            "workload": canon_wl(r["workload"]),
            "sit":    r["sit_median"],
            "active": r["active"],
            "stall":  r["stall"],
            "idle":   r["idle"],
            "adapter_mode": r["adapter_mode"],
        })
    rdf = pd.DataFrame(rows).drop_duplicates(subset=["platform","workload"])
    return rdf

# ─── Utilities ────────────────────────────────────────────────────────────────

def savefig(fig, stem):
    for ext in ("pdf", "png"):
        fig.savefig(OUT_DIR / f"{stem}.{ext}")
    print(f"  {stem}")
    plt.close(fig)

def val_labels(ax, bars, fmt="{:.3f}", fs=5.5, pad=0.0008):
    for b in bars:
        h = b.get_height()
        if math.isnan(h) or h == 0: continue
        ax.text(b.get_x() + b.get_width()/2, h + pad, fmt.format(h),
                ha="center", va="bottom", fontsize=fs)

def outside_legend(ax, ncol=3, loc="upper center", yanchor=1.14, **kw):
    """Place legend above the axes, outside the plot area."""
    ax.legend(loc=loc, bbox_to_anchor=(0.5, yanchor),
              ncol=ncol, bbox_transform=ax.transAxes,
              frameon=True, **kw)

# ═══════════════════════════════════════════════════════════════════════════════
# Fig 5 — QEMU vs gem5 SIT
# ═══════════════════════════════════════════════════════════════════════════════

def fig5_qemu_vs_gem5(rdf):
    wls  = WL_ORDER
    qemu = rdf[rdf["platform"]=="QEMU"].set_index("workload")["sit"]
    gem5 = rdf[rdf["platform"]=="gem5"].set_index("workload")["sit"]

    x, w = np.arange(len(wls)), 0.32
    fig, ax = plt.subplots(figsize=(COL2*0.78, 2.6))

    b1 = ax.bar(x-w/2, [qemu.get(wl, float("nan")) for wl in wls], w,
                label="QEMU", color=C_QEMU, hatch="//", edgecolor="0.2", lw=0.5)
    b2 = ax.bar(x+w/2, [gem5.get(wl, float("nan")) for wl in wls], w,
                label="gem5 (TimingSimpleCPU)", color=C_GEM5, hatch="xx", edgecolor="0.2", lw=0.5)

    ax.axhline(1.0, color="0.35", lw=1.0, ls="--", zorder=0, label="TT Wormhole reference (1.0)")
    val_labels(ax, b2, pad=0.0006)
    ax.set_xticks(x); ax.set_xticklabels(wls, rotation=20, ha="right")
    ax.set_ylabel("Normalized SIT Score")
    ax.set_ylim(0.910, 1.030)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    outside_legend(ax, ncol=3, yanchor=1.18)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "fig5_qemu_vs_gem5_sit")

# ═══════════════════════════════════════════════════════════════════════════════
# Fig 6 — gem5 Exec mode vs Stats mode
# ═══════════════════════════════════════════════════════════════════════════════

def fig6_gem5_exec_vs_stats(df):
    gem5_df = df[df["platform"]=="gem5"].copy()
    gem5_df["wl_c"] = gem5_df["workload"].apply(canon_wl)

    exec_wls  = ["MatMul (single)", "MatMul (multi)"]
    stats_wls = ["Eltwise Bin", "Eltwise SFPU", "SFPI Add", "Smoothstep"]
    all_wls   = exec_wls + stats_wls

    repr_rows = [r for _, r in gem5_df.iterrows()
                 if REPR.get(r["workload"]) == r["config"]]
    gdf = pd.DataFrame(repr_rows).drop_duplicates("wl_c").set_index("wl_c")

    sits    = [gdf["sit_median"].get(w, float("nan")) for w in all_wls]
    colors  = [C_EXEC if w in exec_wls else C_STATS for w in all_wls]
    hatches = ["//"   if w in exec_wls else ".."    for w in all_wls]

    x, w = np.arange(len(all_wls)), 0.48
    fig, ax = plt.subplots(figsize=(COL2*0.78, 2.6))

    bars = []
    for i, (sit, col, hatch) in enumerate(zip(sits, colors, hatches)):
        b = ax.bar(i, sit, w, color=col, hatch=hatch, edgecolor="0.2", lw=0.5)
        bars.append(b[0])
        val_labels(ax, b, pad=0.0006)

    # divider between exec / stats regions
    div = len(exec_wls) - 0.5
    ax.axvline(div, color="0.4", lw=1.0, ls=":", zorder=5)
    yann = 1.028
    ax.text(div - 0.08, yann, "exec mode",  ha="right", va="bottom",
            fontsize=6.5, color="0.25", style="italic")
    ax.text(div + 0.08, yann, "stats mode", ha="left",  va="bottom",
            fontsize=6.5, color="0.25", style="italic")

    ax.axhline(1.0, color="0.35", lw=1.0, ls="--", zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(all_wls, rotation=20, ha="right")
    ax.set_ylabel("Normalized SIT Score")
    ax.set_ylim(0.960, 1.035)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))

    ep = mpatches.Patch(facecolor=C_EXEC,  hatch="//", edgecolor="0.2",
                        label="gem5 exec mode (compute-biased)")
    sp = mpatches.Patch(facecolor=C_STATS, hatch="..", edgecolor="0.2",
                        label="gem5 stats mode (strict IPC)")
    ax.legend(handles=[ep, sp], loc="upper center",
              bbox_to_anchor=(0.5, 1.18), bbox_transform=ax.transAxes, ncol=2)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "fig6_gem5_exec_vs_stats_sit")

# ═══════════════════════════════════════════════════════════════════════════════
# Fig 7 — Cross-platform SIT (all 4 platforms × 6 workloads)
# ═══════════════════════════════════════════════════════════════════════════════

def fig7_cross_platform_sit(rdf):
    platforms = ["TT Wormhole", "QEMU", "gem5", "Spike"]
    wls = WL_ORDER
    n_pl, n_wl = len(platforms), len(wls)
    total_w = 0.80
    w = total_w / n_pl
    x = np.arange(n_wl)

    fig, ax = plt.subplots(figsize=(COL2, 2.8))
    piv = rdf.pivot(index="workload", columns="platform", values="sit")

    for i, pl in enumerate(platforms):
        vals = [piv[pl].get(wl, float("nan")) if pl in piv.columns else float("nan")
                for wl in wls]
        offset = (i - (n_pl-1)/2) * w
        bars = ax.bar(x+offset, vals, w, label=pl,
                      color=PAL[pl], hatch=HATCHES[pl], edgecolor="0.2", lw=0.5)
        # label only non-reference, non-trivial bars
        if pl in ("gem5", "Spike"):
            val_labels(ax, bars, fs=5.0, pad=0.0008)

    ax.axhline(1.0, color="0.35", lw=1.0, ls="--", zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(wls, rotation=20, ha="right")
    ax.set_ylabel("Normalized SIT Score\n(TT Wormhole = 1.0)")
    ax.set_ylim(0.905, 1.030)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    outside_legend(ax, ncol=4, yanchor=1.18)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "fig7_cross_platform_sit")

# ═══════════════════════════════════════════════════════════════════════════════
# Fig 8 — SIT Reproducibility (intra-run window CV)
# ═══════════════════════════════════════════════════════════════════════════════

def fig8_reproducibility(df):
    platforms = ["QEMU", "gem5", "Spike"]
    wls = WL_ORDER
    cv_data = {}

    for pl in platforms:
        raw_pl = pl.lower()
        cvs = []
        for wl_name in wls:
            matched = None
            for _, r in df[df["platform"]==raw_pl].iterrows():
                if canon_wl(r["workload"])==wl_name and REPR.get(r["workload"])==r["config"]:
                    matched = r; break
            cv = float("nan")
            if matched is not None:
                wf = Path(matched["windows_file"])
                if wf.exists():
                    try:
                        wdf = pd.read_csv(wf)
                        sits = wdf["sit"].dropna()
                        cv = sits.std()/sits.mean()*100 if len(sits)>1 and sits.mean()>0 else 0.0
                    except Exception:
                        pass
            cvs.append(cv)
        cv_data[pl] = cvs

    x = np.arange(len(wls))
    n_pl = len(platforms)
    w = 0.65 / n_pl

    fig, ax = plt.subplots(figsize=(COL2*0.78, 2.6))
    for i, pl in enumerate(platforms):
        offset = (i-(n_pl-1)/2)*w
        ax.bar(x+offset, cv_data[pl], w, label=pl,
               color=PAL[pl], hatch=HATCHES[pl], edgecolor="0.2", lw=0.5)

    ax.axhline(2.0, color="0.3", lw=1.2, ls="--", label="2 % threshold")
    ax.set_xticks(x); ax.set_xticklabels(wls, rotation=20, ha="right")
    ax.set_ylabel("Intra-run SIT CV (%)")
    ax.set_ylim(bottom=0)
    outside_legend(ax, ncol=4, yanchor=1.18)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "fig8_sit_reproducibility")

# ═══════════════════════════════════════════════════════════════════════════════
# Supp S1 — Residency decomposition (4 subplots)
# ═══════════════════════════════════════════════════════════════════════════════

def figS1_residency(rdf):
    platforms = ["TT Wormhole", "QEMU", "gem5", "Spike"]
    wls = WL_ORDER
    c_a, c_s, c_i = "#2166AC", "#D6604D", "#B2ABD2"

    fig, axes = plt.subplots(1, 4, figsize=(COL2, 2.8), sharey=True)

    for ax, pl in zip(axes, platforms):
        pdata = rdf[rdf["platform"]==pl]
        av, sv, iv = [], [], []
        for wl in wls:
            row = pdata[pdata["workload"]==wl]
            if row.empty:
                av.append(0); sv.append(0); iv.append(0)
            else:
                r = row.iloc[0]
                a = 0 if math.isnan(r["active"]) else r["active"]
                s = 0 if math.isnan(r["stall"])  else r["stall"]
                ii= 0 if math.isnan(r["idle"])   else r["idle"]
                av.append(a); sv.append(s); iv.append(ii)

        xi = np.arange(len(wls))
        ax.bar(xi, av, 0.6, color=c_a, edgecolor="0.3", lw=0.4)
        ax.bar(xi, sv, 0.6, bottom=av, color=c_s, edgecolor="0.3", lw=0.4)
        ax.bar(xi, iv, 0.6, bottom=[a+s for a,s in zip(av,sv)],
               color=c_i, edgecolor="0.3", lw=0.4)

        ax.set_title(pl, fontsize=7.5, pad=3)
        ax.set_xticks(xi)
        ax.set_xticklabels([w.replace(" ","\n") for w in wls], fontsize=5.5)
        ax.set_ylim(0, 1.06)
        if ax is axes[0]:
            ax.set_ylabel("Residency fraction")

    handles = [mpatches.Patch(color=c_a, label="Active"),
               mpatches.Patch(color=c_s, label="Stall"),
               mpatches.Patch(color=c_i, label="Idle")]
    fig.legend(handles=handles, loc="upper center",
               bbox_to_anchor=(0.5, 1.04), ncol=3, fontsize=7,
               frameon=True, edgecolor="0.7")
    fig.subplots_adjust(top=0.88, wspace=0.08)
    savefig(fig, "figS1_residency_decomposition")

# ═══════════════════════════════════════════════════════════════════════════════
# Supp S2 — SIT vs matmul matrix size
# ═══════════════════════════════════════════════════════════════════════════════

def figS2_size_scaling(df):
    size_map = {
        "tt_m320_n320_k320": 320, "tt_m640_n640_k640": 640,
        "tt_m960_n960_k960": 960, "tt_m1280_n1280_k1280": 1280,
    }
    sims = [("qemu","QEMU"), ("gem5","gem5"), ("spike","Spike")]

    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.5), sharey=True)

    for ax, (wl_base, title) in zip(axes, [("matmul","MatMul Single"),
                                            ("matmul_multicore","MatMul Multicore")]):
        for raw_pl, label in sims:
            rows = df[(df["platform"]==raw_pl)&(df["workload"]==wl_base)]
            pts = sorted((size_map[r["config"]], r["sit_median"])
                         for _, r in rows.iterrows() if r["config"] in size_map)
            if not pts: continue
            xs, ys = zip(*pts)
            col, ls, mk = LINE_STYLES[label]
            ax.plot(xs, ys, color=col, ls=ls, marker=mk, ms=5, lw=1.8, label=label)

        ax.axhline(1.0, color=C_TT, lw=1.5, ls="--", label="TT Wormhole (ref)")
        ax.set_xlabel("Matrix dimension N")
        ax.set_xticks([320, 640, 960, 1280])
        ax.set_xticklabels(["320", "640", "960", "1280"])
        ax.set_ylim(0.960, 1.010)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
        ax.set_title(title, fontsize=8, pad=3)

    axes[0].set_ylabel("Normalized SIT Score")
    # single shared legend above both subplots
    handles, labels = axes[0].get_legend_handles_labels()
    # deduplicate
    seen = {}
    for h, l in zip(handles, labels):
        seen[l] = h
    fig.legend(seen.values(), seen.keys(), loc="upper center",
               bbox_to_anchor=(0.5, 1.10), ncol=4, fontsize=7,
               frameon=True, edgecolor="0.7")
    fig.subplots_adjust(top=0.85, wspace=0.06)
    savefig(fig, "figS2_sit_size_scaling")

# ═══════════════════════════════════════════════════════════════════════════════
# Supp S3 — Stall fraction heatmap
# ═══════════════════════════════════════════════════════════════════════════════

def figS3_stall_heatmap(rdf):
    platforms = ["TT Wormhole", "QEMU", "gem5", "Spike"]
    wls = WL_ORDER
    data = np.zeros((len(platforms), len(wls)))
    for i, pl in enumerate(platforms):
        for j, wl in enumerate(wls):
            row = rdf[(rdf["platform"]==pl)&(rdf["workload"]==wl)]
            if not row.empty:
                v = row.iloc[0]["stall"]
                data[i,j] = 0 if math.isnan(v) else v*100

    fig, ax = plt.subplots(figsize=(COL2*0.72, 2.4))
    im = ax.imshow(data, cmap="Reds", aspect="auto",
                   vmin=0, vmax=max(data.max(), 0.1))
    ax.set_xticks(range(len(wls))); ax.set_xticklabels(wls, rotation=20, ha="right")
    ax.set_yticks(range(len(platforms))); ax.set_yticklabels(platforms)

    vmax = data.max()
    for i in range(len(platforms)):
        for j in range(len(wls)):
            v = data[i,j]
            tc = "white" if v > vmax*0.55 else "black"
            ax.text(j, i, f"{v:.2f}%", ha="center", va="center",
                    fontsize=5.5, color=tc)

    cb = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cb.set_label("Stall fraction (%)", fontsize=7)
    fig.tight_layout()
    savefig(fig, "figS3_stall_heatmap")

# ═══════════════════════════════════════════════════════════════════════════════
# Supp S4 — Per-window SIT time-series (matmul 640)
# ═══════════════════════════════════════════════════════════════════════════════

def figS4_window_timeseries(df):
    sims = [("gem5","gem5"), ("spike","Spike"), ("qemu","QEMU")]

    fig, ax = plt.subplots(figsize=(COL2*0.72, 2.5))

    for raw_pl, label in sims:
        rows = df[(df["platform"]==raw_pl) &
                  (df["workload"]=="matmul") &
                  (df["config"]=="tt_m640_n640_k640")]
        if rows.empty: continue
        wf = Path(rows.iloc[0]["windows_file"])
        if not wf.exists(): continue
        wdf = pd.read_csv(wf)
        sits = wdf["sit"].dropna().values
        col, ls, mk = LINE_STYLES[label]
        xvals = np.arange(len(sits))
        ax.plot(xvals, sits, color=col, ls=ls, marker=mk,
                ms=4, lw=2.0, alpha=0.9, label=label,
                markevery=max(1, len(sits)//8))

    ax.axhline(1.0, color=C_TT, lw=1.8, ls="--", label="TT Wormhole (ref)")
    ax.set_xlabel("Window index")
    ax.set_ylabel("SIT Score")
    ax.set_ylim(0.968, 1.008)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))

    outside_legend(ax, ncol=4, yanchor=1.18)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "figS4_window_timeseries_matmul")

# ═══════════════════════════════════════════════════════════════════════════════
# Supp S5 — TT vs simulator SIT scatter
# ═══════════════════════════════════════════════════════════════════════════════

def figS5_tt_vs_sim_scatter(rdf):
    tt  = rdf[rdf["platform"]=="TT Wormhole"].set_index("workload")["sit"]
    sims = ["QEMU", "gem5", "Spike"]
    mks  = {"QEMU":"o", "gem5":"s", "Spike":"^"}
    szs  = {"QEMU":45,  "gem5":45,  "Spike":45}

    fig, ax = plt.subplots(figsize=(2.9, 2.9))
    for sim in sims:
        sd = rdf[rdf["platform"]==sim].set_index("workload")["sit"]
        xs = [tt.get(wl, float("nan"))  for wl in WL_ORDER if wl in sd.index]
        ys = [sd.get(wl, float("nan"))  for wl in WL_ORDER if wl in sd.index]
        labels_for_pts = [wl for wl in WL_ORDER if wl in sd.index]
        ax.scatter(xs, ys, label=sim, color=PAL[sim],
                   marker=mks[sim], s=szs[sim], zorder=4, edgecolors="0.2", lw=0.5)
        for wl, xi, yi in zip(labels_for_pts, xs, ys):
            if not (math.isnan(xi) or math.isnan(yi)):
                ax.annotate(wl[:7], (xi, yi), textcoords="offset points",
                            xytext=(4, 2), fontsize=5.0, color="0.35")

    lims = [0.925, 1.005]
    ax.plot(lims, lims, color="0.3", lw=1.0, ls="--", label="y = x")
    ax.set_xlim(*lims); ax.set_ylim(*lims)
    ax.set_xlabel("TT Wormhole SIT")
    ax.set_ylabel("Simulator SIT")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    outside_legend(ax, ncol=2, yanchor=1.18)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "figS5_tt_vs_simulator_scatter")

# ═══════════════════════════════════════════════════════════════════════════════
# Supp S6 — ΔSIT (simulator − TT reference)
# ═══════════════════════════════════════════════════════════════════════════════

def figS6_sit_delta(rdf):
    tt   = rdf[rdf["platform"]=="TT Wormhole"].set_index("workload")["sit"]
    sims = ["QEMU", "gem5", "Spike"]
    wls  = WL_ORDER
    x    = np.arange(len(wls))
    w    = 0.65 / len(sims)

    fig, ax = plt.subplots(figsize=(COL2*0.78, 2.6))
    for i, sim in enumerate(sims):
        sd = rdf[rdf["platform"]==sim].set_index("workload")["sit"]
        deltas = []
        for wl in wls:
            tv = tt.get(wl, float("nan"))
            sv = sd.get(wl, float("nan"))
            deltas.append(float("nan") if math.isnan(tv) or math.isnan(sv)
                          else (sv - tv) * 100)
        offset = (i - (len(sims)-1)/2) * w
        ax.bar(x+offset, deltas, w, label=sim,
               color=PAL[sim], hatch=HATCHES[sim], edgecolor="0.2", lw=0.5)

    ax.axhline(0, color="0.2", lw=1.0)
    ax.set_xticks(x); ax.set_xticklabels(wls, rotation=20, ha="right")
    ax.set_ylabel("ΔSIT (simulator − TT), pp")
    outside_legend(ax, ncol=3, yanchor=1.18)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "figS6_sit_delta_from_tt")

# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("Loading run data …")
    df  = collect_all_runs()
    rdf = build_repr_df(df)
    print(f"  {len(df)} configs, {len(rdf)} representative rows")
    print("  Platforms:", sorted(rdf["platform"].unique()))
    print("  Workloads:", sorted(rdf["workload"].unique()))

    print(f"\nWriting → {OUT_DIR}")
    fig5_qemu_vs_gem5(rdf)
    fig6_gem5_exec_vs_stats(df)
    fig7_cross_platform_sit(rdf)
    fig8_reproducibility(df)
    figS1_residency(rdf)
    figS2_size_scaling(df)
    figS3_stall_heatmap(rdf)
    figS4_window_timeseries(df)
    figS5_tt_vs_sim_scatter(rdf)
    figS6_sit_delta(rdf)
    print(f"\nDone — {len(list(OUT_DIR.glob('*.pdf')))} PDFs in {OUT_DIR}")

if __name__ == "__main__":
    main()
