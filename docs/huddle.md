# Hour 2 huddle — 15 minutes, all three

**Nobody builds until this is done.** This is the last gate before A and B start coding against real
contracts.

Prep is already done so you can spend all 15 minutes on decisions, not on reading. Everything below is
committed on `hour0-2-lock`.

```bash
git fetch && git checkout hour0-2-lock
```

## Before you start (30 seconds, me)

Put these three files on a shared screen. That is all anyone needs to read:

1. `config/models.yaml` — the locked contract
2. `docs/cut_list.md` — what is cut
3. `config/validation_cases.yaml` — the proof plan

---

## Run of show

### 1 · The cut list (4 min) — **B enforces this**

Read `docs/cut_list.md`. Tier 2 is cut by default. The only decision needed is:

> **Does B accept the enforcer role?** Nothing outside Tier 1 starts without B's explicit OK.

**Why this is on the agenda at all:** I hold three roles and I am the busiest person here. If I am also
the one saying no, I will end up silently cutting my own work — which is the irreplaceable part —
instead of the team's. B saying no is the whole mechanism. Agree it out loud now.

**Never cut, at any hour:** the skeptical reviewer · provenance (`source_passage` + `mapping`) · the
validation table · the cached hero scenario.

### 2 · Handover to B (3 min) — **the gateway contract**

B reads `docs/llm_gateway_spec.md`. Five things he must know, and only he needs to know them:

| # | Point |
|---|---|
| 1 | Provider is **Gemini**, not Anthropic. One adapter class. The provider changed twice inside this window (Anthropic → DeepSeek → Gemini) and it was still `models.yaml` + one file. If a second file has to change, rule 10 is broken. |
| 2 | Key is `GEMINI_API_KEY` in a gitignored `.env`. He needs his own; do not send the value over chat. |
| 3 | `gemini-3.8-flash`, **thinking budget 0 on every request**. Gemini thinks by default; thought parts come back flagged and must never be parsed as content. |
| 4 | `responseSchema` **400s** on `additionalProperties` and on union types, both of which our schemas use. Translate, then validate against the full untranslated schema. A nullable field goes out **unrequired** or the model invents a value. |
| 5 | **Concurrency 2.** Free tier returned 429 then 503 within a few calls at 8. Retries and the resumable cache are correctness features now, not extras. |

**Ask B to confirm he can start today** and that the 11 acceptance tests in the spec are reachable by
Hour 6.

### 3 · Handover to A (3 min) — **the UI contract**

A reads `frontend/src/mock/README.md`. Three things:

1. **Build against `frontend/src/mock/hero_run.json`.** 21 events: 15 trace, 5 results, `done`. Every
   state he needs is in there, including cache-hit, `llm_retry`, the rewrite loop, and both
   `matched_on` values.
2. **Every `source_passage` in the mock is verbatim from a real paper's abstract** — I verified all five
   against OpenAlex and Europe PMC. So the mock shows what production will actually look like.
3. **`prior_art` does not exist. `chaos` is accepted and ignored.** The original team brief still shows
   both; the brief is superseded. If his UI needs a shape that is not in the mock, that is a contract
   question for me, not something for him to invent.

**Ask A to confirm the result card and the trace panel are unblocked today.**

### 4 · Open risks (3 min) — **say them out loud now, not at Hour 14**

1. **The abstractor can name the answer.** With a loose prompt it returned
   `domain_tags: ['granular_jamming']` for the hero input. That puts the correct collision in the
   query, so retrieval becomes self-fulfilling — it would demo well and prove nothing. Gateway rule 17
   makes a leak fail the call instead of being cached. **The few-shot work at Hours 4–6 is the thing
   standing between a real result and a rigged one.**
2. **Free-tier rate limits.** We got 503s, connection resets and read timeouts on a single call this
   hour. The cached hero scenario and the backup video are not paranoia, they are the plan.
3. **One validation case dropped.** `ant_colony_routing` had 0 of 3 seeds with an abstract in any
   source. Five cases remain, which is the gate minimum. Recorded as a dated amendment; nothing else
   in the protocol was touched.
4. **The excluded outcome papers are all in OpenAlex with full abstracts.** Brown 2010 — the paper
   that actually built the jamming gripper — matches its title perfectly. If the ingest job does not
   apply `exclude_titles_from`, every validation number is meaningless. That is my next task.

### 5 · Who does what next (2 min)

| Who | Next | By |
|---|---|---|
| **Me** | Ingest job: fetch corpus, apply seed + exclusion filters, tag fields, run the 600-paper pilot | Hour 4 launch |
| **Me** | `docs/field_qa.md` — 20 titles per field, hand-read | Hour 4 |
| **Me** | Six missing abstracts by `manual_paste` (Shapley 1974, Gale 1962, Nakagaki 2000, and the three ant papers). **None are gate-blocking** — every surviving case already has 2 verified. Low priority. | Hour 6 |
| **B** | Gateway with the Gemini adapter + acceptance tests | Hour 6 |
| **A** | Result cards + trace panel on the mock | Hour 6 |

---

## Decisions needed in these 15 minutes

1. **Does B accept the enforcer role?** (yes/no)
2. **Do A and B both have their own `.env` keys ready?** (yes/no)
3. **Anyone object to `ant_colony_routing` being dropped?** It is the only way to hit the gate minimum
   of 5, and manual recovery means three 1990s entomology abstracts pasted by hand.
4. **Is anybody free between Hour 2 and Hour 4 to read the four held-out `input_text`s cold** and flag
   any word that gives away the source field? (`input_language_check` — it cannot be done by me, because
   I wrote the answers.)

## Closing line

> "Contracts are frozen. Nobody changes one without telling everyone. Tier 2 stays cut unless B says
> otherwise. Go."