# Animated Pond Process Contract V1

This repository implements the governed Smart Koi Pond V0.14 state-bound animation direction.

The renderer is a projection consumer, not a control engine. `ProcessVisualState` is derived from the canonical runtime snapshot and must never create a second state, command, alarm, verification, or recovery decision.

## V1 visual truth

- Circulation motion requires canonical simulated/measured total flow plus an active/effective pump path.
- Main and backup circulation paths remain distinguishable so takeover is visible.
- Aeration motion reflects canonical actuator feedback, availability, and modeled effectiveness; verification status remains separately visible.
- Water level is rendered directly from canonical pond state.
- Top-up, drain, and backwash motion follows canonical asset/workflow state.
- Drain/backwash discharge may be shown qualitatively when the governed valve/workflow is active, but no quantitative discharge rate is displayed unless the runtime models it.
- Waste/sludge quantity is explicitly NOT MODELED in V1 and must not be fabricated.
- Alarm, verification, execution/operating mode, pause, acceleration, and historian playback remain synchronized to the same runtime/run identity.
- Historical playback uses the same process-visual projection contract and remains read-only.

## Renderer replacement rule

The first accepted renderer may use HTML/CSS/SVG. A later WebGL/full-3D renderer may replace or augment it only as a presentation layer consuming the same `ProcessVisualState`. Renderer technology never changes control authority or process truth.
