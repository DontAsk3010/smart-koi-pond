# Smart Koi Pond — Material Change PR

## Responsibility
- **PRIMARY IMPLEMENTER:** ChatGPT
- **OPTIONAL SECOND-OPINION REVIEWER:** Claude / other independent reviewer when requested
- **BASE ACCEPTED MAIN:** `<sha>`
- **PR HEAD:** `<sha>`

> ACTIVE Handbook V0.19 §46 governs this assignment. If the owner explicitly reassigns a named task, record the exact exception here. An optional reviewer is never a substitute for Drive authority or reproducible evidence.

## Governing authority
List the exact Drive authority/specification sections that govern this change.

- Project Router reviewed: [ ]
- ACTIVE Handbook V0.19 reviewed: [ ]
- Current State reviewed: [ ]
- ACTIVE Portable Handoff reviewed: [ ]
- Relevant governed spec(s) reviewed: [ ]
- Fresh accepted `main` + CI verified: [ ]

## Problem / requirement
Describe the owner requirement, governed OPEN item, or reproducible defect.

## ChatGPT design / implementation
Explain the engineering reasoning, affected canonical path, and why the implementation belongs in the existing runtime rather than a second engine.

## Files changed
List code, tests, configuration, docs and governance artifacts changed.

## Safety / truth invariants
Confirm or explain any exception:
- [ ] Missing evidence remains UNKNOWN / UNAVAILABLE / INPUT_REQUIRED rather than fabricated.
- [ ] Command/feedback is not treated as process recovery without verification.
- [ ] No second controller, browser calculator, hidden threshold set or parallel state store is introduced.
- [ ] Critical life-support behavior remains deterministic/local and has no AI runtime dependency.
- [ ] Real actuator authority is not widened without governed commissioning evidence.
- [ ] High-risk automatic chemical dosing authority is not widened.
- [ ] Unsupported numeric thresholds/timeouts/retry limits were not invented.
- [ ] Previously accepted evidence lanes are preserved.

## Validation
Record exact results from this PR head.

- Lint:
- Python 3.11 tests:
- Python 3.12 tests:
- Relevant regression/evidence workflows:
- Visual acceptance, if affected:
- Deployment/Windows packaging, if affected:

## Evidence-backed self-audit
- **AUDITED HEAD:** `<sha>`
- **AUTHORITY CHECK:** PENDING
- **DIFF / ARCHITECTURE CHECK:** PENDING
- **FAILURE-PATH / NO-FABRICATION CHECK:** PENDING
- **VALIDATION CHECK:** PENDING
- **DISPOSITION:** `PENDING / ACCEPTABLE / CHANGES REQUIRED / HOLD`

## Optional independent second opinion
- **REVIEW REQUIRED BY OWNER:** `NO / YES`
- **REVIEWER:** `Claude / other / N/A`
- **REVIEWED HEAD:** `<sha / N/A>`
- **FINDINGS:** `N/A` unless review requested/performed

## Risks / OPEN / HOLD items
List unresolved governance, timing, threshold, hardware, source-water, persistence or commissioning items explicitly.

A material PR is not accepted solely because CI is green. Acceptance requires alignment with current Drive authority, reproducible validation, and no unresolved authority/safety/evidence blocker. Claude review is optional unless the owner explicitly makes it a named gate.