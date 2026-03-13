# Phase-0

Phase-0 contains the Tenstorrent prototype source tree restored from `internal/main`.

- prototype root: [`Prototype-Tenstorrent/`](Prototype-Tenstorrent)
- instructions: [`Prototype-Tenstorrent/README.txt`](Prototype-Tenstorrent/README.txt)
- workloads: `fm_loopback/`, `fm_mm/`, `fm_read/`, `fm_write/`
- helpers: [`Prototype-Tenstorrent/looper.py`](Prototype-Tenstorrent/looper.py), [`Prototype-Tenstorrent/Bucketized performance generator.py`](Prototype-Tenstorrent/Bucketized%20performance%20generator.py)

The shared Phase-0 Tenstorrent calibration notes, commands, evaluation snapshot, and baseline image live in [`../docs/PHASE0_TENSTORRENT_BASELINE.md`](../docs/PHASE0_TENSTORRENT_BASELINE.md).

For the cross-phase Phase-0 parity path:

- converter carried into Phase-1: [`../Phase-1/phase0_trace_to_sit.py`](../Phase-1/phase0_trace_to_sit.py)
- strict parity gate: [`../Phase-1/tests/check_phase0_parity.py`](../Phase-1/tests/check_phase0_parity.py)
- cross-phase validation commands: [`../docs/ALL_TARGETS_VALIDATION_COMMANDS.md`](../docs/ALL_TARGETS_VALIDATION_COMMANDS.md)
