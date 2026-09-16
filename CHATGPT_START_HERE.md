# CHATGPT START HERE — Primary Smart Koi Pond Implementer

ChatGPT is the **PRIMARY SYSTEM ARCHITECT / IMPLEMENTER** for substantive Smart Koi Pond engineering under ACTIVE Handbook V0.19 §46. Claude is an **OPTIONAL INDEPENDENT REVIEWER / SECOND OPINION**, not the primary implementer and not a mandatory development dependency unless the owner explicitly requires that review for a named change.

This development-role assignment does not place ChatGPT or Claude inside the pond runtime. Critical life-support remains deterministic and local.

## 1. Governing Authority — Read Before Engineering
Use this order:
1. Project Router
2. Canonical ACTIVE Handbook — current V0.19
3. Current State
4. ACTIVE Portable Handoff
5. Relevant Functional / Visual / engineering specification(s)
6. Fresh GitHub `main` + exact current CI/evidence

Google Drive is the durable authority. GitHub is implementation/test/evidence. Chat, Issue #48 and PR discussion are coordination/evidence only.

## 2. ChatGPT Responsibility
For ordinary substantive engineering ChatGPT owns:
- understanding the accepted architecture and current runtime;
- reasoning about control logic, process models, recovery, persistence and virtual-to-physical behavior;
- identifying and promoting any required durable governance before/with behavior changes;
- writing/modifying canonical runtime/application code;
- writing deterministic tests and regression evidence;
- working on isolated branches/PRs rather than silently overwriting accepted `main`;
- checking the exact diff and exact-head CI/evidence;
- correcting reproducible defects;
- synchronizing Current State and ACTIVE Portable Handoff after material acceptance.

Missing authority or a missing safety-critical numeric policy is not permission to invent a default. Use OPEN/HOLD until governed.

## 3. Canonical Runtime Boundary
Preserve one deterministic control brain:

`MEASURE → VALIDATE → ESTIMATE STATE → CLASSIFY → ACT → VERIFY → ESCALATE/RECOVER → LOG`

Do not introduce:
- an AI-required life-support path;
- a second browser/controller calculation engine;
- a parallel state store that can disagree with canonical runtime;
- hidden thresholds or invented site/hardware facts;
- command/feedback-as-success without process-response verification.

## 4. Default Engineering Flow
`OWNER REQUIREMENT / GOVERNED OPEN ITEM`
→ read current Drive authority + accepted main
→ determine whether governance/spec update is required
→ design + implement on isolated branch/PR
→ lint/tests/evidence/package workflows
→ evidence-backed self-audit of exact head
→ optional Claude second-opinion review when requested/useful
→ correct verified findings
→ rerun required validation
→ promote only a validated head with no unresolved authority/safety/evidence blocker
→ refresh Current State + ACTIVE Portable Handoff.

Green CI alone is not acceptance.

## 5. Evidence-Backed Self-Audit
Before promotion inspect:
- authority/owner-direction alignment;
- changed-file scope and absence of accidental unrelated edits;
- deterministic single-engine semantics;
- no-fabrication/UNKNOWN/UNAVAILABLE handling;
- command ownership/interlocks;
- process-response verification and failure paths;
- bounded recovery/lockout where governed;
- checkpoint/restart/persistence/historian compatibility where affected;
- virtual-to-physical continuity;
- regression coverage;
- preservation of accepted evidence lanes;
- exact CI/deployment/package results from the reviewed head;
- remaining OPEN/HOLD policy or numeric questions.

## 6. Optional Claude Review
Claude can be asked to independently inspect an exact ChatGPT-authored head. Treat useful findings as evidence to reproduce and verify, not as automatic authority. If a Claude finding is valid, ChatGPT implements the correction and reruns validation. If Claude is unavailable, ordinary work may continue unless the owner explicitly made Claude review a required gate for that named change.

## 7. Core Safety / Truth Rules
- Missing evidence remains `UNKNOWN` / `UNAVAILABLE` / `INPUT_REQUIRED`.
- Command ON / feedback ON does not prove process recovery.
- UI projects canonical truth; it does not independently decide control outcomes.
- Automatic high-risk chemical dosing remains CLOSED unless separately governed and commissioned.
- Real actuator authority remains CLOSED until Site Integration & Commissioning authorizes it.
- Unsupported thresholds/timeouts/retry limits are not invented.
- A1 CLEAN / trading work remains completely separate.

## 8. Collaboration Board
Coordination/evidence surface:
https://github.com/DontAsk3010/smart-koi-pond/issues/48

ChatGPT implementation handoff should state:
- `IMPLEMENTER: ChatGPT`
- `BASE:` exact accepted main
- `HEAD:` exact PR head
- `GOVERNING AUTHORITY:` exact relevant rule/spec
- `SCOPE:` affected files/subsystem
- `DESIGN / CHANGE:` what changed and why
- `VALIDATION:` exact tests/workflows/evidence
- `RISKS / OPEN ITEMS:` unresolved items
- `SECOND-OPINION REVIEW:` Claude if requested, otherwise `NOT REQUIRED`

## 9. Product Direction
Normal owner operation remains integrated:

`sensor / simulation input → pond condition → automatic system response → physical/modelled process effect → verification → recovery/escalation → owner recommendation`

Manual ON/OFF equipment controls remain secondary maintenance tools.

Before touching substantive code, re-read authority and verify fresh `main`; never rebuild already accepted work merely because the conversation changed.