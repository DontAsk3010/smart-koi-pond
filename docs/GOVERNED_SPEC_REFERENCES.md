# Governed Specification References

Google Drive remains the durable project authority. This repository is the engineering execution layer and must not become a second handbook.

## Mandatory authority/read references

- Project Router: `00_READ_FIRST_SMART_KOI_POND_PROJECT_ROUTER` — Drive ID `1Vk0rlLuamhXzV4e9Ezx7wBzdJkLe8-APX0hbuZQeRAQ`
- Active handbook: `00_SMART_KOI_POND_CLOSED_LOOP_CONTROL_SYSTEM_HANDBOOK_ACTIVE.docx` — Drive ID `1m8uokr6rrEXJp_jtMfte7oQWaUDxJgwn` — current governed version **V0.19**
- Current-state checkpoint: `90_SMART_KOI_POND_CURRENT_STATE_ACTIVE` — Drive ID `1u8EaG1J5Eoqo8b1HKvRljBShpbTRrTnudSGQ45M20hI`
- Active Portable Handoff: `90_SMART_KOI_POND_ACTIVE_PORTABLE_HANDOFF` — Drive ID `1h1FvTFrl_hKrINEWgWE0XoC9UaIVOqYnyjsNkMTFEz4`
- Visual screen specification: `SMART_KOI_POND_DIGITAL_TWIN_V1_VISUAL_SCREEN_SPECIFICATION` — Drive ID `1_TOalbTZjLPAcUu2Ah2ayerJN3VLwRtqWf2GiD4SRDY`
- Functional specification: `SMART_KOI_POND_DIGITAL_TWIN_FUNCTIONAL_SPECIFICATION_V1` — Drive ID `19t3Nx_C7GF2ipXarsJLpV_3-ub-SA1nIDSu_MIkCsGc`

Read order is:

`Router → ACTIVE Handbook → Current State → ACTIVE Portable Handoff → relevant governed specification(s) → latest validated GitHub main/CI evidence`

## Current durable handbook structure relevant to repository work

The ACTIVE handbook is cumulative. Current V0.19 includes, among earlier durable sections:
- Section 40 — Capability-Based Modular Product Architecture and Minimum Life-Support Baseline;
- Section 41 — Integrated Koi Pond Environmental Regulation System / Primary Product Objective;
- Section 42 — Reconfigurable Pond Design, Capacity Advisory and Adaptive Environmental Regulation;
- Section 43 — Governed Reconfiguration, Update/Rollback and Self-Recovery Architecture;
- Section 44 — Koi Stock, Biomass-Derived Feeding and Water-Quality Recovery Architecture;
- Section 45 — Integrated Owner Operation, Guided Testing and Backwash Water Restoration;
- Section 46 — AI Engineering Responsibility Model: **ChatGPT primary architect/implementer; Claude optional independent review / second opinion**.

Older version labels such as V0.13 describe historical milestones only and must not be presented as the current ACTIVE authority.

Commercial/package labels are metadata only. Runtime capability/dependency state, Pond-Profile-derived Minimum Life-Support Baseline, canonical control state and exact validation evidence remain authoritative within their governed scope.

## Dynamic checkpoint rule

Do **not** duplicate an exact current-main SHA, CI run, artifact ID or next-work checkpoint into this static index. Those change frequently and belong in `90_SMART_KOI_POND_CURRENT_STATE_ACTIVE` and `90_SMART_KOI_POND_ACTIVE_PORTABLE_HANDOFF`.

The Portable Handoff is execution continuity state only. It cannot create or override system policy. If any cached/pasted handoff or repository note conflicts with newer Drive authority, Drive authority wins and continuity must be reconciled before implementation continues.

Implementation changes that alter safety, operating modes, system semantics, state ownership, validation, deployment, persistence, dependency handling, modularity, recovery, UI-control semantics, or acceptance criteria must update the governed Drive authority first or in the same governed change.
