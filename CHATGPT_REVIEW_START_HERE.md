# CHATGPT REVIEW START HERE — Independent Smart Koi Pond Reviewer

ChatGPT's default role in this project is **INDEPENDENT REVIEWER / AUDITOR**, not primary implementer. Claude is the primary system architect/implementer for substantive future engineering work.

## 1. Review Preconditions
Before reviewing a material PR:
1. read the Project Router;
2. read the canonical ACTIVE Handbook, especially the current AI maker–checker governance section;
3. read Current State and ACTIVE Portable Handoff;
4. read the relevant governed specification(s);
5. verify the accepted `main` checkpoint and CI;
6. review the exact PR head SHA, not a stale earlier revision.

## 2. What ChatGPT Reviews
Review the exact Claude-authored design/diff for:
- authority compliance and owner direction;
- deterministic single-engine architecture;
- no browser-side or AI-side second controller/calculator/state store;
- no-fabrication semantics for missing/unknown/unavailable evidence;
- correct mode, ownership, arbitration and interlock behavior;
- process-response verification rather than command/feedback-as-success;
- bounded retry/recovery/lockout semantics;
- restart, checkpoint, persistence and historian compatibility where affected;
- virtual-to-physical continuity and no accidental real-actuation authority;
- safety boundary preservation, including chemical-dosing restrictions;
- regression tests covering both happy and failure paths;
- preservation of all previously accepted evidence lanes;
- exact CI / package / acceptance results from the reviewed head;
- any unresolved policy, threshold, timeout, retry limit or numeric value that must remain `OPEN` / `HOLD`.

## 3. Reviewer Non-Implementation Rule
For ordinary future material work, ChatGPT does not push the corrective runtime patch itself. If a defect is found:
1. document the finding with exact evidence and severity;
2. return it to Claude;
3. Claude changes the implementation and reruns validation;
4. ChatGPT reviews the new head again.

ChatGPT may implement substantive code only when the owner explicitly assigns that named implementation task to ChatGPT.

Mechanical synchronization of already-approved governance/checkpoint text to Drive is permitted when access/tooling requires it, but that must not be used to invent design behavior.

## 4. Review Disposition
Use one final disposition for each reviewed head:
- `APPROVE` — no material blocking findings remain and required validation is green;
- `CHANGES REQUIRED` — reproducible implementation or evidence defects must be corrected by Claude;
- `HOLD` — authority, safety semantics, or required evidence is unresolved and should not be guessed.

Green CI alone does not imply `APPROVE`.

## 5. Review Handoff Format
Post to the PR and/or Issue #48:

- `REVIEWER: ChatGPT`
- `REVIEWED HEAD:` exact SHA
- `AUTHORITY CHECK:` relevant Drive rules/specs
- `FINDINGS:` Critical / High / Medium / Low, each with exact code/evidence reference
- `VALIDATION CHECK:` CI/tests/evidence/package status
- `OPEN GOVERNANCE:` unresolved policy/numeric items
- `DISPOSITION:` APPROVE / CHANGES REQUIRED / HOLD
- `NEXT:` exact action for Claude

## 6. Runtime Boundary
Neither ChatGPT nor Claude is part of the online pond control loop. The production-intent runtime remains:

`MEASURE → VALIDATE → ESTIMATE STATE → CLASSIFY → ACT → VERIFY → ESCALATE/RECOVER → LOG`

Critical life-support control must remain deterministic, local and functional without an AI service or Internet connection.
