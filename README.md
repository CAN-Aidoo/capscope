# capscope: zero-inference capability manifests against prompt injection

Code, tool profiles, pre-registered protocol and results for the paper *How Much Prompt-Injection Defense Does a
Free Tool Whitelist Buy? Zero-Inference Capability Manifests for Tool-Calling Agents* (Clement Aidoo, CANLABS).
capscope is the capability-scoping defense from the AI-Jailor project.

**Idea.** Build a tool whitelist once, from the user's instruction, by matching stemmed action verbs against per-tool
profiles. Gate every tool call against it. Tool outputs (where injections live) can never widen it. No model call.

**Oracle result (AgentDojo v1.2, 949 user x injection pairs, ground-truth tool calls, no model):**

| manifest | benign tasks kept | attacks blocked |
|---|---|---|
| capscope, hand-written verbs | 91% | 77% (95% CI 70-82) |
| capscope, auto keywords | 85% | 56% |
| oracle tools (ceiling for any tool whitelist) | 100% | 87% |

13% of attacks (33% in banking) use only tools the user's own task needs; no tool-level policy can stop them.

**Status.** Q1-Q3 (oracle) complete. Q4 (end-to-end with Claude Haiku) pending; see `RUN_ON_YOUR_LAPTOP.md`.

## Layout
| Path | What it is |
|---|---|
| `PROTOCOL.md` | Questions, metrics and profiles frozen before evaluation; dated deviations D1-D2 |
| `code/capscope/manifest.py` | Manifest construction (Porter-stemmed keyword match) and decisions |
| `code/capscope/pipeline.py` | AgentDojo pipeline elements: gate replacing `ToolsExecutor`, original-query recorder |
| `code/capscope/profiles.py` | Tool profiles for workspace, travel, banking, Slack (hand-written and auto variants) |
| `code/oracle_eval.py` | Q1-Q3: oracle evaluation -> `results/oracle.json`, `results/oracle_pairs.csv` |
| `code/run_llm.py`, `code/analyze_llm.py` | Q4: Claude runs (no defense, capscope, LLM tool filter) and analysis |
| `code/make_numbers.py`, `code/make_figures.py` | Every number, table and figure in the paper |
| `paper/` | LaTeX source |

## Reproduce
```bash
pip install -r code/requirements.txt
cd code && PYTHONPATH=. pytest tests -q && python3 oracle_eval.py && python3 make_numbers.py && python3 make_figures.py
cd ../paper && pdflatex main.tex && pdflatex main.tex
```

## Disclosure
Code, analysis and drafting were carried out with the assistance of an AI model (Claude, Anthropic) under the
author's direction. The author takes responsibility for the content.

## Licence
MIT (code), CC BY 4.0 (data and paper).
