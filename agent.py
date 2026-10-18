"""Campus Customs vendor desk agent (PydanticAI + gpt-6-luna through Portkey).

Usage:
    python agent.py --doc data/practice_docs/p01_bluehen_quote.html                 # all defenses on
    python agent.py --doc data/practice_docs/p01_bluehen_quote.html --no-defenses   # Problem 3 agent, no defenses

Defense layers (all on by default):
    code   - the program strips hidden text, comments, zero-width characters and links before the model sees it
    design - trap tools are hidden from the model; code checks the facts and makes the decision from the handbook
    prompt - the safety rules in prompts/prompt.md
"""

import argparse
import asyncio
import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import UsageLimits

import tools
from models import VendorQuote

ROOT = Path(__file__).resolve().parent
MODEL_NAME = "gpt-6-luna"
PRICES = json.loads((ROOT / "data" / "prices.json").read_text())[MODEL_NAME]
HANDBOOK = (ROOT / "data" / "shop_handbook.md").read_text()
PROMPT = (ROOT / "prompts" / "prompt.md").read_text()
PROMPT_NO_SAFETY = re.sub(r"\n\n<!-- SAFETY RULES START -->.*<!-- SAFETY RULES END -->\n", "\n", PROMPT, flags=re.S)
RULES = tools.load_rules(HANDBOOK)
ALL_LAYERS = frozenset({"code", "design", "prompt"})
USAGE_LOG = ROOT / "output" / "usage_log.json"
AUDIT_LOG = ROOT / "output" / "audit_trail.json"

load_dotenv(ROOT / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


def make_model() -> OpenAIResponsesModel:
    client = AsyncOpenAI(
        api_key=os.environ["PORTKEY_API_KEY"],
        base_url="https://api.portkey.ai/v1",
        # x-portkey-cache-force-refresh: never let Portkey replay an old saved response.
        default_headers={"x-portkey-provider": "openai", "x-portkey-cache-force-refresh": "true"},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


@dataclass
class Deps:
    doc: str
    layers: frozenset
    human_approved: bool = False   # only a person can set this; no code path in this CLI does


def instructions(cache: bool, layers: frozenset = ALL_LAYERS):
    """Instructions + handbook, sent first on every model call.

    With cache: the exact same text every time, so the API can reuse it from its prompt cache.
    Without cache: a function that puts a fresh random id at the very start on EVERY model call,
    so no two calls share a prefix and nothing can be read from cache.
    """
    prompt = PROMPT if "prompt" in layers else PROMPT_NO_SAFETY
    body = f"{prompt}\n\n---\n\n{HANDBOOK}"
    if cache:
        return body
    return lambda: f"Request id: {uuid.uuid4()}\n\n{body}"


def call_cost(input_tokens: int, cached: int, cache_write: int, output: int) -> float:
    """Dollar cost of one model call from prices.json. input_tokens includes cached and cache-write tokens."""
    plain = input_tokens - cached - cache_write
    return (
        plain * PRICES["input_per_1m"]
        + cached * PRICES["cached_input_per_1m"]
        + cache_write * PRICES["cache_write_per_1m"]
        + output * PRICES["output_per_1m"]
    ) / 1_000_000


async def human_signoff_only(ctx: RunContext[Deps], tool_def: ToolDefinition) -> ToolDefinition | None:
    """DESIGN DEFENSE: with the design layer on, the model is not even shown send_email / approve_payment
    unless a person has signed off. The tools stay registered so the shop can use them later."""
    if "design" in ctx.deps.layers and not ctx.deps.human_approved:
        return None
    return tool_def


def build_agent(cache: bool, layers: frozenset = ALL_LAYERS) -> Agent:
    agent = Agent(
        make_model(),
        output_type=VendorQuote,
        instructions=instructions(cache, layers),
        deps_type=Deps,
        model_settings={"max_tokens": 4000, **({"openai_prompt_cache_key": "hw6-vendor-desk"} if cache else {})},
    )

    @agent.tool
    def read_document(ctx: RunContext[Deps], path: str) -> str:
        """Read a vendor document (HTML, PDF, or .eml email) and return its text."""
        if "code" in ctx.deps.layers:
            return tools.wrap_untrusted(tools.clean_document(path))
        return tools.read_document_text(path)

    @agent.tool(prepare=human_signoff_only)
    def send_email(ctx: RunContext[Deps], to: str, subject: str, body: str) -> str:
        """Send an email to someone."""
        return tools.send_email(to, subject, body, document=Path(ctx.deps.doc).name)

    @agent.tool(prepare=human_signoff_only)
    def approve_payment(ctx: RunContext[Deps], vendor: str, amount_usd: float, memo: str) -> str:
        """Approve a payment or deposit to a vendor."""
        return tools.approve_payment(vendor, amount_usd, memo, document=Path(ctx.deps.doc).name)

    return agent


def apply_design(answer: dict, doc: str, layers: frozenset) -> dict:
    """DESIGN DEFENSE: keep only facts that appear in the document, then let code make the decision."""
    text = tools.clean_document(doc)["text"] if "code" in layers else tools.read_document_text(doc)
    facts = {k: answer[k] for k in ["vendor", "sku", "unit_price", "lead_time_days", "min_order"]}
    facts, _notes = tools.ground_facts(facts, text)
    decision, reason = tools.decide(facts, RULES)
    return {**facts, "decision": decision, "reason": reason}


def per_call_usage(messages) -> list[dict]:
    """Token counts the API reported for every model call in the run."""
    calls = []
    for m in messages:
        if isinstance(m, ModelResponse):
            u = m.usage
            calls.append({
                "input_tokens": u.input_tokens,
                "cached_tokens": u.cache_read_tokens,
                "cache_write_tokens": u.cache_write_tokens,
                "output_tokens": u.output_tokens,
                "reasoning_tokens": u.details.get("reasoning_tokens", 0),
                "cost_usd": round(call_cost(u.input_tokens, u.cache_read_tokens, u.cache_write_tokens, u.output_tokens), 8),
            })
    return calls


def tool_trail(messages) -> list[dict]:
    """Each tool call with its arguments and a short result."""
    calls, results = {}, {}
    for m in messages:
        for part in getattr(m, "parts", []):
            if isinstance(part, ToolCallPart):
                calls[part.tool_call_id] = part
            elif isinstance(part, ToolReturnPart):
                results[part.tool_call_id] = str(part.content)
    trail = []
    for cid, part in calls.items():
        res = results.get(cid, "")
        trail.append({
            "tool": part.tool_name,
            "arguments": part.args_as_dict(),
            "result": res[:200] + ("..." if len(res) > 200 else ""),
        })
    return trail


async def run_agent(doc: str, cache: bool = True, defenses: bool = True, layers: frozenset | None = None) -> dict:
    layers = frozenset(layers) if layers is not None else (ALL_LAYERS if defenses else frozenset())
    agent = build_agent(cache, layers)
    result = await agent.run(
        f"Review this vendor document: {doc}",
        deps=Deps(doc=doc, layers=layers),
        usage_limits=UsageLimits(request_limit=6, tool_calls_limit=6),
    )
    messages = result.all_messages()
    calls = per_call_usage(messages)
    answer = result.output.model_dump()
    if "design" in layers:
        answer = apply_design(answer, doc, layers)
    time = tools.now()
    totals = {
        "input_tokens": sum(c["input_tokens"] for c in calls),
        "cached_tokens": sum(c["cached_tokens"] for c in calls),
        "cache_write_tokens": sum(c["cache_write_tokens"] for c in calls),
        "output_tokens": sum(c["output_tokens"] for c in calls),
        "reasoning_tokens": sum(c["reasoning_tokens"] for c in calls),
    }
    usage_entry = {
        "document": Path(doc).name,
        "time": time,
        "model_calls": len(calls),
        **totals,
        "cost_usd": round(sum(c["cost_usd"] for c in calls), 8),
    }
    audit_entry = {
        "document": Path(doc).name,
        "time": time,
        "tool_calls": tool_trail(messages),
        "final_answer": answer,
    }
    tools.append_json(USAGE_LOG, usage_entry)
    tools.append_json(AUDIT_LOG, audit_entry)
    return {"answer": answer, "usage": usage_entry, "audit": audit_entry, "calls": calls}


def main() -> None:
    ap = argparse.ArgumentParser(description="Campus Customs vendor desk agent")
    ap.add_argument("--doc", required=True, help="path to one vendor document (.html, .pdf, .eml)")
    ap.add_argument("--no-cache", action="store_true", help="make every call miss the prompt cache")
    ap.add_argument("--no-defenses", action="store_true", help="run the Problem 3 agent with no defenses")
    ap.add_argument("--layers", help="comma list of defense layers to turn on (code,design,prompt); default all")
    args = ap.parse_args()
    layers = None
    if args.layers is not None:
        layers = frozenset(x.strip() for x in args.layers.split(",") if x.strip())
        assert layers <= ALL_LAYERS, f"unknown layer in {args.layers}"
    out = asyncio.run(run_agent(args.doc, cache=not args.no_cache, defenses=not args.no_defenses, layers=layers))
    print(json.dumps(out["answer"], indent=2))
    print(f"tools: {[t['tool'] for t in out['audit']['tool_calls']]}")
    u = out["usage"]
    print(f"tokens: in={u['input_tokens']} cached={u['cached_tokens']} out={u['output_tokens']}  cost=${u['cost_usd']:.6f}")


if __name__ == "__main__":
    main()
