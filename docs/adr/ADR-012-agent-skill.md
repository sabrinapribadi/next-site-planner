# ADR-012: Agent Skill for the Planner (R24)

**Status:** Accepted
**Date:** 2026-11-17
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

- The planner already serves four tools over REST and MCP (ADR-009, ADR-011), but an AI agent does not know when to use them or how to read their numbers.
- Several fields are easy to misread: `plan_gain_vs_kpi` is a relative gain (1.85 means 2.85× as many people), `people` is the smaller of two population estimates, and rank orders sites by expected people lifted.
- **Question:** how can any coding or chat agent use the planner correctly, with proof that it does?

## Decision Drivers

- Agents answer from the API's numbers only and say when a place is out of scope.
- Works without installing packages or holding keys; free to run (R20).
- Tested like the rest of the project (R19, R24).

## Considered Options

| Option | Chosen | Why |
|---|---|---|
| **Agent Skill (`SKILL.md`) + dependency-free client + evals** | **Yes** | Portable across agents that read skills; carries the reading rules; testable |
| MCP server only | No | Gives tools but not when to use them or how to read the numbers |
| Paid skill marketplace listing | No | Speed data is non-commercial (CC BY-NC-SA 4.0); MIT code; employment terms |

## Decision

- `skills/next-site-planner/`: `SKILL.md` (trigger description, workflow, reading rules, licence, limits), `scripts/nsp.py` (standard library only, one retry for cold starts), `references/fields.md` (every field).
- `evals/`: four task cases in the `claude plugin eval` layout (gap check, shortlist, country comparison, out-of-scope) with 15 graders; `trigger-evals.json` with 10 should-trigger and 10 near-miss prompts.
- CI: `tests/test_skill_client.py` (client and skill files, offline) and `scripts/skill_live_check.py` after every deploy (live API and the facts the graders use).

## Empirical Results (2026-11-17)

- Task cases: **15 of 15** checks pass, verified by script against the live API. Runs were done by the session that wrote the skill, so there is no independent no-skill baseline yet; `claude plugin eval` gives one.
- One change came from the runs: pair `plan_gain_vs_kpi` with `plan_people_lifted`, because the UAE's 3.8× applies to about 311 people.
- Three facts were corrected while writing the field reference (R23): rank is by expected people lifted, not per cost; `people` is the smaller of the two population estimates; expected people lifted = people × chance below 25 Mbps × the measured lift share.

### Iteration 2 (2026-11-17, after a radio planner's review)

- **Review:** show the data and its period first; define the baseline and its KPIs with its own numbers; say how many weeks a probability comes from; explain why a hexagon is not in the plan; show a map with buildings; call shortlists estimates and ask for CAPEX, OPEX, market share and strategy.
- **Changes:** `about` command (sources, quarter dates, check time); `map` command (exact H3 outline over satellite imagery); `references/data-sources.md` (sources and vintages, how the chance is made, the KPI baseline and its numbers per country, reasons a hexagon is left out, inputs that sharpen a shortlist); an answer structure in `SKILL.md`.
- **Corrections found while writing it (R23):** steep and high sites are flags, not rejections (only under 1,000 m² of built-up land rejects); the UAE's budget is 29.3 tower-equivalents, not 1,000.
- **Result:** 10 new graders encode the review; **25 of 25** pass against the live API.

## Consequences

- **Positive:** agents can use the planner correctly from a plain question; regressions in the data surface in CI.
- **Negative:** trigger accuracy is not yet measured with a model; the graders depend on the current quarter's data and need updating when it is refreshed (the live check flags it).

## Related Decisions

- ADR-008 (plan and expected people lifted), ADR-009 (tools and notes), ADR-011 (public API and MCP).
