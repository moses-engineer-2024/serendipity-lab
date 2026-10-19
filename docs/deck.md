# Deck skeleton — 5 slides

**Status: skeleton.** Slides 1–4 are written. **Slide 5 is empty on purpose** — it holds the real
validation numbers and cannot be written until the Hour 14 gate.

Nothing here is final copy. Speaker notes are the part that matters and they are marked.

---

## Slide 1 — The problem (20s, me)

**Headline:** Serendipity is not gone from search. It is systematically deprioritized.

- Search is optimized for **relevance**, so a researcher's own field dominates their results.
- The most useful paper in their literature is often **not in their literature** at all.
- Do **not** say serendipity was "completely engineered out". Say **systematically deprioritized**.

> Speaker note: this is the honest framing and it is also the stronger one. "Engineered out" invites
> "so what did you actually do about it". "Deprioritized" sets up the fix.

---

## Slide 2 — Prior work (10s, me)

**Headline:** Others find links *within* connected literatures. We find analogies *across unconnected fields*.

- **Literature-based discovery (LBD)** and analogy mining link works that already share citations or
  terminology. If your field has no bridge, they find nothing.
- **Serendipity Lab** strips domain vocabulary first, then searches *other* fields for the same
  abstract problem.
- One line, then move: *"We're different because of where we look, not because of what we rank."*

> Speaker note: credit them properly, one line only. Do not turn this into a literature review. The
> differentiating clause is "across unconnected fields" — say that phrase out loud.

---

## Slide 3 — The insight (30s, me) · **this is the load-bearing slide**

**Headline:** Match on structure, not topic.

| Step | Content |
|---|---|
| **Home-field text** | "Pick up objects of unknown shape without per-object programming…" |
| **Abstraction** | *see below* |
| **Collision, other field** | The jamming transition in granular matter (statistical physics) |
| **The aha** | *"Wait, it's the vacuum-packed coffee brick thing?"* |

### The abstraction on this slide

**Real system output.** Captured from a live `gemini-3.8-flash` run of
`prompts/abstractor.md` — the actual prompt, not an illustration — and verified
leak-free by `data/check_abstractor_prompt.py`:

> Conform to an arbitrary boundary and immobilise what it encloses, without
> item-specific configuration and without continuous sensing.

The full recorded output:

```json
{
  "functional_problem": "Conform to an arbitrary boundary and immobilise what it encloses, without
                         item-specific configuration and without continuous sensing.",
  "constraints": [
    "must work across unknown and irregular shapes",
    "must not require per-item setup",
    "must hold firmly once engaged",
    "must use minimal sensing"
  ],
  "mechanism": null,
  "domain_tags": ["end effector", "gripper", "mugs", "tools", "produce", "force sensing"]
}
```

The design target the abstraction was written against, from
`config/validation_cases.yaml: abstract_problem_target`:

> "A mechanism that is soft and conformal on command, then rigid on command, driven by one global
> control signal rather than distributed actuation."

> Speaker note: the whole slide works because **the abstraction contains no physics and no robotics**.
> Say that explicitly: *"the system's own words contain neither 'gripper' nor 'granular'. The match is
> not doing keyword work."* That is the proof of the insight in one breath.
>
> This matters more than it looks. With a looser prompt the same model returned
> `domain_tags: ['granular_jamming', ...]` — the answer, handed to the search. It would have demoed
> beautifully and proved nothing. The few-shots in `prompts/abstractor.md` are what prevent it, and
> `data/check_abstractor_prompt.py` fails the build if a leak reappears.
>
> **Non-negotiable rule:** a hand-written abstraction is never shown as if the system produced it.
> Regenerate this from the final prompt before Hour 6 — one API call.

---

## Slide 4 — Why it is an agent (25s, me)

**Headline:** It plans, decomposes, retrieves, criticises itself, and asks again.

1. Abstract the problem
2. Decompose into 2–4 sub-problems
3. Retrieve top-K per query, **home field excluded**
4. A **skeptical reviewer** kills weak candidates
5. Weak ones trigger a **query rewrite**, then re-retrieve (max 2 loops)
6. Rank survivors, then translate each into a grounded hypothesis
7. **Drop rule:** no source passage and no mapping ⇒ dropped, not shown

**Anti-hallucination, stated as a rule, not a feature:** every hypothesis cites an exact quote from
the source abstract and a concept mapping table. If the translator cannot produce both, the suggestion
does not ship.

> Speaker note: the visible trace is the proof it is an agent and not one big query. Person A runs the
> live demo, so the trace is their moment; you narrate the logic and hand over.

---

## Slide 5 — Proof (**EMPTY — do not fill until Hour 14**)

Rows = the 5 surviving pre-registered cases. Columns = baseline vs ours.

```text
case                  baseline@5  ours@5   baseline@10  ours@10   matched_on
jamming_gripper*            -         -            -         -            -
gecko_adhesive              -         -            -         -            -
kidney_exchange             -         -            -         -            -
physarum_network            -         -            -         -            -
simulated_annealing         -         -            -         -            -
                          --------------------------------------------
                          N / 5 hit@5                          N / 5 hit@10

* dev case, and also the hero. Presented as tuned, not as an untuned result.
```

Footer must carry: git commit, prompt SHA-256 prefixes, model names, corpus size.

**Rules for this slide, which judges will probe:**

- The **baseline gets home-field exclusion too**. A no-exclusion baseline is reported as secondary. If
  the headline comparison is a strawman, the whole deck is worthless.
- Report the **first full run (Hour 14, held-out untuned)** *and* the final run, naming which cases
  influenced tuning.
- Report **which cases failed and why**. Those become the limitations slide.
- "We win 4 of 5" is a good result.

> Speaker note: I built the system being tested, so say so before a judge does. Volunteering the
> methodology is what makes the number believable.

---

## Back-up slide — Limitations (write at Hour 18)

Say these out loud before anyone asks:

1. Abstraction quality depends on the LLM. The reviewer exists *because* of this.
2. The corpus is **small and curated** — 3,000 papers, 8 fields, hand-auditable — not a survey of
   science. Say the number first so it cannot sound like an excuse.
3. Seeds were chosen by us, because they are the known sources of the cases we test.
4. Analogies still need expert judgment. We narrow the space and cite the evidence; we do not replace
   the researcher.

## Back-up slide — Honest framing on the hero

- This is a **known, historical** collision. The question is *"would this system have surfaced it?"*
  We are **not** claiming a new discovery.
- The real gripper came from physicists and roboticists who were already collaborating. **That is the
  problem this tool exists to solve.**

---

## Build notes

- Slide 3 and Slide 4 are the demo. Do not spend time polishing slide 1 or 2.
- Slide 5 is the only slide nobody can help you with, and it needs the Hour 14 run to exist.
- The abstraction on slide 3 must be **regenerated from the final prompt before Hour 6**. Regenerating
  costs one API call.
- Rehearse the *switch*, not just the happy path: live → cached result → backup video.