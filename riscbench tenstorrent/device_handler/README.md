# Device Handler

This layer owns orchestration and backend execution.

Main files:

- `orchestrator.py`: public orchestration logic
- `backend_runner.py`: per-backend execution path
- `simulator_toolchain_manager.py`: simulator path resolution and optional install support

Responsibilities:

- target selection
- TT input resolution
- simulator fan-out
- toolchain discovery
- command construction
- run logging

This layer consumes TT profiler outputs and forwards normalized backend runs into the SIT classifier layer.
