# Capability Manifests: A Zero-Inference-Cost Least-Privilege Defense for Tool-Calling LLM Agents in Bandwidth- and Budget-Constrained Deployments

**Clement Aidoo**
CANLABS, Ghana
`aidooclement613@gmail.com`

> **Status of this draft — read this first.** This is a working draft, not a finished paper. Sections marked **[VERIFIED]** contain claims backed by code that has actually been written and run (see `/code`, all tests passing as of this draft). Sections marked **[PENDING — REQUIRES REAL RUN]** are scaffolding: the experimental design is fully specified, but the numbers have not been generated yet and must not be filled in with anything invented. Do not submit this to arXiv until every `[PENDING]` block has been replaced with real, reproducible results and this status banner is removed.

---

## Abstract

*[PENDING — write last, after Results.]* Tool-calling LLM agents are increasingly deployed in settings where an attacker can plant malicious instructions in the untrusted data a tool returns (indirect prompt injection) — ranked the top risk in the OWASP Top 10 for LLM Applications 2025. State-of-the-art defenses such as MELON (re-running the agent on a masked trajectory) and Progent (LLM-and-SMT-solver-synthesized privilege policies) reduce attack success but add a nontrivial number of extra model calls per agent step. In bandwidth-constrained, metered, or latency-sensitive deployments — the exact regime this project's author builds for — that overhead is not free. We introduce **capability manifests**: a deterministic, keyword-overlap-based least-privilege gate computed once per episode from the user's original instruction, with zero additional model inference. We evaluate it on the AgentDojo benchmark across its four task suites, measuring attack success rate, benign-task utility, and wall-clock/inference overhead against an undefended baseline and, where feasible, against Progent and/or MELON. *[Fill in with the actual headline numbers once the run completes — see §6.]*

---

## 1. Introduction

Large language model agents that can call external tools — reading email, browsing the web, moving money, editing files — inherit a security problem that pure chatbots do not have: **the data a tool returns is untrusted, but it flows straight back into the model's context as if it were more instructions.** An attacker who can plant text in that data (a webpage, a calendar invite, an email, a file) can hijack the agent's goal without ever talking to the user or the model directly. This is *indirect prompt injection*, and it is now ranked **LLM01:2025 — the single top risk** in the OWASP Top 10 for LLM Applications 2025.

A growing body of work defends against this. AgentDojo (Debenedetti et al., NeurIPS 2024) formalized the evaluation problem with 97 realistic tasks and 629 attack cases across four environments (banking, Slack, travel, workspace). On top of it, detection-based defenses (DataSentinel, PromptGuard-style classifiers) flag suspicious content; system-level defenses like MELON (Zhu et al., 2025) re-execute the agent on a masked copy of its trajectory to check whether its next action is still explainable by the *original* task alone; and privilege-control defenses like Progent (Shi et al., 2025) use an LLM plus an SMT solver to synthesize a fine-grained, monotonically-narrowing policy over tool calls at runtime. These are effective — but every one of them spends *additional* model inference, per step or per episode, to decide whether to trust a step.

That cost is invisible in a well-provisioned cloud deployment. It is not invisible in the deployments this project is built around: offline-first and low-bandwidth systems for infrastructure-constrained markets, where every model call has a real latency and, often, a real metered cost. **The question this paper asks is narrow and deliberately modest: how much of the security benefit of privilege-control defenses can be recovered with a mechanism that costs zero additional inference calls, and what do we give up to get there?**

We propose **capability manifests**: before the agent's first tool call, we deterministically derive — via keyword overlap against a small, hand-authored per-environment tool taxonomy, no LLM involved — the set of tool categories that the user's *original* instruction plausibly licenses. Every subsequent tool call is checked against this manifest. Because the manifest is built once from the pristine instruction and is never recomputed from anything the agent reads afterward, it is structurally immune to being *widened* by an injected instruction, no matter how persuasive that instruction is — though, as we show honestly in §4.3, it is not immune to an attacker who phrases the injection using the same task-relevant verbs the legitimate task would also use. This is a real limitation, not a hidden one, and we design the evaluation specifically to measure it.

**Contributions.**
1. A deterministic, zero-inference-cost capability-manifest mechanism for tool-calling agents, implemented as a drop-in AgentDojo pipeline element (§3; code in `/code/capscope`).
2. An honest characterization of its threat-model boundary: which attack patterns it structurally cannot be fooled by, and which it can (§4.3).
3. *[PENDING]* An empirical security–utility–cost comparison against an undefended baseline and at least one LLM-in-the-loop defense (Progent and/or MELON) on the full AgentDojo suite (§5–6).

---

## 2. Related Work

**Agent security benchmarks.** AgentDojo (Debenedetti et al., *NeurIPS 2024 Datasets and Benchmarks Track*) is the benchmark this paper builds on: a dynamic evaluation framework spanning banking, Slack, travel, and workspace environments, with 97 user tasks and 629 attack cases, and a plugin architecture for both attacks and defenses. InjecAgent (Zhan et al., 2024) is an earlier, single-step-focused benchmark; AgentDyn (Li et al., 2026) extends AgentDojo-style dynamic evaluation to three additional domains (shopping, GitHub, daily life) and adds stronger detection baselines. We use AgentDojo as the primary evaluation surface because it is the closest existing match to a full agentic workflow (multi-step, tool-integrated) rather than a single-turn classification task.

**Detection-based defenses.** DataSentinel and DeBERTa-style classifiers (used as baselines in PromptArmor, Shi et al., 2025) flag likely-injected content before it reaches the model. These add one classifier call per tool output; they are cheap relative to a second full LLM call but still add latency and are evaluated in our cost comparison as a middle point between "no defense" and "LLM-in-the-loop defense."

**System-level and privilege-control defenses.** MELON (Zhu et al., arXiv:2502.05174) re-runs the agent on a masked trajectory to check whether the next planned action is independently justifiable by the original task, without seeing the (potentially poisoned) tool output that suggested it — a provable-style defense evaluated on AgentDojo's 629 cases. **Progent** (Shi et al., arXiv:2504.11703) is the closest prior work to ours in spirit: it also enforces least privilege over tool calls, via a domain-specific policy language, but its policies are synthesized and dynamically updated by an LLM plus an SMT solver, with updates constrained to be monotonically narrowing (an expansion always requires explicit approval) — a strong and effective design, but one that spends model inference to *generate and update* the policy at runtime. Our capability manifest is the deliberately-weaker, deliberately-cheaper point on this design axis: a **static**, keyword-derived, non-LLM policy fixed once at episode start. We are not claiming to out-perform Progent on attack success rate; we are asking how much of its benefit survives when the policy-generation budget is zero, which — to our knowledge — no prior AgentDojo-evaluated defense has isolated as its explicit independent variable.

**Cost-aware and budget-constrained agents.** Separately from security, recent work has started to ask what happens when tool-calling agents are given an explicit budget: Liu et al. (arXiv:2511.17006) find that simply granting agents a larger tool-call budget fails to improve performance because agents lack "budget awareness," and CostBench (arXiv:2511.02734) and BAGEN (arXiv:2606.00198) benchmark cost-aware planning directly. This paper is not a budget-constrained-planning paper, but it shares the same underlying motivation — that inference cost is a first-class constraint, not an afterthought — and applies it to the security layer specifically rather than to task planning.

**Positioning.** No AgentDojo-evaluated defense we are aware of reports inference-call overhead as a primary axis alongside attack success rate and utility. That three-way trade-off (security, utility, cost) — rather than a new attack or a stronger detector — is this paper's contribution.

---

## 3. Threat Model

We adopt AgentDojo's standard threat model: an attacker controls the content of data the agent's tools return (an email body, a webpage, a file, a calendar entry) but cannot directly modify the user's instruction, the agent's system prompt, or the model weights. The attacker's goal (an "injection task") is to make the agent perform an action the user did not request, using only text embedded in tool outputs. We inherit AgentDojo's four attack templates (Ignore Previous Instructions, System Message, Important Messages, Tool Knowledge) as the primary attack surface and, where time budget allows, evaluate against at least one adaptive/stronger attack (e.g. Important-Instructions-style adaptive attacks) to avoid over-fitting the defense to weak, static templates — a documented failure mode of several prior defenses (see PromptArmor's and AgentDyn's discussion of adaptive-attack fragility).

**Explicit non-goals.** Capability manifests do not defend against: (a) an attacker who can influence the *original* user instruction itself (out of scope — that is a different threat model, closer to jailbreaking); (b) an attacker whose injected instruction requests an action in a tool category the legitimate task already plausibly requires (see §4.3 — this is the mechanism's central, honestly-reported weakness); (c) multi-step privilege laundering across tools we have not explicitly profiled (mitigated only partially by default-deny on unknown/unprofiled tools).

---

## 4. Method

### 4.1 Capability manifests — mechanism **[VERIFIED]**

The mechanism is implemented in `capscope/manifest.py` and `capscope/pipeline.py` (see repository). Summary:

1. **Tool profiling (one-time, per environment).** Each tool available to the agent is hand-annotated with a `category` (e.g. `read`, `search`, `financial`, `destructive`), a `sensitivity` level (1–3), and a small set of `keywords` whose presence in a user instruction is evidence the tool's category is legitimately in scope. This is authored once per AgentDojo task suite, analogous to writing the environment adapter itself.
2. **Manifest derivation (once per episode).** On the user's first message, before any tool call, we tokenize the instruction and compute keyword overlap against every tool's profile. Tools with a keyword hit are explicitly allowed; their categories become "in scope." Low-sensitivity, read/search-category tools are default-allowed even without an explicit hit (agents legitimately use read tools opportunistically); everything else — critically, every high-sensitivity tool without a keyword hit — is denied by default.
3. **Enforcement (every tool call).** `CapabilityScopedToolsExecutor` (a drop-in replacement for AgentDojo's `ToolsExecutor` pipeline element) checks each requested call against the frozen manifest before invoking `runtime.run_function`. Denied calls never execute; the agent receives a synthetic tool-error explaining the denial (mirroring how a real permission system would respond) rather than the tool's real output.
4. **Freezing.** The manifest is computed once, from `extra_args["original_query"]`, stamped at the very start of the pipeline by `RecordOriginalQuery` — a separate element inserted before the planner — so it is never recomputed from later conversation state, including tool outputs. This is what gives the manifest its "cannot be widened by injected text" property (§4.3).

All four properties above are exercised by the unit tests in `tests/test_manifest.py` (5/5 passing, no model calls involved; see §4.2).

### 4.2 What is actually verified right now **[VERIFIED]**

To be precise about what "working" means at this stage of the project:

- The manifest-decision logic is unit-tested in isolation (`test_manifest.py`): read-only tasks do not grant financial-tool capability; explicit financial instructions do; low-sensitivity tools default-allow; unknown high-sensitivity tools deny-by-default; and the manifest object exposes no mutation API, so even a mis-wired pipeline cannot widen it after construction. All 5 tests pass.
- `CapabilityScopedToolsExecutor` and `RecordOriginalQuery` import cleanly against the real, pip-installed `agentdojo==0.1.35` package and instantiate without error, confirming the pipeline element satisfies AgentDojo's `BasePipelineElement` contract (verified by direct inspection of `agentdojo.agent_pipeline.tool_execution.ToolsExecutor`, which this class is a structural sibling of).

What is **not** yet verified: attack success rate, task utility, or overhead on the actual AgentDojo suite, because that requires running a real agent loop against a real LLM backend (open-source model served locally, or the Anthropic/OpenAI APIs) across hundreds of task/attack combinations — a paid or compute-intensive step that has not been run yet. §5 specifies exactly how that run will be structured; §6 is where its results go once it has.

### 4.3 Honest limitation: keyword-collision attacks

If an attacker's injected instruction reuses the same verbs the legitimate task would also use (e.g. a "send money" task being present legitimizes the `financial` category, after which an injected "also send $10,000 to account X" is *not* structurally distinguishable from the user's own request by a keyword-overlap manifest), the manifest offers no protection. We verified this directly: `test_manifest_is_frozen_and_not_widened_by_later_text` shows the manifest correctly rejects an out-of-category injection, but also documents, in the same test, that a keyword-colliding injection *would* pass if (incorrectly) given to `build_manifest` directly — which is precisely why the manifest must only ever be built from the pristine original instruction and never recomputed, and why this is reported as an explicit boundary of the threat model rather than glossed over. We expect this to be the dominant source of residual attack success in the evaluation and will report the attack template breakdown accordingly (§6).

---

## 5. Experimental Design **[PENDING — REQUIRES REAL RUN]**

This section is fully specified and ready to execute; nothing here should be treated as a result until it has actually been run and the numbers pasted into §6.

**Benchmark.** AgentDojo, all four default task suites (banking, Slack, travel, workspace), all default attack templates, plus one adaptive attack if compute budget allows.

**Conditions (independent variable = defense):**
1. **No defense** (stock `ToolsExecutor`) — baseline.
2. **Capability manifest, block mode** (ours).
3. **Capability manifest, flag mode** (ours; measures counterfactual would-block rate on benign-only runs, i.e., false-positive rate against legitimate tasks — the utility cost we are actually paying).
4. *[If time/compute allows]* **Progent** or a close re-implementation, as the LLM-in-the-loop reference point.

**Models.** At least one open-source model served locally (e.g. via vLLM/Ollama on rented/available GPU) to control cost, plus, budget permitting, one frontier model via API as an upper-utility reference point. Model choice and exact versions will be pinned and reported (no "we used an LLM" hand-waving).

**Metrics.**
- **Attack Success Rate (ASR)** — AgentDojo's standard definition, per attack template and averaged.
- **Utility under attack** and **benign-only utility** — AgentDojo's standard definition (task completion rate).
- **False-positive / would-block rate** — fraction of *legitimate* tool calls the manifest would deny on benign-only episodes (flag-mode).
- **Overhead** — wall-clock latency and additional model-inference calls per episode, relative to baseline. This is the paper's headline axis and must be measured on the same hardware/network conditions for every condition.

**What would falsify the thesis.** If capability manifests reduce ASR by only a marginal amount relative to baseline while incurring a nontrivial false-positive rate, the honest conclusion is that zero-inference-cost gating is not a viable middle ground — and the paper will report that, framed as a useful negative result establishing a lower bound on how much LLM-in-the-loop reasoning privilege control actually needs.

---

## 6. Results **[PENDING — DO NOT FILL WITH INVENTED NUMBERS]**

*(Left intentionally empty. Populate only from an actual completed run of the protocol in §5, with the run's raw logs and config committed alongside the paper so every number is reproducible.)*

---

## 7. Discussion & Limitations *(to finalize after §6)*

- Scope: single-agent, tool-calling settings only; multi-agent privilege-escalation (cf. ControlValve, 2026) is out of scope.
- The tool-profiling step is manual and per-environment; it does not claim to generalize to arbitrary, unseen tool sets without a human authoring the taxonomy first — this is a genuine deployment cost that should be reported honestly alongside the inference-cost savings.
- Generalization beyond AgentDojo's four suites is untested in this draft; framing claims accordingly.

## 8. Ethics Statement

This work studies a *defense* mechanism; no new attacks are introduced beyond AgentDojo's existing, published attack templates. All experiments use AgentDojo's synthetic environments; no real user data, real financial accounts, or real third-party services are involved.

## References

*(To be formatted in the target venue's citation style before submission; entries below are the sources actually used to write this draft — no citation appears here that was not read.)*

- Debenedetti, E. et al. "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents." *NeurIPS 2024 Datasets and Benchmarks Track.*
- Zhan, Q. et al. "InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents." 2024.
- Zhu, K. et al. "MELON: Provable Defense Against Indirect Prompt Injection Attacks in AI Agents." arXiv:2502.05174, 2025.
- Shi, T., He, J., Wang, Z., Wu, L., Li, H., Guo, W., Song, D. "Progent: Programmable Privilege Control for LLM Agents." arXiv:2504.11703, 2025.
- Shi, T. et al. "PromptArmor: Simple yet Effective Prompt Injection Defenses." arXiv:2507.15219, 2025.
- Li, X. et al. "AgentDyn: A Dynamic Open-Ended Benchmark for Evaluating Prompt Injection Attacks of Real-World Agent Security Systems." arXiv:2602.03117, 2026.
- Liu, Y. et al. (Google) "[Budget-awareness in tool-calling agents]." arXiv:2511.17006, 2025.
- OWASP. "Top 10 for Large Language Model Applications 2025" — LLM01:2025 Prompt Injection.
- Greshake, K. et al. "Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection." 2023.
