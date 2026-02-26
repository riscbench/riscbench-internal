"""Utilities for converting phase 0 traces into SIT inputs."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Iterable


def parse_trace_csv(trace_csv: str | Path) -> Iterable[dict[str, str]]:
    """Parse a trace CSV file, skipping initial metadata lines.

    The trace CSV may include metadata lines (e.g., ARCH: ...) before the header.
    We scan until a header line containing both "core_x" and "core_y" is found.
    """

    trace_csv = Path(trace_csv)
    header_found = False
    remaining_lines: list[str] = []

    with trace_csv.open("r", newline="") as handle:
        for line in handle:
            if not header_found:
                if "core_x" in line and "core_y" in line:
                    header_found = True
                    remaining_lines.append(line)
                continue
            remaining_lines.append(line)

    if not header_found:
        raise ValueError(
            f"Unable to find a valid header containing 'core_x' and 'core_y' in {trace_csv}."
        )

    reader = csv.DictReader(io.StringIO("".join(remaining_lines)))
    return list(reader)
