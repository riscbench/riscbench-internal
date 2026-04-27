#!/usr/bin/env python3.9
"""
RISCBench — generates all IEEE tables and figures from run data.

Tables  → results/tables_ieee/
Figures → results/ieee_plots/
"""

import json, math, glob
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE     = Path(__file__).resolve().parent.parent
RUNS_DIR = BASE / "runs"
RES_DIR  = BASE / "results"
OUT_TAB  = RES_DIR / "tables_ieee"
OUT_FIG  = RES_DIR / "ieee_plots"
OUT_TAB.mkdir(parents=True, exist_ok=True)
OUT_FIG.mkdir(parents=True, exist_ok=True)

# ─── IEEE plot style ──────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman","DejaVu Serif"],
    "font.size": 8, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "legend.framealpha": 0.95, "legend.edgecolor": "0.7",
    "lines.linewidth": 1.8, "lines.markersize": 5,
    "axes.linewidth": 0.8, "axes.grid": True, "axes.axisbelow": True,
    "grid.linestyle": "--", "grid.linewidth": 0.4, "grid.alpha": 0.5,
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.04, "pdf.fonttype": 42, "ps.fonttype": 42,
})

COL1, COL2 = 3.5, 7.16
C = {"TT Wormhole":"#648FFF","QEMU":"#FE6100","gem5":"#DC267F","Spike":"#785EF0"}
H = {"TT Wormhole":"","QEMU":"//","gem5":"xx","Spike":".."}
LS = {"TT Wormhole":("-","o"),"QEMU":("--","s"),"gem5":("-.",  "^"),"Spike":(":", "D")}

WL_LABEL = {
    "matmul":"MatMul Single","tt_matmul_single":"MatMul Single",
    "matmul_multicore":"MatMul Multi","tt_matmul_multi":"MatMul Multi",
    "eltwise_binary":"Eltwise Binary","tt_eltwise_binary":"Eltwise Binary",
    "eltwise_sfpu":"Eltwise SFPU","tt_eltwise_sfpu":"Eltwise SFPU",
    "custom_sfpi_add":"SFPI Add","tt_custom_sfpi_add":"SFPI Add",
    "custom_sfpi_smoothstep":"SFPI Smoothstep","tt_custom_sfpi_smoothstep":"SFPI Smoothstep",
    "tt_sfpu_chain":"SFPU Chain",
}
CFG_LABEL = {
    "tt_m320_n320_k320":"M320","tt_m640_n640_k640":"M640",
    "tt_m960_n960_k960":"M960","tt_m1280_n1280_k1280":"M1280",
    "tt_32tile":"32t","tt_64tile":"64t","tt_128tile":"128t","tt_1tile":"1t",
}
PL_LABEL = {"tt_wormhole":"TT Wormhole","qemu":"QEMU","gem5":"gem5","spike":"Spike"}

WL_ORDER = ["MatMul Single","MatMul Multi","SFPU Chain",
            "Eltwise SFPU","Eltwise Binary","SFPI Add","SFPI Smoothstep"]

# ─── Load all comparison CSVs (most-recent per key) ──────────────────────────

def load_all_runs() -> pd.DataFrame:
    dfs = []
    for p in sorted(glob.glob(str(RES_DIR / "202*" / "comparison_rows.csv"))):
        try:
            df = pd.read_csv(p)
            df["_src"] = Path(p).parent.name
            dfs.append(df)
        except Exception:
            pass
    if not dfs:
        return pd.DataFrame()
    all_df = pd.concat(dfs, ignore_index=True)
    all_df = all_df.sort_values("_src").drop_duplicates(
        subset=["target","workload","workload_size","label"], keep="last")

    # Enrich with expected_work_rate + no_work_global_active_sit from summary.json
    def get_extras(run_dir):
        sf = Path(run_dir) / "summary.json"
        if not sf.exists(): return {}, {}
        raw = sf.read_text().replace(": NaN",": null")
        s = json.loads(raw)
        mf = Path(run_dir) / "adapter_meta.json"
        meta = json.loads(mf.read_text()) if mf.exists() else {}
        return s, meta

    ew_rates, nw_sits, modes = [], [], []
    for _, row in all_df.iterrows():
        s, meta = get_extras(row.get("run_dir",""))
        ew = s.get("expected_work_rate")
        ew_rates.append(None if ew is None or (isinstance(ew,float) and math.isnan(ew)) else ew)
        nw = s.get("no_work_global_active_sit")
        nw_sits.append(None if nw is None or (isinstance(nw,float) and math.isnan(nw)) else nw)
        modes.append(meta.get("adapter_mode",""))

    all_df["expected_work_rate"] = ew_rates
    all_df["no_work_sit"]        = nw_sits
    all_df["adapter_mode"]       = modes

    # Canonical names
    all_df["wl"]  = all_df["workload"].map(WL_LABEL)
    all_df["cfg"] = all_df["workload_size"].map(CFG_LABEL)
    all_df["pl"]  = all_df["target"].map(PL_LABEL)

    # Correct SIT: stats-mode uses no_work_sit; everything else uses sit_median
    def correct_sit(row):
        if row["adapter_mode"] == "stats" and row["no_work_sit"] is not None:
            return row["no_work_sit"]
        v = row["sit_median"]
        return None if (v is None or (isinstance(v,float) and math.isnan(v))) else v
    all_df["sit"] = all_df.apply(correct_sit, axis=1)

    return all_df

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _f(v, fmt=".4f", fallback="---"):
    if v is None or (isinstance(v, float) and math.isnan(v)): return fallback
    return format(float(v), fmt)

def _pct(v, fallback="---"):
    if v is None or (isinstance(v, float) and math.isnan(v)): return fallback
    return f"{float(v)*100:.1f}"

def savefig(fig, stem):
    for ext in ("pdf","png"):
        fig.savefig(OUT_FIG / f"{stem}.{ext}")
    print(f"  fig: {stem}")
    plt.close(fig)

def outside_legend(ax, ncol=3, yanchor=1.18):
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, yanchor),
              ncol=ncol, bbox_transform=ax.transAxes, frameon=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TABLE — one per platform, reference format
# ═══════════════════════════════════════════════════════════════════════════════

def build_platform_table(df: pd.DataFrame, platform: str) -> str:
    """LaTeX table matching the reference format for one platform."""
    pdata = df[df["pl"] == platform].copy()
    is_tt = (platform == "TT Wormhole")

    # sort by WL_ORDER then cfg
    cfg_rank = {v: i for i,v in enumerate(["M320","M640","M960","M1280",
                                            "1t","32t","64t","128t"])}
    wl_rank  = {v: i for i,v in enumerate(WL_ORDER)}
    pdata = pdata.copy()
    pdata["_wlr"] = pdata["wl"].map(lambda x: wl_rank.get(x, 99))
    pdata["_cfgr"] = pdata["cfg"].map(lambda x: cfg_rank.get(x, 99))
    pdata = pdata.sort_values(["_wlr","_cfgr"])

    pl_escape = platform.replace("_","\_")

    lines = []
    lines.append(f"% {platform} — SIT sweep summary")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    if is_tt:
        lines.append(f"\\caption{{{pl_escape} SIT sweep summary using formula-based "
                     r"expected work rate and kernel-envelope residency.}")
    else:
        lines.append(f"\\caption{{{pl_escape} SIT sweep summary.}}")
    lines.append(f"\\label{{tab:sit_{platform.lower().replace(' ','_')}}}")
    lines.append(r"\setlength{\tabcolsep}{4pt}")
    lines.append(r"\renewcommand{\arraystretch}{0.92}")

    if is_tt:
        lines.append(r"\begin{tabular}{llrrrrccc}")
        lines.append(r"\toprule")
        lines.append(r"\textbf{Workload} & \textbf{Case} & "
                     r"\textbf{Obs.} & \textbf{Exp.} & \textbf{Obs./Exp.} & "
                     r"\textbf{SIT} & \textbf{Active\,(\%)} & \textbf{Stall\,(\%)} \\")
    else:
        mode_col = r" & \textbf{Mode}" if platform == "gem5" else ""
        lines.append(r"\begin{tabular}{ll" + ("l" if platform=="gem5" else "") + r"cccc}")
        lines.append(r"\toprule")
        lines.append(r"\textbf{Workload} & \textbf{Case}" + mode_col +
                     r" & \textbf{SIT} & \textbf{Obs./Exp.} & "
                     r"\textbf{Active\,(\%)} & \textbf{Stall\,(\%)} \\")
    lines.append(r"\midrule")

    prev_wl = None
    for _, row in pdata.iterrows():
        wl  = row["wl"]  or "?"
        cfg = row["cfg"] or "?"
        sit = row["sit"]
        obs = row.get("observed_work_rate_median")
        exp = row.get("expected_work_rate")
        act = row.get("residency_active_avg")
        stl = row.get("residency_stall_avg")
        mode = row.get("adapter_mode","")

        # obs/exp ratio
        ratio = None
        if obs and exp and exp > 0:
            ratio = obs / exp
        elif sit is not None:
            ratio = sit  # use SIT as proxy for sim platforms

        sit_str = _f(sit, ".3f") if sit is not None else "---"
        if sit is not None and abs(float(sit) - 1.0) < 0.0005:
            sit_str = r"\textbf{1.000}"

        if wl != prev_wl and prev_wl is not None:
            lines.append(r"\midrule")
        prev_wl = wl

        if is_tt:
            lines.append(
                f"{wl} & {cfg} & "
                f"{_f(obs,',.1f')} & {_f(exp,',.1f')} & "
                f"{_f(ratio,'.3f')} & {sit_str} & "
                f"{_pct(act)} & {_pct(stl)} \\\\"
            )
        else:
            mode_cell = f" & \\texttt{{{mode}}}" if platform == "gem5" else ""
            ratio_str = _f(ratio, ".3f") if ratio is not None else "---"
            lines.append(
                f"{wl} & {cfg}{mode_cell} & "
                f"{sit_str} & {ratio_str} & "
                f"{_pct(act)} & {_pct(stl)} \\\\"
            )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    # footnotes
    lines.append(r"\smallskip")
    lines.append(r"\begin{flushleft}\footnotesize")
    if is_tt:
        lines.append(r"Obs.\ and Exp.\ are in ops/$\mu$s. "
                     r"SIT is normalized to \texttt{expected\_work\_rate} "
                     r"from the kernel-envelope residency model. "
                     r"Active and Stall fractions include thermal and DRAM-refresh effects.")
    elif platform == "gem5":
        lines.append(r"\texttt{exec} mode: \texttt{compute\_biased} classification from "
                     r"instruction-execution trace (\texttt{sit\_median}). "
                     r"\texttt{stats} mode: \texttt{strict} IPC classification; "
                     r"SIT reported as \texttt{no\_work\_global\_active\_sit}.")
    elif platform == "QEMU":
        lines.append(r"QEMU uses dynamic translation blocks "
                     r"(\texttt{dynamic\_tb\_trace} adapter). "
                     r"No memory latency modelling; stall fraction is always 0. "
                     r"SIT $\approx$ 1 reflects pure instruction-type activity ratio.")
    elif platform == "Spike":
        lines.append(r"Spike uses a commit log (\texttt{commit\_log} adapter). "
                     r"No memory latency modelling; stall fraction is always 0. "
                     r"SIT reflects instruction-type active classification only.")
    lines.append(r"\end{flushleft}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def write_tables(df: pd.DataFrame):
    for pl in ["TT Wormhole","QEMU","gem5","Spike"]:
        fname = f"table_{pl.lower().replace(' ','_')}_sit.tex"
        tex = build_platform_table(df, pl)
        (OUT_TAB / fname).write_text(tex)
        print(f"  tab: {fname}")

    # Also write a combined Table VIII (cross-platform sweep summary)
    write_table_viii(df)


def write_table_viii(df: pd.DataFrame):
    """Combined sweep table: rows = (workload, config), cols = 4 platforms."""
    # Use correct sit field per platform/mode
    piv_sit = df.pivot_table(index=["wl","cfg"], columns="pl", values="sit", aggfunc="first")
    piv_act = df.pivot_table(index=["wl","cfg"], columns="pl", values="residency_active_avg", aggfunc="first")
    piv_stl = df.pivot_table(index=["wl","cfg"], columns="pl", values="residency_stall_avg", aggfunc="first")

    cfg_rank = {v:i for i,v in enumerate(["M320","M640","M960","M1280","1t","32t","64t","128t"])}
    wl_rank  = {v:i for i,v in enumerate(WL_ORDER)}

    def row_sort(idx):
        wl, cfg = idx
        return (wl_rank.get(wl,99), cfg_rank.get(cfg,99))

    sorted_idx = sorted(piv_sit.index, key=row_sort)

    pls = ["TT Wormhole","QEMU","gem5","Spike"]

    lines = []
    lines.append(r"% Table VIII — Normalized SIT Scores: Full Sweep, All Platforms")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\caption{Normalized SIT Scores Across All Platforms and Configurations}")
    lines.append(r"\label{tab:sit_all}")
    lines.append(r"\setlength{\tabcolsep}{4pt}")
    lines.append(r"\renewcommand{\arraystretch}{0.92}")
    lines.append(r"\begin{tabular}{llcccc}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Workload} & \textbf{Config} & "
                 r"\textbf{TT~Worm.}\textsuperscript{$\dagger$} & "
                 r"\textbf{QEMU} & "
                 r"\textbf{gem5}\textsuperscript{$\ddagger$} & "
                 r"\textbf{Spike} \\")
    lines.append(r"\midrule")

    prev_wl = None
    for (wl, cfg) in sorted_idx:
        if wl != prev_wl and prev_wl is not None:
            lines.append(r"\midrule")
        prev_wl = wl

        cells = [wl, cfg]
        for pl in pls:
            v = piv_sit[pl].get((wl,cfg), float("nan")) if pl in piv_sit.columns else float("nan")
            if v is None or (isinstance(v, float) and math.isnan(v)):
                cells.append("---")
            elif abs(float(v) - 1.0) < 0.0005:
                cells.append(r"\textbf{1.000}")
            else:
                cells.append(f"{float(v):.4f}")
        lines.append(" & ".join(cells) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\smallskip")
    lines.append(r"\begin{flushleft}\footnotesize")
    lines.append(r"\textsuperscript{$\dagger$}TT Wormhole is the reference; "
                 r"SIT normalised to \texttt{expected\_work\_rate}.")
    lines.append(r"\textsuperscript{$\ddagger$}gem5: \texttt{exec} mode for MatMul "
                 r"(\texttt{sit\_median}); \texttt{stats} mode for tile workloads "
                 r"(\texttt{no\_work\_global\_active\_sit}).")
    lines.append(r"\end{flushleft}")
    lines.append(r"\end{table}")

    (OUT_TAB / "table_viii_sit_scores.tex").write_text("\n".join(lines))
    print("  tab: table_viii_sit_scores.tex")

# ═══════════════════════════════════════════════════════════════════════════════
# FIGURES (updated with precise comparison_rows values)
# ═══════════════════════════════════════════════════════════════════════════════

def prep_repr(df: pd.DataFrame) -> pd.DataFrame:
    """One representative row per (platform, canonical workload)."""
    repr_cfg = {
        "MatMul Single":"M640","MatMul Multi":"M640",
        "SFPU Chain":"1t",
        "Eltwise Binary":"64t","Eltwise SFPU":"64t",
        "SFPI Add":"64t","SFPI Smoothstep":"64t",
    }
    rows = []
    for (wl, cfg), grp in df.groupby(["wl","cfg"]):
        if repr_cfg.get(wl) != cfg: continue
        for _, r in grp.iterrows():
            rows.append(r)
    rdf = pd.DataFrame(rows).drop_duplicates(subset=["pl","wl"])
    return rdf

WLS6 = ["MatMul Single","MatMul Multi","Eltwise Binary","Eltwise SFPU","SFPI Add","SFPI Smoothstep"]
PLATS = ["TT Wormhole","QEMU","gem5","Spike"]

# ── Fig 5: QEMU vs gem5 ──────────────────────────────────────────────────────
def fig5(rdf):
    wls = WLS6
    q = rdf[rdf["pl"]=="QEMU"].set_index("wl")["sit"]
    g = rdf[rdf["pl"]=="gem5"].set_index("wl")["sit"]

    x, w = np.arange(len(wls)), 0.32
    fig, ax = plt.subplots(figsize=(COL2*0.78, 2.6))
    b1 = ax.bar(x-w/2, [q.get(wl) for wl in wls], w,
                label="QEMU", color=C["QEMU"], hatch="//", edgecolor="0.2", lw=0.5)
    b2 = ax.bar(x+w/2, [g.get(wl) for wl in wls], w,
                label="gem5", color=C["gem5"], hatch="xx", edgecolor="0.2", lw=0.5)
    for bars, skip_one in [(b2, False)]:
        for b in bars:
            h = b.get_height()
            if h is None or math.isnan(h): continue
            ax.text(b.get_x()+b.get_width()/2, h+0.0006, f"{h:.4f}",
                    ha="center", va="bottom", fontsize=5.5)
    ax.axhline(1.0, color="0.35", lw=1.0, ls="--", zorder=0, label="TT reference")
    ax.set_xticks(x); ax.set_xticklabels(wls, rotation=20, ha="right")
    ax.set_ylabel("Normalized SIT Score")
    ax.set_ylim(0.910, 1.030)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    outside_legend(ax, ncol=3)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "fig5_qemu_vs_gem5_sit")

# ── Fig 6: gem5 exec vs stats ─────────────────────────────────────────────────
def fig6(df):
    exec_wls  = ["MatMul Single","MatMul Multi"]
    stats_wls = ["Eltwise Binary","Eltwise SFPU","SFPI Add","SFPI Smoothstep"]
    all_wls   = exec_wls + stats_wls
    C_EXEC, C_STATS = "#009E73", "#E69F00"

    gdf = df[df["pl"]=="gem5"].copy()
    repr_cfg = {"MatMul Single":"M640","MatMul Multi":"M640",
                "Eltwise Binary":"64t","Eltwise SFPU":"64t",
                "SFPI Add":"64t","SFPI Smoothstep":"64t"}
    gdf = gdf[gdf.apply(lambda r: repr_cfg.get(r["wl"])==r["cfg"], axis=1)]
    gdf = gdf.drop_duplicates("wl").set_index("wl")

    sits    = [gdf["sit"].get(w) for w in all_wls]
    colors  = [C_EXEC if w in exec_wls else C_STATS for w in all_wls]
    hatches = ["//"   if w in exec_wls else ".."    for w in all_wls]

    x, w = np.arange(len(all_wls)), 0.48
    fig, ax = plt.subplots(figsize=(COL2*0.78, 2.6))
    for i, (sit, col, hatch) in enumerate(zip(sits, colors, hatches)):
        b = ax.bar(i, sit, w, color=col, hatch=hatch, edgecolor="0.2", lw=0.5)
        if sit: ax.text(i, sit+0.0006, f"{sit:.4f}", ha="center", va="bottom", fontsize=5.5)

    ax.axvline(len(exec_wls)-0.5, color="0.4", lw=1.0, ls=":", zorder=5)
    ax.text(len(exec_wls)-0.55, 1.030, "exec mode", ha="right", va="bottom",
            fontsize=6.5, color="0.25", style="italic")
    ax.text(len(exec_wls)-0.45, 1.030, "stats mode", ha="left", va="bottom",
            fontsize=6.5, color="0.25", style="italic")
    ax.axhline(1.0, color="0.35", lw=1.0, ls="--", zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(all_wls, rotation=20, ha="right")
    ax.set_ylabel("Normalized SIT Score")
    ax.set_ylim(0.960, 1.038)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    ep = mpatches.Patch(facecolor=C_EXEC, hatch="//", edgecolor="0.2",
                        label="gem5 exec (compute-biased)")
    sp = mpatches.Patch(facecolor=C_STATS, hatch="..", edgecolor="0.2",
                        label="gem5 stats (strict IPC)")
    ax.legend(handles=[ep,sp], loc="upper center",
              bbox_to_anchor=(0.5,1.18), bbox_transform=ax.transAxes, ncol=2)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "fig6_gem5_exec_vs_stats_sit")

# ── Fig 7: cross-platform ────────────────────────────────────────────────────
def fig7(rdf):
    wls = WLS6
    n_pl = len(PLATS)
    w = 0.80 / n_pl
    x = np.arange(len(wls))
    piv = rdf.pivot_table(index="wl", columns="pl", values="sit", aggfunc="first")

    fig, ax = plt.subplots(figsize=(COL2, 2.8))
    for i, pl in enumerate(PLATS):
        vals = [piv[pl].get(wl, float("nan")) if pl in piv.columns else float("nan")
                for wl in wls]
        offset = (i-(n_pl-1)/2)*w
        bars = ax.bar(x+offset, vals, w, label=pl,
                      color=C[pl], hatch=H[pl], edgecolor="0.2", lw=0.5)
        if pl in ("gem5","Spike"):
            for b in bars:
                h = b.get_height()
                if h and not math.isnan(h):
                    ax.text(b.get_x()+b.get_width()/2, h+0.0008, f"{h:.3f}",
                            ha="center", va="bottom", fontsize=4.8)
    ax.axhline(1.0, color="0.35", lw=1.0, ls="--", zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(wls, rotation=20, ha="right")
    ax.set_ylabel("Normalized SIT Score\n(TT Wormhole = 1.0)")
    ax.set_ylim(0.905, 1.030)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    outside_legend(ax, ncol=4)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "fig7_cross_platform_sit")

# ── Fig 8: reproducibility (CV per workload) ─────────────────────────────────
def fig8(df):
    sims = ["QEMU","gem5","Spike"]
    wls  = WLS6
    repr_cfg = {"MatMul Single":"M640","MatMul Multi":"M640",
                "SFPU Chain":"1t","Eltwise Binary":"64t","Eltwise SFPU":"64t",
                "SFPI Add":"64t","SFPI Smoothstep":"64t"}
    cv_data = {}
    for pl in sims:
        cvs = []
        for wl in wls:
            cfg = repr_cfg.get(wl)
            rows = df[(df["pl"]==pl)&(df["wl"]==wl)&(df["cfg"]==cfg)]
            cv = float("nan")
            if not rows.empty:
                rd = rows.iloc[0].get("run_dir","")
                wf = Path(rd) / "windows.csv"
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
    w = 0.65 / len(sims)
    fig, ax = plt.subplots(figsize=(COL2*0.78, 2.6))
    for i, pl in enumerate(sims):
        offset = (i-(len(sims)-1)/2)*w
        ax.bar(x+offset, cv_data[pl], w, label=pl,
               color=C[pl], hatch=H[pl], edgecolor="0.2", lw=0.5)
    ax.axhline(2.0, color="0.3", lw=1.2, ls="--", label="2% threshold")
    ax.set_xticks(x); ax.set_xticklabels(wls, rotation=20, ha="right")
    ax.set_ylabel("Intra-run SIT CV (%)")
    ax.set_ylim(bottom=0)
    outside_legend(ax, ncol=4)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "fig8_sit_reproducibility")

# ── FigS1: residency decomposition ───────────────────────────────────────────
def figS1(rdf):
    wls = WLS6
    ca, cs, ci = "#2166AC","#D6604D","#B2ABD2"
    fig, axes = plt.subplots(1, 4, figsize=(COL2, 2.8), sharey=True)
    for ax, pl in zip(axes, PLATS):
        pdata = rdf[rdf["pl"]==pl]
        av, sv, iv = [], [], []
        for wl in wls:
            r = pdata[pdata["wl"]==wl]
            if r.empty: av.append(0); sv.append(0); iv.append(0)
            else:
                a = r.iloc[0]["residency_active_avg"] or 0
                s = r.iloc[0]["residency_stall_avg"]  or 0
                ii= r.iloc[0]["residency_idle_avg"]   if "residency_idle_avg" in r.columns and r.iloc[0]["residency_idle_avg"] else 0
                av.append(a); sv.append(s); iv.append(ii)
        xi = np.arange(len(wls))
        ax.bar(xi, av, 0.6, color=ca, edgecolor="0.3", lw=0.4)
        ax.bar(xi, sv, 0.6, bottom=av, color=cs, edgecolor="0.3", lw=0.4)
        ax.bar(xi, iv, 0.6, bottom=[a+s for a,s in zip(av,sv)], color=ci, edgecolor="0.3", lw=0.4)
        ax.set_title(pl, fontsize=7.5, pad=3)
        ax.set_xticks(xi)
        ax.set_xticklabels([w.replace(" ","\n") for w in wls], fontsize=5.0)
        ax.set_ylim(0, 1.06)
        if ax is axes[0]: ax.set_ylabel("Residency fraction")
    handles = [mpatches.Patch(color=ca, label="Active"),
               mpatches.Patch(color=cs, label="Stall"),
               mpatches.Patch(color=ci, label="Idle")]
    fig.legend(handles=handles, loc="upper center",
               bbox_to_anchor=(0.5,1.04), ncol=3, fontsize=7, frameon=True)
    fig.subplots_adjust(top=0.88, wspace=0.08)
    savefig(fig, "figS1_residency_decomposition")

# ── FigS2: tile sweep — SIT vs tile count (gem5 & spike) ────────────────────
def figS2_tile_sweep(df):
    tile_wls = ["Eltwise Binary","Eltwise SFPU","SFPI Add","SFPI Smoothstep"]
    cfgs = ["32t","64t","128t"]
    cfg_x = {"32t":32,"64t":64,"128t":128}
    sims = [("gem5","gem5"),("spike","Spike"),("qemu","QEMU")]

    fig, axes = plt.subplots(1,4, figsize=(COL2, 2.4), sharey=True, sharex=True)
    for ax, wl in zip(axes, tile_wls):
        for raw_pl, pl_label in sims:
            rows = df[(df["pl"]==pl_label)&(df["wl"]==wl)&(df["cfg"].isin(cfgs))]
            pts = sorted((cfg_x[r["cfg"]], r["sit"])
                         for _, r in rows.iterrows() if r["sit"] is not None)
            if not pts: continue
            xs, ys = zip(*pts)
            ls, mk = LS[pl_label]
            ax.plot(xs, ys, color=C[pl_label], ls=ls, marker=mk,
                    ms=4, lw=1.8, label=pl_label)
        ax.axhline(1.0, color=C["TT Wormhole"], lw=1.2, ls="--")
        ax.set_title(wl, fontsize=7, pad=3)
        ax.set_xticks([32,64,128])
        ax.set_ylim(0.930, 1.010)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
        ax.set_xlabel("Tile count")
    axes[0].set_ylabel("Normalized SIT Score")
    handles, labels = axes[0].get_legend_handles_labels()
    # add TT ref patch
    handles.append(plt.Line2D([0],[0], color=C["TT Wormhole"], ls="--", lw=1.2))
    labels.append("TT Wormhole (ref)")
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5,1.06),
               ncol=4, fontsize=7, frameon=True)
    fig.subplots_adjust(top=0.85, wspace=0.06)
    savefig(fig, "figS2_tile_sweep_sit")

# ── FigS3: matmul size sweep ──────────────────────────────────────────────────
def figS3_matmul_sweep(df):
    size_x = {"M320":320,"M640":640,"M960":960,"M1280":1280}
    sims = [("gem5","gem5"),("spike","Spike"),("qemu","QEMU")]

    fig, axes = plt.subplots(1,2, figsize=(COL2*0.85, 2.4), sharey=True)
    for ax, wl in zip(axes, ["MatMul Single","MatMul Multi"]):
        for raw_pl, pl_label in sims:
            rows = df[(df["pl"]==pl_label)&(df["wl"]==wl)]
            pts = sorted((size_x[r["cfg"]], r["sit"])
                         for _, r in rows.iterrows()
                         if r["cfg"] in size_x and r["sit"] is not None)
            if not pts: continue
            xs, ys = zip(*pts)
            ls, mk = LS[pl_label]
            ax.plot(xs, ys, color=C[pl_label], ls=ls, marker=mk,
                    ms=4, lw=1.8, label=pl_label)
        ax.axhline(1.0, color=C["TT Wormhole"], lw=1.2, ls="--")
        ax.set_title(wl, fontsize=8, pad=3)
        ax.set_xticks([320,640,960,1280])
        ax.set_xticklabels(["320","640","960","1280"])
        ax.set_ylim(0.958, 1.008)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
        ax.set_xlabel("Matrix dim N")
    axes[0].set_ylabel("Normalized SIT Score")
    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(plt.Line2D([0],[0], color=C["TT Wormhole"], ls="--", lw=1.2))
    labels.append("TT Wormhole (ref)")
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5,1.08),
               ncol=4, fontsize=7, frameon=True)
    fig.subplots_adjust(top=0.85, wspace=0.06)
    savefig(fig, "figS3_matmul_sweep_sit")

# ── FigS4: stall heatmap ──────────────────────────────────────────────────────
def figS4_stall_heatmap(rdf):
    wls = WLS6
    data = np.zeros((len(PLATS), len(wls)))
    for i, pl in enumerate(PLATS):
        for j, wl in enumerate(wls):
            r = rdf[(rdf["pl"]==pl)&(rdf["wl"]==wl)]
            if not r.empty:
                v = r.iloc[0]["residency_stall_avg"]
                data[i,j] = 0 if (v is None or math.isnan(float(v))) else float(v)*100
    fig, ax = plt.subplots(figsize=(COL2*0.72, 2.4))
    im = ax.imshow(data, cmap="Reds", aspect="auto", vmin=0, vmax=max(data.max(),0.1))
    ax.set_xticks(range(len(wls))); ax.set_xticklabels(wls, rotation=20, ha="right")
    ax.set_yticks(range(len(PLATS))); ax.set_yticklabels(PLATS)
    vmax = data.max()
    for i in range(len(PLATS)):
        for j in range(len(wls)):
            v = data[i,j]
            ax.text(j, i, f"{v:.2f}%", ha="center", va="center",
                    fontsize=5.5, color="white" if v>vmax*0.55 else "black")
    cb = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cb.set_label("Stall fraction (%)", fontsize=7)
    fig.tight_layout()
    savefig(fig, "figS4_stall_heatmap")

# ── FigS5: ΔSIT from TT reference ────────────────────────────────────────────
def figS5_delta(rdf):
    wls = WLS6
    tt  = rdf[rdf["pl"]=="TT Wormhole"].set_index("wl")["sit"]
    x   = np.arange(len(wls))
    sims = ["QEMU","gem5","Spike"]
    w = 0.65/len(sims)
    fig, ax = plt.subplots(figsize=(COL2*0.78, 2.6))
    for i, pl in enumerate(sims):
        sd = rdf[rdf["pl"]==pl].set_index("wl")["sit"]
        deltas = []
        for wl in wls:
            tv = tt.get(wl); sv = sd.get(wl)
            if tv is None or sv is None: deltas.append(float("nan"))
            else: deltas.append((float(sv)-float(tv))*100)
        offset = (i-(len(sims)-1)/2)*w
        ax.bar(x+offset, deltas, w, label=pl, color=C[pl], hatch=H[pl], edgecolor="0.2", lw=0.5)
    ax.axhline(0, color="0.2", lw=1.0)
    ax.set_xticks(x); ax.set_xticklabels(wls, rotation=20, ha="right")
    ax.set_ylabel("ΔSIT (simulator − TT), pp")
    outside_legend(ax, ncol=3)
    fig.subplots_adjust(top=0.84)
    savefig(fig, "figS5_sit_delta_from_tt")

# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("Loading data from comparison CSVs …")
    df = load_all_runs()
    print(f"  {len(df)} rows | platforms: {sorted(df['pl'].dropna().unique())}")
    rdf = prep_repr(df)

    print("\nWriting tables →", OUT_TAB)
    write_tables(df)

    print("\nWriting figures →", OUT_FIG)
    fig5(rdf)
    fig6(df)
    fig7(rdf)
    fig8(df)
    figS1(rdf)
    figS2_tile_sweep(df)
    figS3_matmul_sweep(df)
    figS4_stall_heatmap(rdf)
    figS5_delta(rdf)

    n_pdf = len(list(OUT_FIG.glob("*.pdf")))
    n_tex = len(list(OUT_TAB.glob("*.tex")))
    print(f"\nDone — {n_tex} .tex tables, {n_pdf} PDFs")

if __name__ == "__main__":
    main()
