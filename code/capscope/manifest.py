"""
capscope.manifest
==================

Deterministic, LLM-free capability manifest derivation for tool-calling LLM
agents.

Core idea
---------
Before the agent takes a single step, we derive a *capability manifest* --
a static, machine-checkable description of which tools (and, where
practical, which argument patterns / target-entity classes) are legitimately
needed to satisfy the user's ORIGINAL instruction.  Every subsequent tool
call the agent attempts is checked against this manifest.  Calls outside the
manifest are blocked (or, in "flag" mode, allowed but logged) regardless of
what any tool *output* the agent has since read tells it to do.

This is deliberately the cheapest possible version of least-privilege
control for tool-calling agents:

  * No LLM call is used to build or update the policy (contrast: Progent
    [Shi et al., 2025, arXiv:2504.11703], which uses an LLM + SMT solver to
    synthesize and monotonically narrow policies at *runtime*).
  * No alignment/relatedness classifier is invoked per tool call (contrast:
    MELON [Zhu et al., 2025, arXiv:2502.05174], which re-runs the agent
    LLM on a masked copy of the trajectory to detect apparent goal
    drift).
  * The manifest is built ONCE, synchronously, from the user's instruction
    text plus a small static tool-metadata table, using nothing more than
    keyword/embedding similarity and a hand-authored tool taxonomy.

The bet this design is testing is narrow and falsifiable: in the specific
regime this project targets -- intermittent connectivity / metered,
latency-sensitive deployments where an *extra LLM call per tool
invocation is itself a cost the system cannot always afford* -- does a
zero-inference-cost, deterministic capability gate retain a useful fraction
of the security benefit that LLM-in-the-loop privilege controllers provide,
at a fraction of the overhead?  This module intentionally does NOT claim to
match or beat Progent/MELON on raw attack-success-rate; the contribution is
the cost/security trade-off curve, measured honestly (see
`evaluation/README.md`).

Everything in this file is deterministic and unit-testable without any
model calls, which is why it is safe to build and test now, before we have
committed API budget for the full AgentDojo run.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable


@dataclasses.dataclass(frozen=True)
class ToolProfile:
    """Static, hand-authored metadata about one tool the agent can call.

    Parameters
    ----------
    name:
        The tool's function name, as registered with the agent runtime.
    category:
        A coarse capability class, e.g. "read", "send", "write", "financial",
        "search". Used for manifest matching and for reporting *which*
        capability class an attack tried to reach.
    keywords:
        Terms whose presence in the user's instruction are evidence that
        this tool's category is legitimately in scope for the task.
    sensitivity:
        1 (low; e.g. read-only search) to 3 (high; e.g. money transfer,
        irreversible send/delete). Used only for reporting and for the
        "sensitive tools always require an explicit keyword match, never a
        default-allow" rule below.
    """

    name: str
    category: str
    keywords: tuple[str, ...]
    sensitivity: int = 1


@dataclasses.dataclass(frozen=True)
class CapabilityDecision:
    tool_name: str
    allowed: bool
    reason: str


class CapabilityManifest:
    """A frozen, per-episode set of permitted tool categories.

    The manifest is derived once from the user's ORIGINAL instruction and
    the static `ToolProfile` table for the environment. It is never updated
    from tool outputs -- that is the entire point: injected instructions
    arrive as tool outputs, so a policy that can only shrink or stay fixed
    (never grow) from that channel cannot be expanded by an attacker no
    matter how persuasive the injected text is.
    """

    def __init__(
        self,
        allowed_categories: frozenset[str],
        matched_tools: frozenset[str],
        low_sensitivity_default_allow: bool = True,
    ) -> None:
        self.allowed_categories = allowed_categories
        self.matched_tools = matched_tools
        self.low_sensitivity_default_allow = low_sensitivity_default_allow

    def decide(self, tool: ToolProfile) -> CapabilityDecision:
        if tool.name in self.matched_tools:
            return CapabilityDecision(tool.name, True, "explicit keyword match")

        if tool.category in self.allowed_categories:
            return CapabilityDecision(tool.name, True, "category in scope")

        if (
            self.low_sensitivity_default_allow
            and tool.sensitivity <= 1
            and tool.category in {"read", "search"}
        ):
            return CapabilityDecision(tool.name, True, "low-sensitivity default-allow")

        return CapabilityDecision(
            tool.name,
            False,
            f"category '{tool.category}' (sensitivity={tool.sensitivity}) "
            f"not evidenced by the original user instruction",
        )


_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_']+")


from nltk.stem.porter import PorterStemmer

_PORTER = PorterStemmer()


def _stem(word: str) -> str:
    """Porter stem (NLTK), so that 'emails'/'email', 'scheduled'/'schedule',
    'paying'/'pay' match. Fixed, off-the-shelf, and not tuned on benchmark prompts."""
    return _PORTER.stem(word.lower().strip("'"))


def _tokenize(text: str) -> set[str]:
    return {_stem(w) for w in _WORD_RE.findall(text)}


def build_manifest(
    user_instruction: str,
    tool_profiles: Iterable[ToolProfile],
    low_sensitivity_default_allow: bool = True,
) -> CapabilityManifest:
    """Deterministically derive a capability manifest from a user instruction.

    This is intentionally a simple, auditable keyword-overlap rule rather
    than an LLM call or a learned classifier -- auditability and zero
    inference cost are the point of this design, not novelty of the
    matching algorithm. A stronger matcher (e.g. a small local sentence
    embedding model) is a documented ablation, not a requirement, see
    `evaluation/ablations.py`.
    """
    tokens = _tokenize(user_instruction)
    allowed_categories: set[str] = set()
    matched_tools: set[str] = set()

    for tool in tool_profiles:
        kw_hits = sum(1 for kw in tool.keywords if _stem(kw) in tokens)
        if kw_hits > 0:
            matched_tools.add(tool.name)
            allowed_categories.add(tool.category)

    return CapabilityManifest(
        allowed_categories=frozenset(allowed_categories),
        matched_tools=frozenset(matched_tools),
        low_sensitivity_default_allow=low_sensitivity_default_allow,
    )
