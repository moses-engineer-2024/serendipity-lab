# Hour 0-2 Sign-off

Everything that needed a decision has one. What remains is verification that needs a network and a person, listed in §3.

## 1. Decision log

| # | Decision | Why | Consumers |
|---|---|---|---|
| D1 | **Hero = robot gripper ← granular jamming** | Near-zero keyword overlap, crisp abstraction, instant aha | everyone |
| D2 | **6 validation cases**, pre-registered, split into 2 dev and 4 held-out | Held-out cases are not run until the Hour 14 gate, so tuning cannot leak into the proof | me |
| D3 | **Outcome papers are excluded from the corpus** (Brown 2010, Tero 2010, Roth–Sönmez–Ünver 2004/05, Kirkpatrick 1983, Dorigo 1996, Geim 2003) | They carry the home-field vocabulary and would make the test trivial | me |
| D4 | **The baseline gets home-field exclusion too** | Otherwise the baseline drowns in home-field papers and the comparison is a strawman. A no-exclusion row is reported as secondary | me, deck |
| D5 | **Two ablations:** `ours_retrieval_only` and `ours_full` vs baseline | Shows where the lift comes from, and that the drop rule can only remove hits | me, deck |
| D6 | **Corpus = OpenAlex, 3,000 papers, 8 fields × 375**, reproducible sample (seed 42), year-stratified, plus 25 most-cited "classics" per field | One consistent taxonomy with abstracts. Classics and year strata stop seeds being identifiable by fame or era | me |
| D7 | **Field tags are a deterministic subfield lookup, never an LLM.** Ambiguous papers are dropped | Home-field exclusion depends on tags being right | me |
| D8 | **Two structural vectors per paper** (problem, mechanism) plus a raw vector for the baseline. `structural_score = max cosine over both vectors and all queries` | The user's problem should match a paper's problem or its mechanism. Cheap, and it gives an inspector-ready `matched_on` | me, B |
| D9 | **Embedding = `BAAI/bge-base-en-v1.5`**, local, normalized, cosine, no query prefix, model asserted at load | No network risk at demo time; symmetric matching needs no prefix | me, B |
| D10 | **Vector store = ChromaDB**, 3 collections, `$nin` filter on `field` | Metadata filtering; stays small | me, B |
| D11 | **LLM = Anthropic `claude-sonnet-5-5` for all four tasks.** Abstractor and decomposer must share a model. Skeptic is first to drop to `claude-haiku-5-5` if latency hurts | Consistent embedding space; quality over cost at 3k papers | me, B |
| D12 | **Four prompts:** `abstractor`, `decomposer` (also rewrite mode), `skeptic`, `translator`. `prior_art` is cut | Decomposer replaces prior-art as the fourth prompt | me |
| D13 | **Cache key = `(task, cache_id, prompt_sha256, model, schema_sha256)`** | A superset of the planned key. Editing a prompt cannot return stale results | B |
| D14 | **`mechanism` is nullable in the abstraction schema** (required for corpus papers, null for user input with no proposed approach) | Users often state a problem, not a solution | A, B |
| D15 | **Contract deltas:** `chaos` accepted and ignored, `prior_art` removed, `heresy` derived, `matched_on` added | See `cut_list.md` | A, B |
| D16 | **Report both the first full run (Hour 14) and the final run**, naming which cases influenced tuning | Defends against "you tuned on the test" | deck |
| D17 | **Slide 3 uses the hero example**, hand-written until Hour 6, then replaced with real system output | The audience should see the abstraction of the case they are about to watch | deck |

## 2. Corrections to earlier advice

- **Brown et al. 2010 is not a hit target.** I listed it as an acceptable source for the hero. It is the *outcome* paper, in the home field. It is excluded from the corpus and used only as a slide reference.
- **Tero et al. 2010 and the Roth–Sönmez–Ünver kidney papers are excluded for the same reason.**
- **Shark-skin riblets and termite mounds were dropped.** The source-side literature with retrievable abstracts was too thin. Gecko adhesion replaced shark skin.

## 3. Hour 2 gate

Status as of the close of the Hour 2 window. Two items still need people, not code.

- [ ] **Huddle (15 min, all three).** Agenda and hand-off contents ready in
      **`docs/huddle.md`** so the 15 minutes is spent deciding rather than reading. Needs the three
      people in a room.
- [x] **Get keys.** `GEMINI_API_KEY` obtained and verified with a live `generateContent` call.
      `OPENALEX_API_KEY` obtained and verified with live OpenAlex queries. Both live in a gitignored
      `.env`; see `.env.example`. (The LLM provider moved Anthropic → DeepSeek → Gemini; see §6–7.)
- [x] **Resolve subfields.** `data/resolve_subfields.py` run against `config/corpus.yaml`.
      **All 21 subfield names resolved exactly** across 8 fields, 0 unresolved, no collisions against
      `unique_subfield_assertion`. `config/corpus.lock.yaml` committed. Re-check with
      `python3 data/resolve_subfields.py --check`.
- [x] **Verify seed abstracts.** `data/verify_seeds.py` run. OpenAlex, then Europe PMC and arXiv per
      `corpus.yaml source.fallbacks`. **5 of 6 cases survive; the gate minimum is 5, so it passes.**

      | Case | Verified | Note |
      |---|---|---|
      | `jamming_gripper` | 3/4 | Trappe 2001 recovered from Europe PMC |
      | `gecko_adhesive` | 3/3 | Autumn 2000 recovered from Europe PMC |
      | `kidney_exchange` | 2/4 | exactly at threshold; Shapley and Gale need `manual_paste` |
      | `physarum_network` | 2/3 | Tero 2007 recovered; OpenAlex alone left this at 1/3 |
      | `simulated_annealing` | 3/3 | all verified |
      | `ant_colony_routing` | 0/3 | **DROPPED** — no abstract in any of the three sources |

      `ant_colony_routing` is dropped: Deneubourg 1990, Goss 1989 and Beckers 1992 carry no abstract in
      OpenAlex, Europe PMC or arXiv. Recorded as a dated amendment. No `input_text`,
      `acceptable_sources`, metric, baseline or reporting rule was altered. Six seeds remain
      `manual_paste` but **none is gate-blocking**.

      All 7 `excluded_outcome_papers` were confirmed present in OpenAlex **with full abstracts**. The
      ingest job must apply `corpus.yaml exclude_titles_from` or the validation cases answer themselves.
- [ ] **Input-language check.** Have A or B read each `input_text` cold and flag any word that gives
      away the source field. Set `input_language_check.status`. **Cannot be done by me** — I wrote the
      answers.
- [x] **Commit** and the hash recorded in `validation_cases.yaml: locked_at_commit`
      (`d561ca9`, the commit that locked the content; recorded in `17b0405`).
- [x] **Slide 3.** Deck skeleton written in **`docs/deck.md`**, all five slides, slide 5 intentionally
      empty until the Hour 14 numbers exist. Slide 3 carries a **real** capture from a live
      `gemini-3.8-flash` abstractor run, marked provisional and leak-checked, to be regenerated from
      the final prompt by Hour 6.
- [x] **Mock data for A.** `frontend/src/mock/hero_run.json` (21 events) and
      `dropped_candidate.json`, with `frontend/src/mock/README.md`. Every `source_passage` is verbatim
      from a real paper's abstract, verified against OpenAlex and Europe PMC.

**Still not done, and it is the real blocker:** the **abstraction batch job cannot run yet**.
The corpus exists (3,000 papers) and the baseline index exists, but `abstractions_*` needs
two things that are not written: Person B's gateway and `prompts/abstractor.md`. Until both
exist there is no abstraction index, so `retrieve()` has nothing to search and the hero
collision cannot land.

The pipeline itself is built and verified:
`data/resolve_subfields.py` → `data/ingest_corpus.py` → `data/abstract_corpus.py` →
`data/build_index.py`, each resumable, with `requirements.txt` pinning the environment.

**Two remaining items are cheap and should not be skipped:

1. **`docs/field_qa.md`** — 20 random titles per field, read by hand. 160 reads catches a
   wrong field tag before 3,000 papers are abstracted with it.
   Regenerate with `python3 data/sample_field_qa.py`; seeded, so the sample is identical every
   time and cannot be accused of being cherry-picked. **~40 minutes.**
2. **The 600-paper pilot** before the full run. The LLM provider changed twice inside this
   window, and abstraction quality is the entire thesis.

## 8. Third amendment status: `prompts/abstractor.md` written and tested

The abstractor prompt exists and has been **run live against `gemini-3.8-flash` and verified**,
not merely drafted. `data/check_abstractor_prompt.py` asserts on the three cases that matter
and currently passes 3/3:

| Input | leak-free | `mechanism` |
|---|---|---|
| Hero (robotics → physics) | yes | `null`, as D14 requires |
| `gecko_adhesive` (dev) | yes | `null`, as D14 requires |
| A jamming seed **paper** | yes | present, as required for corpus papers |

The hero input abstracts to *"Conform to an arbitrary boundary and immobilise what it encloses,
without item-specific configuration and without continuous sensing."* — no robotics, no physics,
and `mechanism` correctly null because the input states a problem and not an approach.

This is what makes the few-shots load-bearing rather than decorative. The same model with a
looser prompt returned `domain_tags: ['granular_jamming', ...]` for the same input, which places
the answer in the query and makes retrieval self-fulfilling.

**Two defects found by running it, both now fixed and both recorded for B:**

1. Gemini cannot express `["string","null"]`, so a nullable field left in `required` is forced to
   `STRING` and the model satisfies it with the literal text `"null"`. Truthy downstream, and
   indexable as a real mechanism. Fixed by dropping nullable fields from `required` and
   normalising `"null"`/`"none"`/`"n/a"`/`""` to `None`. Gateway rule 15.
2. `data/verify_seeds.py` now rejects OpenAlex **citation stubs** as abstracts. Measured: Gale
   1962's `abstract_inverted_index` holds
   `"(2013). College Admissions and the Stability of Marriage. The American Mathematical
   Monthly: Vol. 120, No. 5, pp. 386-391."` — bibliographic metadata. Unchecked it would have
   been abstracted into the index as though it were prose.

**Seed recovery outcome, stated plainly:** 3 of the 4 `manual_paste` seeds are **not
recoverable** from any open source. Shapley 1974 and Nakagaki 2000 have no abstract in OpenAlex,
Europe PMC or arXiv; Gale 1962's only OpenAlex "abstract" is the citation stub above; Liu 2010
is `type=review` and is excluded by the corpus type filter. Recovering them needs a human with
journal access. **None is gate-blocking** — every surviving case already clears 2 verified — so
this is a nice-to-have, not a blocker.

## 9. Third provider-shape finding

The one remaining hard dependency is **Person B's gateway**. `prompts/abstractor.md` and
`data/abstract_corpus.py` are both ready and `--dry-run` clean, but a live batch needs
`backend/app/gateway.py` exposing `LLMGateway.run(task, inputs, cache_id=...)`. Until it exists,
`data/corpus/abstractions.jsonl` cannot be written and the abstraction index cannot be built.

## 4. Pre-registration statement

`config/validation_cases.yaml` was written before any system was run on any case. The inputs, acceptable sources, metrics, baselines, and reporting rules in it are fixed. Any later change is a dated amendment, and the table in the deck says so if one was made.

## 5. Files

```text
config/corpus.yaml
config/models.yaml
config/validation_cases.yaml
config/schemas/abstraction.schema.json
docs/hero_scenario.md
docs/cut_list.md
docs/llm_gateway_spec.md
docs/HOUR2_SIGNOFF.md
```

Still to write by Hour 6: `prompts/{abstractor,decomposer,skeptic,translator}.md` and the `decomposer`, `skeptic`, `translator` schemas.

---

## 6. Amendments to the decision log

D11 stands as written above. It is superseded by:

| # | Supersedes | Decision | Why |
|---|---|---|---|
| A1 | D11 | **LLM provider = DeepSeek**, `deepseek-v4-pro` on all four tasks. `llm.base_url = https://api.deepseek.com`, `llm.api_key_env = DEEPSEEK_API_KEY`. **Thinking mode disabled on every request.** | Team moved off Anthropic. The swap was anticipated by `llm_gateway_spec.md` rule 10, so it is `models.yaml` plus one adapter file. |

Two things this changes that are not obvious:

- **No validation re-run is owed.** `validation_cases.yaml` requires a full re-run after any model change.
  No case has been run yet, so the switch lands before the first call rather than after it.
- **Thinking mode is the real hazard, not the model.** DeepSeek enables it by default at effort `high`,
  and in thinking mode it *silently ignores* `temperature`. Left on, `temperature: 0` on the abstractor is a
  no-op, the validation table stops being reproducible, and the chain of thought will not fit the 20s hero
  budget. See `llm_gateway_spec.md` rules 12-13.

Unverified, and honest about it: DeepSeek also serves an Anthropic-format mirror at
`https://api.deepseek.com/anthropic`. The route exists and accepts the key, but it has **not** been tested for
tool use or structured output. If it passes the gateway acceptance tests it becomes the cheaper swap, because
the adapter keeps its existing shape. Until then the OpenAI-format base_url stands.

Operational note: the DeepSeek account was at zero balance when this was written. Every call returns
`Insufficient Balance` until it is topped up. Anthropic's monthly credits have no equivalent — DeepSeek is
prepaid. At ~750k output tokens for the full 3k-paper run this costs on the order of $1-2, so a small
top-up covers the whole project.

---

## 7. Second amendment: DeepSeek to Gemini

A1 above is superseded by:

| # | Supersedes | Decision | Why |
|---|---|---|---|
| A2 | A1, D11 | **LLM provider = Google Gemini**, `gemini-3.8-flash` on all four tasks. `llm.base_url = https://generativelanguage.googleapis.com/v1beta`, `llm.api_key_env = GEMINI_API_KEY`, **thinking budget 0**. **Concurrency 8 -> 2.** | DeepSeek is prepaid and the account was unfunded, so every call failed. Moved to the Gemini free tier. |

The model was chosen from this account's **live catalogue**, not from memory, and that mattered:

- `gemini-2.5-pro` and `gemini-2.5-flash` are **retired for new accounts**. They return HTTP 404 with a
  message pointing at `gemini-3.8-flash`. Guessing from memory would have produced a 404 at Hour 6.
- `gemini-3.1-pro-preview` rate-limited (429) immediately and is a **preview** model, so it must not be in a
  demo: it can be withdrawn mid-pitch.
- `gemini-3.8-flash` is GA, and measured clean on the hero input at thinkingBudget 0: 2.6-5.9s, no thought
  parts, schema-valid JSON.

Measured facts that now constrain the build:

1. **Free-tier rate limits, not tokens, are the binding constraint.** At concurrency 8 the account returned
   429 then 503 after one to three rapid calls. Concurrency is now 2. The retry policy and the resumable
   cache are what make the 3k-paper batch survivable, so they are correctness features here, not extras.
2. **`responseSchema` rejects two things our own schemas use.** It 400s on `additionalProperties` and on
   union types such as `["string", "null"]`. The gateway must translate to Gemini's proto-flavoured schema
   and drop those keywords, then validate against the **full untranslated** schema afterwards. See gateway
   rules 14-16.
3. **A nullable field must not be sent as a required string.** D14 makes `mechanism` nullable for user
   input. Sent as a required `STRING`, the model invented one ("Micro- and nanostructures...") for a
   problem that proposed no approach. Leave it out of `required` for user-input calls.

And the one finding that matters most for the thesis:

4. **The abstractor will name the answer if allowed to.** With a loose prompt, the hero input came back with
   `domain_tags: ['robotics', 'soft_actuation', 'granular_jamming', 'mechanical_design']` and a `mechanism`
   reading "a flexible enclosure filled with granular material". That puts the correct collision directly
   into the query, so retrieval finds the jamming papers no matter what the index contains. It would look
   like a successful demo and it would be worthless — and it would invalidate the `jamming_gripper` case.

   This is fixable and was verified fixed: with a prompt that names the field meanings and forbids naming a
   solution, the same input produced "Envelop and securely retain items of unpredictable geometry..." and a
   mechanism of "A phase-like or state-changing transformation within a conformable medium" — abstract, and
   no leak. So the few-shot work at Hours 4-6 is not a quality nicety here, it is the thing standing between
   a real result and a rigged one. Gateway rule 17 adds a leak check so a leak fails the call instead of
   being cached.

No validation re-run is owed for either provider change: `validation_cases.yaml` requires one after any model
change, and no case has been run yet. That window is now open a second time and worth protecting.
