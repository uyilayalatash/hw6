# Campus Customs Vendor Desk Agent — MGT 409 Homework 6

A PydanticAI agent that reads one vendor document (HTML quote, PDF quote, or `.eml` email), pulls out vendor, SKU, unit price, lead time and minimum order, and recommends `recommend` / `do_not_recommend` using the rules in `data/shop_handbook.md`. It uses **gpt-6-luna** through Portkey.

## Setup

1. Create a virtual environment and install the requirements:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and add your own Portkey API key:
   ```bash
   cp .env.example .env
   ```
   Then open `.env` and fill in `PORTKEY_API_KEY=`. Never commit `.env`.

## Run the agent

Normal run (all defenses on):
```bash
python agent.py --doc data/practice_docs/p01_bluehen_quote.html
```

No defenses (the original Problem 3 agent, used for the attack tests):
```bash
python agent.py --doc data/practice_docs/p01_bluehen_quote.html --no-defenses
```

Other options: `--no-cache` makes every model call miss the prompt cache (Problem 4); `--layers code,design,prompt` turns on only the defense layers you list.

Each run prints the answer, the tools used and the cost, and appends to `output/usage_log.json` and `output/audit_trail.json`. The trap tools `send_email` and `approve_payment` never send or pay anything; they only append to `output/trap_calls.json`.

## What's where

| Path | What it is |
|---|---|
| `agent.py`, `tools.py`, `models.py`, `prompts/prompt.md` | The agent |
| `data/` | Course data, plus our two attack files in `data/my_attacks/` |
| `output/handbook_estimate.md` | P2: handbook token count and cost estimate |
| `output/harness.md` | P3/P6: fields, tools, and the Safety section |
| `output/cache_test.*` | P4: with vs. without prompt caching |
| `output/attack_results.*` | P5: undefended agent vs. booby-trapped documents |
| `output/defense_results.*` | P6: defended agent, before/after, cost per layer |
| `output/red_team.md` | P7: our two new attacks |
| `output/exam_results.json` | P8: final defended agent on the 10 exam documents |
| `output/hw6_report.html` | P9: results page (opens offline, no other files needed) |
| `AI_prompts.md` | P1: prompts given to the coding assistant, per problem |
