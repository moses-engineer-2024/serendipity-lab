# eval/ — Validation experiment

Owner: **Me** (roles 1 + 4). This is the strongest slide and the go/no-go signal at **Hour 14**.

The plan is **pre-registered** in [`config/validation_cases.yaml`](../config/validation_cases.yaml)
and was written before any case was run. It is fixed. Any later change is a dated amendment in that
file, and the deck says so if one was made.

**Question:** "How do you know it works?"

## Systems compared

| Name | What |
|---|---|
| `baseline_raw_excl` | **Primary baseline.** `bge-base` embedding of raw user text vs raw abstracts, **with home-field exclusion applied**. |
| `baseline_raw_noexcl` | Secondary, reported but not the headline. |
| `ours_retrieval_only` | Ablation: abstractor + decomposer + dual-vector retrieval. No agent loop. |
| `ours_full` | What the UI shows: retrieval + skeptic + rewrite loop + drop rule. |

The baseline gets home-field exclusion too. Without it the baseline drowns in home-field papers and
the comparison is a strawman that flatters us. The no-exclusion row exists to show what that filter
is worth, not to be the headline.

## Cases

6 cases, split **2 dev / 4 held-out**:

- dev (usable freely while tuning prompts): `jamming_gripper` (also the hero), `gecko_adhesive`
- held-out (**not run before the Hour 14 gate**, never used as few-shots): `kidney_exchange`,
  `physarum_network`, `simulated_annealing`, `ant_colony_routing`

Shark-skin riblets and termite mounds were **dropped** — the source-side literature with retrievable
abstracts was too thin. Gecko adhesion replaced shark skin. Kidney exchange and ant colony are the
cases most likely to fail seed verification; a case drops if fewer than 2 acceptable sources have a
retrievable abstract, and **at least 5 cases must survive**.

Each `input_text` uses **home-field language only**. A teammate who has not seen the answers reads
each one cold and flags any word that gives away the source field.

## Metric

`hit@5` and `hit@10`: at least one **pre-registered acceptable source** in the top-k, deduplicated by
paper. Also report the rank of the first hit, and `matched_on` for ours. Other relevant-looking papers
do not count.

## Reporting rules — these are the credibility of the slide

1. Baseline is measured on **raw abstracts** and is never re-tuned to flatter our system.
2. Report the **first full run at Hour 14** (held-out cases untuned) *and* the final run, naming which
   cases influenced tuning. This is the answer to "you tuned on the test".
3. After **any** change to the abstractor prompt, schema, model, embedding model or corpus, **re-run
   all cases** and report only complete re-runs. Never a mixed table.
4. Table footer carries: git commit, prompt SHA-256 prefixes, model names, corpus size.
5. **Record which cases fail and why.** Those become the limitations slide. "We win 4 of 6" is a good
   result; a fabricated sweep is not.

## Integrity note

I designed the system being tested, so the bar for myself is higher, not lower. Two provider changes
were already made inside the Hour 2 window (Anthropic -> DeepSeek -> Gemini, see
`docs/HOUR2_SIGNOFF.md` §6–7). Neither triggered a re-run, because no case had been run yet. That
window is now closed: from the first run onward, a model change costs a full re-run of all cases.

## Known corpus biases — state these, don't hide them

- Small and curated (3,000 papers, 8 fields), not a survey of science.
- Seeds were chosen by us, because they are the known sources of the cases we test.
- Biology is the source field in half the cases.
- Subfield-based tagging is coarse; a paper can read as "the wrong field" to a human.

Frame it as curation, not limitation: *"a hand-auditable corpus of 3,000 papers across 8 fields, seeded
with every case we test."* Say the size out loud first, so it does not sound like an excuse.