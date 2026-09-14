# Smart Koi Pond

Private engineering repository for the governed **Smart Koi Pond Closed-Loop IoT System**.

## Authority

This repository is the **engineering execution layer**. Project governance, safety direction, accepted architecture, validation boundaries, and durable design decisions remain authoritative in the Google Drive project:

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

**Production-intent Digital Twin fidelity is accepted through integrated hydraulics, biology/environment, mechanical filtration, and governed fault/recovery. The next product-integration milestone is one concrete Integrated Virtual Pond runtime/browser experience driven by the same canonical state, followed later by separately governed physical HIL/bench/shadow validation.**

The project is building a deterministic, inspectable closed-loop system that follows:

`MEASURE -> VALIDATE -> ESTIMATE STATE -> CLASSIFY -> ACT -> VERIFY -> ESCALATE/RECOVER -> LOG`

The Digital Twin is production-intent engineering, not a disposable demo. The same domain model, state contracts, command arbitration, verification, event semantics, historian lineage, process models, and operator workflow are intended to survive the path from simulation to physical operation through validated adapters.

Current accepted software scope includes the validated Digital Twin core, modular capability platform, state-bound animated process projection, Simulation Exit/SIL evidence, source/authority adapters, virtual fault/recovery, reconfigurable pond/hydraulic profiles, integrated biological/environmental process behavior, and mechanical filtration/waste/sludge/filter-loading fidelity. Exact accepted commit, CI run, test count, evidence lanes, and next work are maintained in the governed Current State and ACTIVE Portable Handoff rather than duplicated here as a competing checkpoint.

## Repository scope

- canonical Digital Twin pond-state and process simulation
- reconfigurable pond profile and route-aware hydraulic modeling
- biological/environmental process modeling for explicit configured inputs
- mechanical filtration, solids capture, filter loading, restriction, backwash, and evidence-bound TSS/turbidity state
- virtual sensors and virtual actuators
- deterministic control/state-machine implementation
- operating modes, command ownership, interlocks, and safe degradation
- maintenance, calibration, water-change, filter-clean/backwash, shutdown, and recovery workflows
- blackout recovery and dependency-aware return-to-auto re-synchronization
- governed scenario and fault-injection engine
- source/authority boundaries for future virtual/real adapter transition
- event logging, alarm/incident evidence, historian, and playback
- canonical runtime publication, API, and state-bound browser UI integration
- automated tests, CI, regression matrices, and machine-readable evidence artifacts

## Engineering truth and evidence rules

- Missing engineering facts remain explicit as `UNKNOWN`, `INPUT_REQUIRED`, `UNAVAILABLE`, or the applicable governed absence state; they are not filled with synthetic values merely to complete a screen or calculation.
- Quantitative inputs and outputs must retain traceable provenance such as user-configured scenario input, datasheet/manual data, governed calculation, measurement, or calibration as applicable.
- Engineering quantities use SI/metric conventions appropriate for Indonesia; domain-standard water-quality units such as mg/L, ppm, pH, and mg/L as CaCO3 remain where applicable.
- Calculated system requirements and capacity guidance are advisory. The software must not conclude that real hardware is faulty, oversized, undersized, or requires upgrade without supporting evidence.
- TSS, turbidity, and visual clarity are distinct evidence domains. A modeled or measured value in one domain does not automatically certify another.
- A command, device feedback state, animation, or UI indicator is not proof of process recovery; material effects must be verified through the governed process/evidence chain.

## Safety and anti-drift rules

- Critical life-support control must remain local and deterministic.
- AI/cloud features must not silently override the safety controller.
- Planned OFF, maintenance, calibration, filter-clean/backwash, water-change, and shutdown states are not automatically failures.
- One unavailable subsystem must not cause uncontrolled cascades in unrelated subsystems.
- Command ownership is explicit; automatic logic must not fight authorized manual/maintenance ownership.
- Return to AUTO requires fresh-state validation and controlled re-synchronization.
- Real actuator authority remains closed unless separately authorized through the governed validation ladder.
- Chemical dosing remains disabled until separately validated and governed.
- Final production engineering setpoints are not frozen by software examples or virtual configuration values.
- Durable changes to system behavior, safety, modes, dependencies, recovery, deployment, UI control semantics, or validation must be promoted into governed Drive authority/specifications.

## Repository isolation

This repository is exclusively dedicated to the **Smart Koi Pond Closed-Loop IoT System**. External projects and unrelated workflows, datasets, credentials, secrets, runners, automations, and execution environments are outside this repository's authority and scope.

## Virtual-to-physical lineage

The intended lineage is progressive rather than a rebuild:

`DIGITAL TWIN / SIMULATION -> HIL -> BENCH / SMALL-TANK -> REAL-POND SHADOW / READ-ONLY -> SEPARATELY AUTHORIZED CONTROLLED AUTOMATION`

Physical validation is a separate evidence layer. Software/SIL PASS is not physical certification, and the absence of current hardware does not authorize invented physical facts.

## Layout

```text
src/smart_koi_pond/
  domain/          # governed state vocabulary, canonical process projection, and core types
  digital_twin/    # pond, hydraulic, biology/environment, filtration, clock, runtime, scenarios
  sensors/         # virtual/real sensor interfaces and validation
  actuators/       # virtual/real actuator interfaces and authority boundaries
  control/         # deterministic decisions, operating modes, arbitration/interlocks, verification
  scenarios/       # scenario/fault execution and evidence matrices
  events/          # event model, logging, alarms/incidents, historian, replay
  dashboard/       # canonical runtime service, API, and state-bound browser UI
config/            # governed configuration schemas; no ad-hoc safety values
scenarios/         # scenario definitions and replay inputs
tests/             # unit/integration/fault/regression tests
docs/              # engineering references derived from Drive authority
```

## Development rule

`main` represents the accepted engineering baseline. Material behavior changes are developed on an isolated branch/PR and promoted only after the relevant automated tests and evidence lanes pass. Failed or missing critical regression blocks promotion.

The browser/visual layer must remain a projection of canonical runtime truth. It must not create a second control engine, fabricate missing values, or display decorative success that is unsupported by process state and verification evidence.
