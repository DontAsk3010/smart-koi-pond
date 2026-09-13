# Smart Koi Pond

Private engineering repository for the governed **Smart Koi Pond Closed-Loop IoT System**.

## Authority

This repository is the **engineering execution layer**. Project governance, safety direction, accepted architecture and durable design decisions remain authoritative in the Google Drive project:

`SMART_KOI_POND_CLOSED_LOOP_IOT_SYSTEM`

Mandatory read order before substantive changes:

1. `00_READ_FIRST_SMART_KOI_POND_PROJECT_ROUTER`
2. `00_SMART_KOI_POND_CLOSED_LOOP_CONTROL_SYSTEM_HANDBOOK_ACTIVE.docx`
3. `90_SMART_KOI_POND_CURRENT_STATE_ACTIVE`
4. `90_SMART_KOI_POND_ACTIVE_PORTABLE_HANDOFF`
5. Relevant governed specification(s)
6. Latest validated `main` commit and CI evidence

The portable handoff is continuity state only. It does not override the handbook or governed specifications.

## Current phase

**Executable Digital Twin Core V1 -> operating-mode expansion -> live runtime/UI integration.**

The project is building a deterministic, inspectable closed-loop system that follows:

`MEASURE -> VALIDATE -> ESTIMATE STATE -> CLASSIFY -> ACT -> VERIFY -> ESCALATE/RECOVER -> LOG`

The Digital Twin is production-intent engineering, not a disposable demo. The same domain model, state contracts, command arbitration, verification, event semantics and operator workflow are intended to survive the path from simulation to physical operation through validated adapters.

## Repository scope

- Digital Twin and pond-state simulation
- virtual sensors and virtual actuators
- deterministic control/state-machine implementation
- operating modes, command ownership and safe degradation
- maintenance, calibration, water-change, filter-clean and shutdown workflows
- blackout recovery and dependency-aware return-to-auto re-synchronization
- scenario and fault-injection engine
- event logging and incident replay
- runtime publication contracts and later live dashboard integration
- automated tests, CI and regression validation

## Safety and anti-drift rules

- Critical life-support control must remain local and deterministic.
- AI/cloud features must not silently override the safety controller.
- Planned OFF, maintenance, calibration and shutdown states are not automatically failures.
- One unavailable subsystem must not cause uncontrolled cascades in unrelated subsystems.
- Command ownership is explicit; automatic logic must not fight authorized manual/maintenance ownership.
- Return to AUTO requires fresh-state validation and controlled re-synchronization.
- A command or device feedback state is not proof of process recovery; material effects must be verified.
- Chemical dosing remains disabled until separately validated and governed.
- Final engineering setpoints are not defined in this repository until frozen by governing project authority.
- Durable changes to system behavior, safety, modes, dependencies, recovery, deployment, UI control semantics or validation must be promoted into governed Drive authority/specifications.

## Isolation

This repository is separate from all stock-market / A1 CLEAN repositories. Trading repositories, workflows, data, secrets and runners are out of scope.

## Layout

```text
src/smart_koi_pond/
  domain/          # governed state vocabulary and core types
  digital_twin/    # pond process model and runtime
  sensors/         # virtual/real sensor interfaces and validation
  actuators/       # virtual/real actuator interfaces
  control/         # deterministic decisions, operating modes, arbitration/interlocks
  scenarios/       # scenario/fault execution
  events/          # event model, logging, replay
  dashboard/       # UI/API integration
config/            # governed configuration schemas; no ad-hoc safety values
scenarios/         # scenario definitions and replay inputs
tests/             # unit/integration/fault/regression tests
docs/              # engineering references derived from Drive authority
```

## Development rule

`main` represents the accepted engineering baseline. Material behavior changes are developed on an isolated branch/PR and promoted only after the relevant automated tests pass. A failed or missing critical regression blocks promotion.
