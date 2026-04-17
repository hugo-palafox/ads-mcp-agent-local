from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


OutcomeEvaluator = Callable[["StepDefinition", str, str, int], tuple[str, str, bool]]


@dataclass(frozen=True)
class StepDefinition:
    id: str
    name: str
    category: str
    kind: str
    args: list[str]
    description: str
    why_it_matters: str
    replay_note: str
    expected_classification: str
    hard_failure: bool
    prompt: str | None = None
    intent: str | None = None
    evaluator: OutcomeEvaluator | None = None


@dataclass
class StepResult:
    step: StepDefinition
    command: str
    exit_code: int
    elapsed_seconds: float
    stdout: str
    stderr: str
    classification: str
    observation: str
    success: bool


def shell_quote(parts: list[str]) -> str:
    rendered: list[str] = []
    for part in parts:
        if not part or any(ch.isspace() or ch in {'"', "'"} for ch in part):
            rendered.append(json.dumps(part))
        else:
            rendered.append(part)
    return " ".join(rendered)


def _extract_prompt(args: list[str]) -> str | None:
    if "--prompt" not in args:
        return None
    index = args.index("--prompt")
    if index + 1 >= len(args):
        return None
    return args[index + 1]


def _default_success(step: StepDefinition, stdout: str, stderr: str, exit_code: int) -> tuple[str, str, bool]:
    if exit_code == 0:
        return step.expected_classification, "Command completed successfully.", True
    return "failure", f"Command failed with exit code {exit_code}. stderr={stderr.strip()!r}", False


def _strict_stdout_contains(*needles: str) -> OutcomeEvaluator:
    def _check(step: StepDefinition, stdout: str, stderr: str, exit_code: int) -> tuple[str, str, bool]:
        if exit_code != 0:
            return "failure", f"Expected exit code 0, got {exit_code}. stderr={stderr.strip()!r}", False
        missing = [needle for needle in needles if needle not in stdout]
        if missing:
            return "failure", f"Missing stdout fragments: {missing!r}", False
        return "success", "Expected stdout fragments found.", True

    return _check


def _strict_stdout_or_stderr_contains(*needles: str) -> OutcomeEvaluator:
    def _check(step: StepDefinition, stdout: str, stderr: str, exit_code: int) -> tuple[str, str, bool]:
        if exit_code != 0:
            return "failure", f"Expected exit code 0, got {exit_code}. stderr={stderr.strip()!r}", False
        combined = stdout + "\n" + stderr
        missing = [needle for needle in needles if needle not in combined]
        if missing:
            return "failure", f"Missing output fragments: {missing!r}", False
        return "success", "Expected output fragments found.", True

    return _check


def _demo_success_contains(*needles: str) -> OutcomeEvaluator:
    def _check(step: StepDefinition, stdout: str, stderr: str, exit_code: int) -> tuple[str, str, bool]:
        if exit_code != 0:
            return "failure", f"Command failed with exit code {exit_code}. stderr={stderr.strip()!r}", False
        missing = [needle for needle in needles if needle not in stdout]
        if missing:
            return "failure", f"Missing expected output fragments: {missing!r}", False
        return "success", "Observed the expected successful behavior.", True

    return _check


def _demo_clarification(*needles: str) -> OutcomeEvaluator:
    def _check(step: StepDefinition, stdout: str, stderr: str, exit_code: int) -> tuple[str, str, bool]:
        if exit_code != 0:
            return "failure", f"Command failed with exit code {exit_code}. stderr={stderr.strip()!r}", False
        combined = stdout + "\n" + stderr
        matched = [needle for needle in needles if needle.lower() in combined.lower()]
        if matched:
            return "expected_clarification", f"Model showed clarification/uncertainty via {matched!r}.", True
        return "failure", "Expected clarification or uncertainty behavior was not observed.", False

    return _check


def _demo_guardrail(*needles: str) -> OutcomeEvaluator:
    def _check(step: StepDefinition, stdout: str, stderr: str, exit_code: int) -> tuple[str, str, bool]:
        if exit_code != 0:
            return "failure", f"Command failed with exit code {exit_code}. stderr={stderr.strip()!r}", False
        combined = stdout + "\n" + stderr
        matched = [needle for needle in needles if needle in combined]
        if matched:
            return "expected_guardrail", f"Observed expected guardrail behavior via {matched!r}.", True
        return "failure", "Expected guardrail behavior was not observed.", False

    return _check


def _demo_invalid_write_rejection(step: StepDefinition, stdout: str, stderr: str, exit_code: int) -> tuple[str, str, bool]:
    if exit_code != 0:
        return "failure", f"Command failed with exit code {exit_code}. stderr={stderr.strip()!r}", False
    combined = stdout + "\n" + stderr
    needles = [
        "No discovered tag matched query",
        '"status": "rejected"',
        "rejected because no discovered tag matched",
    ]
    matched = [needle for needle in needles if needle in combined]
    if matched:
        return "expected_guardrail", f"Invalid write was safely rejected via {matched!r}.", True
    return "failure", "Invalid write did not show a safe rejection outcome.", False


def _demo_learning_improvement(step: StepDefinition, stdout: str, stderr: str, exit_code: int) -> tuple[str, str, bool]:
    if exit_code != 0:
        return "failure", f"Command failed with exit code {exit_code}. stderr={stderr.strip()!r}", False
    lower = stdout.lower()
    if "throughput bucket" in lower and "not found" not in lower and "please confirm" not in lower:
        return "success", "The follow-up prompt used the learned alias successfully.", True
    if "globals.ngood" in lower:
        return "success", "The follow-up prompt resolved to the learned target tag.", True
    return "failure", "The follow-up prompt did not clearly show improvement from the learned alias.", False


def _run_step(
    step: StepDefinition,
    *,
    base_command: list[str],
    env: dict[str, str],
    cwd: Path,
    timeout_seconds: float,
) -> StepResult:
    command_parts = [*base_command, *step.args]
    started = time.perf_counter()
    completed = subprocess.run(
        command_parts,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    elapsed = time.perf_counter() - started
    evaluator = step.evaluator or _default_success
    classification, observation, success = evaluator(step, completed.stdout, completed.stderr, completed.returncode)
    return StepResult(
        step=step,
        command=shell_quote(command_parts),
        exit_code=completed.returncode,
        elapsed_seconds=elapsed,
        stdout=completed.stdout,
        stderr=completed.stderr,
        classification=classification,
        observation=observation,
        success=success,
    )


def build_smoke_steps(machine: str, model: str) -> list[StepDefinition]:
    return [
        StepDefinition(
            id="diagnose_model",
            name="Model connectivity",
            category="model_readiness",
            kind="diagnostic",
            args=["diagnose-model", "--model", model, "--no-think"],
            description="Validate model connectivity with thinking disabled.",
            why_it_matters="Confirms the model endpoint is reachable before deeper validation.",
            replay_note="Expect JSON with content OK.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains('"content": "OK"'),
        ),
        StepDefinition(
            id="model_chat",
            name="Direct model chat",
            category="agent_readiness",
            kind="model_chat",
            args=["model-chat", "--model", model, "--no-think", "--prompt", "Reply with one short sentence."],
            prompt="Reply with one short sentence.",
            description="Validate direct chat completion and timing output.",
            why_it_matters="Shows the model can answer outside the tool loop.",
            replay_note="Expect a short sentence and timing output.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains("Response time:"),
        ),
        StepDefinition(
            id="diagnose_mcp",
            name="MCP bridge connectivity",
            category="mcp_connectivity",
            kind="diagnostic",
            args=["diagnose-mcp", "--machine", machine],
            description="Validate MCP bridge connectivity.",
            why_it_matters="Confirms the agent can reach the local bridge and machine memory metadata.",
            replay_note="Expect machine, groups, and memory tag metadata.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains('"machine":', '"list_groups":', '"list_memory_tags":'),
        ),
        StepDefinition(
            id="chat_state_trace",
            name="State read with trace",
            category="bulk_read",
            kind="chat",
            args=["chat", "--machine", machine, "--model", model, "--no-think", "--prompt", "What is the machine state?", "--show-tool-trace"],
            prompt="What is the machine state?",
            description="Validate broad state query with tool trace.",
            why_it_matters="Shows grounded state reads through the tool loop.",
            replay_note="Expect read_memory in the tool trace.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains('"tool_name": "read_memory"', "Response time:"),
        ),
        StepDefinition(
            id="chat_memory_pretty_trace",
            name="Memory summary with pretty trace",
            category="bulk_read",
            kind="chat",
            args=[
                "chat",
                "--machine",
                machine,
                "--model",
                model,
                "--no-think",
                "--prompt",
                "Read all memory tags and summarize them",
                "--show-tool-trace",
                "--tool-trace-format",
                "pretty",
            ],
            prompt="Read all memory tags and summarize them",
            description="Validate pretty tool trace formatting for memory reads.",
            why_it_matters="Shows a presentation-friendly trace view for broad reads.",
            replay_note="Expect Tool Trace and read_memory [OK].",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains("Tool Trace:", "read_memory [OK]"),
        ),
        StepDefinition(
            id="learning_rules",
            name="Learning rules shortcut",
            category="teaching",
            kind="chat",
            args=["chat", "--machine", machine, "--prompt", "Show learning rules"],
            prompt="Show learning rules",
            description="Validate direct learning rules shortcut.",
            why_it_matters="Shows the built-in learning guardrail contract.",
            replay_note="Expect rules mentioning tag aliases.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains("Learning rules:", "tag aliases"),
        ),
        StepDefinition(
            id="teach_response_behavior",
            name="Teach response behavior",
            category="teaching",
            kind="chat",
            args=["chat", "--machine", machine, "--prompt", "Teach response behavior: be concise and use bullet points."],
            prompt="Teach response behavior: be concise and use bullet points.",
            description="Validate response-behavior teaching flow.",
            why_it_matters="Confirms response preferences can be learned and persisted.",
            replay_note="Expect a saved response behavior rule.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains("Saved 1 response behavior rule(s)"),
        ),
        StepDefinition(
            id="teach_alias",
            name="Teach alias",
            category="teaching",
            kind="chat",
            args=["chat", "--machine", machine, "--prompt", "Learn alias Good Parts for Globals.nGood."],
            prompt="Learn alias Good Parts for Globals.nGood.",
            description="Validate alias teaching flow.",
            why_it_matters="Confirms user terminology can be mapped onto real PLC tags.",
            replay_note="Expect a saved tag alias rule mentioning Good Parts.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains("Saved 1 tag alias rule(s)", "Good Parts"),
        ),
        StepDefinition(
            id="show_learning_aliases",
            name="Show learned aliases",
            category="teaching",
            kind="chat",
            args=["chat", "--machine", machine, "--prompt", "Show learning aliases"],
            prompt="Show learning aliases",
            description="Validate learned alias display.",
            why_it_matters="Shows the stored alias mapping used to improve later prompts.",
            replay_note="Expect Current learned tag aliases with Good Parts.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains("Current learned tag aliases:", "Good Parts"),
        ),
        StepDefinition(
            id="show_learning_registry",
            name="Show learning registry",
            category="teaching",
            kind="chat",
            args=["chat", "--machine", machine, "--prompt", "Show learning registry json"],
            prompt="Show learning registry json",
            description="Validate learning registry output.",
            why_it_matters="Shows the registry of accepted and rejected teaching events.",
            replay_note="Expect learning_registry and tag_alias_rules JSON keys.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains('"learning_registry"', '"tag_alias_rules"'),
        ),
        StepDefinition(
            id="write_auto_cancel",
            name="Guarded write auto-cancel",
            category="guarded_write",
            kind="chat",
            args=["chat", "--machine", machine, "--model", model, "--no-think", "--prompt", "Set Globals.bStartButton to true", "--show-tool-trace"],
            prompt="Set Globals.bStartButton to true",
            description="Validate guarded write flow with safe non-interactive auto-cancel.",
            why_it_matters="Shows that writes are never performed unattended.",
            replay_note="Expect request_tag_write and confirm_tag_write with auto-cancel.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_or_stderr_contains(
                "Write confirmation requires interactive input. Auto-cancelling",
                '"tool_name": "request_tag_write"',
                '"tool_name": "confirm_tag_write"',
            ),
        ),
        StepDefinition(
            id="chat_specific_tag_trace",
            name="Specific tag read",
            category="direct_tag_read",
            kind="chat",
            args=["chat", "--machine", machine, "--model", model, "--no-think", "--prompt", "Read Globals.bRun", "--show-tool-trace"],
            prompt="Read Globals.bRun",
            description="Validate specific tag read flow and tool selection.",
            why_it_matters="Shows direct tag reads use the specific read tool.",
            replay_note="Expect read_tag in the tool trace.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_strict_stdout_contains('"tool_name": "read_tag"', "Globals.bRun"),
        ),
    ]


def build_demo_steps(machine: str, model: str) -> list[StepDefinition]:
    unknown_prompt = "What does throughput bucket mean on this machine?"
    return [
        StepDefinition(
            id="learning_reset_start",
            name="Reset learned memory",
            category="teaching_reset",
            kind="learning_reset",
            args=["learning", "reset", "--machine", machine],
            intent=f"Clear learned memory for {machine} before the demo starts.",
            description="Reset learned memory at the start of the demo.",
            why_it_matters="Guarantees the clarification and learning steps start from a clean slate.",
            replay_note="Expect reset=true; this only clears agent learning memory.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_demo_success_contains('"reset": true'),
        ),
        StepDefinition(
            id="model_readiness",
            name="Model readiness",
            category="model_readiness",
            kind="diagnostic",
            args=["diagnose-model", "--model", model, "--no-think"],
            description="Verify the model endpoint is ready.",
            why_it_matters="A live demo is blocked if the model endpoint is not reachable.",
            replay_note="Expect JSON content OK.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_demo_success_contains('"content": "OK"'),
        ),
        StepDefinition(
            id="agent_readiness",
            name="Direct agent/model chat",
            category="agent_readiness",
            kind="model_chat",
            args=["model-chat", "--model", model, "--no-think", "--prompt", "Reply with one sentence describing your role."],
            prompt="Reply with one sentence describing your role.",
            description="Verify the agent can produce a direct model answer.",
            why_it_matters="Shows the model is responsive before tool-heavy steps.",
            replay_note="Expect a natural-language one-sentence answer.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_demo_success_contains("Response time:"),
        ),
        StepDefinition(
            id="mcp_connectivity",
            name="MCP connectivity",
            category="mcp_connectivity",
            kind="diagnostic",
            args=["diagnose-mcp", "--machine", machine],
            description="Verify the MCP bridge is reachable.",
            why_it_matters="Without MCP connectivity, the demo cannot ground answers in PLC data.",
            replay_note="Expect machine, groups, and memory tags in JSON output.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_demo_success_contains('"machine":', '"list_groups":', '"list_memory_tags":'),
        ),
        StepDefinition(
            id="machine_discovery",
            name="Machine discovery via MCP context",
            category="machine_discovery",
            kind="chat",
            args=["chat", "--machine", machine, "--model", model, "--no-think", "--prompt", "List memory tags", "--show-tool-trace"],
            prompt="List memory tags",
            description="Discover machine-specific memory/tag surface.",
            why_it_matters="Shows the agent can enumerate the machine context it is working with.",
            replay_note="Expect list_memory_tags in the tool trace.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_demo_success_contains('"tool_name": "list_memory_tags"'),
        ),
        StepDefinition(
            id="tag_discovery",
            name="PLC tag discovery",
            category="tag_discovery",
            kind="chat",
            args=["chat", "--machine", machine, "--model", model, "--no-think", "--prompt", "List memory tags", "--show-tool-trace", "--tool-trace-format", "pretty"],
            prompt="List memory tags",
            description="Show discovered PLC tag names in a presenter-friendly format.",
            why_it_matters="Gives the operator a visible list of actual PLC-facing tags.",
            replay_note="Expect Tool Trace and list_memory_tags [OK].",
            expected_classification="success",
            hard_failure=False,
            evaluator=_demo_success_contains("Tool Trace:", "list_memory_tags [OK]"),
        ),
        StepDefinition(
            id="direct_tag_read",
            name="Direct tag read",
            category="direct_tag_read",
            kind="chat",
            args=["chat", "--machine", machine, "--model", model, "--no-think", "--prompt", "Read Globals.bRun", "--show-tool-trace"],
            prompt="Read Globals.bRun",
            description="Read a specific PLC tag.",
            why_it_matters="Shows precise grounding for a single tag query.",
            replay_note="Expect read_tag in the trace and Globals.bRun in the response.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_demo_success_contains('"tool_name": "read_tag"', "Globals.bRun"),
        ),
        StepDefinition(
            id="bulk_memory_summary",
            name="Bulk memory summary",
            category="bulk_read",
            kind="chat",
            args=[
                "chat",
                "--machine",
                machine,
                "--model",
                model,
                "--no-think",
                "--prompt",
                "Read all memory tags and summarize them",
                "--show-tool-trace",
                "--tool-trace-format",
                "pretty",
            ],
            prompt="Read all memory tags and summarize them",
            description="Summarize broad machine memory.",
            why_it_matters="Shows a broad operational summary grounded in tool output.",
            replay_note="Expect read_memory and a readable summary.",
            expected_classification="success",
            hard_failure=True,
            evaluator=_demo_success_contains("Tool Trace:", "read_memory [OK]"),
        ),
        StepDefinition(
            id="unknown_term_before_learning",
            name="Unknown-term clarification",
            category="clarification",
            kind="chat",
            args=["chat", "--machine", machine, "--model", model, "--no-think", "--prompt", unknown_prompt],
            prompt=unknown_prompt,
            description="Ask about an unknown business term before learning.",
            why_it_matters="Shows the model asks for clarification instead of inventing meaning.",
            replay_note="A clarification or uncertainty answer is the correct outcome.",
            expected_classification="expected_clarification",
            hard_failure=False,
            evaluator=_demo_clarification(
                "not found",
                "there is no tag named",
                "would you like me to list the available memory tags",
                "please confirm its exact name",
                "unable to retrieve",
            ),
        ),
        StepDefinition(
            id="teach_state_meaning",
            name="Teach state meaning",
            category="teaching",
            kind="chat",
            args=["chat", "--machine", machine, "--prompt", "Teach that nMachineState == 2 means faulted"],
            prompt="Teach that nMachineState == 2 means faulted",
            description="Teach a machine-state meaning.",
            why_it_matters="Shows the agent can learn safe machine-state semantics.",
            replay_note="Expect a saved tag behavior mapping.",
            expected_classification="success",
            hard_failure=False,
            evaluator=_demo_success_contains("Saved 1 tag behavior mapping(s)"),
        ),
        StepDefinition(
            id="teach_response_behavior",
            name="Teach response style",
            category="teaching",
            kind="chat",
            args=["chat", "--machine", machine, "--prompt", "Teach response behavior: be concise and use bullet points"],
            prompt="Teach response behavior: be concise and use bullet points",
            description="Teach preferred response style.",
            why_it_matters="Shows the agent can learn presentation preferences.",
            replay_note="Expect a saved response behavior rule.",
            expected_classification="success",
            hard_failure=False,
            evaluator=_demo_success_contains("Saved 1 response behavior rule(s)"),
        ),
        StepDefinition(
            id="teach_alias",
            name="Teach alias",
            category="teaching",
            kind="chat",
            args=["chat", "--machine", machine, "--prompt", "Learn alias Throughput Bucket for Globals.nGood"],
            prompt="Learn alias Throughput Bucket for Globals.nGood",
            description="Teach the unclear business term as an alias.",
            why_it_matters="Shows learning can connect business language to a real PLC tag.",
            replay_note="Expect a saved alias for Throughput Bucket.",
            expected_classification="success",
            hard_failure=False,
            evaluator=_demo_success_contains("Saved 1 tag alias rule(s)", "Throughput Bucket"),
        ),
        StepDefinition(
            id="show_learning_aliases",
            name="Show learned aliases",
            category="teaching",
            kind="chat",
            args=["chat", "--machine", machine, "--prompt", "Show learning aliases"],
            prompt="Show learning aliases",
            description="Display currently learned aliases.",
            why_it_matters="Makes the learned mapping visible to the operator.",
            replay_note="Expect Throughput Bucket in the alias list.",
            expected_classification="success",
            hard_failure=False,
            evaluator=_demo_success_contains("Throughput Bucket"),
        ),
        StepDefinition(
            id="show_learning_registry",
            name="Show learning registry",
            category="teaching",
            kind="chat",
            args=["chat", "--machine", machine, "--prompt", "Show learning registry json"],
            prompt="Show learning registry json",
            description="Display learning registry metadata.",
            why_it_matters="Shows accepted learning events and registry metadata for the demo run.",
            replay_note="Expect learning_registry JSON with accepted events.",
            expected_classification="success",
            hard_failure=False,
            evaluator=_demo_success_contains('"learning_registry"', '"accepted_tag_alias"', '"accepted_response_behavior"'),
        ),
        StepDefinition(
            id="unknown_term_after_learning",
            name="Follow-up after learning",
            category="learning_improvement",
            kind="chat",
            args=["chat", "--machine", machine, "--model", model, "--no-think", "--prompt", unknown_prompt],
            prompt=unknown_prompt,
            description="Repeat the same business term after alias teaching.",
            why_it_matters="Shows a concrete improvement in behavior after learning.",
            replay_note="Expect the response to resolve Throughput Bucket to Globals.nGood or return a grounded value.",
            expected_classification="success",
            hard_failure=False,
            evaluator=_demo_learning_improvement,
        ),
        StepDefinition(
            id="guarded_write_auto_cancel",
            name="Guarded write auto-cancel",
            category="guarded_write",
            kind="chat",
            args=["chat", "--machine", machine, "--model", model, "--no-think", "--prompt", "Set Globals.bStartButton to true", "--show-tool-trace"],
            prompt="Set Globals.bStartButton to true",
            description="Trigger a safe non-interactive write flow.",
            why_it_matters="Shows the agent requests confirmation and safely auto-cancels unattended writes.",
            replay_note="Auto-cancel is the correct unattended outcome.",
            expected_classification="expected_guardrail",
            hard_failure=False,
            evaluator=_demo_guardrail(
                "Write confirmation requires interactive input. Auto-cancelling",
                '"tool_name": "request_tag_write"',
                '"tool_name": "confirm_tag_write"',
            ),
        ),
        StepDefinition(
            id="invalid_write_rejection",
            name="Invalid write rejection",
            category="guarded_write",
            kind="chat",
            args=["chat", "--machine", machine, "--model", model, "--no-think", "--prompt", "Set Imaginary.DoesNotExist to true", "--show-tool-trace"],
            prompt="Set Imaginary.DoesNotExist to true",
            description="Attempt an invalid write target.",
            why_it_matters="Shows unknown or invalid writes are rejected instead of hallucinated as successful.",
            replay_note="A safe rejection is the desired outcome.",
            expected_classification="expected_guardrail",
            hard_failure=False,
            evaluator=_demo_invalid_write_rejection,
        ),
    ]


def build_capability_map(results: list[StepResult]) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    for result in results:
        category = result.step.category
        if category in seen:
            continue
        seen.add(category)
        lines.append(f"- `{category}`: {result.step.why_it_matters}")
    return lines


def render_smoke_report(
    *,
    results: list[StepResult],
    started_at: str,
    machine: str,
    model: str,
    teaching_store_dir: Path,
    base_command: list[str],
) -> str:
    total = len(results)
    passed = sum(1 for result in results if result.success)
    lines = [
        "ads-mcp-agent-local Feature Smoke Test Report",
        "=" * 44,
        f"Started: {started_at}",
        f"Machine: {machine}",
        f"Model: {model}",
        f"Base command: {shell_quote(base_command)}",
        f"Teaching store dir: {teaching_store_dir}",
        f"Summary: passed={passed} failed={total - passed} total={total}",
        "",
    ]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"[{index:02d}] {result.step.id} - {'PASS' if result.success else 'FAIL'}",
                f"Description: {result.step.description}",
                f"Command: {result.command}",
                f"Exit code: {result.exit_code}",
                f"Elapsed: {result.elapsed_seconds:.3f}s",
                f"Observation: {result.observation}",
                "--- stdout ---",
                result.stdout.rstrip() or "<empty>",
                "--- stderr ---",
                result.stderr.rstrip() or "<empty>",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_demo_transcript(
    *,
    results: list[StepResult],
    started_at: str,
    machine: str,
    model: str,
    teaching_store_dir: Path,
    base_command: list[str],
) -> str:
    hard_failures = [result for result in results if result.classification == "failure" and result.step.hard_failure]
    soft_deviations = [result for result in results if result.classification == "failure" and not result.step.hard_failure]
    expected_positive = [result for result in results if result.classification in {"expected_clarification", "expected_guardrail"}]
    lines = [
        "# Feature Demo Transcript",
        "",
        "## Demo Summary",
        f"- Started: `{started_at}`",
        f"- Machine: `{machine}`",
        f"- Model: `{model}`",
        f"- Base command: `{shell_quote(base_command)}`",
        f"- Teaching store: `{teaching_store_dir}`",
        f"- Steps: `{len(results)}`",
        f"- Hard failures: `{len(hard_failures)}`",
        f"- Soft deviations: `{len(soft_deviations)}`",
        f"- Positive clarification/guardrail outcomes: `{len(expected_positive)}`",
        "",
        "## Capability Map",
        *build_capability_map(results),
        "",
        "## Live Operator Notes",
        "- Reset happens once at the start so the learning story is repeatable.",
        "- Clarification on unknown business terms is a positive outcome before teaching.",
        "- Guarded write auto-cancel and invalid write rejection are positive safety outcomes.",
        "- This transcript preserves the actual model/CLI wording so presentation review can focus on real behavior, not summaries.",
        "",
        "## Suggested Talking Points",
        "- Start by proving model readiness and MCP connectivity.",
        "- Show that broad and specific reads are grounded in tool output.",
        "- Highlight the moment where the model does not understand a business term and asks for clarification.",
        "- Teach the alias and then repeat the same prompt to show measurable improvement.",
        "- End on safety: unattended writes do not execute, and invalid writes are rejected.",
        "",
    ]
    for index, result in enumerate(results, start=1):
        asked = result.step.prompt or result.step.intent or result.step.name
        response = result.stdout.rstrip() or "<empty>"
        stderr = result.stderr.rstrip() or "<empty>"
        lines.extend(
            [
                f"## Step {index:02d} - {result.step.name}",
                f"- Capability category: `{result.step.category}`",
                f"- Outcome classification: `{result.classification}`",
                f"- Exit code: `{result.exit_code}`",
                f"- Elapsed: `{result.elapsed_seconds:.3f}s`",
                f"- Why this matters: {result.step.why_it_matters}",
                f"- Observation: {result.observation}",
                "",
                "### What Was Asked",
                result.step.description,
                "",
                "### Prompt or Intent",
                "```text",
                asked,
                "```",
                "",
                "### Exact Command",
                "```bash",
                result.command,
                "```",
                "",
                "### Actual Response",
                "```text",
                response,
                "```",
                "",
                "### Stderr",
                "```text",
                stderr,
                "```",
                "",
                "### Replay Note",
                result.step.replay_note,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_demo_replay(results: list[StepResult]) -> str:
    lines = [
        "# Feature Demo Replay Commands",
        "# Run these in order during a live presentation.",
        "# Clarification and guardrail outcomes are good outcomes where noted.",
        "",
    ]
    for index, result in enumerate(results, start=1):
        asked = result.step.prompt or result.step.intent or result.step.name
        lines.extend(
            [
                f"# Step {index:02d}: {result.step.name}",
                f"# Category: {result.step.category}",
                f"# Ask/Say: {asked}",
                f"# What to look for: {result.step.replay_note}",
                f"# Why it matters: {result.step.why_it_matters}",
                result.command,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_demo_raw_payload(
    *,
    results: list[StepResult],
    started_at: str,
    machine: str,
    model: str,
    teaching_store_dir: Path,
    base_command: list[str],
) -> dict[str, object]:
    return {
        "run_type": "demo",
        "started_at": started_at,
        "machine": machine,
        "model": model,
        "base_command": base_command,
        "teaching_store_dir": str(teaching_store_dir),
        "summary": {
            "total_steps": len(results),
            "hard_failures": sum(1 for result in results if result.classification == "failure" and result.step.hard_failure),
            "soft_deviations": sum(1 for result in results if result.classification == "failure" and not result.step.hard_failure),
            "expected_positive_outcomes": sum(
                1 for result in results if result.classification in {"expected_clarification", "expected_guardrail"}
            ),
        },
        "steps": [
            {
                "index": index,
                "step": {
                    **asdict(result.step),
                    "evaluator": None,
                },
                "command": result.command,
                "exit_code": result.exit_code,
                "elapsed_seconds": result.elapsed_seconds,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "classification": result.classification,
                "observation": result.observation,
                "success": result.success,
            }
            for index, result in enumerate(results, start=1)
        ],
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the agent feature harness in strict smoke-validation mode or in live demo mode "
            "that generates JSON, Markdown, and replay artifacts."
        )
    )
    parser.add_argument("--mode", choices=("smoke", "demo"), default="smoke", help="Execution mode. Default: smoke")
    parser.add_argument("--machine", default="Machine1", help="Machine id to target. Default: Machine1")
    parser.add_argument("--model", default="gemma4:e4b", help="Model name to use for model-backed steps.")
    parser.add_argument(
        "--report-dir",
        default="artifacts/smoke-tests",
        help="Directory where smoke and demo artifacts are written. Default: artifacts/smoke-tests",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=180.0,
        help="Per-command timeout in seconds. Default: 180",
    )
    parser.add_argument(
        "--use-entrypoint",
        action="store_true",
        help="Use the installed 'ads-agent' entrypoint instead of 'python -m cli.main'.",
    )
    parser.add_argument(
        "--keep-teaching-store",
        action="store_true",
        help="Keep the temporary teaching store directory after the run for inspection.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parent.parent
    report_dir = (repo_root / args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    teaching_dir_context = tempfile.TemporaryDirectory(prefix="ads-agent-smoke-teaching-")
    teaching_store_dir = Path(teaching_dir_context.name)
    base_command = ["ads-agent"] if args.use_entrypoint else [sys.executable, "-m", "cli.main"]
    env = os.environ.copy()
    env["ADS_AGENT_MODEL_NAME"] = args.model
    env["ADS_AGENT_MODEL_THINKING"] = "false"
    env["ADS_AGENT_TEACHING_STORE_DIR"] = str(teaching_store_dir)

    started_at = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    steps = build_demo_steps(args.machine, args.model) if args.mode == "demo" else build_smoke_steps(args.machine, args.model)
    results: list[StepResult] = []
    try:
        for step in steps:
            result = _run_step(
                step,
                base_command=base_command,
                env=env,
                cwd=repo_root,
                timeout_seconds=args.timeout_seconds,
            )
            results.append(result)
            status = result.classification.upper()
            print(f"[{status}] {step.id} ({result.elapsed_seconds:.2f}s)")

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        if args.mode == "demo":
            raw_payload = build_demo_raw_payload(
                results=results,
                started_at=started_at,
                machine=args.machine,
                model=args.model,
                teaching_store_dir=teaching_store_dir,
                base_command=base_command,
            )
            raw_path = report_dir / f"feature-demo-raw-{timestamp}.json"
            transcript_path = report_dir / f"feature-demo-transcript-{timestamp}.md"
            replay_path = report_dir / f"feature-demo-replay-{timestamp}.txt"
            raw_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")
            transcript_path.write_text(
                render_demo_transcript(
                    results=results,
                    started_at=started_at,
                    machine=args.machine,
                    model=args.model,
                    teaching_store_dir=teaching_store_dir,
                    base_command=base_command,
                ),
                encoding="utf-8",
            )
            replay_path.write_text(render_demo_replay(results), encoding="utf-8")
            hard_failures = sum(1 for result in results if result.classification == "failure" and result.step.hard_failure)
            soft_deviations = sum(1 for result in results if result.classification == "failure" and not result.step.hard_failure)
            print(f"\nDemo summary: hard_failures={hard_failures} soft_deviations={soft_deviations} total_steps={len(results)}")
            print(f"Raw JSON: {raw_path}")
            print(f"Transcript: {transcript_path}")
            print(f"Replay: {replay_path}")
            return 0 if hard_failures == 0 else 1

        report_text = render_smoke_report(
            results=results,
            started_at=started_at,
            machine=args.machine,
            model=args.model,
            teaching_store_dir=teaching_store_dir,
            base_command=base_command,
        )
        report_path = report_dir / f"feature-smoke-report-{timestamp}.log"
        report_path.write_text(report_text, encoding="utf-8")
        passed = sum(1 for result in results if result.success)
        print(f"\nSummary: passed={passed} failed={len(results) - passed} total={len(results)}")
        print(f"Report: {report_path}")
        return 0 if passed == len(results) else 1
    finally:
        if args.keep_teaching_store:
            print(f"Teaching store kept at: {teaching_store_dir}")
        else:
            teaching_dir_context.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
