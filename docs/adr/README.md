# Architecture Decision Records

Key design decisions for the next-site planner. Each ADR records the context, the options considered (with a SOTA comparison and an evidence table, rule R2), the decision and its consequences — written before implementation, not after.

## Index

| # | Title | Status | Summary |
|---|-------|--------|---------|
| [ADR-001](ADR-001-framing-and-analysis-unit.md) | Measured experience per person on an H3 grid, seven countries | Proposed | Ookla speed tiles weighted by Kontur population on H3 resolution 8; shares of people below 10 / 25 Mbps, raw and density-adjusted; R15 justification for Spark and Databricks. |
| [ADR-002](ADR-002-validation-and-gates.md) | Validation strategy and gates for every phase | Proposed | Spatial block CV, FDR-controlled hotspots, staggered difference-in-differences with pre-trend tests, covering optimiser vs ranking; gates P0–P7 fixed before any analysis. |
| [ADR-003](ADR-003-industry-alignment.md) | Industry alignment: plan sites the way network planners do | Proposed | Coverage vs capacity gap types, Degree of Urbanisation morphology, 3GPP TR 38.901 service radii, co-location-first interventions with FCC cost ratios, regulatory benchmarks, planner-ready CSV/GeoJSON/KML; amends gates P0, P1, P4. |
| [ADR-004](ADR-004-speed-model-for-untested-areas.md) | Speed model for untested areas (P2) | Proposed | LightGBM with neighbour, nearest-observation and history features vs ordinary kriging; H3 resolution-6 block CV chosen by distance matching (kNNDM); predictive distribution per ring distance; area of applicability. |
| [ADR-005](ADR-005-measurement-noise.md) | Measurement noise: small-area shrinkage and noise-aware scoring | Proposed (post-hoc) | Tile-pair noise model; Fay–Herriot shrinkage with a leave-one-out kriging prior; noise-corrected P1 shares beside the raw ones; noise-aware P2 scoring; kriging deployed because the P2 gate failed. |

## Decision Dependencies

```
ADR-001 (framing, unit, metrics)
  ├── ADR-002 (validation and gates)
  ├── ADR-003 (industry alignment) ── amends ADR-002 P0, P1, P4
  ├── ADR-004 (P2 speed model) ── details the P2 gate
  └── ADR-005 (measurement noise, post-hoc) ── follow-up to ADR-004's failed gate
```
