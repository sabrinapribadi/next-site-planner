# ADR-009: Planner API, MCP Tools and Grounded Site Notes (P5)

**Status:** Accepted — written and pushed before any P5 code (commit `b87f4a4`, 16:53); gate **failed** on live latency only (results below)
**Date:** 2026-10-14
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

Planners and AI assistants ask the same four questions of the results (PRD user stories):

| Question a planner asks | Tool |
|---|---|
| How slow is it here, and for how many people? | `gap_at(lat, lon)` |
| Which sites should we look at first, in this country? | `top_sites(country, k)` |
| Why is this nominal on the list? | `explain_site(country, rank)` |
| How do the countries compare? | `compare_countries(bar_mbps)` |

The fourth answer is a short written note. Language models invent numbers, so a note may only state numbers that the tools returned.

## Decision (pre-registered)

### Serving

- **One tool registry,** shared by a REST API (FastAPI) and an MCP server, so apps and agents get identical answers.
- **Serving store:** a small read-only store built from the outputs (`scripts/build_serving_store.py`, kept in `GEO_DATA_DIR/serving`, never in the repository): per-hexagon speed, people and gap type for populated hexagons; the checked site plans; country summaries.
- **Contracts:** typed requests and responses (pydantic), with units in field names (`people`, `share`, `mbps`).
- **Errors:** inputs outside the seven countries return a typed "out of scope" answer, not an error.
- **CI fixture:** a few-hexagon store committed under `tests/fixtures`, so contract tests run without data.

### Grounded site note (`explain_site`)

- **Facts given to the model:** the nominal's row (rank, intervention, people on both maps, chance below 25 Mbps, expected people lifted, built-up m², elevation, slope, flags), its district, and the country's lift rate.
- **Writer:** `gpt-6-luna` (OpenAI Responses API, reasoning effort "none"), behind a provider interface (one config line to swap).
- **Grader (deterministic):**
  - every number in the note must appear in the facts (rounding allowed);
  - at most 70 words;
  - no operator or vendor names, and no promises ("will", "guaranteed").
- **Fallback:** a template note built only from the facts. It is used when the grader fails, the call times out, or no key is set. Served notes are therefore always grounded.
- **Cache:** notes are cached by a hash of their facts, so repeated questions cost nothing.

### Budgets (R13; prices from developers.openai.com/api/docs/pricing, retrieved 2026-10-14)

| Item | Budget | Basis |
|---|---|---|
| Cost per 1,000 live notes | ≤ $0.20 | ~600 input + ~120 output tokens at $0.10 / $0.50 per million ≈ $0.12 |
| p95 latency, live call | ≤ 3,000 ms | One short completion |
| p95 latency, cached note | ≤ 50 ms | Local lookup |
| Cost lever | Batch precompute of every nominal's note | Batch API at half price; ≈ $0.8 for all ~12,750 nominals |

### Evaluation set

- **70 nominals:** 10 per country, stratified by rank (top, middle, bottom of each plan) and intervention.
- **10 hard cases:** crowding-flagged, steep or high, the two maps far apart, unchecked plans.
- **Measured:**
  - grounded pass rate of the live model before fallback;
  - required-fact coverage (intervention, people, chance below 25 Mbps, ground check);
  - cost per 1,000 and p50/p95 latency.

## Gate (ADR-002 P5, made precise here)

1. **Contracts:** API and MCP contract tests pass in CI.
2. **Evaluation:**
   - live grounded pass rate ≥ 90% before fallback;
   - 100% of served notes grounded after fallback;
   - required-fact coverage ≥ 90%.
3. **R13:** measured cost per 1,000 and p95 latency within budget (live run, recorded).
4. **CI:** CI replays the recorded live responses and re-grades them with the same grader, with no API key and no cost. A change to the grader or the facts that breaks a recorded note fails CI.

The 90% thresholds are our own pre-set choice, not a published standard.

## SOTA comparison

| Family | Method | Tested | Cited, not tested (why) |
|---|---|---|---|
| Tool use | Typed tools called by the model or the app | Yes | — |
| Grounding check | Every number traced to a tool result (deterministic) | Yes | — |
| Fact-level scoring | Atomic-fact precision against a source (FActScore) | No | Our facts are numbers; exact matching is stricter and free |
| Retrieval | Retrieval-augmented generation over documents | No | Answers come from structured tool results, not documents |
| Self-checking | A second model judges the first | No | Adds cost and its own errors; a rule-based grader is deterministic |

## Evidence (OpenAlex, retrieved 2026-10-14)

| Reference | Venue | Peer-reviewed | Year | Citations | Per year | Used for |
|---|---|---|---|---|---|---|
| Survey of Hallucination in Natural Language Generation | ACM Computing Surveys | yes | 2022 | 4,716 | 943.2 | language models state unsupported facts (why notes are graded) |
| FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation | Conference on Empirical Methods in Natural Language Processing (EMNLP) | yes | 2023 | 374 | 93.5 | fact-level precision scoring (compared, not used) |

Vendor and standards documents: OpenAI API pricing (developers.openai.com/api/docs/pricing, 2026-10-14); Model Context Protocol specification (modelcontextprotocol.io).

## Falsification

| Result | Diagnosis | Next action |
|---|---|---|
| Live grounded pass rate < 90% | The model adds or computes numbers | Tighten the prompt; else serve the template and say so |
| Cost or p95 over budget | Prompt too long or model too slow | Trim facts; precompute in batch; report the miss |
| Notes pass but omit required facts | Prompt underspecified | Required-fact checklist in the prompt |

## Results (2026-10-14; `data/outputs/p5_notes_eval.json`, run 1 in `p5_notes_eval_run1.json`)

**Built:**

- Serving store: 6,387,083 hexagons, 12,713 nominals, 7 countries (`scripts/build_serving_store.py`).
- REST API (FastAPI, `src/serving/api.py`) and MCP server (`src/serving/mcp_server.py`, MCP SDK 2.3) over one registry of four tools.
- 12 tests in CI (7 contract, 5 replay), with a 41 KB fixture store and no API key.

**Evaluation, 80 cases (70 stratified + 10 hard), `gpt-6-luna`:**

| Gate item | Run 1 (prompt v1) | Run 2 (prompt v2) | Budget or threshold | Pass (run 2) |
|---|---|---|---|---|
| Live grounded pass rate | 100% | 100% | ≥ 90% | Yes |
| Served notes grounded | 100% | 100% | 100% | Yes |
| Required-fact coverage | 78.8% | 100% | ≥ 90% | Yes |
| Cost per 1,000 live notes | $0.076 | $0.064 | ≤ $0.20 | Yes |
| p95 latency, live | 3,217 ms | 4,166 ms | ≤ 3,000 ms | **No** |
| p95 latency, cached | 1.7 ms | 1.8 ms | ≤ 50 ms | Yes |
| p50 latency, live | 2,347 ms | 2,329 ms | reported | — |
| Mean tokens (input / output) | 310 / 91 | 306 / 66 | reported | — |

**Between runs (pre-set remedies only):**

- **Run 1** missed coverage. US notes did not say "not yet checked on the ground", and some wrote "a 0.215 chance" instead of a percentage.
- **Prompt v2** added the required-fact checklist and a shorter target (45 words), and dropped two unused facts.
- **Disclosed fix:** the coverage check missed "small-cell" spelled with a hyphen (2 notes); it now accepts both spellings.

**Checks made stricter after run 2 (all 80 recorded notes still pass):**

- **Rounding:** must keep two significant figures. 2,161 may become 2,200 but not 2,000; 66 may not become 70.
- **Place names:** a name that appears in the facts (e.g. the district "Orange, Vermont") is not treated as an operator.
- **Template:** shares under 10% show one decimal.

**Gate: failed** on live p95 latency (4,166 ms vs 3,000 ms). The median is steady (2.3 s); the slow tail is API response time, not note length.

**As pre-set, the miss is reported and the cost lever applies:**

- Every nominal's note is written once (batch) and served from the cache: p95 1.8 ms.
- Live writing happens only on a cache miss.
- Notes are precomputed after the US plan is final (≈ $0.8 for all nominals).

## Consequences

- **Positive:** planners and agents query the same checked results; every note is traceable to numbers.
- **Negative:** notes are short and factual by design; anything outside the four tools is out of scope.

## Related Decisions

- ADR-008 (the site plans being explained)
- ADR-003 (planner deliverables)
- ADR-002 (P5 gate)
