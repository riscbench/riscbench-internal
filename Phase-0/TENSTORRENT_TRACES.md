# Tenstorrent Wormhole Traces

This note captures what Phase-0 means in practice for Tenstorrent/Wormhole traces and how it relates to the restored [`Prototype-Tenstorrent/`](Prototype-Tenstorrent) subtree.

## Input Files

The adapter expects the profiler pair below:

- `profile_log_device.csv`
- `zone_src_locations.log`

These files are parsed by [`adapters/tt_wormhole_adapter.py`](adapters/tt_wormhole_adapter.py).

## Adapter Behavior

The Phase-0 adapter:

- reads TT profiler events and zone mappings
- pairs `ZONE_START` / `ZONE_END` events into intervals
- preserves deterministic same-cycle ordering
- converts cycles into microseconds using the chip frequency header
- derives normalized state and residency intervals for the SIT ingest contract

## Documentation Suite

The local Wormhole documentation suite can be run with [`tools/run_tt_wormhole_doc_suite.py`](tools/run_tt_wormhole_doc_suite.py). In the current workspace, the generated report shows TT cases such as:

- `tt_loopback`
- `tt_matmul_single`
- `tt_matmul_multi`
- `tt_sfpu_chain`
- `tt_vecadd`
- `tt_noc_transfer`

## Downstream Usage

- `Prototype-Tenstorrent/` provides the original TT program examples.
- Phase-1 uses the Wormhole-derived parity trace and parity checks to lock semantics.
- Phase-2 uses the same normalized contract for engine execution and report generation.
