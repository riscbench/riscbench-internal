# Adding A New Simulator

Use this checklist when adding a future simulator backend.

## 1. Add The Adapter

Start from:

- `sit_classifier/adapters/adapter_template.py`

Create:

- `sit_classifier/adapters/<simulator>_adapter.py`

Your adapter should emit:

- `state_df`: `start_us,end_us,core,state[,work_done]`
- `resid_df`: `start_us,end_us,core[,resident]`

## 2. Expose The Backend In The Orchestrator

Update:

- `device_handler/orchestrator.py`

Add the new backend to:

- `VALID_TARGETS`
- `FLAG_MAP` and any backend-specific flags
- `BACKEND_HANDLERS`
- simulator template expansion if it should auto-fan-out from TT
- prerequisite checks

## 3. Add Execution Logic

Update:

- `device_handler/backend_runner.py`

Add:

- CLI switches for the new simulator
- compile/run command construction
- adapter invocation
- summary metadata

## 4. Add Simulator Toolchain Support

If the simulator needs binary/path resolution or optional install support, update:

- `device_handler/simulator_toolchain_manager.py`

Add:

- resolve function
- optional install plan
- dispatch entry in `prepare_backend_toolchain()`

## 5. Document The Switches

Update:

- `README.md`

Add the simulator to:

- platform switch table
- simulator toolchain section if applicable
- usage examples if needed

## 6. Keep Compatibility

If you move code:

- keep root-level wrappers thin
- avoid putting real logic into root shims

## 7. Verify

At minimum run:

```bash
python3 -m py_compile \
  device_handler/backend_runner.py \
  device_handler/orchestrator.py \
  sit_classifier/adapters/<simulator>_adapter.py
```

Then validate:

```bash
python3 device_handler/orchestrator.py --check-only --skip-missing-tools ...
python3 device_handler/orchestrator.py --dry-run --skip-missing-tools --show-commands ...
```
