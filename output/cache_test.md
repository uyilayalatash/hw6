# Problem 4 — With and without cached tokens

All 12 practice documents were run through the agent twice. Every model call is saved in `output/cache_test.json` (24 calls per setup — PydanticAI makes 2 model calls per document: one to call `read_document`, one to return the answer).

## How each setup works

| Setup | How it's built | Proof from the API's token counts |
|---|---|---|
| **With cache** | Instructions + handbook are the exact same text on every call, sent first, with a fixed `prompt_cache_key`. | Every call after the very first reports `cached_tokens` ≈ 10,559–10,581. |
| **Without cache** | A fresh random `Request id` is put at the very start of the instructions on **every model call**, so no two calls share a prefix. | All 24 calls report `cached_tokens = 0`. |

The only with-cache call that shows 0 cached tokens is the very first call (p01, call 1), which filled the cache.

## Results (real runs, prices from `data/prices.json`)

| | With cache | Without cache |
|---|---|---|
| Model calls | 24 | 24 |
| Input tokens (total) | 260,479 | 261,142 |
| – read from cache ($0.01/1M) | 243,100 | 0 |
| – written to cache ($0.125/1M) | 14,355 | 258,118 |
| – plain input ($0.10/1M) | 3,024 | 3,024 |
| Output tokens ($0.50/1M) | 1,834 | 1,935 |
| **Total cost, 12 docs** | **$0.005445** | **$0.033535** |
| **Cost per document** | **$0.000454** | **$0.002795** |
| Cost per document once the cache is warm (p02–p12) | $0.000352 | $0.002795 |

**Percent saved with cache: 83.8%** ($0.033535 → $0.005445). Once the cache is warm the saving is **87.4%** per document.

Where the money goes:

| Cost part | With cache | Without cache |
|---|---|---|
| Cached reads | $0.002431 | $0 |
| Cache writes | $0.001794 | $0.032265 |
| Plain input | $0.000302 | $0.000302 |
| Output | $0.000917 | $0.000968 |

## Compared with the Problem 2 estimate

| | P2 estimate (handbook only, per call) | Real, per model call (everything) |
|---|---|---|
| Without cache | $0.0010058 (10,058 × $0.10) | $0.0013973 ($0.033535 / 24) |
| With cache | $0.00010058 (10,058 × $0.01) | $0.0002269 ($0.005445 / 24) |
| Saving | 90% | 83.8% |

- The handbook is the bulk of every call: each call's input is about 10,700–11,200 tokens, and 10,058 of those are the handbook. So the P2 token count was right.
- **Without cache the real cost is about 39% above the P2 estimate.** The P2 estimate priced un-cached tokens at $0.10/1M, but the API bills them as cache *writes* at $0.125/1M (25% more). The rest of the gap is the prompt, tool definitions, the document, and output.
- **Per document it's about 2× the per-call number**, because each document takes 2 model calls and the handbook goes out on both.
- With cache, the real saving (83.8%) is a bit below the ideal 90% because each call still writes a few hundred new tokens (the document and tool result) at the higher write price, and output tokens are never discounted.

## Projection: 1,000 documents a day for 30 days (30,000 documents)

| Setup | Per document | Per day (1,000 docs) | Per 30 days |
|---|---|---|---|
| Without cache | $0.002795 | $2.79 | **$83.84** |
| With cache (12-doc average, incl. cold start) | $0.000454 | $0.45 | **$13.61** |
| With cache (warm, realistic at 1,000/day) | $0.000352 | $0.35 | **$10.55** |

At 1,000 documents a day the cache stays warm almost all day, so the warm number (~$10.55/month) is the best estimate. Caching saves about **$73 a month**.

## Surprises in the numbers, and why

1. **"No cache" still writes to the cache on every call.** Every without-cache call reported `cache_write_tokens` ≈ 10,600–11,100. The API always tries to cache the prompt prefix; because our prefix changes every time, it pays to write and never gets to read. So "turning caching off" is actually the most expensive option — it costs more than plain input would.
2. **The second call of each document also writes cache.** Call 2 adds the document text and the tool result after the handbook. That new part (128–485 tokens) is a cache write each time. Longer HTML documents (p02, p03, p04, p11) cost more here because the raw HTML is longer than the PDF/email text.
3. **Cached tokens stop at 10,559 / ~10,580, not the full input.** The cache only matches the shared prefix (instructions + handbook + tool definitions). The user message with the document path, and anything after it, is different for each document.
4. **The very first call was a full miss.** Changing how the instructions are sent (from a system prompt to PydanticAI `instructions`) changed the prefix, so p01's first call had to fill a new cache. After that, every call hit.
5. **Output is a tiny part of the bill** (about $0.0009 for 12 documents). Almost all the cost is the handbook going in, which is why caching matters so much here.
