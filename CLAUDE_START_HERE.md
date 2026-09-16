# CLAUDE START HERE — Optional Independent Smart Koi Pond Reviewer

Claude is **NOT the primary implementer** under the current owner-directed Smart Koi Pond governance. ACTIVE Handbook V0.19 §46 assigns **ChatGPT as PRIMARY SYSTEM ARCHITECT / IMPLEMENTER**. Claude may be used as an **OPTIONAL INDEPENDENT REVIEWER / SECOND OPINION** when the owner requests it or when an additional review is materially useful.

This is development governance only. Neither Claude nor ChatGPT is part of the online pond-control loop. Critical life-support remains deterministic and local.

## 1. Repository
- Public repository: https://github.com/DontAsk3010/smart-koi-pond
- Accepted branch: `main`
- Public visibility grants read/review access, not authority to bypass Drive governance, write/merge control, deployment policy, secrets or real-pond control restrictions.

## 2. Governing Authority
Google Drive remains durable authority. Read before any review:
1. Project Router
2. Canonical ACTIVE Handbook — current V0.19
3. Current State
4. ACTIVE Portable Handoff
5. Relevant Functional / Visual / engineering specification
6. Fresh GitHub `main`, exact PR head and CI/evidence

If Drive authority is inaccessible or ambiguous, do not invent policy. Record the missing authority as OPEN/HOLD and request the exact governing excerpt.

## 3. Claude Role — Review / Second Opinion
When requested, independently inspect the exact ChatGPT-authored head for:
- Drive authority and owner-direction compliance;
- deterministic single-engine architecture;
- no second controller, browser calculator, hidden threshold set or alternate state store;
- no-fabrication semantics for missing/invalid evidence;
- safety/interlock and command-ownership behavior;
- command/feedback versus actual process-response verification;
- bounded failure/recovery/lockout semantics where governed;
- checkpoint/restart/persistence/historian compatibility where affected;
- virtual-to-physical continuity and no accidental real-actuation authority;
- regression tests, especially failure paths;
- preservation of accepted evidence lanes;
- unsupported threshold/timeout/retry/numeric values that must remain OPEN/HOLD;
- exact CI/package/acceptance evidence from the reviewed head.

Claude must not silently create a competing implementation, parallel controller, alternate state store, or replacement architecture while reviewing.

## 4. Review Output
Use:
- `REVIEWER: Claude`
- `REVIEWED HEAD:` exact SHA
- `GOVERNING AUTHORITY:` relevant Drive rules/specs
- `FINDINGS:` severity + exact reproducible evidence
- `VALIDATION CHECK:` exact CI/tests/evidence/package state
- `OPEN GOVERNANCE:` unresolved policy/numeric items
- `DISPOSITION:` `NO BLOCKING FINDING / CHANGES SUGGESTED / HOLD RECOMMENDED`
- `NEXT:` exact action for ChatGPT

A finding must be evidence-backed. If proposing a correction, state the affected file/path, reproducible behavior and the smallest compatible change. ChatGPT remains responsible for implementing verified corrections unless the owner explicitly reassigns that named task.

## 5. Runtime Non-AI Boundary
The governing closed loop remains:

`MEASURE → VALIDATE → ESTIMATE STATE → CLASSIFY → ACT → VERIFY → ESCALATE/RECOVER → LOG`

Neither Claude nor ChatGPT may be inserted as a required online decision service for critical aeration/circulation, arbitration, interlocks, process-response verification, fail-safe behavior, restart/reconciliation or real-time pond control.

## 6. Core Truth / Safety Rules
- command ON / feedback ON does not prove process recovery;
- missing evidence remains `UNKNOWN` / `UNAVAILABLE` / `INPUT_REQUIRED`, never fabricated healthy/zero/success;
- owner UI projects canonical runtime truth and does not decide outcomes independently;
- automatic high-risk chemical dosing remains CLOSED unless separately governed and commissioned;
- real actuator authority remains CLOSED until Site Integration & Commissioning authorizes it;
- unsupported thresholds/timeouts/retry limits must not be invented;
- A1 CLEAN/trading work remains completely separate.

## 7. Collaboration Surface
Issue #48 is the coordination/review surface:
https://github.com/DontAsk3010/smart-koi-pond/issues/48

Issue/PR discussion is execution evidence only. It does not replace Drive authority.

## 8. Owner Product Direction
Normal owner operation remains:

`sensor / simulation input → pond condition → automatic system response → physical/modelled process effect → verification → recovery/escalation → owner recommendation`

Manual device ON/OFF remains secondary maintenance functionality.

Claude review is optional unless the owner explicitly requires it for a named change. Claude availability must not block ordinary ChatGPT-led engineering.