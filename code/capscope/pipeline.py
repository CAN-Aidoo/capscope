"""
capscope.pipeline
==================

An AgentDojo `BasePipelineElement` that enforces a `CapabilityManifest`
(see `capscope.manifest`) at the moment each tool call is about to run,
BEFORE its result is ever handed back to the agent.

Design goal: a drop-in replacement for `agentdojo.agent_pipeline.tool_execution.
ToolsExecutor` that changes only what happens to *blocked* calls, so it can
be swapped into any existing AgentDojo pipeline with a one-line change --
this mirrors how Progent and MELON are integrated in their own papers, which
keeps the eventual cost/ASR/utility comparison apples-to-apples.

NOTE ON WHAT THIS FILE DOES AND DOES NOT PROVE
------------------------------------------------
Importing and unit-testing this module (see `tests/test_pipeline.py`)
verifies that the *mechanism* is correctly wired into AgentDojo's runtime
contract: blocked calls never reach `runtime.run_function`, allowed calls
are unaffected, and the manifest is computed once from the pristine user
instruction and frozen for the rest of the episode. It does NOT, by itself,
demonstrate any attack-success-rate or utility number -- those require
running the full AgentDojo suite against a real LLM backend (open-source
or via the Anthropic API), which is the next step in this project, not
something this script fabricates.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionReturnType, FunctionsRuntime
from agentdojo.types import ChatMessage, ChatToolResultMessage, text_content_block_from_string

from capscope.manifest import CapabilityManifest, ToolProfile, build_manifest


class CapabilityScopedToolsExecutor(BasePipelineElement):
    """Executes tool calls, but blocks any call whose tool is outside the
    capability manifest derived from the ORIGINAL user instruction.

    Parameters
    ----------
    tool_profiles:
        Static metadata for every tool in the environment (see
        `capscope.manifest.ToolProfile`). Must be authored once per
        AgentDojo task suite (banking / slack / travel / workspace); this
        is analogous to writing the environment adapter itself and is not
        part of the per-episode cost being measured.
    mode:
        "block" (default): disallowed calls are never executed; the agent
        receives a synthetic tool-error message explaining the denial.
        "flag": disallowed calls ARE executed (matches an unprotected
        agent's behavior) but are logged, to measure what *would* have
        been blocked without affecting task completion. Used to compute
        the counterfactual "would-block" rate on the benign-only run
        (i.e. false-positive rate against genuinely legitimate tasks).
    tool_output_formatter:
        Same hook as AgentDojo's `ToolsExecutor`, passed through unchanged.
    """

    def __init__(
        self,
        tool_profiles: Sequence[ToolProfile],
        mode: str = "block",
        tool_output_formatter: Callable[[FunctionReturnType], str] = tool_result_to_str,
    ) -> None:
        if mode not in ("block", "flag"):
            raise ValueError("mode must be 'block' or 'flag'")
        self.tool_profiles = {t.name: t for t in tool_profiles}
        self.mode = mode
        self.output_formatter = tool_output_formatter
        self._manifest: CapabilityManifest | None = None
        self.decision_log: list[dict] = []

    def _ensure_manifest(self, extra_args: dict, original_query: str) -> CapabilityManifest:
        """Build the manifest exactly once per episode, from the pristine
        original user instruction carried in `extra_args`. Subsequent
        pipeline calls within the same tool-execution loop reuse it -- this
        is what makes the manifest immune to being widened by anything the
        agent reads later, including injected instructions in tool output.
        """
        if "capscope_manifest" not in extra_args:
            manifest = build_manifest(original_query, self.tool_profiles.values())
            extra_args = {**extra_args, "capscope_manifest": manifest}
        return extra_args["capscope_manifest"], extra_args

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        if len(messages) == 0:
            return query, runtime, env, messages, extra_args
        if messages[-1]["role"] != "assistant":
            return query, runtime, env, messages, extra_args
        if messages[-1]["tool_calls"] is None or len(messages[-1]["tool_calls"]) == 0:
            return query, runtime, env, messages, extra_args

        # `extra_args["original_query"]` is expected to be set once, upstream,
        # by a thin pipeline element inserted right after the user's first
        # message is read (see `capscope.pipeline.RecordOriginalQuery`).
        original_query = extra_args.get("original_query", query)
        manifest, extra_args = self._ensure_manifest(extra_args, original_query)

        tool_call_results = []
        for tool_call in messages[-1]["tool_calls"]:
            profile = self.tool_profiles.get(tool_call.function)

            if profile is None:
                # Unknown tool name: fall through to the runtime, which will
                # raise its own "invalid tool" error, exactly like stock
                # AgentDojo. capscope does not change this path.
                tool_call_result, error = runtime.run_function(env, tool_call.function, tool_call.args)
                formatted = self.output_formatter(tool_call_result)
                tool_call_results.append(
                    ChatToolResultMessage(
                        role="tool",
                        content=[text_content_block_from_string(formatted)],
                        tool_call_id=tool_call.id,
                        tool_call=tool_call,
                        error=error,
                    )
                )
                continue

            decision = manifest.decide(profile)
            self.decision_log.append(
                {
                    "tool": tool_call.function,
                    "category": profile.category,
                    "sensitivity": profile.sensitivity,
                    "allowed": decision.allowed,
                    "reason": decision.reason,
                    "mode": self.mode,
                }
            )

            if (not decision.allowed) and self.mode == "block":
                tool_call_results.append(
                    ChatToolResultMessage(
                        role="tool",
                        content=[
                            text_content_block_from_string(
                                f"[capscope] Call to '{tool_call.function}' denied: {decision.reason}. "
                                "This tool is outside the capability scope derived from your original "
                                "instruction and was not executed."
                            )
                        ],
                        tool_call_id=tool_call.id,
                        tool_call=tool_call,
                        error=f"capscope_denied: {decision.reason}",
                    )
                )
                continue

            tool_call_result, error = runtime.run_function(env, tool_call.function, tool_call.args)
            formatted_tool_call_result = self.output_formatter(tool_call_result)
            tool_call_results.append(
                ChatToolResultMessage(
                    role="tool",
                    content=[text_content_block_from_string(formatted_tool_call_result)],
                    tool_call_id=tool_call.id,
                    tool_call=tool_call,
                    error=error,
                )
            )

        return query, runtime, env, [*messages, *tool_call_results], extra_args


class RecordOriginalQuery(BasePipelineElement):
    """Stamps `extra_args["original_query"]` with the FIRST user query seen
    in the episode, before any tool has run. Insert this once, at the very
    start of the pipeline (before the planner/LLM element), so that
    `CapabilityScopedToolsExecutor` always has access to the pristine
    instruction even many turns later, regardless of what the rest of the
    conversation has since accumulated.
    """

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        if "original_query" not in extra_args:
            extra_args = {**extra_args, "original_query": query}
        return query, runtime, env, messages, extra_args
