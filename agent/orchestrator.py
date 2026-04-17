from __future__ import annotations

import json
import re
from typing import Any, Callable

from agent.conversation import Conversation
from agent.models import AgentRunResult
from agent.prompts import build_system_prompt
from agent.teaching import (
    LearningRejection,
    ResponseBehaviorRule,
    StateRule,
    TagAliasRule,
    TeachingStore,
    evaluate_tag_alias_rule,
    evaluate_response_behavior_rule,
    format_tag_alias_rules_for_user,
    format_response_rules_for_user,
    format_state_rules_for_user,
    interpret_state_from_memory,
    learning_guardrail_message,
    learning_rules_for_user,
    looks_like_tag_alias_query,
    looks_like_learning_intent,
    looks_like_learning_registry_query,
    looks_like_learning_rules_query,
    looks_like_response_behavior_query,
    looks_like_state_rule_query,
    normalize_alias,
    parse_response_behavior_prompt,
    parse_tag_alias_prompt,
    parse_teaching_prompt,
    resolve_alias_target,
)
from agent.tool_executor import ToolExecutor
from agent.tool_registry import ToolRegistry
from config.settings import Settings
from llm.client import LLMClient


class AgentOrchestrator:
    def __init__(
        self,
        settings: Settings,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        write_confirmer: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor
        self.write_confirmer = write_confirmer
        self.teaching_store = TeachingStore(settings.teaching_store_dir)

    def run(self, *, machine_id: str, prompt: str) -> AgentRunResult:
        learned_state_rules = self.teaching_store.list_state_rules(machine_id)
        learned_response_rules = self.teaching_store.list_response_rules(machine_id)
        learned_tag_alias_rules = self.teaching_store.list_tag_alias_rules(machine_id)
        conversation = Conversation(
            build_system_prompt(machine_id, learned_state_rules, learned_response_rules, learned_tag_alias_rules)
        )
        teaching_result = self._attempt_teaching_prompt(
            machine_id=machine_id,
            prompt=prompt,
            conversation=conversation,
            learned_state_rules=learned_state_rules,
            learned_response_rules=learned_response_rules,
            learned_tag_alias_rules=learned_tag_alias_rules,
        )
        if teaching_result is not None:
            return teaching_result

        enriched_prompt = self._augment_prompt_with_alias_hints(prompt, learned_tag_alias_rules)
        enriched_prompt = self._augment_prompt_with_intent_hints(enriched_prompt)
        conversation.add_user(enriched_prompt)
        tool_trace = []
        failed_tool_calls = 0

        for iteration in range(1, self.settings.max_tool_steps + 1):
            response = self.llm_client.complete(conversation.messages, self.tool_registry.list_for_model())
            conversation.add_assistant(response.content, [
                {
                    "id": call.id,
                    "type": "function",
                    # OpenAI-compatible APIs expect function.arguments as a JSON string.
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                }
                for call in response.tool_calls
            ] if response.tool_calls else None)

            if not response.tool_calls:
                if not response.content and not tool_trace:
                    direct_intent_result = self._attempt_direct_machine_command(
                        machine_id=machine_id,
                        prompt=prompt,
                        conversation=conversation,
                        tool_trace=tool_trace,
                        iteration=iteration,
                    )
                    if direct_intent_result is not None:
                        return direct_intent_result
                answer = response.content or self._fallback_answer_for_empty_content(tool_trace, prompt)
                answer = self._append_learned_state_interpretation(
                    answer=answer,
                    prompt=prompt,
                    tool_trace=tool_trace,
                    learned_state_rules=learned_state_rules,
                )
                return AgentRunResult(
                    answer=answer,
                    messages=conversation.messages,
                    tool_trace=tool_trace,
                    iterations=iteration,
                )

            for tool_call in response.tool_calls:
                arguments = dict(tool_call.arguments)
                # Keep tool execution bound to the CLI-selected machine context,
                # even if the model emits a different machine_id (for example "M1").
                arguments["machine_id"] = machine_id
                result = self.tool_executor.execute(tool_call.name, arguments)
                tool_trace.append(result)
                conversation.add_tool_result(tool_call.id, tool_call.name, result.to_message_payload())
                if not result.ok:
                    failed_tool_calls += 1
                    if failed_tool_calls >= self.settings.max_tool_failures:
                        return AgentRunResult(
                            answer=f"Stopped after repeated tool failures. Last error: {result.error}",
                            messages=conversation.messages,
                            tool_trace=tool_trace,
                            iterations=iteration,
                        )
                    continue

                pending_request = self._extract_pending_request(result.output, arguments)
                if tool_call.name == "request_tag_write" and pending_request is not None:
                    confirmed = self.write_confirmer(pending_request) if self.write_confirmer is not None else False
                    confirm_call_id = f"{tool_call.id}:confirm"
                    confirm_arguments = {
                        "machine_id": machine_id,
                        "request_id": pending_request["request_id"],
                        "confirmed": bool(confirmed),
                    }
                    conversation.add_assistant(
                        content=None,
                        tool_calls=[
                            {
                                "id": confirm_call_id,
                                "type": "function",
                                "function": {
                                    "name": "confirm_tag_write",
                                    "arguments": json.dumps(confirm_arguments),
                                },
                            }
                        ],
                    )
                    confirm_result = self.tool_executor.execute_internal("confirm_tag_write", confirm_arguments)
                    tool_trace.append(confirm_result)
                    conversation.add_tool_result(confirm_call_id, "confirm_tag_write", confirm_result.to_message_payload())
                    if not confirm_result.ok:
                        failed_tool_calls += 1
                        if failed_tool_calls >= self.settings.max_tool_failures:
                            return AgentRunResult(
                                answer=f"Stopped after repeated tool failures. Last error: {confirm_result.error}",
                                messages=conversation.messages,
                                tool_trace=tool_trace,
                                iterations=iteration,
                            )

        return AgentRunResult(
            answer="Stopped before completion because the maximum tool iteration limit was reached.",
            messages=conversation.messages,
            tool_trace=tool_trace,
            iterations=self.settings.max_tool_steps,
        )

    def _attempt_teaching_prompt(
        self,
        *,
        machine_id: str,
        prompt: str,
        conversation: Conversation,
        learned_state_rules: list[StateRule],
        learned_response_rules: list[ResponseBehaviorRule],
        learned_tag_alias_rules: list[TagAliasRule],
    ) -> AgentRunResult | None:
        if looks_like_learning_rules_query(prompt):
            conversation.add_user(prompt)
            answer = learning_rules_for_user()
            conversation.add_assistant(answer)
            return AgentRunResult(answer=answer, messages=conversation.messages, tool_trace=[], iterations=0)

        if looks_like_learning_registry_query(prompt):
            conversation.add_user(prompt)
            answer = self.teaching_store.format_registry_json(machine_id)
            conversation.add_assistant(answer)
            return AgentRunResult(answer=answer, messages=conversation.messages, tool_trace=[], iterations=0)

        if looks_like_tag_alias_query(prompt):
            conversation.add_user(prompt)
            answer = format_tag_alias_rules_for_user(learned_tag_alias_rules)
            conversation.add_assistant(answer)
            return AgentRunResult(answer=answer, messages=conversation.messages, tool_trace=[], iterations=0)

        parsed_state_rules = parse_teaching_prompt(prompt)
        parsed_response_rules = parse_response_behavior_prompt(prompt)
        parsed_alias_rules = parse_tag_alias_prompt(prompt)
        accepted_response_rules: list[ResponseBehaviorRule] = []
        rejected_response_rejections: list[LearningRejection] = []
        accepted_alias_rules: list[TagAliasRule] = []
        rejected_alias_rejections: list[LearningRejection] = []
        known_targets = self._discover_known_learning_targets(machine_id) if parsed_alias_rules else []
        alias_target_index = {target.lower(): target for target in known_targets}
        current_alias_index = {normalize_alias(rule.alias_display): rule for rule in learned_tag_alias_rules}
        pending_alias_index = dict(current_alias_index)
        for rule in parsed_response_rules:
            rejection = evaluate_response_behavior_rule(rule)
            if rejection is not None:
                rejected_response_rejections.append(rejection)
                continue
            accepted_response_rules.append(rule)
        for rule in parsed_alias_rules:
            basic_rejection = evaluate_tag_alias_rule(rule)
            if basic_rejection is not None:
                rejected_alias_rejections.append(basic_rejection)
                continue
            canonical_target, ambiguous_candidates = resolve_alias_target(rule.target_tag, known_targets)
            if ambiguous_candidates:
                rejected_alias_rejections.append(
                    LearningRejection(
                        reason_code="tag_alias_ambiguous_target",
                        message=f"Alias target '{rule.target_tag}' is ambiguous; matches: {', '.join(ambiguous_candidates)}.",
                    )
                )
                continue
            if canonical_target is None:
                rejected_alias_rejections.append(
                    LearningRejection(
                        reason_code="tag_alias_unknown_target",
                        message=f"Alias target '{rule.target_tag}' was not found in known machine memory/tag fields.",
                    )
                )
                continue
            alias_key = normalize_alias(rule.alias_display)
            existing = pending_alias_index.get(alias_key)
            if existing is not None and existing.target_tag.lower() != canonical_target.lower():
                rejected_alias_rejections.append(
                    LearningRejection(
                        reason_code="tag_alias_conflict",
                        message=(
                            f"Alias '{rule.alias_display}' already maps to '{existing.target_tag}' "
                            f"and cannot be remapped to '{canonical_target}'."
                        ),
                    )
                )
                continue
            canonical_rule = TagAliasRule(
                alias_display=rule.alias_display,
                alias_normalized=alias_key,
                target_tag=alias_target_index.get(canonical_target.lower(), canonical_target),
            )
            accepted_alias_rules.append(canonical_rule)
            pending_alias_index[alias_key] = canonical_rule

        if parsed_state_rules or parsed_response_rules or parsed_alias_rules:
            conversation.add_user(prompt)
            answer_parts: list[str] = []
            answer_parts.append(
                f"Learning summary for {machine_id}: "
                f"accepted_tag_behavior={len(parsed_state_rules)}, "
                f"accepted_response_behavior={len(accepted_response_rules)}, "
                f"rejected_response_behavior={len(rejected_response_rejections)}, "
                f"accepted_tag_alias={len(accepted_alias_rules)}, "
                f"rejected_tag_alias={len(rejected_alias_rejections)}."
            )

            merged_state_rules = learned_state_rules
            if parsed_state_rules:
                added_state, updated_state, merged_state_rules = self.teaching_store.upsert_state_rules(machine_id, parsed_state_rules)
                detail = (
                    f"Saved {len(parsed_state_rules)} tag behavior mapping(s) "
                    f"(added={added_state}, updated={updated_state})."
                )
                self.teaching_store.record_learning_event(
                    machine_id,
                    category="tag_behavior",
                    status="accepted",
                    source_prompt=prompt,
                    detail=detail,
                    reason_code="accepted_tag_behavior",
                    metadata={
                        "parsed_state_rules": len(parsed_state_rules),
                        "added": added_state,
                        "updated": updated_state,
                    },
                )
                answer_parts.append(detail)

            merged_response_rules = learned_response_rules
            if accepted_response_rules:
                added_response, updated_response, merged_response_rules = self.teaching_store.upsert_response_rules(
                    machine_id,
                    accepted_response_rules,
                )
                detail = (
                    f"Saved {len(accepted_response_rules)} response behavior rule(s) "
                    f"(added={added_response}, updated={updated_response})."
                )
                self.teaching_store.record_learning_event(
                    machine_id,
                    category="response_behavior",
                    status="accepted",
                    source_prompt=prompt,
                    detail=detail,
                    reason_code="accepted_response_behavior",
                    metadata={
                        "parsed_response_rules": len(parsed_response_rules),
                        "accepted_response_rules": len(accepted_response_rules),
                        "added": added_response,
                        "updated": updated_response,
                    },
                )
                answer_parts.append(detail)

            merged_tag_alias_rules = learned_tag_alias_rules
            if accepted_alias_rules:
                added_alias, updated_alias, merged_tag_alias_rules = self.teaching_store.upsert_tag_alias_rules(
                    machine_id,
                    accepted_alias_rules,
                )
                detail = (
                    f"Saved {len(accepted_alias_rules)} tag alias rule(s) "
                    f"(added={added_alias}, updated={updated_alias})."
                )
                self.teaching_store.record_learning_event(
                    machine_id,
                    category="tag_alias",
                    status="accepted",
                    source_prompt=prompt,
                    detail=detail,
                    reason_code="accepted_tag_alias",
                    metadata={
                        "parsed_tag_alias_rules": len(parsed_alias_rules),
                        "accepted_tag_alias_rules": len(accepted_alias_rules),
                        "added": added_alias,
                        "updated": updated_alias,
                    },
                )
                answer_parts.append(detail)

            if rejected_response_rejections:
                first_rejection = rejected_response_rejections[0]
                rejection_detail = (
                    f"Rejected {len(rejected_response_rejections)} response behavior rule(s). "
                    f"First reason [{first_rejection.reason_code}]: {first_rejection.message}"
                )
                self.teaching_store.record_learning_event(
                    machine_id,
                    category="response_behavior",
                    status="rejected",
                    source_prompt=prompt,
                    detail=rejection_detail,
                    reason_code=first_rejection.reason_code,
                    metadata={
                        "parsed_response_rules": len(parsed_response_rules),
                        "rejected_response_rules": len(rejected_response_rejections),
                    },
                )
                answer_parts.append(rejection_detail)

            if rejected_alias_rejections:
                first_rejection = rejected_alias_rejections[0]
                rejection_detail = (
                    f"Rejected {len(rejected_alias_rejections)} tag alias rule(s). "
                    f"First reason [{first_rejection.reason_code}]: {first_rejection.message}"
                )
                self.teaching_store.record_learning_event(
                    machine_id,
                    category="tag_alias",
                    status="rejected",
                    source_prompt=prompt,
                    detail=rejection_detail,
                    reason_code=first_rejection.reason_code,
                    metadata={
                        "parsed_tag_alias_rules": len(parsed_alias_rules),
                        "rejected_tag_alias_rules": len(rejected_alias_rejections),
                    },
                )
                answer_parts.append(rejection_detail)

            if parsed_state_rules:
                answer_parts.append(format_state_rules_for_user(merged_state_rules))
            if accepted_response_rules:
                answer_parts.append(format_response_rules_for_user(merged_response_rules))
            if accepted_alias_rules:
                answer_parts.append(format_tag_alias_rules_for_user(merged_tag_alias_rules))

            answer = " ".join(answer_parts)
            conversation.add_assistant(answer)
            return AgentRunResult(answer=answer, messages=conversation.messages, tool_trace=[], iterations=0)

        if looks_like_learning_intent(prompt):
            conversation.add_user(prompt)
            detail = learning_guardrail_message()
            reason_code = "unsupported_learning_intent"
            self.teaching_store.record_learning_event(
                machine_id,
                category="unknown",
                status="rejected",
                source_prompt=prompt,
                detail=detail,
                reason_code=reason_code,
                metadata={
                    "parsed_state_rules": 0,
                    "parsed_response_rules": 0,
                },
            )
            answer = (
                f"Learning rejected [{reason_code}]: {detail} "
                "Example tag behavior: 'Teach that nMachineState == 2 means faulted.' "
                "Example response behavior: 'Teach response behavior: be concise and use bullets.' "
                "Example tag alias: 'Learn alias Good Parts for Globals.nGood.'"
            )
            conversation.add_assistant(answer)
            return AgentRunResult(answer=answer, messages=conversation.messages, tool_trace=[], iterations=0)

        if looks_like_response_behavior_query(prompt):
            conversation.add_user(prompt)
            answer = format_response_rules_for_user(learned_response_rules)
            conversation.add_assistant(answer)
            return AgentRunResult(answer=answer, messages=conversation.messages, tool_trace=[], iterations=0)

        if looks_like_state_rule_query(prompt):
            conversation.add_user(prompt)
            answer = format_state_rules_for_user(learned_state_rules)
            conversation.add_assistant(answer)
            return AgentRunResult(answer=answer, messages=conversation.messages, tool_trace=[], iterations=0)

        return None

    def _discover_known_learning_targets(self, machine_id: str) -> list[str]:
        known_targets: list[str] = []
        seen: set[str] = set()

        tags_result = self.tool_executor.execute("list_memory_tags", {"machine_id": machine_id})
        if tags_result.ok and isinstance(tags_result.output, list):
            for item in tags_result.output:
                if not isinstance(item, dict):
                    continue
                for key in ("name", "tag_name", "tag", "alias"):
                    raw = item.get(key)
                    if isinstance(raw, str):
                        candidate = raw.strip()
                        if candidate and candidate.lower() not in seen:
                            seen.add(candidate.lower())
                            known_targets.append(candidate)

        memory_result = self.tool_executor.execute("read_memory", {"machine_id": machine_id})
        if memory_result.ok and isinstance(memory_result.output, dict):
            for key in memory_result.output.keys():
                if not isinstance(key, str):
                    continue
                candidate = key.strip()
                if candidate and candidate.lower() not in seen:
                    seen.add(candidate.lower())
                    known_targets.append(candidate)

        return known_targets

    def _fallback_answer_for_empty_content(self, tool_trace: list, user_prompt: str) -> str:
        if not tool_trace:
            low = user_prompt.lower()
            if self._looks_like_start_intent(low):
                return (
                    "Model returned no final text for start intent. "
                    "Try: 'Set Globals.bStartButton to true' and confirm the write."
                )
            if self._looks_like_stop_intent(low):
                return (
                    "Model returned no final text for stop intent. "
                    "Try: 'Set Globals.bStopButton to true' and confirm the write."
                )
            if self._looks_like_write_without_value(user_prompt):
                return (
                    "Write request is missing a target value. "
                    "Example: Set Globals.bStopButton to true."
                )
            return "No answer returned by the model."

        last = tool_trace[-1]
        if last.ok and last.tool_name == "read_memory" and isinstance(last.output, dict):
            if not last.output:
                return (
                    "No memory values were returned for this machine. "
                    "Configure memory tags in ads-mcp-server and try again."
                )
            return self._summarize_memory(last.output)

        if last.ok and last.tool_name == "list_memory_tags" and isinstance(last.output, list) and not last.output:
            return (
                "No curated memory tags are configured for this machine. "
                "Use ads-mcp-server setup/discovery commands, then add memory tags."
            )

        return (
            "No answer returned by the model after tool execution. "
            f"Last tool: {last.tool_name} (ok={last.ok})."
        )

    def _summarize_memory(self, memory: dict[str, Any]) -> str:
        parts: list[str] = []
        machine_state = memory.get("Globals.nMachineState")
        if machine_state is not None:
            parts.append(f"Globals.nMachineState={machine_state}")
        for key in ("Globals.bRun", "Globals.bFault", "Globals.bStop"):
            if key in memory:
                parts.append(f"{key}={memory[key]}")
        for key in ("Globals.nGood", "Globals.nReject"):
            if key in memory:
                parts.append(f"{key}={memory[key]}")
        if not parts:
            return (
                "Model returned no final text. "
                "Tool read_memory succeeded and returned values."
            )
        return (
            "Model returned no final text. "
            "Tool summary: " + ", ".join(parts) + "."
        )

    def _append_learned_state_interpretation(
        self,
        *,
        answer: str,
        prompt: str,
        tool_trace: list,
        learned_state_rules: list[StateRule],
    ) -> str:
        if not learned_state_rules:
            return answer
        if not self._looks_like_state_summary_prompt(prompt):
            return answer
        memory = self._latest_read_memory_output(tool_trace)
        if memory is None:
            return answer
        interpretation = interpret_state_from_memory(memory, learned_state_rules)
        if not interpretation:
            return answer
        suffix = f"Learned-state interpretation: {interpretation}."
        if suffix.lower() in answer.lower():
            return answer
        if answer.endswith("."):
            return f"{answer} {suffix}"
        return f"{answer}. {suffix}"

    def _latest_read_memory_output(self, tool_trace: list) -> dict[str, Any] | None:
        for item in reversed(tool_trace):
            if item.ok and item.tool_name == "read_memory" and isinstance(item.output, dict):
                return item.output
        return None

    def _attempt_direct_machine_command(
        self,
        *,
        machine_id: str,
        prompt: str,
        conversation: Conversation,
        tool_trace: list,
        iteration: int,
    ) -> AgentRunResult | None:
        direct = self._detect_direct_machine_command(prompt)
        if direct is None:
            return None
        verb, tag_query, value = direct
        request_call_id = "intent-request"
        request_args = {"machine_id": machine_id, "tag_query": tag_query, "value": value}
        conversation.add_assistant(
            content=None,
            tool_calls=[
                {
                    "id": request_call_id,
                    "type": "function",
                    "function": {
                        "name": "request_tag_write",
                        "arguments": json.dumps(request_args),
                    },
                }
            ],
        )
        request_result = self.tool_executor.execute("request_tag_write", request_args)
        tool_trace.append(request_result)
        conversation.add_tool_result(request_call_id, "request_tag_write", request_result.to_message_payload())
        if not request_result.ok:
            return AgentRunResult(
                answer=f"{verb.title()} command failed before confirmation: {request_result.error}",
                messages=conversation.messages,
                tool_trace=tool_trace,
                iterations=iteration,
            )

        pending_request = self._extract_pending_request(request_result.output, request_args)
        if pending_request is None:
            reason = None
            if isinstance(request_result.output, dict):
                reason = request_result.output.get("reason")
            detail = reason or "write request was not accepted as pending."
            return AgentRunResult(
                answer=f"{verb.title()} command was not accepted: {detail}",
                messages=conversation.messages,
                tool_trace=tool_trace,
                iterations=iteration,
            )

        confirmed = self.write_confirmer(pending_request) if self.write_confirmer is not None else False
        confirm_call_id = "intent-confirm"
        confirm_args = {
            "machine_id": machine_id,
            "request_id": pending_request["request_id"],
            "confirmed": bool(confirmed),
        }
        conversation.add_assistant(
            content=None,
            tool_calls=[
                {
                    "id": confirm_call_id,
                    "type": "function",
                    "function": {
                        "name": "confirm_tag_write",
                        "arguments": json.dumps(confirm_args),
                    },
                }
            ],
        )
        confirm_result = self.tool_executor.execute_internal("confirm_tag_write", confirm_args)
        tool_trace.append(confirm_result)
        conversation.add_tool_result(confirm_call_id, "confirm_tag_write", confirm_result.to_message_payload())
        if not confirm_result.ok:
            return AgentRunResult(
                answer=f"{verb.title()} command confirmation failed: {confirm_result.error}",
                messages=conversation.messages,
                tool_trace=tool_trace,
                iterations=iteration,
            )

        answer = self._format_direct_intent_answer(verb, confirm_result.output)
        return AgentRunResult(
            answer=answer,
            messages=conversation.messages,
            tool_trace=tool_trace,
            iterations=iteration,
        )

    def _format_direct_intent_answer(self, verb: str, output: Any) -> str:
        if not isinstance(output, dict):
            return f"{verb.title()} command completed with non-standard confirmation output."
        status = output.get("status")
        tag_name = output.get("tag_name")
        if status == "written":
            value = output.get("written_value")
            ts = output.get("timestamp_utc")
            return f"{verb.title()} command completed: wrote {tag_name}={value} at {ts}."
        if status == "cancelled":
            return f"{verb.title()} command was cancelled at confirmation prompt."
        if status == "rejected":
            return f"{verb.title()} command was rejected: {output.get('reason')}"
        if status == "expired":
            return f"{verb.title()} command expired before confirmation."
        return f"{verb.title()} command finished with status={status}."

    def _augment_prompt_with_intent_hints(self, prompt: str) -> str:
        p = prompt.strip()
        low = p.lower()
        hints: list[str] = []

        if self._looks_like_start_intent(low):
            hints.append("Intent hint: start command likely means request_tag_write with tag_query containing startbutton and value true.")
        if self._looks_like_stop_intent(low):
            hints.append("Intent hint: stop command likely means request_tag_write with tag_query containing stopbutton and value true.")
        if self._looks_like_write_without_value(p):
            hints.append("Intent hint: write target is present but no value is specified; ask user to provide true/false explicitly.")

        if not hints:
            return p
        return f"{p}\n\n[Runtime intent hints]\n- " + "\n- ".join(hints)

    def _augment_prompt_with_alias_hints(self, prompt: str, learned_aliases: list[TagAliasRule]) -> str:
        if not learned_aliases:
            return prompt.strip()
        text = prompt.strip()
        matched_hints: list[str] = []
        seen_targets: set[str] = set()
        for rule in sorted(learned_aliases, key=lambda item: len(item.alias_display), reverse=True):
            pattern = re.compile(rf"(?<!\w){re.escape(rule.alias_display)}(?!\w)", flags=re.IGNORECASE)
            if not pattern.search(text):
                continue
            target_key = rule.target_tag.lower()
            if target_key in seen_targets:
                continue
            seen_targets.add(target_key)
            matched_hints.append(f'"{rule.alias_display}" refers to "{rule.target_tag}".')
        if not matched_hints:
            return text
        return f"{text}\n\n[Learned alias hints]\n- " + "\n- ".join(matched_hints)

    def _looks_like_start_intent(self, low_prompt: str) -> bool:
        phrases = ("start machine", "start the machine", "turn on machine", "turn on the machine", "start machine1")
        return any(phrase in low_prompt for phrase in phrases)

    def _looks_like_stop_intent(self, low_prompt: str) -> bool:
        phrases = ("stop machine", "stop the machine", "turn off machine", "turn off the machine", "stop machine1")
        return any(phrase in low_prompt for phrase in phrases)

    def _detect_direct_machine_command(self, prompt: str) -> tuple[str, str, bool] | None:
        low = prompt.strip().lower()
        if re.match(r"^(start|turn on|turn on the)\s+(the\s+)?(machine|machine1)\b", low):
            return ("start", "startbutton", True)
        if re.match(r"^(stop|turn off|turn off the)\s+(the\s+)?(machine|machine1)\b", low):
            return ("stop", "stopbutton", True)
        return None

    def _looks_like_write_without_value(self, prompt: str) -> bool:
        low = prompt.lower().strip()
        if not (low.startswith("set ") or low.startswith("write ")):
            return False
        if re.search(r"\b(to\s+)?(true|false|on|off|0|1)\b", low):
            return False
        return True

    def _looks_like_state_summary_prompt(self, prompt: str) -> bool:
        low = prompt.lower()
        if "what is the machine state" in low:
            return True
        if "machine state" in low:
            return True
        if "summarize" in low and "memory" in low:
            return True
        if "running or faulted" in low:
            return True
        return False

    def _extract_pending_request(self, output: Any, arguments: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(output, dict):
            return None
        if output.get("status") != "pending":
            return None
        request_id = output.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            return None
        return {
            "request_id": request_id,
            "resolved_tag_name": output.get("resolved_tag_name"),
            "value": arguments.get("value"),
            "machine_id": arguments.get("machine_id"),
        }
