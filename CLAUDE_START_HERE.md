# CLAUDE START HERE — Smart Koi Pond Collaboration

This file is the public bootstrap entry for Claude when collaborating with ChatGPT on `DontAsk3010/smart-koi-pond`.

## 1. Repository
- Public repository: https://github.com/DontAsk3010/smart-koi-pond
- Default branch: `main`
- Do not treat public visibility as permission to bypass governed change control.

## 2. Collaboration Board
Read this first after opening the repository:
- https://github.com/DontAsk3010/smart-koi-pond/issues/48

Issue #48 is the shared ChatGPT × Claude coordination board. Use it or the relevant PR discussion to leave findings, proposals, reviews, implementation notes, test evidence, and exact next actions.

## 3. Governing Authority
Google Drive remains the durable authority for the project handbook, current state, handoff, and governed specifications. GitHub is the execution/review layer.

Required authority order before substantive implementation:
1. Project Router
2. Canonical ACTIVE Handbook
3. Current State
4. ACTIVE Portable Handoff
5. Relevant Functional / Visual specifications
6. Fresh GitHub `main` + CI evidence

If Drive authority is not directly accessible to Claude, do NOT invent missing governance. Use Issue #48 and repository evidence as the public collaboration bootstrap, and ask the owner/ChatGPT to provide or mirror the exact governing excerpt needed for a proposed change.

## 4. Current Accepted Direction
The system is a production-intent Smart Koi Pond closed-loop environmental regulation system. The governing loop is:

MEASURE → VALIDATE → ESTIMATE STATE → CLASSIFY → ACT → VERIFY → ESCALATE/RECOVER → LOG

Key rules:
- command ON / device feedback ON does not prove recovery; verify the measured/modelled process response;
- missing evidence remains `UNKNOWN` / `UNAVAILABLE` / `INPUT_REQUIRED`, never zero/healthy/success;
- owner UI is a projection of canonical runtime state, not a second control engine;
- automatic high-risk chemical dosing remains CLOSED;
- real actuator authority remains CLOSED until Site Integration & Commissioning;
- trading/A1 CLEAN repositories are completely separate from this project.

## 5. Current Product Direction
Normal owner operation should be integrated and simple:

sensor or simulation input → pond condition → automatic system response → physical/modelled process effect → verification → recovery/escalation → owner recommendation

Manual ON/OFF equipment controls are secondary maintenance tools, not the normal owner workflow.

The latest accepted owner-operation work includes guided simulation values and an integrated backwash workflow that must behave physically:

backwash → water level decreases → backwash stops → qualified source-water refill → chemistry/state re-evaluation → verification → final result

The browser must not sequence this logic independently; orchestration belongs in the canonical runtime.

## 6. How Claude and ChatGPT Should Collaborate
Either assistant may implement or review. Preferred pattern:
- one assistant identifies a reproducible defect or improvement;
- leave a GitHub Issue/PR note with exact evidence;
- implement on a branch/fork rather than silently overwriting accepted `main`;
- run relevant tests/CI;
- the other assistant reviews against governance + runtime evidence;
- merge only validated changes.

If assistants disagree, resolve using governed authority and reproducible runtime/CI evidence rather than preference.

## 7. Required Handoff Format
Use this format in Issue #48 or a PR comment:

- `FROM:` ChatGPT or Claude
- `STATUS:` FINDING / PROPOSAL / IMPLEMENTED / REVIEWED / BLOCKED
- `BASE:` exact commit SHA
- `SCOPE:` files / subsystem
- `EVIDENCE:` observed behavior, tests, logs, screenshots, code references
- `CHANGE:` what changed or is proposed
- `VALIDATION:` tests/workflows and results
- `NEXT:` exact next action

## 8. Before Touching Code
Claude should first:
1. read this file;
2. read Issue #48;
3. inspect current `main` and recent accepted PRs/CI;
4. understand existing runtime and tests before proposing new architecture;
5. avoid rebuilding accepted capabilities or introducing a second state/control/calculation path.

This bootstrap exists so the owner does not need to manually reconstruct the project context between ChatGPT and Claude.
