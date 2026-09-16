# Smart Koi Pond

Public engineering repository for the governed **Smart Koi Pond Closed-Loop IoT System**. Public visibility supports transparent inspection/review; write, merge, deployment, secrets, configuration and physical-control authority remain explicitly governed.

## Authority

This repository is the **engineering execution layer**. Durable project governance, safety direction, accepted architecture, validation boundaries and design decisions remain authoritative in Google Drive under:

`SMART_KOI_POND_CLOSED_LOOP_IOT_SYSTEM`

Mandatory read order before substantive work:
1. `00_READ_FIRST_SMART_KOI_POND_PROJECT_ROUTER`
2. `00_SMART_KOI_POND_CLOSED_LOOP_CONTROL_SYSTEM_HANDBOOK_ACTIVE.docx` — current V0.19
3. `90_SMART_KOI_POND_CURRENT_STATE_ACTIVE`
4. `90_SMART_KOI_POND_ACTIVE_PORTABLE_HANDOFF`
5. Relevant governed specification(s)
6. Latest validated `main` commit and exact CI/evidence

The Portable Handoff is continuity state only. It does not override the handbook or governed specifications.

## AI engineering responsibility — V0.19

The owner has reassigned the development workflow:

- **ChatGPT = PRIMARY SYSTEM ARCHITECT / IMPLEMENTER.** ChatGPT performs first-pass substantive engineering reasoning, promotes required governance, writes or modifies code and tests, prepares branch/PR changes, inspects exact-head evidence, corrects verified findings and synchronizes continuity after acceptance.
- **Claude = OPTIONAL INDEPENDENT REVIEWER / SECOND OPINION.** Claude may inspect a ChatGPT-authored exact head when requested or useful, but does not own primary implementation and is not a mandatory development dependency unless the owner explicitly makes Claude review a gate for a named change.
- Green CI is necessary but not sufficient. Acceptance requires current Drive authority, reproducible evidence and no unresolved authority/safety/evidence blocker.

This is a development workflow only. **Neither AI is part of the pond runtime.** Critical life-support remains deterministic and local; no AI service is required for real-time control, arbitration, verification, fail-safe operation or recovery.

See [`CHATGPT_START_HERE.md`](CHATGPT_START_HERE.md) for the primary implementer protocol and [`CLAUDE_START_HERE.md`](CLAUDE_START_HERE.md) for optional independent review.

## Runtime principle

The project implements one deterministic, inspectable closed loop:

`MEASURE -> VALIDATE -> ESTIMATE STATE -> CLASSIFY -> ACT -> VERIFY -> ESCALATE/RECOVER -> LOG`

The Digital Twin is production-intent engineering, not a disposable demo. The same domain model, state contracts, command arbitration, verification, event semantics, historian lineage, process models and operator workflow are intended to survive the transition from simulation to physical operation through validated adapters.

## Current product direction

Smart Koi Pond is an integrated koi-pond environmental regulation system. Normal owner operation is:

`sensor / simulation input -> pond condition -> automatic system response -> physical/modelled process effect -> verification -> recovery/escalation -> owner recommendation`

Manual ON/OFF equipment controls are secondary maintenance tools. The product must preserve healthy koi, biologically safe/stable water, clean/clear water, reliable life support, filtration/hydraulic health and evidence-backed owner operation without sacrificing biological safety for appearance.

Exact accepted main SHA, CI run, test count, artifacts and next work are maintained in governed Current State and ACTIVE Portable Handoff rather than duplicated here as stale checkpoints.

## Repository scope

The accepted production-intent software includes, within its governed capability boundaries:
- canonical Digital Twin pond/process simulation and simulation clock;
- virtual sensors/actuators and future real-adapter authority boundaries;
- sensor validation, state estimation/classification and deterministic control intents;
- command ownership, arbitration, interlocks and safe degradation;
- response verification, recovery/escalation and restart reconciliation;
- maintenance, calibration, water-change, filter-clean/backwash, shutdown and recovery workflows;
- alarm/incident evidence, append-only events, historian and playback;
- reconfigurable pond profile and route-aware hydraulic modeling;
- biological/environmental process modeling for explicit evidence-backed inputs;
- mechanical filtration, solids/filter loading, restriction and backwash evidence;
- source-water qualification and water-exchange mass balance;
- koi stock/biomass/feeding and water-quality recovery relationships;
- integrated owner operation and guided simulation testing;
- canonical runtime publication/API and state-bound browser application;
- vendor-neutral deployment and Windows packaging;
- deterministic tests, fault/regression matrices, CI and machine-readable evidence.

## Engineering truth and evidence rules

- Missing facts remain explicit as `UNKNOWN`, `INPUT_REQUIRED`, `UNAVAILABLE` or another governed absence state; do not invent values merely to complete a screen/calculation.
- Quantitative inputs/outputs retain provenance such as user-configured scenario input, datasheet/manual data, governed calculation, measurement or calibration.
- A command, device feedback state, animation or UI indicator is not proof of process recovery; material effects require governed process verification.
- UI/browser is a projection/client of canonical runtime truth and must not create a second control engine, hidden threshold set, independent calculator or parallel state store.
- Calculated hardware requirements/capacity guidance are advisory; do not declare real hardware defective, oversized, undersized or upgrade-required without supporting evidence.
- TSS, turbidity and visual clarity remain distinct evidence domains.

## Safety and anti-drift rules

- Critical life-support control remains local and deterministic.
- AI/cloud features cannot silently override the safety controller.
- Unknown/unavailable evidence is never converted to zero/healthy/success.
- Planned OFF, maintenance, calibration, filter-clean/backwash, water-change and shutdown states are distinct from unexpected failure.
- Command ownership is explicit; AUTO must not fight authorized MANUAL/MAINTENANCE ownership.
- Return to AUTO requires fresh-state validation and controlled re-synchronization.
- Real actuator authority remains CLOSED unless separately authorized through Site Integration & Commissioning evidence.
- High-risk automatic chemical dosing remains CLOSED unless separately validated, governed and commissioned.
- Final production engineering setpoints are not frozen by UI examples or simulation defaults.
- Unsupported numeric thresholds, timeout values, retry limits or safety parameters must not be invented merely to complete implementation.
- Durable changes to behavior, safety, modes, dependencies, recovery, deployment, persistence, UI-control semantics or acceptance must be promoted into Drive authority/specifications before or with implementation.

## Development workflow

`main` represents the accepted engineering baseline. Ordinary material changes follow:

`OWNER REQUIREMENT / GOVERNED OPEN ITEM`
→ ChatGPT reads current Drive authority + accepted main
→ ChatGPT designs/governs/implements on isolated branch/PR
→ automated lint/tests/evidence/package gates
→ ChatGPT performs an evidence-backed exact-head self-audit
→ optional Claude independent second opinion when requested/useful
→ ChatGPT corrects verified findings and reruns validation
→ only a validated head with no unresolved authority/safety/evidence blocker is promoted
→ Current State + ACTIVE Portable Handoff are refreshed.

Claude review is optional unless the owner explicitly requires it for a named change.

## Repository isolation

This repository is exclusively for **Smart Koi Pond**. A1 CLEAN/trading repositories, datasets, credentials, runners, automations and execution environments remain outside this repository's authority and must not be coupled as a workaround.

## Virtual Pond deployment

GitHub remains source-code/versioning/CI/evidence. The accepted Virtual Pond is a browser application served by a host/server environment.

Security/deployment boundaries:
- direct-host bind defaults to `127.0.0.1`;
- public/remote exposure requires a separately governed authenticated/authorized supervisory boundary and TLS;
- the built-in application server must not be exposed directly as a privileged public endpoint;
- historian/runtime state remains persistent runtime data rather than baked into images;
- real secrets stay outside source/image context;
- packaged development remains explicitly `SIMULATION / NO REAL DEVICE CONTROL` until physical authority is separately commissioned.

See [`docs/VIRTUAL_POND_DEPLOYMENT_V1.md`](docs/VIRTUAL_POND_DEPLOYMENT_V1.md) for deployment boundaries.

## Virtual-to-physical continuity

The same production-intent software progresses without rebuilding the control brain:

`PRODUCTION SOFTWARE / SIMULATION -> OPTIONAL RISK-DRIVEN HIL / BENCH / PILOT / SHADOW AS NEEDED -> SITE INTEGRATION & COMMISSIONING -> SEPARATELY AUTHORIZED LIMITED_LIVE -> FULL_LIVE`

Software/SIL or Virtual Pond PASS is not physical certification. Real sensor/actuator integration replaces or augments validated adapters and evidence sources while retaining canonical control semantics.

## Layout

```text
src/smart_koi_pond/
  domain/          # governed state vocabulary and canonical process projection
  digital_twin/    # pond/hydraulic/biology/filtration/runtime/scenarios
  sensors/         # virtual/real sensor interfaces and validation
  actuators/       # virtual/real actuator interfaces and authority boundaries
  control/         # deterministic decisions, modes, arbitration and verification
  scenarios/       # scenario/fault execution and evidence matrices
  events/          # events, alarms/incidents, historian and replay
  dashboard/       # canonical runtime service, API and state-bound browser UI
config/            # governed schemas; no ad-hoc safety values
scenarios/         # reproducible scenario definitions/replay inputs
tests/             # unit/integration/fault/regression tests
docs/              # engineering references derived from Drive authority
Dockerfile          # vendor-neutral packaging
```
