# Governed NH3 / Koi Freshwater Health Reference V1

This repository note mirrors the governing Drive authority; it does not replace it.

## Biological intent

The control runtime shall protect koi/common-carp health using relationship-aware water-quality evidence rather than isolated TAN alone. Toxic un-ionized ammonia is derived only from validated TAN-N, pH, and water temperature. Missing or invalid inputs remain unavailable; no NH3 value is fabricated.

## Unit contract

- TAN input: mg N/L.
- EPA/Emerson speciation first derives NH3-N in mg N/L.
- Biological limits in the governing fish-health references are expressed as molecular NH3 mg/L.
- Therefore molecular NH3 is calculated from NH3-N using the NH3/N molecular-mass ratio before biological threshold comparison.
- `unionized_ammonia_n_mg_l` is retained for auditability.
- `unionized_ammonia_nh3_mg_l` is the biological threshold-comparison parameter.

## Governed freshwater/koi reference envelope

The source-backed reference registry exposes, but does not silently auto-apply, the following health-oriented values:

- dissolved oxygen preferred control band: 6–8 mg/L; warning below 5 mg/L; emergency at or below 4 mg/L;
- common-carp growth-temperature reference: 23–30 °C;
- pH reference range: 6.5–9.0;
- TAN target: 0 mg N/L; general freshwater tolerance boundary <1 mg N/L is a secondary alert boundary, not a target;
- un-ionized molecular NH3 target: as close to 0 as practical; WATCH at 0.02 mg/L; cyprinid maximum-admissible/emergency boundary at 0.05 mg/L;
- nitrite target: 0 mg/L; reference WATCH at 0.1 mg/L;
- nitrate reference: <20 mg/L;
- total alkalinity: >100 mg/L as CaCO3;
- total hardness: >20 mg/L as CaCO3;
- total/free chlorine: 0 mg/L.

A commissioned site policy may intentionally use narrower protective bands. It shall not weaken the biological-safety envelope merely for easier operation.

## Response boundary

High NH3 may inhibit feeding and request available aeration/circulation support. Bounded water exchange may be requested only through the existing governed WATER_CHANGE workflow when source water is positively qualified and is calculated to move the relevant chemistry in a safer direction. Automatic ammonia binder, salt, acid/base, buffer, or other high-risk chemical dosing remains unauthorized.

## Sources

- SMART KOI POND canonical Handbook V0.17.
- Merck Veterinary Manual, Normal Reference Ranges for Routine Water Quality Analysis.
- FAO cultured-species profile for Cyprinus carpio.
- FAO fish-health guidance for un-ionized ammonia in cyprinids.
- US EPA 2013 Freshwater Aquatic Life Ambient Water Quality Criteria for Ammonia; Emerson et al. freshwater speciation relationship.
