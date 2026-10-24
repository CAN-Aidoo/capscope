"""Q4: end-to-end AgentDojo run with a Claude model. Run on your own machine with your own API key.

  set ANTHROPIC_API_KEY in your environment first (never paste it into code or chat)
  python run_llm.py --defense none      --suite banking --pilot     # ~2 user tasks, prints a cost estimate
  python run_llm.py --defense none                                   # full run, all 4 suites
  python run_llm.py --defense capscope
  python run_llm.py --defense tool_filter

Resumable: finished tasks are skipped (logs in runs/<model>-<defense>/). Writes
runs/summary_<model>_<defense>.json with utility, attack success and per-task call/token/time counts.
Offline check without any API key:  python run_llm.py --dry-run --pilot   (fake model, no network)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agentdojo.agent_pipeline import AgentPipeline, InitQuery, SystemMessage, ToolsExecutionLoop, ToolsExecutor
from agentdojo.agent_pipeline.agent_pipeline import TOOL_FILTER_PROMPT, load_system_message
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.benchmark import benchmark_suite_with_injections, benchmark_suite_without_injections
from agentdojo.functions_runtime import EmptyEnv
from agentdojo.logging import OutputLogger
from agentdojo.models import MODEL_NAMES
from agentdojo.task_suite.load_suites import get_suites

from capscope.pipeline import CapabilityScopedToolsExecutor, RecordOriginalQuery
from capscope.profiles import MANUAL

VERSION = "v1.2"
ATTACK = "important_instructions"
STATS = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0, "filter_calls": 0}


class CountingClient:
    """Wraps anthropic.Anthropic so every messages.create call is counted (calls, tokens, latency)."""

    def __init__(self, client, tag="calls"):
        self._c, self._tag = client, tag
        self.messages = self

    def create(self, **kw):
        t = time.time()
        r = self._c.messages.create(**kw)
        STATS["seconds"] += time.time() - t
        STATS[self._tag] += 1
        STATS["input_tokens"] += r.usage.input_tokens
        STATS["output_tokens"] += r.usage.output_tokens
        return r

    def __getattr__(self, k):
        return getattr(self._c, k)


class AnthropicToolFilter(BasePipelineElement):
    """LLM tool filter (AgentDojo's 'tool_filter' defense, which ships for OpenAI models only), ported
    to Claude: one extra model call lists the tools needed for the user's request; all other tools are
    removed from the runtime before the agent starts. Tool names are matched as whole words."""

    def __init__(self, client, model):
        self.client, self.model = client, model

    def query(self, query, runtime, env=EmptyEnv(), messages=[], extra_args={}):
        catalogue = "\n".join(f"- {n}: {(f.description or '').strip().splitlines()[0]}" for n, f in runtime.functions.items())
        r = self.client.messages.create(
            model=self.model, max_tokens=512, temperature=0.0,
            messages=[{"role": "user", "content": f"{TOOL_FILTER_PROMPT}\n\nUser task: {query}\n\nTools:\n{catalogue}"}])
        text = "".join(getattr(b, "text", "") for b in r.content)
        keep = {n: f for n, f in runtime.functions.items() if re.search(rf"\b{re.escape(n)}\b", text)}
        runtime.update_functions(keep)
        return query, runtime, env, messages, extra_args


class FakeAnthropic:
    """Offline stand-in for --dry-run: on the first turn of each episode it calls the most sensitive-looking
    tool offered (to exercise capscope's deny path), then answers in text. Returns real anthropic types."""

    def __init__(self):
        self.messages = self

    def create(self, **kw):
        from anthropic.types import Message, TextBlock, ToolUseBlock, Usage
        tools = [t["name"] for t in kw.get("tools") or []]
        first = sum(1 for m in kw["messages"] if m["role"] == "assistant") == 0
        pref = [t for t in tools if t.startswith(("send", "delete", "update", "reserve", "post", "invite"))]
        if tools and first:
            content = [ToolUseBlock(type="tool_use", id="tu_1", name=(pref or tools)[0], input={})]
            stop = "tool_use"
        else:
            content = [TextBlock(type="text", text="Done. " + " ".join(tools[:3]))]
            stop = "end_turn"
        return Message(id="m", type="message", role="assistant", model=kw["model"], content=content,
                       stop_reason=stop, usage=Usage(input_tokens=1000, output_tokens=50))


async def _chat_completion_request(client, model, messages, tools, max_tokens, system_prompt=None,
                                   temperature=0.0, thinking_budget_tokens=None):
    """Replaces agentdojo's streaming async request with a plain (counted) messages.create call, so the
    same code path serves the real API and the offline fake. Retries are handled by the SDK (max_retries)."""
    kw = dict(model=model, messages=messages, max_tokens=max_tokens)
    if tools:
        kw["tools"] = tools
    if system_prompt:
        kw["system"] = system_prompt
    if temperature is not None:
        kw["temperature"] = temperature
    return client.messages.create(**kw)


def build_pipeline(model, defense, suite_name, dry_run=False):
    import agentdojo.agent_pipeline.llms.anthropic_llm as AL
    from agentdojo.agent_pipeline.llms.anthropic_llm import AnthropicLLM

    AL.chat_completion_request = _chat_completion_request

    if dry_run:
        raw = FakeAnthropic()
    else:
        import anthropic
        raw = anthropic.Anthropic(max_retries=8)
    llm = AnthropicLLM(CountingClient(raw), model)
    sysmsg = SystemMessage(load_system_message(None))
    if defense == "none":
        elems = [sysmsg, InitQuery(), llm, ToolsExecutionLoop([ToolsExecutor(), llm])]
    elif defense == "capscope":
        ex = CapabilityScopedToolsExecutor(MANUAL[suite_name], mode="block")
        elems = [sysmsg, RecordOriginalQuery(), InitQuery(), llm, ToolsExecutionLoop([ex, llm])]
    elif defense == "tool_filter":
        flt = AnthropicToolFilter(CountingClient(raw, "filter_calls"), model)
        elems = [sysmsg, InitQuery(), flt, llm, ToolsExecutionLoop([ToolsExecutor(), llm])]
    else:
        raise SystemExit("defense must be none | capscope | tool_filter")
    p = AgentPipeline(elems)
    p.name = f"{model}-{defense}"
    MODEL_NAMES.setdefault(p.name, "Claude")  # lets the attack address the model by name, as AgentDojo does
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--defense", default="none")
    ap.add_argument("--suite", action="append", help="repeatable; default all four")
    ap.add_argument("--pilot", action="store_true", help="2 user tasks x all injections of one suite")
    ap.add_argument("--dry-run", action="store_true", help="fake offline model, no API, checks wiring")
    a = ap.parse_args()
    suites = get_suites(VERSION)
    names = a.suite or list(suites)
    tag = "dryrun" if a.dry_run else a.model
    logdir = HERE.parent / "runs" / f"{tag}-{a.defense}"
    out = {"model": a.model, "defense": a.defense, "attack": ATTACK, "agentdojo_version": VERSION, "suites": {}}
    t0 = time.time()
    for s in names:
        suite = suites[s]
        pipe = build_pipeline(a.model, a.defense, s, a.dry_run)
        ut = list(suite.user_tasks)[:2] if a.pilot else None
        with OutputLogger(str(logdir)):
            benign = benchmark_suite_without_injections(pipe, suite, logdir, False, ut, benchmark_version=VERSION)
            attack = load_attack(ATTACK, suite, pipe)
            inj = benchmark_suite_with_injections(pipe, suite, attack, logdir, False, ut, benchmark_version=VERSION)
        out["suites"][s] = {
            "benign_utility": {k[0]: bool(v) for k, v in benign["utility_results"].items()},
            "attacked_utility": {f"{k[0]}|{k[1]}": bool(v) for k, v in inj["utility_results"].items()},
            "attack_success": {f"{k[0]}|{k[1]}": bool(v) for k, v in inj["security_results"].items()},
        }
        r = out["suites"][s]
        print(f"[{s}] benign utility {sum(r['benign_utility'].values())}/{len(r['benign_utility'])}  "
              f"attacked utility {sum(r['attacked_utility'].values())}/{len(r['attacked_utility'])}  "
              f"ASR {sum(r['attack_success'].values())}/{len(r['attack_success'])}", flush=True)
    out["usage"] = {**STATS, "wall_seconds": time.time() - t0}
    out["usage_note"] = "usage counts only calls made in this invocation (resumed tasks are not re-counted)"
    p = HERE.parent / "runs" / f"summary_{tag}_{a.defense}{'_pilot' if a.pilot else ''}.json"
    p.parent.mkdir(exist_ok=True)
    json.dump(out, open(p, "w"), indent=1)
    print("usage:", out["usage"], "\nwritten", p)
    if a.pilot and STATS["calls"]:
        full_tasks = 97 + 949 + 35
        done = sum(len(v["benign_utility"]) + len(v["attack_success"]) for v in out["suites"].values())
        f = full_tasks / max(done, 1)
        print(f"\nEstimate for a FULL run of this defense: ~{STATS['input_tokens'] * f / 1e6:.1f}M input and "
              f"~{STATS['output_tokens'] * f / 1e6:.2f}M output tokens. Multiply by your model's per-token price.")


if __name__ == "__main__":
    main()
