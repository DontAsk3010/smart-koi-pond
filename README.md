# Smart Koi Pond

Private engineering repository for the governed **Smart Koi Pond Closed-Loop IoT System**.

## Authority

This repository is the **engineering execution layer**. Project governance, safety direction, accepted architecture and durable design decisions remain authoritative in the Google Drive project:

`SMART_KOI_POND_CLOSED_LOOP_IOT_SYSTEM`

Read order before substantive changes:

1. `00_READ_FIRST_SMART_KOI_POND_PROJECT_ROUTER`
2. `00_SMART_KOI_POND_CLOSED_LOOP_CONTROL_SYSTEM_HANDBOOK_ACTIVE.docx`
3. `90_SMART_KOI_POND_CURRENT_STATE_ACTIVE`
4. Relevant subsystem specification and latest validated checkpoint

## Current phase

**Simulation-first Digital Twin engineering.**

The project is building a deterministic, inspectable closed-loop system that follows:

`MEASURE -> VALIDATE -> ESTIMATE STATE -> CLASSIFY -> ACT -> VERIFY -> ESCALATE/RECOVER -> LOG`

The Digital Twin is part of the real engineering program, not a disposable demo. It is used to verify system behavior before broad hardware purchasing.

## Repository scope

- Digital Twin and pond-state simulation
- virtual sensors and virtual actuators
- deterministic control/state-machine implementation
- operational modes and safe degradation
- scenario and fault-injection engine
- event logging and incident replay
- dashboard and engineering/operator UI
- automated tests, CI and regression validation

## Safety and anti-drift rules

- Critical life-support control must remain local and deterministic.
- AI/cloud features must not silently override the safety controller.
- Planned OFF, maintenance, calibration and shutdown states are not automatically failures.
- One unavailable subsystem must not cause uncontrolled cascades in unrelated subsystems.
- Return to AUTO requires fresh-state validation and controlled re-synchronization.
- Chemical dosing remains disabled until separately validated and governed.
- Final engineering setpoints are not defined in this repository until they are frozen by the governing project authority.
- Durable changes to system behavior, safety, modes, dependencies, recovery, UI control semantics or validation must first be promoted into the governed authority/specification.

## Isolation

This repository is separate from all stock-market / A1 CLEAN repositories. Trading repositories, workflows, data, secrets and runners are out of scope.

## Initial layout

```text
src/smart_koi_pond/
  domain/          # governed state vocabulary and core types
  digital_twin/    # pond process model
  sensors/         # virtual/real sensor interfaces and validation
  actuators/       # virtual/real actuator interfaces
  control/         # deterministic state machine and interlocks
  scenarios/       # scenario/fault execution
  events/          # event model, logging, replay
  dashboard/       # UI/API integration
config/            # governed configuration schemas; no ad-hoc safety values
scenarios/         # scenario definitions and replay inputs
tests/             # unit/integration/fault/regression tests
docs/              # engineering notes derived from Drive authority
```

## Development rule

`main` represents the accepted engineering baseline. New behavior should be implemented through reviewed, testable changes with reproducible evidence.
