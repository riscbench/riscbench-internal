## Development Phases and Alignment

RISCBench development follows a phased roadmap with **Phase 1 (SIT Engine core)** as the center of gravity.

Before contributing to simulator adapters, kernels, or extensions, contributors **must review the Phase 1 and Phase 2 Alignment Guide**:

➡️ [PHASE1_PHASE2_ALIGNMENT.md](./PHASE1_PHASE2_ALIGNMENT.md)

All contributions are expected to:
- Respect Phase 1 as the single source of truth for SIT computation
- Route simulator and platform work through the Phase 1 engine APIs
- Preserve schema discipline and golden-trace validation

Pull requests that diverge from this alignment may be asked to revise before review.
