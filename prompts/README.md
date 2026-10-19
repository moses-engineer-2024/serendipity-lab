# prompts/ — AI Prompt & Agent Engineer

Owner: **Me** (role 4, also roles 1 and 3). **Due Hour 6.**

Four prompts, each returning structured JSON, each testable independently:

- `abstractor` — user text **and** corpus papers -> functional problem / constraints /
  mechanism / domain tags. Schema: [`config/schemas/abstraction.schema.json`](../config/schemas/abstraction.schema.json).
  Required for corpus papers; `mechanism` is nullable for user input that proposes no approach.
- `decomposer` — user abstraction -> 2–4 sub-problems / alternative abstractions. **Also used in
  rewrite mode**: given a skeptic critique, produce better queries.
- `skeptic` / reviewer — critique each candidate, decide keep vs. drop, with a reason and
  boundary conditions.
- `translator` — grounded what-if hypothesis + `source_passage` + `mapping` +
  `reviewer_note`. **No passage and no mapping means the suggestion is dropped, not shown.**

`prior_art` was **cut** at Hour 2 — the decomposer replaces it. See [`docs/cut_list.md`](../docs/cut_list.md).

Format is plain markdown with YAML front matter, so prompts can be edited without touching Python:

```markdown
---
version: v1
---
## SYSTEM
You are ...

## USER
Problem text: {{text}}
```

## `abstractor.md` — written and live-verified

**Status: written, run against `gemini-3.8-flash`, verified 3/3.** Check it yourself:

```bash
set -a; source .env; set +a
python3 data/check_abstractor_prompt.py
```

It asserts, on the hero input, on `gecko_adhesive`, and on a jamming seed paper:

- no leak in `functional_problem` or `mechanism`
- `mechanism` is `null` for user input (D14) and present for a paper
- output validates against the full untranslated schema

| Input | leak-free | `mechanism` |
|---|---|---|
| Hero (robotics → physics) | yes | `null` |
| `gecko_adhesive` | yes | `null` |
| Jamming seed paper | yes | present |

The hero input abstracts to *"Conform to an arbitrary boundary and immobilise what it encloses,
without item-specific configuration and without continuous sensing."* No robotics, no physics.

## The one thing that can invalidate the result

The abstractor **will name the answer if the prompt lets it.** With a loose prompt the same model
returned `domain_tags: ['granular_jamming', ...]` and a mechanism reading "granular material" for
the hero input. That puts the correct collision directly into the query, so retrieval finds the
jamming papers no matter what the index holds. It demos well and proves nothing.

So **the few-shots are load-bearing, not polish.** They are what took that output to the line
above. Gateway rule 17 turns a leak into a failed call rather than a cached one, and
`data/check_abstractor_prompt.py` fails if a leak reappears.

## Still to write by Hour 6

`decomposer.md`, `skeptic.md`, `translator.md`, and the `decomposer` / `skeptic` / `translator`
schemas. All four are wired into `config/models.yaml` already; only the files are missing.

One trap already measured, for the three remaining prompts: Gemini cannot express a nullable
field. If a field is in `required`, the model satisfies it with the **literal string `"null"`**,
which is truthy downstream. Drop nullable fields from `required` and normalise `"null"` / `"none"`
/ `"n/a"` / `""` to `None`. See gateway rule 15.

## Provider

Calls go through **Person B's gateway** — do not call the API directly. It owns timeouts, retries,
caching, schema translation and validation. Model and temperature are read from
[`config/models.yaml`](../config/models.yaml); never hard-code them here.

Note for testing prompts in isolation: DeepSeek and Anthropic were both tried and abandoned inside
the Hour 2 window (see `docs/HOUR2_SIGNOFF.md` §6–7). If a prompt behaves differently under a
different model, that is a finding about the prompt's robustness, not a reason to change provider.