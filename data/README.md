# data/ — Vector DB & Data Engineer

Owner: **Me** (role 3, also roles 1 and 4). Corpus locked at Hour 2 in
[`config/corpus.yaml`](../config/corpus.yaml).

**Current state: the corpus and the baseline index exist. The abstraction index does not
yet, because it needs Person B's gateway and `prompts/abstractor.md`.**

## The one command that rebuilds everything

```bash
python3 -m pip install -r requirements.txt
set -a; source .env; set +a

python3 data/resolve_subfields.py     # config/corpus.lock.yaml  (fails loudly on a miss)
python3 data/ingest_corpus.py         # data/corpus/corpus.jsonl  -> 3,000 papers
python3 data/abstract_corpus.py       # data/corpus/abstractions.jsonl  (needs the gateway)
python3 data/build_index.py           # data/chroma/  (all three collections)
```

Every step is resumable and safe to interrupt. Corpus and index artifacts are gitignored;
the commands are the deliverable.

## Scripts

| Script | Does | Needs a key? |
|---|---|---|
| `resolve_subfields.py` | Resolves the 21 OpenAlex subfield names in `corpus.yaml` to IDs, writes `config/corpus.lock.yaml`. Enforces `unique_subfield_assertion`: a non-optional miss or a subfield claimed by two of our fields is a **hard failure**, because a wrong field tag produces a "cross-domain" hit that is really the user's own field. | yes |
| `verify_seeds.py` | The Hour 2 seed gate. OpenAlex → Europe PMC → arXiv, per `source.fallbacks`. Writes `verified`/`manual_paste` and, with `--apply-status --yes`, appends the dated amendment. | yes |
| `ingest_corpus.py` | Fetches the corpus: seeds first, then distractor classics, then the year-stratified sample. Applies every `corpus.yaml` rule. | yes |
| `embedder.py` | Shared embedder. Enforces `one_model_rule` and `assert_at_load`. | no |
| `abstract_corpus.py` | Resumable batch job over B's gateway. Leak check, full-schema post-validation, failures to a retry file. | yes |
| `build_index.py` | ChromaDB, 3 collections. Refuses to mix vector spaces if the embedder changed. | no |
| `retrieve.py` | `structural_score`, `matched_on`, derived `heresy`, home-field exclusion, drop rule. | no |

## Corpus as built

3,000 papers, 375 per field, 13 seeds, 200 distractor classics, 2,787 stratified sample.
Verified: unique paper IDs and DOIs, no non-article types, no unknown field tags, no empty
abstracts, abstracts 400–3000 chars, **0 outcome papers present**. Reproducible from
`random_seed: 42` — a fresh draw with the same seed returns papers already in the corpus.

Two judgement calls, both measured rather than assumed:

- **Field assignment uses `primary_topic.subfield`, the same criterion as the fetch filter**,
  so the two cannot disagree. OpenAlex files O'Hern's 2003 jamming paper under "Materials
  Chemistry" and Metropolis' 1953 paper under "Biomedical Engineering". Reading the full
  `topics` array finds the right subfield for those, but then genuinely interdisciplinary
  papers collide into two of our fields. Seeds keep their hand-assigned field from
  `validation_cases.yaml`, per `corpus.yaml tagging.seeds`.
- **Field tagging is never LLM-based.** Home-field exclusion depends on it being right, and
  `tests/test_retrieve.py` proves exclusion by assertion rather than by eye.

## The exclusion is the load-bearing part

All 7 outcome papers — the breakthroughs the validation is built on — exist in OpenAlex
**with full abstracts**. During the run the filter caught Kirkpatrick 1983 "Optimization by
simulated annealing", which would otherwise have passed every other check. If this filter is
broken, the validation cases answer themselves and every number in the deck is meaningless.

Dropping `ant_colony_routing` at the seed gate initially took Dorigo 1996 with it and
silently un-excluded it. It is retained under `excluded_outcome_papers_dropped`.

## Still open

1. **4 seeds need `manual_paste`** (Liu 2010, Shapley 1974, Gale 1962, Nakagaki 2000). None
   is gate-blocking — every surviving case already clears 2 verified.
2. **`docs/field_qa.md`** — 20 random titles per field, read by hand. The single highest-value
   Hour 4 check: 8 fields × 20 titles is 160 reads and it catches a wrong field tag before
   3,000 papers are abstracted with it.
3. **The 600-paper pilot.** Do not skip it. The LLM provider changed twice inside the Hour 2
   window, and abstraction quality is the whole thesis.
