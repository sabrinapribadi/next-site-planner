# ADR-011: Public API, Remote MCP and Technology Assessment (R19–R21)

**Status:** Accepted — checks passed locally (2026-11-11); public deploy waits for the release asset and the host token
**Date:** 2026-11-11
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

- ADR-009 built the planner API, MCP tools and grounded notes; they run only on a laptop.
- Portfolio rules now require CI/CD (R19), zero hosting cost (R20) and a technology assessment (R21).
- **Question:** how can hiring teams and AI assistants call the four planner tools publicly, for $0?

## Decision Drivers

- Same tools and numbers as ADR-009, including `gap_at` for any of the 6.4 million hexagons.
- No API key on the host; public traffic never spends tokens.
- Data licences respected: derived speed data shared under CC BY-NC-SA 4.0 with attribution, non-commercial host.

## Decision

### 1. App

- `src/serving/public.py`: the four REST tools plus the same tools as a stateless MCP endpoint at `/mcp` (spec 2026-07-28; Python SDK 2.3.0).
- **Notes:** served from the notes cache for the configured model, else the template; no model is ever called.
- **Hosts:** DNS-rebinding protection on; only localhost and the deployment's own hostnames reach `/mcp`.
- **Attribution:** every root reply and the API description carry the data sources and licence.

### 2. Data and bundle

- The serving store (6.4 million hexagons, 12,716 planned sites, notes) is 66.6 MB compressed: too large for git.
- It travels as a release asset (`serving-data-v1`) whose SHA-256 is committed in `deploy/serving_data.sha256`; the build refuses a mismatch.
- `gap_at` reads the hexagon table with DuckDB; the table is sorted by H3 cell in 50,000-row groups, so one lookup reads one group.
- Plans are read with DuckDB too, so the host needs no pyarrow (dependencies 143 MB instead of 277 MB).
- **Host:** Vercel Hobby (free, non-commercial). The results page stays the static fallback (R20).

### 3. CD (R19)

- On push to `main` after tests: fetch the store, build the bundle, sign its build provenance (GitHub artifact attestations), deploy, smoke-test `/health`, a Jakarta speed gap, Indonesia's first sites and note, MCP `tools/list` and an injection probe.

### 4. Technology assessment (portfolio plan §10)

| Technology | Rating | Where in GEO-1 |
|---|---|---|
| CI/CD + build provenance | Adopt | §3; error-level lint added to CI |
| Remote MCP, 2026-07-28 spec | Adopt | `/mcp` on the public app |
| Prompt-injection tests on tools | Adopt | Tools never echo country input; tests over REST and MCP |
| OpenTelemetry GenAI traces | Trial | Pattern proven in the lithology project; add when notes are regenerated |
| Databricks Apps | Trial | The P6 job already runs on Databricks; an app would need a workspace login |
| Multi-agent over A2A | Hold | No question needs a second agent |

## Empirical results (2026-11-11, local)

| Check | Target | Result |
|---|---|---|
| Plans read by DuckDB vs pandas | Identical | Identical on the fixture and on all 12,716 real rows |
| Public notes for every planned site | Grounded; no model call | 12,716 of 12,716 from the cached model notes, all pass the grader |
| `gap_at`, 200 random points in four countries | Report | 89 inside a populated hexagon; p50 24 ms, p95 38 ms |
| Cold import of the app | Report | 2.6 s |
| Bundle size (code + store) and dependencies | ≤ 500 MB (host limit) | 102 MB + 143 MB |
| Injected text (REST and MCP) | Refused, not echoed | Passed |
| MCP from an unknown host | Rejected | 421 |
| Smoke test on the built bundle | Pass | Passed |

## Considered Options

| Option | Status | Why |
|---|---|---|
| **Store as a checksummed release asset; DuckDB on Vercel Hobby** | **Chosen** | Free; exact values; small, fast lookups |
| Commit the store to git | Rejected | 89 MB file; bloats history for good |
| Round values to shrink the store | Rejected | Numbers would differ from the results page |
| Render | Rejected | Paid instances bill while idle (R20) |

## Consequences

- **Positive:** anyone can check the speed gap at any point in seven countries, and get a planned site's note, at $0.
- **Negative:** cold starts on a free host; a new store needs a new release asset and checksum.

## Related Decisions

- ADR-008 (budgeted site plan), ADR-009 (planner API, MCP, notes), ADR-010 (Databricks job)

## Evidence

| Source | Issuer | Used for |
|---|---|---|
| The 2026-07-28 Specification (MCP blog) | Model Context Protocol | Stateless core, Streamable HTTP |
| Deploy a FastAPI app on Vercel (docs, updated 2026-08-27) | Vercel | Hosting |
| Artifact attestations (docs) | GitHub | Build provenance, free for public repositories |
| Top Strategic Technology Trends for 2026 (press release, 20 Oct 2025) | Gartner | AI security platforms, digital provenance |
| Speedtest by Ookla open data licence (CC BY-NC-SA 4.0) | Ookla | Attribution and share-alike for derived data |
