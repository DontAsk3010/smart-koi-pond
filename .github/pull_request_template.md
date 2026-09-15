# Smart Koi Pond — Material Change PR

## Responsibility
- **IMPLEMENTER:** Claude
- **INDEPENDENT REVIEWER:** ChatGPT
- **BASE ACCEPTED MAIN:** `<sha>`
- **PR HEAD:** `<sha>`

> If the owner explicitly reassigned this named implementation task away from Claude, state the exception and owner instruction here.

## Governing authority
List the exact Drive authority/specification sections that govern this change.

- Project Router reviewed: [ ]
- ACTIVE Handbook reviewed: [ ]
- Current State reviewed: [ ]
- ACTIVE Portable Handoff reviewed: [ ]
- Relevant governed spec(s) reviewed: [ ]
- Fresh accepted `main` + CI verified: [ ]

## Problem / requirement
Describe the owner requirement, governed OPEN item, or reproducible defect.

## Claude design / implementation
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

## Risks / OPEN / HOLD items
List unresolved governance, timing, threshold, hardware, source-water, persistence or commissioning items explicitly.

## ChatGPT independent review
- **REVIEWED HEAD:** `<sha>`
- **AUTHORITY CHECK:** PENDING
- **FINDINGS:** PENDING
- **VALIDATION CHECK:** PENDING
- **DISPOSITION:** `PENDING / APPROVE / CHANGES REQUIRED / HOLD`

A material PR is not accepted solely because CI is green. Claude addresses review findings; ChatGPT re-reviews the corrected head before promotion.
