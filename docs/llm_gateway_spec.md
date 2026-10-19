# LLM Gateway Spec (for Person B)

**Deliver by Hour 6.** This is the plumbing layer around every LLM call. Prompts and schemas are mine; this wrapper is yours.

## Division of work

| Person B owns | M1/M3/M4 owns |
|---|---|
| Timeouts, retries, rate-limit backoff | Prompt text (`prompts/*.md`) |
| JSON parsing and schema validation | Schema content (`config/schemas/*.schema.json`) |
| Disk cache, cache-only mode | Retrieval, scoring, the agent loop |
| Trace-event emission | Which prompt runs when |

The gateway never contains prompt text and never contains domain logic.

## Prompt file format

Plain markdown with YAML front matter. I iterate on these in minutes without touching Python.

```markdown
---
version: v1
---
## SYSTEM
You are ...

## USER
Problem text: {{text}}
```

`{{name}}` placeholders are filled from `inputs`. A missing placeholder raises. Extra inputs are ignored.

## Interface

```python
@dataclass
class LLMResult:
    data: dict            # validated against the task's schema
    cached: bool
    model: str
    attempts: int
    latency_ms: int
    usage: dict | None

class LLMFailure(Exception):
    reason: Literal["timeout", "rate_limit", "provider_error", "validation", "cache_only_miss"]
    detail: str

class TraceSink(Protocol):
    def emit(self, event: dict) -> None: ...

class LLMGateway:
    def __init__(self, models_cfg="config/models.yaml", trace: TraceSink | None = None): ...

    async def arun(self, task: str, inputs: dict, *,
                   cache_id: str | None = None, run_id: str | None = None) -> LLMResult: ...

    def run(self, task: str, inputs: dict, *, cache_id: str | None = None) -> LLMResult:
        """Sync wrapper for the corpus batch job."""
```

`task` is a key under `llm.tasks` in `config/models.yaml`. The gateway reads model, temperature, `max_tokens`, timeout, prompt file, and schema file from there.

## Behavior rules

1. **Cache key** = `sha256(task, cache_id, prompt_sha256, model, schema_sha256)`. If `cache_id` is `None`, use a hash of `inputs`. Editing a prompt file changes the hash, so a stale hit is impossible even if I forget to bump `version`.
2. **Cache store:** SQLite in WAL mode at `cache/llm_cache.sqlite`. Writes are atomic. Killing the process mid-run loses nothing already written.
3. **Never cache a failure.**
4. **`LLM_CACHE_ONLY=1`:** a miss raises `LLMFailure("cache_only_miss")` and makes no API call. This is the stage-safety switch.
5. **Transport retries** (timeout, 429, 5xx): up to `retries.transport`, exponential backoff with jitter, honor `Retry-After`.
6. **Validation retries:** if the output is not valid JSON or fails the schema, retry up to `retries.validation`, appending the validation error text to the prompt. These counts are separate from transport retries.
7. **Final failure raises `LLMFailure`.** The gateway never returns partial or unvalidated data. Callers decide what to do (the batch job writes to the retry file; the live run falls back).
8. **Concurrency:** one global semaphore (`llm.concurrency`) across all tasks.
9. **Structured output:** prefer the provider's tool-use / structured-output mechanism with the schema. Still validate afterward.
10. **Provider isolation:** all provider-specific code lives in one adapter class. Swapping provider means changing `models.yaml` and one file. This has now been exercised for real: the provider went Anthropic -> DeepSeek -> Gemini inside the Hour 2 window, and `models.yaml` plus this one adapter class were the only things that changed. If a second file has to be touched to swap providers, that is a bug in this rule.
11. **Counters:** log cache hits, misses, retries, and token usage per task. One summary line at the end of a batch.
12. **Thinking budget 0 on every request.** Provider is Gemini (`config/models.yaml: llm.provider`), which
    thinks by default. Send `generationConfig.thinkingConfig.thinkingBudget = 0` on **every** request, read
    from `llm.thinking.budget`. Verified at 0: no thought parts, hero input in 2.6-5.9s. Thinking left on
    does not fit the 20s hero budget.
13. **Reasoning output is not content.** Gemini returns thinking as parts flagged `thought: true`, alongside
    the real parts. Only non-thought parts are parsed. Never concatenate thought parts into the context and
    never let them reach the schema validator.
14. **`responseSchema` cannot express our schemas. Translate, then validate.** Gemini's `responseSchema` is
    proto-flavoured, not JSON Schema, and it **rejects with HTTP 400** two things our schema files use:
    `additionalProperties` and union types like `["string", "null"]`. Verified against the real
    `config/schemas/abstraction.schema.json`. So:
    - Uppercase the types: `string`->`STRING`, `object`->`OBJECT`, `array`->`ARRAY`.
    - **Drop `additionalProperties`, `minLength`, `maxLength`, `minItems`, `maxItems`.** They are accepted
      but not enforced; enforcement is the post-validation step below.
    - **Drop any union type.** Do not fake a nullable field as a required string. See rule 15.
    - Keep `propertyOrdering`. It makes the abstraction legible to a human auditor.
15. **Nullable fields: omit from `required`, and trust the prompt — not the schema.** D14 makes `mechanism`
    nullable for user input. Gemini cannot express `["string","null"]` (rule 14), so a nullable field left
    in `required` is forced to `STRING` and the model satisfies it with the **literal text `"null"`**.
    Measured: with `mechanism` in `required`, the hero input came back with `"mechanism": "null"` — truthy
    downstream, and indexable as though it were a real mechanism. So:
    - For calls that allow null, **drop the field from `required`** and let the prompt state it may be null.
    - After parsing, **normalise the literal strings** `"null"`, `"none"`, `"n/a"`, `""` to `None` before
      validation. This is not paranoia: it is what the model actually returns.
    - Corpus papers keep `mechanism` required, and the batch job retries on null, which is the existing rule.
    - A reference implementation of this translation is `data/check_abstractor_prompt.py`; `translate()`
      there is the exact mapping to copy.
16. **Always validate after.** Post-validate every response against the **full, untranslated**
    `config/schemas/*.schema.json`. That is the only place `minLength`, `maxLength` and nullability are
    actually enforced, and it is what the cache stores.
17. **Abstraction leak check — treat a leak as a validation failure.** The model will happily name the
    answer. Measured on the hero input: a loose prompt produced `domain_tags: ['granular_jamming', ...]`
    and a `mechanism` saying "granular material" — which puts the correct collision in the query and
    makes retrieval trivially self-fulfilling. That is not a discovery, it is a leak, and it invalidates
    the validation case. Add a check in `run_many` and the live path: `functional_problem` and `mechanism`
    must not contain any token from a supplied `banned_solution_terms` list. Fail the call, do not cache it.
    With a strict prompt the same input produced no leak ("A phase-like or state-changing transformation
    within a conformable medium"), so this is a guard rail, not a reason to distrust the model.
18. **Rate limits are the real constraint, not tokens.** Free tier returned 429 then 503 after 1-3 rapid
    calls. Retries and the resumable cache are what make the 3k batch survivable, so treat both as
    correctness features rather than nice-to-haves, and measure the actual quota before raising
    `llm.concurrency`.

## Trace events

Every call emits events matching the API contract's trace shape, plus a `meta` object:

```json
{ "type": "trace", "step": "abstracting", "message": "Stripping domain terms...", "ts": 1712345678,
  "meta": { "task": "abstractor", "cached": false, "attempt": 1, "ms": 3120 } }
```

Proposed `step` values (frozen at Hour 6): `abstracting`, `decomposing`, `retrieving`, `reviewing`, `rewriting`, `translating`, `ranking`, `llm_retry`, `cache_hit`, `done`.

The gateway emits `llm_retry` and `cache_hit` itself. The agent loop (mine) emits the rest by calling `trace.emit(...)`.

## Batch helper (nice to have)

```python
def run_many(task: str, items: list[dict], *, id_key: str,
             retry_file: str, concurrency: int | None = None) -> dict:
    """Resumable. Skips cached items, writes failures to retry_file as JSONL, prints progress and a summary."""
```

## Environment

`GEMINI_API_KEY`, `LLM_CACHE_ONLY` (optional), `LLM_DRY_RUN` (optional; returns fixtures from `tests/fixtures/{task}.json` so UI and API work needs no key). See `.env.example`.

## Acceptance tests (Hour 6 gate)

Use a fake provider. All must pass:

- [ ] Timeout → retried, then succeeds
- [ ] 429 with `Retry-After` → waits, then succeeds
- [ ] Invalid JSON, then valid JSON → one validation retry, success
- [ ] Persistent invalid output → raises `LLMFailure("validation")`
- [ ] Persistent transport failure → raises with the correct reason
- [ ] Second identical call → cache hit, no provider call
- [ ] Editing the prompt file → cache miss
- [ ] Kill mid-batch, restart → completed items are not re-called
- [ ] Concurrency never exceeds the configured limit
- [ ] `LLM_CACHE_ONLY=1` with a miss → raises, no provider call
- [ ] Trace events emitted for call, retry, and cache hit
