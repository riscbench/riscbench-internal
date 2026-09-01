import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

import common

def export_zoomed_waveforms(
    csv_file, 
    sample_ranges,
    clk_period_ns=10.0, 
    downsample_factor_overview=10
):
    
    # -------------------------------------------------------------------------
    # 1. Parse Vivado ILA CSV Header & Data
    # -------------------------------------------------------------------------
    header_lines = 0
    with open(csv_file, 'r') as f:
        for i, line in enumerate(f):
            if any(k in line for k in ["Sample Window", "Sample Number", "Sample in Buffer"]):
                header_lines = i
                break

    df = pd.read_csv(csv_file, skiprows=header_lines)

    # Clean column names
    df.columns = [col.strip().strip('"').strip('[').strip(']') for col in df.columns]

    # Detect sample index column
    sample_col = None
    for col in df.columns:
        if 'Sample' in col and ('Number' in col or 'Buffer' in col or 'Index' in col or 'Window' in col):
            sample_col = col
            break
    
    if sample_col is None:
        df['Sample Index'] = np.arange(len(df))
        sample_col = 'Sample Index'

    # Clean non-numeric metadata rows (e.g., 'Radix - UNSIGNED')
    df[sample_col] = pd.to_numeric(df[sample_col], errors='coerce')
    df = df.dropna(subset=[sample_col]).reset_index(drop=True)

    # Filter out Vivado metadata columns
    metadata_patterns = ['sample in buffer', 'sample in window', 'sample number', 'trigger']
    signal_cols = [
        c for c in df.columns 
        if not any(pattern in c.lower() for pattern in metadata_patterns)
    ]

    num_signals = len(signal_cols)
    if num_signals == 0:
        raise ValueError("No probe signals found after filtering out metadata columns.")

    total_samples = len(df)
    df_overview = df.iloc[::downsample_factor_overview].copy()
    t_full = df[sample_col].astype(int).values * clk_period_ns
    t_overview = df_overview[sample_col].astype(int).values * clk_period_ns

    # -------------------------------------------------------------------------
    # 2. Iterate Over Target Ranges & Export 1920x1080 Images
    # -------------------------------------------------------------------------
    for range_idx, (start_sample, num_samples) in enumerate(sample_ranges, start=1):
        end_sample = min(start_sample + num_samples, total_samples)
        output_filename = f"{common.env.run_path}/image{range_idx}.png"

        df_zoomed = df.iloc[start_sample:end_sample].copy()
        t_zoom = df_zoomed[sample_col].astype(int).values * clk_period_ns

        zoom_t_start = t_full[start_sample]
        zoom_t_end = t_full[end_sample - 1] if end_sample <= len(t_full) else t_full[-1]
        time_span_zoom = zoom_t_end - zoom_t_start

        # Create 1920x1080 image figure (19.2 x 10.8 inches @ 100 DPI)
        fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
        
        # Split figure into Overview group (top) and Zoomed group (bottom)
        gs = fig.add_gridspec(2, 1, height_ratios=[1, 2.5], hspace=0.45)

        gs_top = gs[0].subgridspec(num_signals, 1, hspace=0.1)
        gs_bottom = gs[1].subgridspec(num_signals, 1, hspace=0.35)

        axes_top = [fig.add_subplot(gs_top[i]) for i in range(num_signals)]
        axes_bottom = [fig.add_subplot(gs_bottom[i]) for i in range(num_signals)]

        # --- Panel 1: Overview ---
        for i, col in enumerate(signal_cols):
            ax = axes_top[i]
            val_series = df_overview[col]

            is_bus = False
            try:
                numeric_vals = pd.to_numeric(val_series)
                if numeric_vals.max() > 1:
                    is_bus = True
            except ValueError:
                is_bus = True

            if not is_bus:
                y = pd.to_numeric(val_series, errors='coerce').fillna(0).values
                ax.step(t_overview, y, where='post', color='#555555', linewidth=0.8)
                ax.set_ylim(-0.2, 1.2)
                ax.set_yticks([])
            else:
                ax.fill_between(t_overview, 0, 1, step='post', color='#cccccc', edgecolor='#666666', linewidth=0.5)
                ax.set_ylim(-0.2, 1.2)
                ax.set_yticks([])

            ax.axvspan(zoom_t_start, zoom_t_end, color='orange', alpha=0.35, edgecolor='orange', linewidth=1.5)
            ax.set_ylabel(col, rotation=0, ha='right', va='center', fontweight='bold', fontsize=10)

            if i < num_signals - 1:
                ax.set_xticks([])

        axes_top[0].set_title(f"OVERVIEW: Full Waveform Capture ({total_samples} samples)", fontsize=13, fontweight='bold', loc='left')
        axes_top[-1].set_xlabel("Time (ns)", fontsize=11, fontweight='bold')

        # --- Panel 2: Detailed Zoomed View ---
        for i, col in enumerate(signal_cols):
            ax = axes_bottom[i]
            val_series = df_zoomed[col]

            is_bus = False
            try:
                numeric_vals = pd.to_numeric(val_series)
                if numeric_vals.max() > 1:
                    is_bus = True
            except ValueError:
                is_bus = True

            if not is_bus:
                y = pd.to_numeric(val_series, errors='coerce').fillna(0).values
                ax.step(t_zoom, y, where='post', color='#1f77b4', linewidth=1.8)
                ax.set_ylim(-0.5, 1.6)
                ax.set_yticks([0, 1])
                ax.set_yticklabels(['0', '1'])

                # Detect transitions
                diffs = np.diff(y, prepend=y[0])
                rising_indices = np.where(diffs == 1)[0]
                falling_indices = np.where(diffs == -1)[0]

                # 1. Annotate '1' High State Durations & Rising Edges
                for r_idx in rising_indices:
                    t_rise = t_zoom[r_idx]

                    # Green arrow pointing UP at rising edge
                    ax.annotate(
                        '', 
                        xy=(t_rise, 1.05), 
                        xytext=(t_rise, 1.35),
                        arrowprops=dict(facecolor='green', edgecolor='green', arrowstyle='->', lw=1.8)
                    )

                    # Match with falling edge for High '1' bracket
                    f_candidates = falling_indices[falling_indices > r_idx]
                    if len(f_candidates) > 0:
                        f_idx = f_candidates[0]
                        t_fall = t_zoom[f_idx]
                        duration_ns = t_fall - t_rise
                        duration_clk = int(round(duration_ns / clk_period_ns))

                        t_mid = (t_rise + t_fall) / 2
                        
                        # RED Measurement bracket for '1'
                        ax.annotate(
                            '', 
                            xy=(t_rise, 1.25), 
                            xytext=(t_fall, 1.25),
                            arrowprops=dict(arrowstyle='<->', color='red', lw=1.2)
                        )
                        
                        if (t_fall - t_rise) > (time_span_zoom * 0.02):
                            ax.text(
                                t_mid, 1.32, 
                                f"HIGH: {duration_ns:.0f}ns ({duration_clk} clks)", 
                                ha='center', va='bottom', color='red', fontsize=8, fontweight='bold'
                            )

                # 2. Annotate '0' Low State Durations
                for f_idx in falling_indices:
                    t_fall = t_zoom[f_idx]

                    # Match with next rising edge for Low '0' bracket
                    r_candidates = rising_indices[rising_indices > f_idx]
                    if len(r_candidates) > 0:
                        r_next_idx = r_candidates[0]
                        t_next_rise = t_zoom[r_next_idx]
                        low_duration_ns = t_next_rise - t_fall
                        low_duration_clk = int(round(low_duration_ns / clk_period_ns))

                        t_low_mid = (t_fall + t_next_rise) / 2

                        # BLUE Measurement bracket for '0' (placed below y=0)
                        ax.annotate(
                            '', 
                            xy=(t_fall, -0.25), 
                            xytext=(t_next_rise, -0.25),
                            arrowprops=dict(arrowstyle='<->', color='#104E8B', lw=1.2)
                        )

                        if (t_next_rise - t_fall) > (time_span_zoom * 0.02):
                            ax.text(
                                t_low_mid, -0.42, 
                                f"LOW: {low_duration_ns:.0f}ns ({low_duration_clk} clks)", 
                                ha='center', va='top', color='#104E8B', fontsize=8, fontweight='bold'
                            )

            else:
                ax.fill_between(t_zoom, 0, 1, step='post', color='#e0e0e0', edgecolor='#333333', linewidth=0.8)
                ax.set_ylim(-0.2, 1.2)
                ax.set_yticks([])

                changes = val_series.ne(val_series.shift()).fillna(True)
                change_indices = np.where(changes)[0]

                for idx in range(len(change_indices)):
                    start_i = change_indices[idx]
                    end_i = change_indices[idx + 1] if idx + 1 < len(change_indices) else len(df_zoomed) - 1
                    
                    t_start = t_zoom[start_i]
                    t_end = t_zoom[end_i]
                    t_mid = (t_start + t_end) / 2
                    val_str = str(val_series.iloc[start_i])

                    if (t_end - t_start) > (time_span_zoom * 0.03):
                        ax.text(t_mid, 0.5, val_str, ha='center', va='center', fontsize=8, fontweight='bold')

            ax.set_ylabel(col, rotation=0, ha='right', va='center', fontweight='bold', fontsize=10)
            ax.grid(True, which='both', linestyle=':', alpha=0.5)

            if i < num_signals - 1:
                ax.set_xticks([])

        axes_bottom[0].set_title(f"ZOOMED DETAIL: Samples #{start_sample} to #{end_sample}", fontsize=13, fontweight='bold', loc='left')
        axes_bottom[-1].set_xlabel("Time (ns)", fontsize=11, fontweight='bold')

        # Top twin axis for cycle index
        ax_top = axes_bottom[0].twiny()
        ax_top.set_xlim(axes_bottom[0].get_xlim())
        ax_top.set_xlabel("Sample / Clock Cycle Index", fontsize=10, fontweight='bold')

        plt.suptitle("Vivado ILA Waveform Timing Analysis", fontsize=16, y=0.99, fontweight='bold')
        
        # Save exact 1920x1080 resolution
        plt.savefig(output_filename, dpi=100, bbox_inches='tight')
        plt.close(fig)
        print(f"[+] Saved standalone 1920x1080 diagram: {output_filename}")

# -------------------------------------------------------------------------
# Execution Configuration
# -------------------------------------------------------------------------
if __name__ == "__main__":
    # Define sample ranges to export: [(start_sample, window_length), ...]
    target_ranges = [
        (1000, 2500),   # Range 1 -> Exports as image1.png
        (15000, 3000)   # Range 2 -> Exports as image2.png
    ]

    export_zoomed_waveforms(
        csv_file='ila_captured_data.csv', 
        sample_ranges=target_ranges,
        clk_period_ns=10.0  # 10ns clock period (100MHz)
    )