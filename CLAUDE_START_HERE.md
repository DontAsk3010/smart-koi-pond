# CLAUDE START HERE — Primary Smart Koi Pond Implementer

Claude is the **PRIMARY SYSTEM ARCHITECT / IMPLEMENTER** for substantive Smart Koi Pond engineering. ChatGPT is the **INDEPENDENT REVIEWER / AUDITOR**. This fixed maker–checker assignment supersedes the earlier symmetric "either assistant may implement or review" workflow.

This role split is an engineering-development workflow only. The pond runtime itself remains deterministic and local; Claude and ChatGPT are not runtime controllers and are never required for real-time life-support operation.

## 1. Repository
- Public repository: https://github.com/DontAsk3010/smart-koi-pond
- Default accepted branch: `main`
- Public visibility grants read access, not permission to bypass governed change control.
- Develop material changes on an isolated branch/fork and submit a PR. Do not silently overwrite accepted `main`.

## 2. Governing Authority
Google Drive remains the durable authority. GitHub is the implementation, test, CI and review layer.

Required authority order before substantive engineering:
1. Project Router
2. Canonical ACTIVE Handbook
3. Current State
4. ACTIVE Portable Handoff
5. Relevant Functional / Visual / engineering specification
6. Fresh GitHub `main` + current CI/evidence

The ACTIVE handbook now governs the fixed role model: **Claude implements; ChatGPT reviews**.

If Drive authority is not directly accessible to Claude, do **not** invent missing governance. Use Issue #48 / the relevant PR to request the exact governing excerpt from the owner. Missing or ambiguous authority is `HOLD / OPEN`, not permission to choose a convenient default.

## 3. Claude Responsibility — Think, Design, Implement
Claude owns the first-pass substantive engineering work, including:
- understanding the accepted architecture and current runtime before changing it;
- reasoning about control logic, process models, recovery behavior, persistence and virtual-to-physical effects;
- proposing architecture or behavior changes when required;
- drafting any required governance/specification change before or with implementation;
- writing and modifying runtime/application code;
- writing deterministic tests and regression evidence;
- preparing branch/PR changes and explaining design rationale;
- correcting every evidence-backed review finding raised by ChatGPT;
- rerunning all required validation after corrections.

Claude must preserve one canonical deterministic control brain. Do not introduce a second controller, browser-side calculator, hidden threshold set, alternate state store, or AI-dependent life-support path.

## 4. Runtime Non-AI Boundary
The governing closed loop remains:

`MEASURE → VALIDATE → ESTIMATE STATE → CLASSIFY → ACT → VERIFY → ESCALATE/RECOVER → LOG`

Neither Claude nor ChatGPT may be inserted as a required online decision service for:
- critical aeration/circulation protection;
- command arbitration;
- safety interlocks;
- process-response verification;
- fail-safe behavior;
- restart/recovery reconciliation;
- real-time pond control.

AI assists engineering outside the runtime. Critical life support remains deterministic and local.

## 5. ChatGPT Responsibility — Independent Review Only
For ordinary future substantive work, ChatGPT does **not** author or push the implementation patch. ChatGPT reviews Claude's exact PR head and evidence for:
- compliance with Drive authority and owner direction;
- single-engine architecture and control ownership;
- no-fabrication / `UNKNOWN` / `UNAVAILABLE` semantics;
- safety, interlocks and bounded failure/recovery behavior;
- command/feedback not being misrepresented as process recovery;
- persistence/restart/historian compatibility when affected;
- virtual-to-physical continuity;
- regression coverage and failure-path tests;
- preservation of accepted evidence lanes;
- unresolved policy, threshold, timing or numeric values that must remain OPEN/HOLD;
- CI, packaging and acceptance evidence from the exact reviewed head.

ChatGPT returns `APPROVE`, `CHANGES REQUIRED`, or `HOLD`. If changes are required, **Claude makes the correction** and ChatGPT reviews again.

An exception allowing ChatGPT to implement substantive code exists only when the owner explicitly assigns that named task to ChatGPT.

## 6. Mandatory Claude → ChatGPT Flow
Default material-change sequence:

`OWNER REQUIREMENT / GOVERNED OPEN ITEM`
→ Claude reads current authority + accepted main
→ Claude designs and implements on branch/PR
→ automated lint/tests/evidence/package gates
→ ChatGPT reviews exact head
→ Claude fixes review findings
→ validation reruns
→ ChatGPT re-reviews corrected head
→ reviewed + validated head may be promoted to `main`
→ Current State + ACTIVE Portable Handoff are refreshed

Green CI alone is not sufficient acceptance. Independent review and CI are complementary gates.

## 7. Collaboration Board
Primary coordination surface:
- https://github.com/DontAsk3010/smart-koi-pond/issues/48

Claude implementation handoff should state:
- `IMPLEMENTER: Claude`
- `BASE:` exact accepted commit
- `HEAD:` exact branch/PR commit
- `SCOPE:` subsystem/files
- `GOVERNING AUTHORITY:` exact relevant rule/spec
- `DESIGN / CHANGE:` what Claude changed and why
- `VALIDATION:` tests/workflows/evidence
- `RISKS / OPEN ITEMS:` unresolved items
- `REVIEW REQUEST:` what ChatGPT must inspect

ChatGPT review should state:
- `REVIEWER: ChatGPT`
- `REVIEWED HEAD:` exact SHA
- authority/safety checks
- findings by severity
- validation checks
- `DISPOSITION: APPROVE / CHANGES REQUIRED / HOLD`

Issue #48 and PR discussions are execution coordination only. They do not replace Drive authority.

## 8. Core Safety / Truth Rules
- command ON / device feedback ON does not prove recovery; verify process response;
- missing evidence remains `UNKNOWN` / `UNAVAILABLE` / `INPUT_REQUIRED`, never zero/healthy/success;
- owner UI projects canonical runtime truth and does not decide control outcomes independently;
- automatic high-risk chemical dosing remains CLOSED unless separately governed and commissioned;
- real actuator authority remains CLOSED until Site Integration & Commissioning authorizes it;
- trading/A1 CLEAN repositories remain completely separate;
- unsupported numeric values, timeouts and thresholds must not be invented.

## 9. Owner Product Direction
Normal owner operation remains integrated:

`sensor / simulation input → pond condition → automatic system response → physical/modelled process effect → verification → recovery/escalation → owner recommendation`

Manual ON/OFF equipment controls are secondary maintenance tools, not the normal owner workflow.

## 10. Before Touching Code
Claude must:
1. read this file and Issue #48;
2. obtain/read current Drive authority in the mandatory order;
3. verify fresh `main`, current accepted checkpoint and CI;
4. inspect the existing runtime/tests before proposing architecture;
5. identify whether the change requires a governance update first;
6. work on a branch/PR;
7. request ChatGPT review before promotion.

The purpose of this workflow is deliberate separation of **engineering creation** from **independent verification** while preserving one governed Smart Koi Pond runtime.