## Contribution gate. Required reading before PRs

Before opening any pull request that touches Phase-0, Phase-1, or Phase-2, you must read these documents

- Phase-0 semantic anchor  
  `Phase-0/README.md`

- Phase-1 generalization mapping  
  `Phase-1/GENERALIZATION.md`

### PR checklist. must be completed

- I read the Phase-0 README and I understand residency-gated SIT semantics
- I read the Phase-1 Generalization Note and I am not changing SIT meaning
- My change does not implement a second SIT engine
- Any schema change is versioned or placed under a versioned extensions namespace
- If I changed behavior, I updated golden traces and invariant tests or explained why not
