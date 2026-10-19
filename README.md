# Serendipity Lab

**Track:** AI Agents & Autonomous Workflows — NYLP AI Products Hackathon
**Team:** 3 engineers, ~24 hours
**Source of truth:** [`serendipity_lab_v2_team_brief.md`](./serendipity_lab_v2_team_brief.md)

> **Build against `hour0-2-lock`, not this file.** The contracts below were locked at Hour 2 and
> **supersede** the team brief wherever they disagree. Read them in this order:
> [`config/`](./config) · [`docs/HOUR2_SIGNOFF.md`](./docs/HOUR2_SIGNOFF.md) (decision log + what is still unverified) ·
> [`docs/cut_list.md`](./docs/cut_list.md) (what is cut) · [`docs/hero_scenario.md`](./docs/hero_scenario.md) ·
> [`docs/llm_gateway_spec.md`](./docs/llm_gateway_spec.md)
>
> Four deltas from the brief, all binding:
> `prior_art` is **removed** — do not render it. `chaos` is **accepted and ignored**.
> `heresy` is **derived** (no separate model). `matched_on` is **added** for the inspector.

> Search tools are optimized for relevance, so they keep researchers inside their own
> field. Serendipity Lab is an autonomous agent that **strips domain vocabulary from a
> researcher's problem down to its underlying functional structure**, then searches the
> literature of *other* fields for papers that solve the *same abstract problem*.

## The insight

Match on **structure, not topic**.

| Stage | Example |
|---|---|
| Original text | "Optimizing traffic routing through a city grid during accidents" |
| Abstracted | "Decentralized rerouting of flow through a network when nodes fail, without central coordination" |
| Collision (other field) | A paper on ant foraging and pheromone-based path reinforcement |

The same abstraction runs on every corpus paper at indexing time, and matching happens in
"structure space." Cross-field results come from **explicitly excluding the user's home
field**, not from sampling distant vectors.

## Architecture

```
User problem text
      |
      v
[1] ABSTRACTOR (LLM)  ->  functional problem statement
      |
      v
[2] AGENT LOOP (visible trace in UI)
       |- Decompose into 2-4 sub-problems / alternative abstractions
       |- Retrieve top-K per query from abstraction index (home field excluded)
       |- SKEPTICAL REVIEWER critiques each candidate
       |     \- weak candidates -> rewrite query -> re-retrieve (max 2 loops)
       \- Rank survivors
       |
       v
[3] WHAT-IF TRANSLATOR (LLM)  ->  grounded hypothesis + concept mapping table
       |
       v
UI: result cards, Why-This-Collided inspector, agent trace, Pulse map
```

> The prior-art check was cut at Hour 2 and no longer exists. See `docs/cut_list.md`.

## Anti-hallucination rules

Every hypothesis must include `source_passage` (exact quote), `mapping` (source concept ->
home concept), and `reviewer_note` (boundary conditions + likely failure mode). If the
translator cannot produce a passage and a mapping, the suggestion is **dropped**.

## Repo layout

| Path | Owner role | Contents |
|---|---|---|
| `backend/` | Backend & API Engineer | FastAPI, SSE streaming, agent-loop orchestration, caching/fallbacks |
| `frontend/` | Frontend & UI/UX Lead | Workspace, streaming trace panel, result cards, inspector, Pulse map |
| `prompts/` | AI Prompt & Agent Engineer | Abstractor, reviewer, translator, prior-art prompts (structured JSON out) |
| `data/` | Vector DB & Data Engineer | Corpus sourcing, abstraction batch job, ChromaDB/FAISS index |
| `eval/` | Product Lead + AI Engineer | Validation experiment: baseline vs. ours on famous cross-domain breakthroughs |

## API contract (locked Sprint 0)

`POST /api/collide` -> `{ "run_id": "..." }` (202)

```json
{ "text": "researcher's problem text", "home_fields": ["civil engineering"], "chaos": 0.6 }
```

> `chaos` stays in the request for contract stability but the slider is cut: **accept it and ignore it.**

`GET /api/runs/{run_id}/stream` -> Server-Sent Events

```json
{ "type": "trace",  "step": "abstracting", "message": "Stripping domain terms...", "ts": 1712345678,
  "meta": { "task": "abstractor", "cached": false, "attempt": 1, "ms": 3120 } }
```

```json
{ "type": "result", "id": "r1", "title": "Paper title", "source_field": "ecology",
  "structural_score": 0.82, "matched_on": "mechanism", "heresy": "high", "hypothesis": "...",
  "source_passage": "exact quote from the retrieved abstract",
  "mapping": [{ "source_concept": "pheromone trail", "home_concept": "congestion-weighted route cost" }],
  "reviewer_note": "boundary conditions and likely failure mode" }
```

`matched_on` is `"problem"` or `"mechanism"` and is optional. `heresy` is derived from topical distance.
`prior_art` no longer exists.

`step` values are frozen: `abstracting`, `decomposing`, `retrieving`, `reviewing`, `rewriting`,
`translating`, `ranking`, `llm_retry`, `cache_hit`, `done`.

Frontend builds against mocks from Hour 0. **Any schema change requires telling the whole team.**

## Roles

3 people, one of whom holds three roles. That is the whole reason Tier 2 is cut.

| Person | Roles | Key deliverable |
|---|---|---|
| **Me** | Product & Pitch Lead (1) + Vector DB & Data (3) + AI Prompt & Agent (4) | Validation table, 5-slide deck, corpus + index + `retrieve()`, all four prompts |
| **A** | Frontend & UI/UX Lead (5) | Complete UI on mock data by Hour 6 |
| **B** | Backend & API Engineer (2) | `/collide` and `/stream` endpoints, and the LLM gateway |

The brief's original 5-role split is preserved in `serendipity_lab_v2_team_brief.md`.

## Timeline

| Hours | Phase | Goals |
|---|---|---|
| 0–2 | Align & lock | Hero scenario, corpus sources/fields, API contract, validation cases, repo + protected `main` |
| 2–6 | Ugly thin slice | End-to-end with hardcoded data; frontend on mocks; corpus batch job starts |
| 6–14 | Parallel build | Agent loop, index + retrieval, SSE, result cards, validation cases drafted |
| 14–18 | Integration & validation | Live backend; run validation; **go/no-go on abstraction vs. baseline** |
| 18–20 | Safety nets & polish | Cached hero + backup cases, fallbacks, micro-copy |
| 20 | **CODE FREEZE** | Bug fixes only, reviewed by two people |
| 20–24 | Pitch | Deck, backup video, rehearsals |

Cut order if behind: Pulse map -> side-by-side view -> prior-art check -> slider polish.
**Never cut the reviewer, the provenance, or the validation table.**

## Guiding principle

> If a feature doesn't make the structural-matching insight more visible, more believable,
> or more provable, it doesn't ship.

## Decisions — all locked at Hour 2

The brief left six open. All six are closed; see `docs/HOUR2_SIGNOFF.md` for the reasoning.

| # | Decision | Where |
|---|---|---|
| 1 | Hero: robot gripper <- granular jamming | `docs/hero_scenario.md` |
| 2 | Corpus: OpenAlex, 3,000 papers, 8 fields x 375, seed 42 | `config/corpus.yaml` |
| 3 | LLM: **Gemini `gemini-3.8-flash`**, free tier, thinking off, concurrency 2 | `config/models.yaml` |
| 4 | Embedding: `BAAI/bge-base-en-v1.5`, local, one model for both sides, asserted at load | `config/models.yaml` |
| 5 | Vector store: ChromaDB, 3 collections | `config/models.yaml` |
| 6 | Validation: 6 pre-registered cases, 2 dev + 4 held-out | `config/validation_cases.yaml` |

**Still open, and owned by me:** seed verification (all 20 seeds are `unverified`, no case has run),
`config/corpus.lock.yaml`, and the 600-paper pilot.