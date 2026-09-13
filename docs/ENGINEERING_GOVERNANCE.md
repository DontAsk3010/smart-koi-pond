# Engineering Governance

## Authority boundary

Google Drive is the durable project authority. This GitHub repository implements accepted specifications and stores executable engineering work, tests and reproducible evidence.

Before substantive changes, read the active Drive router, handbook and current-state checkpoint.

## Mandatory promotion gate

A change that alters system behavior, safety, operating modes, degradation, recovery, dependency handling, automation, UI control semantics or validation criteria is not accepted merely because code exists. The corresponding governed Drive authority/specification must be updated first or as part of the same approved change cycle.

## Safety boundary

- Local deterministic life-support control has priority over cloud/AI convenience.
- Invalid, stale, unavailable or unknown sensor state must never be interpreted as zero or healthy.
- Planned unavailability and unexpected failure are different states.
- Manual operation and maintenance must have explicit command ownership and must not silently conflict with AUTO.
- Return to AUTO requires fresh-state validation and controlled re-synchronization.
- Safe partial shutdown and safe total shutdown must be explicit operating modes.
- Higher-risk automatic chemistry remains disabled until separately validated and authorized.

## Repository isolation

This repository is isolated from all stock-market / A1 CLEAN repositories. It must not import their code, reuse their secrets, share their workflow assumptions, or modify their branches/data.

## Change discipline

- `main` is the accepted baseline.
- New behavior should arrive through small, reviewable changes with tests.
- Every scenario or regression failure must be reproducible from saved inputs.
- A passing UI is not evidence of safe behavior; controller state, events, commands and measured/simulated response must agree.
- Known model limitations must be explicit.
