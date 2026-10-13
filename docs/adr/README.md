# Architecture Decision Records

Key design decisions for the next-site planner. Each ADR records the context, the options considered (with a SOTA comparison and an evidence table, rule R2), the decision and its consequences — written before implementation, not after.

## Index

| # | Title | Status | Summary |
|---|-------|--------|---------|
| [ADR-001](ADR-001-framing-and-analysis-unit.md) | Measured experience per person on an H3 grid, seven countries | Proposed | Ookla speed tiles weighted by Kontur population on H3 resolution 8; shares of people below 10 / 25 Mbps, raw and density-adjusted; R15 justification for Spark and Databricks. |
| [ADR-002](ADR-002-validation-and-gates.md) | Validation strategy and gates for every phase | Proposed | Spatial block CV, FDR-controlled hotspots, staggered difference-in-differences with pre-trend tests, covering optimiser vs ranking; gates P0–P7 fixed before any analysis. |

## Decision Dependencies

```
ADR-001 (framing, unit, metrics)
  └── ADR-002 (validation and gates)
```
