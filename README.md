# capscope: Capability Manifests for Tool-Calling LLM Agents

This repo is the working state of a paper-in-progress (see `draft/paper.md`).

## What's real right now
- `code/capscope/manifest.py` — deterministic, LLM-free capability-derivation logic.
- `code/capscope/pipeline.py` — AgentDojo-compatible pipeline elements (`CapabilityScopedToolsExecutor`,
  `RecordOriginalQuery`) implementing the mechanism against the real `agentdojo` package (v0.1.35, pip-installable).
- `code/tests/test_manifest.py` — 5 unit tests, all passing, exercising the actual security logic
  (deny-by-default on high-sensitivity/out-of-scope tools, default-allow on low-sensitivity read tools,
  and — importantly — an honest test that documents the mechanism's keyword-collision limitation rather
  than hiding it).

Run it yourself:
```bash
cd code
pip install -r requirements.txt
PYTHONPATH=. pytest tests/ -v
```

## What's NOT done yet (and must not be faked)
- No attack-success-rate, utility, or latency-overhead numbers exist yet. Generating them requires
  running the full AgentDojo suite (four task suites, ~629 attack cases) against a real LLM backend —
  either an open-source model served locally/on a rented GPU, or metered API calls (e.g. your Anthropic
  API credits). That's a compute/cost decision only you can make, and it's the next concrete step.
- Section 6 of `draft/paper.md` is deliberately empty. Do not fill it with plausible-sounding numbers —
  that would be fabrication, not a shortcut, and would put your name on a paper with invented data.

## Suggested next session
1. Decide the model backend (recommend starting with one small open model served via Ollama/vLLM on a
   rented GPU — cheapest, fully reproducible, no per-call API cost while you iterate).
2. Author the `ToolProfile` table for AgentDojo's four suites (banking, Slack, travel, workspace) —
   this is a few hours of careful, mechanical work, not research risk.
3. Wire `CapabilityScopedToolsExecutor` into an AgentDojo `AgentPipeline` (replacing `ToolsExecutor`)
   and run the benchmark's own scripts (`agentdojo/scripts/benchmark.py`) across all four conditions
   in §5 of the paper.
4. Paste real numbers into §6, write the Abstract last, then get one outside pair of eyes (even a
   non-expert) to sanity-check the claims against the numbers before arXiv submission.
