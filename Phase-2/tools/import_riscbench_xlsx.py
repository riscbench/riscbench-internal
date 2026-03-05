#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from zipfile import ZipFile
import xml.etree.ElementTree as ET


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _col_to_idx(col: str) -> int:
    out = 0
    for ch in col:
        if "A" <= ch <= "Z":
            out = out * 26 + (ord(ch) - 64)
    return out - 1


def _cell_text(cell: ET.Element, shared: Sequence[str]) -> str:
    t = cell.attrib.get("t")
    v = cell.find("main:v", NS)
    is_elem = cell.find("main:is", NS)
    if t == "s" and v is not None and v.text is not None:
        idx = int(v.text)
        if 0 <= idx < len(shared):
            return shared[idx]
        return ""
    if t == "inlineStr" and is_elem is not None:
        return "".join((n.text or "") for n in is_elem.findall(".//main:t", NS))
    if v is not None and v.text is not None:
        return v.text
    return ""


def _read_shared_strings(zf: ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    shared = []
    for si in shared_root.findall("main:si", NS):
        txt = "".join((n.text or "") for n in si.findall(".//main:t", NS))
        shared.append(txt)
    return shared


def load_workbook_tables(xlsx_path: Path) -> Dict[str, List[List[str]]]:
    tables: Dict[str, List[List[str]]] = {}
    with ZipFile(xlsx_path) as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_map: Dict[str, str] = {}
        for rel in rels.findall("pkgrel:Relationship", NS):
            rel_map[rel.attrib["Id"]] = rel.attrib["Target"]

        shared = _read_shared_strings(zf)
        sheets = wb.find("main:sheets", NS)
        if sheets is None:
            return tables

        for sheet in sheets.findall("main:sheet", NS):
            name = sheet.attrib.get("name", "")
            rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            if rid is None:
                continue
            target = rel_map.get(rid, "")
            if not target:
                continue
            if not target.startswith("/"):
                target = "xl/" + target
            root = ET.fromstring(zf.read(target))
            rows: List[Dict[int, str]] = []
            max_col = -1
            for row in root.findall(".//main:sheetData/main:row", NS):
                vals: Dict[int, str] = {}
                for cell in row.findall("main:c", NS):
                    ref = cell.attrib.get("r", "")
                    m = re.match(r"([A-Z]+)([0-9]+)", ref)
                    if not m:
                        continue
                    col_idx = _col_to_idx(m.group(1))
                    txt = _cell_text(cell, shared).strip()
                    if txt != "":
                        vals[col_idx] = txt
                        if col_idx > max_col:
                            max_col = col_idx
                if vals:
                    rows.append(vals)
            if not rows:
                tables[name] = []
                continue
            width = max_col + 1
            dense_rows: List[List[str]] = []
            for vals in rows:
                dense = ["" for _ in range(width)]
                for col_idx, txt in vals.items():
                    dense[col_idx] = txt
                dense_rows.append(dense)
            tables[name] = dense_rows
    return tables


def _to_float(s: str) -> Optional[float]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _stats(values: Sequence[float]) -> Dict[str, float]:
    vals = [float(v) for v in values]
    if not vals:
        return {"count": 0, "min": float("nan"), "median": float("nan"), "max": float("nan"), "mean": float("nan")}
    return {
        "count": len(vals),
        "min": min(vals),
        "median": statistics.median(vals),
        "max": max(vals),
        "mean": statistics.fmean(vals),
    }


def extract_flops_metrics(tables: Dict[str, List[List[str]]]) -> Tuple[List[int], Dict[str, Dict[str, float]]]:
    dims: List[int] = []
    out: Dict[str, Dict[str, float]] = {}

    for sheet_name, rows in tables.items():
        m_square = re.match(r"^\s*(\d+)\s*x\s*(\d+)\s*FLOPS\s*$", sheet_name, flags=re.IGNORECASE)
        m_dim = re.match(r"^\s*(\d+)\s*$", sheet_name)
        dim = None
        if m_square and m_square.group(1) == m_square.group(2):
            dim = int(m_square.group(1))
        elif m_dim:
            dim = int(m_dim.group(1))
        if dim is None:
            continue

        dims.append(dim)
        gflops_col = None
        for row in rows[:10]:
            for idx, cell in enumerate(row):
                if cell.strip().upper() == "GFLOPS":
                    gflops_col = idx
                    break
            if gflops_col is not None:
                break
        if gflops_col is None:
            continue

        vals: List[float] = []
        for row in rows:
            if gflops_col >= len(row):
                continue
            v = _to_float(row[gflops_col])
            if v is None:
                continue
            if v <= 0:
                continue
            vals.append(v)

        out[str(dim)] = _stats(vals)

    dims_sorted = sorted(set(dims))
    return dims_sorted, out


def extract_bandwidth_metrics(tables: Dict[str, List[List[str]]]) -> Dict[str, Dict[str, float]]:
    rows = tables.get("Bandwidths", [])
    if not rows:
        return {}

    # Detect table blocks from title row followed by a header row containing "Bandwidth (GB/s)".
    metrics: Dict[str, Dict[str, float]] = {}
    i = 0
    while i < len(rows):
        row = rows[i]
        title = row[1].strip() if len(row) > 1 else ""
        if title and i + 1 < len(rows):
            hdr = rows[i + 1]
            gbps_col = None
            for idx, name in enumerate(hdr):
                if name.strip().upper() == "BANDWIDTH (GB/S)":
                    gbps_col = idx
                    break
            if gbps_col is not None:
                vals: List[float] = []
                j = i + 2
                while j < len(rows):
                    r = rows[j]
                    first = r[1].strip() if len(r) > 1 else ""
                    if first and not _to_float(first):
                        break
                    if gbps_col < len(r):
                        v = _to_float(r[gbps_col])
                        if v is not None and v > 0:
                            vals.append(v)
                    j += 1
                key = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
                metrics[key] = _stats(vals)
                i = j
                continue
        i += 1
    return metrics


def build_reference_payload(xlsx_path: Path, required_phase1_trace: str) -> Dict[str, object]:
    tables = load_workbook_tables(xlsx_path)
    dims, flops = extract_flops_metrics(tables)
    bandwidth = extract_bandwidth_metrics(tables)

    payload: Dict[str, object] = {
        "schema_version": 1,
        "source": {
            "xlsx_path": str(xlsx_path.resolve()),
            "xlsx_sha256": sha256_file(xlsx_path),
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "sheet_names": sorted(tables.keys()),
        },
        "phase1": {
            "required_trace_file": required_phase1_trace,
            "required_parity_fixture_trace_file": required_phase1_trace,
        },
        "phase2": {
            "required_dims": dims,
            "flops_gflops_stats_by_dim": flops,
            "bandwidth_gbps_stats": bandwidth,
        },
    }
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Import RISCBench Numbers.xlsx into pinned JSON reference.")
    ap.add_argument("--xlsx", required=True, help="Path to RISCBench Numbers.xlsx")
    ap.add_argument(
        "--out",
        default="Phase-2/datasets/reference/riscvbench_reference.v1.json",
        help="Output JSON path",
    )
    ap.add_argument(
        "--phase1-required-trace",
        default="datasets/traces/trace_F_phase0_wormhole_sample.csv",
        help="Phase-1 parity trace path used as required reference key",
    )
    args = ap.parse_args()

    xlsx_path = Path(args.xlsx).resolve()
    if not xlsx_path.exists():
        raise SystemExit("xlsx not found: %s" % xlsx_path)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_reference_payload(
        xlsx_path=xlsx_path,
        required_phase1_trace=str(args.phase1_required_trace),
    )
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("wrote reference json:", out_path)
    print("phase2 required dims:", payload["phase2"]["required_dims"])  # type: ignore[index]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
