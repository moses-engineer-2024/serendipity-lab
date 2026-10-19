# frontend/src/mock/ — mock data for the UI

**You are Person A. Build against this, not against a guess.**

Everything here matches the contracts frozen at Hour 2. If your UI needs a shape that is not here,
that is a **contract question for me, not something for you to invent** — ask, and I will change
`config/` and `docs/` in a commit you can pull. Do not build against the original team brief; it is
superseded (see `docs/cut_list.md`).

```bash
git fetch && git checkout hour0-2-lock
cat frontend/src/mock/hero_run.json
```

## Files

| File | What it is |
|---|---|
| `hero_run.json` | The full hero run: request, abstractions, and the complete SSE event sequence — 15 trace events then 5 results then `done`. |
| `dropped_candidate.json` | Debug-only. A candidate the drop rule removed. **Never render this as a result.** |

## Play back the stream

The events in `hero_run.json` are in order. Replay them as `EventSource` messages:

```ts
import heroRun from "./mock/hero_run.json";

const source = new EventSource(`/api/runs/${runId}/stream`);
// A: for a mock, iterate heroRun.stream and render each event in order.
for (const ev of heroRun.stream) { /* type === "trace" | "result" | "done" */ }
```

Use the `ts` deltas (~1s apart) for animation so the trace *reads as a process*, not a dump.

## Every state you need is in there, on purpose

The fixture deliberately exercises states that are annoying to build and easy to forget:

- `meta.cached: true` — **cache-hit display**. The hero scenario will be cached for instant replay
  on stage, so this is the *expected* path during a demo, not an edge case.
- `llm_retry` — the retry state, with `attempt` in `meta`.
- `rewriting` then a second `retrieving` — the agent loop actually looping. Show this happening;
  it is the clearest evidence it is an agent and not a single query.
- `reviewing` reporting rejections — the skeptical reviewer working, not just passing.
- Results with `matched_on` of **both** `problem` and `mechanism`, and `heresy` at **all three**
  levels (`high`, `medium`, `low`).
- Two deliberately weak results at the bottom of the ranking.

## The contract, exactly

**Trace** — `type`, `step`, `message`, `ts`, and `meta: {task, cached, attempt, ms}`.
`step` is frozen to these ten values only:

```
abstracting  decomposing  retrieving  reviewing  rewriting
translating  ranking      llm_retry   cache_hit  done
```

**Result** — every one of these fields is required:

```ts
{
  id: string, title: string, year?: number, venue?: string, doi?: string,
  source_field: string,
  structural_score: number,      // 0..1
  matched_on: "problem" | "mechanism",   // drives the inspector
  heresy: "low" | "medium" | "high",     // derived server-side, NOT your job to compute
  hypothesis: string,
  source_passage: string,        // exact quote from the retrieved abstract
  mapping: Array<{ source_concept: string, home_concept: string }>,
  reviewer_note: string          // where the analogy breaks
}
```

## Four things that will bite you if I have not said them clearly

1. **`prior_art` does not exist.** It is cut. The original brief still shows it — ignore the brief.
2. **`chaos` is accepted and ignored.** Keep it in the request so the contract does not break, but
   there is no Serendipity Slider. Do not build a control for it.
3. **`heresy` is derived on the server** from topical distance. Render it as a badge only if you have
   time; it is not worth a panel.
4. **`source_passage` and `mapping` are the product.** Every passage in this fixture is a verbatim
   sentence from a real paper's abstract — I verified all five against OpenAlex and Europe PMC. If
   the passage is missing, the candidate was **dropped by the system** and must not appear. There is
   no partial state and no placeholder text.

## What is invented in this fixture

The scores, `heresy` labels, `reviewer_note` wording and `hypothesis` text are **placeholders I
wrote**. The titles, years, DOIs and passages are real. Real output lands at Hour 6 and will differ.
Build the shapes, not the values.

## The two answers you are building toward

The demo only has to land one idea — *"wait, it's the vacuum-packed coffee brick thing?"* — so the
two UI moments that matter are:

1. **The trace**, streaming, showing the agent decompose and reconsider. This is why it is an agent.
2. **The Why-This-Collided inspector**: the source passage and the concept mapping table, side by
   side. This is what makes it evidence instead of a suggestion.

The inspector is currently **first to reinstate** if we are cut down (`docs/cut_list.md`), so build
the result card with the inspector slot in mind even though the inspector ships later.