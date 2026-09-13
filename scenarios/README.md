# Scenarios

Scenario definitions and replay inputs for the governed Digital Twin live here.

Initial scenario families will include normal operation, heat wave, low DO, pump/flow degradation, sensor faults, maintenance/manual operation, water change, filter cleaning, partial shutdown, safe total shutdown, blackout/restart recovery and combined faults.

Every executable scenario must preserve:

- initial state
- fault/event onset time
- controller detection time
- action timeline
- verification window
- recovery/end state or unresolved status
- reproducible inputs
- PASS/HOLD result against explicit acceptance criteria

Scenario content must be derived from the governed functional specification; this directory is not authority for inventing new safety behavior.
