# Problem 2 — Handbook size and cost estimate

## Token count

| What | Value |
|---|---|
| File | `data/shop_handbook.md` |
| Characters | 28,903 |
| Words | 6,127 |
| **Tokens** | **10,058** |

**Method:** counted with OpenAI's `tiktoken` library using the `o200k_base` encoding (the tokenizer used by gpt-6-luna):

```python
import tiktoken
enc = tiktoken.get_encoding("o200k_base")
len(enc.encode(open("data/shop_handbook.md").read()))   # -> 10058
```

**Cross-check against the API:** a test call to `gpt-6-luna` sending the handbook as the system message plus a 15-token question came back with `prompt_tokens = 10,083`. That is 10,058 (handbook) + 15 (question) + about 10 tokens of chat formatting, so the local count matches what the API bills.

## Prices (`data/prices.json`, per 1M tokens)

| Token type | Price |
|---|---|
| Input (not cached) | $0.10 |
| Cached input (read from cache) | $0.01 |
| Cache write | $0.125 |
| Output | $0.50 |

## Handbook cost — one call

| Case | Math | Cost |
|---|---|---|
| Without cache (normal input) | 10,058 × $0.10 / 1,000,000 | **$0.0010058** |
| With cache (cache hit) | 10,058 × $0.01 / 1,000,000 | **$0.00010058** |
| First call that fills the cache (cache write) | 10,058 × $0.125 / 1,000,000 | $0.00125725 |

## Handbook cost — 1,000 calls

| Case | Math | Cost |
|---|---|---|
| Without cache | 1,000 × $0.0010058 | **$1.0058** |
| With cache, all 1,000 hits (ideal) | 1,000 × $0.00010058 | **$0.1006** |
| With cache, realistic: 1 write + 999 hits | $0.00125725 + 999 × $0.00010058 = $0.00125725 + $0.10047942 | **$0.1017** |

**Expected saving from caching: about 90%** of the handbook cost ($1.0058 → $0.1017 per 1,000 calls), because a cached token costs one tenth of a normal input token.

## Notes and caveats (to check in Problem 4)

- This counts **the handbook only**. Each real agent call also sends the agent instructions (`prompts/prompt.md`), tool definitions, the vendor document, and gets back output and reasoning tokens. Those are measured in Problem 4.
- PydanticAI makes **at least two model calls per document** (one to call the `read_document` tool, one to give the final answer), so the handbook is sent about twice per document. Per-document cost should be roughly 2× the per-call numbers above.
- Estimate: a probe call where the handbook was *not* reused still reported `cache_write_tokens ≈ 10,080`. If the API bills every un-cached call at the cache-write price ($0.125) instead of $0.10, the true "without cache" cost could be closer to 1,000 × $0.00125725 = **$1.257 per 1,000 calls**. Problem 4 checks this with real runs.
