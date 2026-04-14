#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET
from zipfile import ZipFile


NS_MAIN = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NS_REL = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
CELL_RE = re.compile(r"([A-Z]+)(\d+)")
OUTPUT_VECTOR_RE = re.compile(r"Output vector of size\s+(\d+)")


def to_float(raw: str | None, default: float = float("nan")) -> float:
    if raw is None:
        return default
    s = raw.strip()
    if not s:
        return default
    if s.lower() == "nan":
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return default


def finite(v: float) -> bool:
    return math.isfinite(v)


def col_to_num(col: str) -> int:
    out = 0
    for ch in col:
        out = out * 26 + (ord(ch) - 64)
    return out


def num_to_col(n: int) -> str:
    out = []
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out.append(chr(65 + rem))
    return "".join(reversed(out))


def parse_xlsx(path: Path) -> Dict[str, List[Dict[str, str]]]:
    with ZipFile(path) as zf:
        shared: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", NS_MAIN):
                shared.append("".join(t.text or "" for t in si.iterfind(".//a:t", NS_MAIN)))

        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

        out: Dict[str, List[Dict[str, str]]] = {}
        for sheet in wb.find("a:sheets", NS_MAIN):
            name = sheet.attrib["name"]
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = "xl/" + rel_map[rel_id]
            root = ET.fromstring(zf.read(target))
            rows: List[Dict[str, str]] = []
            for row in root.findall(".//a:sheetData/a:row", NS_MAIN):
                row_dict: Dict[str, str] = {}
                for cell in row.findall("a:c", NS_MAIN):
                    ref = cell.attrib.get("r", "")
                    m = CELL_RE.match(ref)
                    if not m:
                        continue
                    col = m.group(1)
                    cell_type = cell.attrib.get("t")
                    val_node = cell.find("a:v", NS_MAIN)
                    if val_node is None:
                        continue
                    raw = val_node.text or ""
                    if cell_type == "s":
                        idx = int(raw)
                        raw = shared[idx] if 0 <= idx < len(shared) else raw
                    row_dict[col] = raw
                if row_dict:
                    row_dict["_row"] = row.attrib.get("r", "")
                    rows.append(row_dict)
            out[name] = rows
        return out


def extract_bandwidth_sections(rows: Sequence[Dict[str, str]]) -> Dict[str, Dict[str, object]]:
    sections = {
        "Loopback Test (DRAM BW)": "loopback_peak_gbps",
        "Independent READ Test (DRAM BW)": "dram_read_peak_gbps",
        "Independent WRITE Test (DRAM BW)": "dram_write_peak_gbps",
        "SRAM Bandwidth for one core (Using Matmult)": "sram_matmul_peak_gbps",
    }
    found: Dict[str, Dict[str, object]] = {}
    idx = 0
    while idx < len(rows):
        row = rows[idx]
        title = row.get("B", "").strip()
        if title in sections:
            section_key = sections[title]
            data_idx = idx + 2
            best_val = float("nan")
            best_row: Optional[Dict[str, str]] = None
            while data_idx < len(rows):
                candidate = rows[data_idx]
                b = candidate.get("B", "").strip()
                h = to_float(candidate.get("H"))
                if b and not finite(to_float(b)):
                    break
                if finite(h) and (not finite(best_val) or h > best_val):
                    best_val = h
                    best_row = candidate
                data_idx += 1
            if best_row is not None:
                found[section_key] = {
                    "section_title": title,
                    "peak_value": best_val,
                    "unit": "GB/s",
                    "peak_row": int(best_row.get("_row", "0") or 0),
                    "label": best_row.get("B", ""),
                }
            idx = data_idx
            continue

        if title == "Aggregate Throughput":
            for offset in range(1, 4):
                if idx + offset >= len(rows):
                    break
                candidate = rows[idx + offset]
                label = candidate.get("B", "").strip()
                value = to_float(candidate.get("C"))
                if finite(value):
                    key = label.lower().replace("(", "").replace(")", "").replace(" ", "_")
                    found[key] = {
                        "section_title": title,
                        "peak_value": value,
                        "unit": "TFLOPS",
                        "peak_row": int(candidate.get("_row", "0") or 0),
                        "label": label,
                    }
        idx += 1
    return found


def extract_sheet_peak_gflops(sheet_name: str, rows: Sequence[Dict[str, str]]) -> Optional[Dict[str, object]]:
    header = rows[0] if rows else {}
    metric_col = None
    for col, val in header.items():
        if col.startswith("_"):
            continue
        if "GFLOPS" in str(val).upper() or "GIGAFLOP" in str(val).upper():
            metric_col = col
            break
    if metric_col is None:
        return None

    best_val = float("nan")
    best_row: Optional[Dict[str, str]] = None
    for row in rows[1:]:
        value = to_float(row.get(metric_col))
        if finite(value) and (not finite(best_val) or value > best_val):
            best_val = value
            best_row = row
    if best_row is None:
        return None
    return {
        "sheet_name": sheet_name,
        "peak_value": best_val,
        "unit": "GFLOPS",
        "peak_row": int(best_row.get("_row", "0") or 0),
        "label": sheet_name,
    }


def read_tt_summary(path: Path) -> Dict[str, Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {row["case"]: row for row in rows}


def infer_matmul_size(console_log: Path) -> Optional[int]:
    if not console_log.exists():
        return None
    text = console_log.read_text(encoding="utf-8", errors="ignore")
    m = OUTPUT_VECTOR_RE.search(text)
    if not m:
        return None
    total = int(m.group(1))
    root = int(round(math.sqrt(total)))
    if root * root == total:
        return root
    return None


def write_csv(rows: List[Dict[str, object]], out_path: Path) -> None:
    if not rows:
        return
    fieldnames = sorted({str(k) for row in rows for k in row.keys()})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def svg_escape(text: object) -> str:
    return html.escape(str(text))


def write_dual_metric_svg(
    rows: Sequence[Dict[str, object]],
    *,
    out_path: Path,
    title: str,
    left_label: str,
    right_label: str,
) -> None:
    if not rows:
        return

    left_max = max(float(row["workbook_peak_value"]) for row in rows)
    right_max = max(1.0, max(float(row["tt_sit_median"]) for row in rows))

    row_h = 54
    top = 92
    bottom = 54
    left_margin = 210
    panel_w = 340
    gap = 90
    width = left_margin + panel_w + gap + panel_w + 80
    height = top + row_h * len(rows) + bottom

    left_x0 = left_margin
    right_x0 = left_margin + panel_w + gap
    bar_h = 18

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2:.1f}" y="28" text-anchor="middle" font-family="sans-serif" font-size="20">{svg_escape(title)}</text>',
        f'<text x="{width/2:.1f}" y="46" text-anchor="middle" font-family="sans-serif" font-size="11">Context only: workbook throughput and TT SIT are different metrics and units.</text>',
        f'<text x="{left_x0 + panel_w/2:.1f}" y="58" text-anchor="middle" font-family="sans-serif" font-size="13">{svg_escape(left_label)}</text>',
        f'<text x="{right_x0 + panel_w/2:.1f}" y="58" text-anchor="middle" font-family="sans-serif" font-size="13">{svg_escape(right_label)}</text>',
        f'<line x1="{left_x0}" y1="{top - 8}" x2="{left_x0}" y2="{height - bottom}" stroke="#222"/>',
        f'<line x1="{right_x0}" y1="{top - 8}" x2="{right_x0}" y2="{height - bottom}" stroke="#222"/>',
    ]

    for i in range(5):
        x = left_x0 + panel_w * (i / 4.0)
        val = left_max * (i / 4.0)
        lines.append(f'<line x1="{x:.1f}" y1="{top - 8}" x2="{x:.1f}" y2="{height - bottom}" stroke="#efefef"/>')
        lines.append(f'<text x="{x:.1f}" y="{height - 20:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10">{val:.2f}</text>')
    for i in range(5):
        x = right_x0 + panel_w * (i / 4.0)
        val = right_max * (i / 4.0)
        lines.append(f'<line x1="{x:.1f}" y1="{top - 8}" x2="{x:.1f}" y2="{height - bottom}" stroke="#efefef"/>')
        lines.append(f'<text x="{x:.1f}" y="{height - 20:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10">{val:.2f}</text>')

    for idx, row in enumerate(rows):
        y = top + idx * row_h
        label = str(row["comparison_label"])
        workbook_value = float(row["workbook_peak_value"])
        sit_value = float(row["tt_sit_median"])

        lines.append(
            f'<text x="{left_margin - 12}" y="{y + 14:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{svg_escape(label)}</text>'
        )

        left_w = 0.0 if left_max <= 0.0 else panel_w * (workbook_value / left_max)
        right_w = 0.0 if right_max <= 0.0 else panel_w * (sit_value / right_max)

        lines.append(f'<rect x="{left_x0}" y="{y}" width="{left_w:.1f}" height="{bar_h}" fill="#1f77b4"/>')
        lines.append(f'<rect x="{right_x0}" y="{y}" width="{right_w:.1f}" height="{bar_h}" fill="#2ca02c"/>')
        lines.append(
            f'<text x="{left_x0 + left_w + 6:.1f}" y="{y + 13:.1f}" font-family="sans-serif" font-size="10">{workbook_value:.3f}</text>'
        )
        lines.append(
            f'<text x="{right_x0 + right_w + 6:.1f}" y="{y + 13:.1f}" font-family="sans-serif" font-size="10">{sit_value:.4f}</text>'
        )
        lines.append(
            f'<text x="{right_x0}" y="{y + 34:.1f}" font-family="sans-serif" font-size="10" fill="#555">case={svg_escape(row["case"])}</text>'
        )

    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    out_path: Path,
    *,
    reference_rows: Sequence[Dict[str, object]],
) -> None:
    lines: List[str] = []
    lines.append("# RISCVBench Workbook Reference Metrics")
    lines.append("")
    lines.append("Direct TT SIT vs workbook throughput comparison is intentionally omitted.")
    lines.append("")
    lines.append("- Workbook values are throughput references in `GB/s`, `GFLOPS`, or `TFLOPS`.")
    lines.append("- TT `sit_median` in the current TT pipeline is a normalized activity-style metric when `work_done` is absent, not a throughput metric.")
    lines.append("- Because the units and semantics differ, no direct validation chart is emitted here.")
    lines.append("")
    lines.append("## Reference Metrics")
    lines.append("")
    for row in reference_rows:
        lines.append(
            "- `{key}`: {label} = {value:.3f} {unit} (sheet/source: {source})".format(
                key=row["key"],
                label=row["label"],
                value=float(row["peak_value"]),
                unit=row["unit"],
                source=row["source_name"],
            )
        )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract RISCVBench workbook peak metrics and compare them side-by-side with TT SIT outputs."
    )
    ap.add_argument("--xlsx", default="RISCBench Numbers.xlsx", help="Path to RISCBench Numbers.xlsx")
    ap.add_argument(
        "--tt-summary",
        default="Phase-2/tt_doc_runs/20260313_044303/tt_doc_summary.csv",
        help="TT documentation summary CSV",
    )
    ap.add_argument(
        "--out-dir",
        default="Phase-2/tt_doc_runs/20260313_044303/riscvbench_compare",
        help="Output directory for comparison artifacts",
    )
    args = ap.parse_args()

    xlsx_path = Path(args.xlsx).resolve()
    tt_summary_path = Path(args.tt_summary).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stale_outputs = [
        out_dir / "tt_riscvbench_bandwidth_and_sit_context.svg",
        out_dir / "tt_riscvbench_compute_and_sit_context.svg",
        out_dir / "tt_vs_riscvbench_bandwidth_vs_sit.svg",
        out_dir / "tt_vs_riscvbench_compute_vs_sit.svg",
        out_dir / "tt_riscvbench_comparison.csv",
    ]
    for stale in stale_outputs:
        if stale.exists():
            stale.unlink()

    workbook = parse_xlsx(xlsx_path)
    tt_summary = read_tt_summary(tt_summary_path)

    reference_rows: List[Dict[str, object]] = []
    bandwidth_refs = extract_bandwidth_sections(workbook["Bandwidths"])
    for key, obj in sorted(bandwidth_refs.items()):
        reference_rows.append(
            {
                "key": key,
                "label": obj["label"],
                "peak_value": obj["peak_value"],
                "unit": obj["unit"],
                "source_name": obj["section_title"],
                "peak_row": obj["peak_row"],
            }
        )

    size_sheet_refs: Dict[int, Dict[str, object]] = {}
    for sheet_name in ["64x64 FLOPS", "128x128 FLOPS", "256x256 FLOPS", "512x512 FLOPS", "640", "768", "1024"]:
        peak = extract_sheet_peak_gflops(sheet_name, workbook.get(sheet_name, []))
        if peak is None:
            continue
        size_match = re.search(r"(\d+)", sheet_name)
        if size_match:
            size_sheet_refs[int(size_match.group(1))] = peak
        reference_rows.append(
            {
                "key": f"{sheet_name.lower().replace(' ', '_')}_peak_gflops",
                "label": sheet_name,
                "peak_value": peak["peak_value"],
                "unit": peak["unit"],
                "source_name": sheet_name,
                "peak_row": peak["peak_row"],
            }
        )

    comparison_rows: List[Dict[str, object]] = []

    def add_comparison(
        *,
        case: str,
        comparison_label: str,
        workbook_key: str,
        workbook_value: float,
        workbook_unit: str,
        note: str,
    ) -> None:
        row = tt_summary.get(case)
        if row is None:
            return
        comparison_rows.append(
            {
                "case": case,
                "comparison_label": comparison_label,
                "comparison_kind": "context_only_different_units",
                "workbook_key": workbook_key,
                "workbook_peak_value": workbook_value,
                "workbook_unit": workbook_unit,
                "tt_sit_median": float(row["sit_median"]),
                "tt_active_avg": float(row["residency_active_avg"]),
                "tt_stall_avg": float(row["residency_stall_avg"]),
                "tt_proxy_workload": row["proxy_workload"],
                "note": note,
            }
        )

    if "loopback_peak_gbps" in bandwidth_refs:
        ref = bandwidth_refs["loopback_peak_gbps"]
        add_comparison(
            case="tt_loopback",
            comparison_label="Loopback BW vs SIT",
            workbook_key="loopback_peak_gbps",
            workbook_value=float(ref["peak_value"]),
            workbook_unit=str(ref["unit"]),
            note="Direct loopback bandwidth reference from workbook.",
        )

    if "dram_read_peak_gbps" in bandwidth_refs:
        ref = bandwidth_refs["dram_read_peak_gbps"]
        add_comparison(
            case="tt_vecadd",
            comparison_label="Streaming Read Proxy vs SIT",
            workbook_key="dram_read_peak_gbps",
            workbook_value=float(ref["peak_value"]),
            workbook_unit=str(ref["unit"]),
            note="tt_vecadd is used as a read-like streaming proxy.",
        )

    if "dram_write_peak_gbps" in bandwidth_refs:
        ref = bandwidth_refs["dram_write_peak_gbps"]
        add_comparison(
            case="tt_vecadd",
            comparison_label="Streaming Write Proxy vs SIT",
            workbook_key="dram_write_peak_gbps",
            workbook_value=float(ref["peak_value"]),
            workbook_unit=str(ref["unit"]),
            note="Workbook write peak shown next to the same vecadd proxy; this is not a true write-only TT trace.",
        )

    for case in ("tt_matmul_single", "tt_matmul_multi"):
        summary_row = tt_summary.get(case)
        if summary_row is None:
            continue
        console_log = Path(summary_row["console_log"])
        size = infer_matmul_size(console_log)
        if size is None or size not in size_sheet_refs:
            continue
        ref = size_sheet_refs[size]
        add_comparison(
            case=case,
            comparison_label=f"Matmul {size}x{size} vs SIT ({case})",
            workbook_key=f"{size}x{size}_peak_gflops",
            workbook_value=float(ref["peak_value"]),
            workbook_unit=str(ref["unit"]),
            note=f"Matrix size inferred from console output vector size -> {size}x{size}.",
        )

    write_csv(reference_rows, out_dir / "riscvbench_reference_metrics.csv")
    write_report(
        out_dir / "report.md",
        reference_rows=reference_rows,
    )
    print(f"Wrote comparison artifacts to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
