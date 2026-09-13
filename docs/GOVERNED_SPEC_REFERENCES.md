# Governed Specification References

Google Drive remains the durable project authority. This repository is the engineering execution layer and must not become a second handbook.

Mandatory authority/read references:

- Project Router: `00_READ_FIRST_SMART_KOI_POND_PROJECT_ROUTER` — Drive ID `1Vk0rlLuamhXzV4e9Ezx7wBzdJkLe8-APX0hbuZQeRAQ`
- Active handbook: `00_SMART_KOI_POND_CLOSED_LOOP_CONTROL_SYSTEM_HANDBOOK_ACTIVE.docx` — Drive ID `1m8uokr6rrEXJp_jtMfte7oQWaUDxJgwn` — current governed version `V0.13`
- Current-state checkpoint: `90_SMART_KOI_POND_CURRENT_STATE_ACTIVE` — Drive ID `1u8EaG1J5Eoqo8b1HKvRljBShpbTRrTnudSGQ45M20hI`
- Active Portable Handoff: `90_SMART_KOI_POND_ACTIVE_PORTABLE_HANDOFF` — Drive ID `1h1FvTFrl_hKrINEWgWE0XoC9UaIVOqYnyjsNkMTFEz4`
- Visual screen specification: `SMART_KOI_POND_DIGITAL_TWIN_V1_VISUAL_SCREEN_SPECIFICATION` — Drive ID `1_TOalbTZjLPAcUu2Ah2ayerJN3VLwRtqWf2GiD4SRDY`
- Functional specification: `SMART_KOI_POND_DIGITAL_TWIN_FUNCTIONAL_SPECIFICATION_V1` — Drive ID `19t3Nx_C7GF2ipXarsJLpV_3-ub-SA1nIDSu_MIkCsGc`

Current durable modular authority is Handbook V0.13 Section 40, Functional Specification Section 30, and Visual Specification Section 23. Commercial package labels are metadata only; runtime capability/dependency state and the Pond-Profile-derived Minimum Life-Support Baseline are authoritative.

Read order is Router -> Active Handbook -> Current State -> Active Portable Handoff -> relevant governed specifications -> latest validated GitHub `main`/CI evidence.

The Portable Handoff is execution continuity state only. It cannot create or override system policy. If any cached/pasted handoff conflicts with newer Drive authority, the Drive authority wins and the handoff must be reconciled before implementation continues.

Implementation changes that alter safety, operating modes, system semantics, state ownership, validation, deployment, persistence, dependency handling, modularity, or acceptance criteria must update the governed Drive authority first or in the same governed change.
