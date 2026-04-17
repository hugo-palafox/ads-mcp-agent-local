from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class StateRule:
    tag: str
    value: bool | int | str
    meaning: str


@dataclass(slots=True, frozen=True)
class ResponseBehaviorRule:
    instruction: str


@dataclass(slots=True, frozen=True)
class TagAliasRule:
    alias_display: str
    alias_normalized: str
    target_tag: str


@dataclass(slots=True, frozen=True)
class LearningRejection:
    reason_code: str
    message: str


class TeachingStore:
    def __init__(self, root_dir: str) -> None:
        self.root_dir = Path(root_dir)

    def list_state_rules(self, machine_id: str) -> list[StateRule]:
        payload = self._load_payload(machine_id)
        return _parse_state_rules(payload.get("state_rules"))

    def list_response_rules(self, machine_id: str) -> list[ResponseBehaviorRule]:
        payload = self._load_payload(machine_id)
        return _parse_response_rules(payload.get("response_rules"))

    def list_tag_alias_rules(self, machine_id: str) -> list[TagAliasRule]:
        payload = self._load_payload(machine_id)
        return _parse_tag_alias_rules(payload.get("tag_alias_rules"))

    def upsert_state_rules(self, machine_id: str, new_rules: list[StateRule]) -> tuple[int, int, list[StateRule]]:
        existing = self.list_state_rules(machine_id)
        merged = list(existing)
        index_by_key = {_rule_key(rule): idx for idx, rule in enumerate(merged)}
        added = 0
        updated = 0

        for rule in new_rules:
            key = _rule_key(rule)
            if key not in index_by_key:
                index_by_key[key] = len(merged)
                merged.append(rule)
                added += 1
                continue
            idx = index_by_key[key]
            if merged[idx].meaning != rule.meaning:
                merged[idx] = rule
                updated += 1

        payload = self._load_payload(machine_id)
        payload["state_rules"] = _serialize_state_rules(merged)
        self._save_payload(machine_id, payload)
        return added, updated, merged

    def upsert_response_rules(
        self,
        machine_id: str,
        new_rules: list[ResponseBehaviorRule],
    ) -> tuple[int, int, list[ResponseBehaviorRule]]:
        existing = self.list_response_rules(machine_id)
        merged = list(existing)
        index_by_key = {_response_rule_key(rule): idx for idx, rule in enumerate(merged)}
        added = 0
        updated = 0

        for rule in new_rules:
            key = _response_rule_key(rule)
            if key not in index_by_key:
                index_by_key[key] = len(merged)
                merged.append(rule)
                added += 1
                continue
            idx = index_by_key[key]
            if merged[idx].instruction != rule.instruction:
                merged[idx] = rule
                updated += 1

        payload = self._load_payload(machine_id)
        payload["response_rules"] = _serialize_response_rules(merged)
        self._save_payload(machine_id, payload)
        return added, updated, merged

    def upsert_tag_alias_rules(
        self,
        machine_id: str,
        new_rules: list[TagAliasRule],
    ) -> tuple[int, int, list[TagAliasRule]]:
        existing = self.list_tag_alias_rules(machine_id)
        merged = list(existing)
        index_by_key = {_tag_alias_rule_key(rule): idx for idx, rule in enumerate(merged)}
        added = 0
        updated = 0

        for rule in new_rules:
            key = _tag_alias_rule_key(rule)
            if key not in index_by_key:
                index_by_key[key] = len(merged)
                merged.append(rule)
                added += 1
                continue
            idx = index_by_key[key]
            if merged[idx].target_tag != rule.target_tag or merged[idx].alias_display != rule.alias_display:
                merged[idx] = rule
                updated += 1

        payload = self._load_payload(machine_id)
        payload["tag_alias_rules"] = _serialize_tag_alias_rules(merged)
        self._save_payload(machine_id, payload)
        return added, updated, merged

    def record_learning_event(
        self,
        machine_id: str,
        *,
        category: str,
        status: str,
        source_prompt: str,
        detail: str,
        reason_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = self._load_payload(machine_id)
        raw_registry = payload.get("learning_registry")
        registry = raw_registry if isinstance(raw_registry, list) else []
        excerpt = _source_prompt_excerpt(source_prompt)
        registry.append(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "category": category,
                "status": status,
                "source_prompt": source_prompt.strip(),
                "source_prompt_excerpt": excerpt,
                "detail": detail,
                "reason_code": reason_code or "none",
                "metadata": _sanitize_metadata(metadata),
            }
        )
        payload["learning_registry"] = registry[-200:]
        self._save_payload(machine_id, payload)

    def get_registry_payload(self, machine_id: str) -> dict[str, Any]:
        payload = self._load_payload(machine_id)
        registry = _parse_learning_registry(payload.get("learning_registry"))
        return {
            "machine_id": machine_id,
            "state_rules": _serialize_state_rules(_parse_state_rules(payload.get("state_rules"))),
            "response_rules": _serialize_response_rules(_parse_response_rules(payload.get("response_rules"))),
            "tag_alias_rules": _serialize_tag_alias_rules(_parse_tag_alias_rules(payload.get("tag_alias_rules"))),
            "learning_registry": registry,
            "registry_metadata": _build_registry_metadata(registry),
        }

    def format_registry_json(self, machine_id: str) -> str:
        return json.dumps(self.get_registry_payload(machine_id), indent=2)

    def reset_machine_learning(self, machine_id: str) -> bool:
        path = self._machine_path(machine_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    def _load_payload(self, machine_id: str) -> dict[str, Any]:
        payload = _base_payload(machine_id)
        path = self._machine_path(machine_id)
        if not path.exists():
            return payload
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return payload
        if not isinstance(raw, dict):
            return payload
        for key in ("state_rules", "response_rules", "tag_alias_rules", "learning_registry"):
            value = raw.get(key)
            if isinstance(value, list):
                payload[key] = value
        return payload

    def _save_payload(self, machine_id: str, payload: dict[str, Any]) -> None:
        path = self._machine_path(machine_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        canonical = {
            "machine_id": machine_id,
            "state_rules": _serialize_state_rules(_parse_state_rules(payload.get("state_rules"))),
            "response_rules": _serialize_response_rules(_parse_response_rules(payload.get("response_rules"))),
            "tag_alias_rules": _serialize_tag_alias_rules(_parse_tag_alias_rules(payload.get("tag_alias_rules"))),
            "learning_registry": _parse_learning_registry(payload.get("learning_registry")),
            "registry_metadata": _build_registry_metadata(_parse_learning_registry(payload.get("learning_registry"))),
        }
        path.write_text(json.dumps(canonical, indent=2), encoding="utf-8")

    def _machine_path(self, machine_id: str) -> Path:
        safe_machine_id = re.sub(r"[^A-Za-z0-9_.-]", "_", machine_id.strip()) or "machine"
        return self.root_dir / f"{safe_machine_id}.json"


def looks_like_learning_intent(prompt: str) -> bool:
    return bool(re.search(r"\b(teach|remember|learn)\b", prompt, flags=re.IGNORECASE))


def parse_teaching_prompt(prompt: str) -> list[StateRule]:
    if not looks_like_learning_intent(prompt):
        return []
    body = _extract_teaching_body(prompt)
    clauses = [chunk.strip(" .\t\r\n") for chunk in re.split(r"(?:,|;|\band\b)", body, flags=re.IGNORECASE)]
    rules: list[StateRule] = []
    last_tag: str | None = None

    for clause in clauses:
        if not clause:
            continue
        parsed = _parse_rule_clause(clause, last_tag)
        if parsed is None:
            continue
        rule, explicit_tag = parsed
        rules.append(rule)
        if explicit_tag:
            last_tag = rule.tag

    return _dedupe_rules_preserve_order(rules)


def parse_response_behavior_prompt(prompt: str) -> list[ResponseBehaviorRule]:
    if not looks_like_learning_intent(prompt):
        return []
    body = _extract_teaching_body(prompt)
    instruction = _extract_response_behavior_instruction(body)
    if instruction is None:
        return []
    normalized = _normalize_response_instruction(instruction)
    if not normalized:
        return []
    return [ResponseBehaviorRule(instruction=normalized)]


def parse_tag_alias_prompt(prompt: str) -> list[TagAliasRule]:
    if not (_looks_like_alias_teaching_intent(prompt) or looks_like_learning_intent(prompt)):
        return []
    body = _extract_teaching_body(prompt)
    clauses = [chunk.strip(" .\t\r\n") for chunk in re.split(r"(?:,|;|\band\b)", body, flags=re.IGNORECASE)]
    rules: list[TagAliasRule] = []
    for clause in clauses:
        parsed = _parse_alias_clause(clause)
        if parsed is None:
            continue
        alias_display, target_tag = parsed
        alias_normalized = normalize_alias(alias_display)
        if not alias_normalized:
            continue
        rules.append(TagAliasRule(alias_display=alias_display, alias_normalized=alias_normalized, target_tag=target_tag))
    return _dedupe_tag_alias_rules_preserve_order(rules)


def normalize_alias(alias_text: str) -> str:
    return " ".join(alias_text.strip().split()).lower()


def evaluate_tag_alias_rule(rule: TagAliasRule) -> LearningRejection | None:
    alias_display = " ".join(rule.alias_display.strip().split())
    if not alias_display:
        return LearningRejection(
            reason_code="empty_tag_alias",
            message="Alias text cannot be empty.",
        )
    if len(alias_display) > 80:
        return LearningRejection(
            reason_code="tag_alias_too_long",
            message="Alias text is too long; keep it short and human-readable.",
        )
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9 _-]*[A-Za-z0-9]$", alias_display):
        return LearningRejection(
            reason_code="tag_alias_invalid_format",
            message="Alias must use letters, numbers, spaces, hyphen, or underscore.",
        )
    target = rule.target_tag.strip()
    if not re.match(r"^[A-Za-z_][\w\.]*$", target):
        return LearningRejection(
            reason_code="tag_alias_invalid_target_format",
            message="Alias target must look like a tag or memory field name.",
        )
    return None


def resolve_alias_target(target_query: str, known_targets: list[str]) -> tuple[str | None, list[str]]:
    clean_query = target_query.strip()
    if not clean_query:
        return None, []
    low_query = clean_query.lower()
    exact = [item for item in known_targets if isinstance(item, str) and item.lower() == low_query]
    if len(exact) == 1:
        return exact[0], []
    if len(exact) > 1:
        return None, exact
    suffix = [
        item
        for item in known_targets
        if isinstance(item, str) and item.lower().endswith(f".{low_query}")
    ]
    if len(suffix) == 1:
        return suffix[0], []
    if len(suffix) > 1:
        return None, suffix
    return None, []


def guardrail_response_behavior_rule(rule: ResponseBehaviorRule) -> str | None:
    rejection = evaluate_response_behavior_rule(rule)
    if rejection is None:
        return None
    return rejection.message


def evaluate_response_behavior_rule(rule: ResponseBehaviorRule) -> LearningRejection | None:
    text = rule.instruction.strip()
    if not text:
        return LearningRejection(
            reason_code="empty_response_behavior_instruction",
            message="Response behavior instruction cannot be empty.",
        )
    if len(text) > 220:
        return LearningRejection(
            reason_code="response_behavior_instruction_too_long",
            message="Response behavior instruction is too long; keep it concise and formatting-focused.",
        )
    low = text.lower()
    blocked_tokens = (
        "ignore previous",
        "ignore prior",
        "system prompt",
        "developer prompt",
        "bypass",
        "disable safety",
        "override safety",
        "confirm_tag_write",
        "request_tag_write",
        "write tag",
        "auto-confirm",
        "password",
        "api key",
        "shell command",
        "execute command",
        "delete files",
        "network call",
        "http://",
        "https://",
    )
    if any(token in low for token in blocked_tokens):
        return LearningRejection(
            reason_code="unsafe_response_behavior_content",
            message="Response behavior instruction includes unsafe control/security content.",
        )
    return None


def learning_guardrail_message() -> str:
    return (
        "I can only learn three safe categories: "
        "tag behavior mappings (tag/value/meaning), response behavior preferences, and tag aliases."
    )


def learning_rules_for_user() -> str:
    return (
        "Learning rules: "
        "1) Allowed categories: tag behavior (for example 'nMachineState == 2 means faulted'), "
        "response behavior (for example 'be concise and use bullet points'), and "
        "tag aliases (for example 'Learn alias Good Parts for Globals.nGood'). "
        "2) Disallowed: control/safety bypass instructions, write-confirmation bypass, credentials/secrets, "
        "and non-learning requests. "
        "3) Use 'Show learning registry json' to inspect accepted/rejected learning events with reason_code."
    )


def format_state_rules_for_prompt(rules: list[StateRule]) -> str:
    if not rules:
        return ""
    lines = ["User-taught state mappings for this machine:"]
    for rule in rules:
        lines.append(f"- {rule.tag} == {_value_to_text(rule.value)} means {rule.meaning}")
    lines.append("Use these mappings when interpreting machine status from read_memory outputs.")
    return "\n".join(lines)


def format_state_rules_for_user(rules: list[StateRule]) -> str:
    if not rules:
        return "No learned state mappings are saved for this machine yet."
    parts = [f"{rule.tag} == {_value_to_text(rule.value)} => {rule.meaning}" for rule in rules]
    return "Current learned state mappings: " + "; ".join(parts) + "."


def format_response_rules_for_prompt(rules: list[ResponseBehaviorRule]) -> str:
    if not rules:
        return ""
    lines = ["User-taught response behavior preferences for this machine:"]
    for rule in rules:
        lines.append(f"- {rule.instruction}")
    lines.append("Apply these preferences only to response style/format, never to tool safety rules.")
    return "\n".join(lines)


def format_response_rules_for_user(rules: list[ResponseBehaviorRule]) -> str:
    if not rules:
        return "No learned response behavior preferences are saved for this machine yet."
    parts = [rule.instruction for rule in rules]
    return "Current learned response behavior preferences: " + "; ".join(parts) + "."


def format_tag_alias_rules_for_prompt(rules: list[TagAliasRule]) -> str:
    if not rules:
        return ""
    lines = ["User-taught tag aliases for this machine:"]
    for rule in rules:
        lines.append(f'- "{rule.alias_display}" maps to {rule.target_tag}')
    lines.append("If a user mentions an alias, treat it as the mapped tag or memory field.")
    return "\n".join(lines)


def format_tag_alias_rules_for_user(rules: list[TagAliasRule]) -> str:
    if not rules:
        return "No learned tag aliases are saved for this machine yet."
    parts = [f'"{rule.alias_display}" => {rule.target_tag}' for rule in rules]
    return "Current learned tag aliases: " + "; ".join(parts) + "."


def interpret_state_from_memory(memory: dict[str, Any], rules: list[StateRule]) -> str | None:
    matches: list[tuple[str, Any, str]] = []
    for rule in rules:
        memory_key = _resolve_memory_key(memory, rule.tag)
        if memory_key is None:
            continue
        memory_value = memory.get(memory_key)
        if _values_match(memory_value, rule.value):
            matches.append((memory_key, memory_value, rule.meaning))

    if not matches:
        return None

    meanings: list[str] = []
    for _, _, meaning in matches:
        normalized = meaning.strip().lower()
        if normalized not in meanings:
            meanings.append(normalized)

    evidence = ", ".join(f"{key}={value}" for key, value, _ in matches)
    if len(meanings) == 1:
        return f"{matches[0][2]} (based on {evidence})"

    details = ", ".join(f"{key}={value}->{meaning}" for key, value, meaning in matches)
    return f"conflicting learned states ({details})"


def looks_like_state_rule_query(prompt: str) -> bool:
    low = prompt.lower()
    explicit = (
        "show learned state mappings",
        "list learned state mappings",
        "show state mappings",
        "show tag behavior mappings",
        "show learned tag behavior",
    )
    if any(phrase in low for phrase in explicit):
        return True
    if not _looks_like_query_request(low):
        return False
    if not any(token in low for token in ("learned", "saved", "taught")):
        return False
    if not any(token in low for token in ("state mapping", "state mappings", "state rule", "state rules", "tag behavior")):
        return False
    return True


def looks_like_response_behavior_query(prompt: str) -> bool:
    low = prompt.lower()
    explicit = (
        "show learned response behavior",
        "list learned response behavior",
        "show response behavior preferences",
    )
    if any(phrase in low for phrase in explicit):
        return True
    if not _looks_like_query_request(low):
        return False
    if not any(token in low for token in ("response", "reply", "answer", "style", "tone", "format")):
        return False
    if not any(token in low for token in ("learned", "saved", "taught")):
        return False
    return True


def looks_like_learning_registry_query(prompt: str) -> bool:
    low = prompt.lower()
    if "what have you learned" in low:
        return True
    if not any(token in low for token in ("registry", "json")):
        return False
    if not any(token in low for token in ("learn", "teach", "saved", "taught", "learning")):
        return False
    return any(token in low for token in ("show", "list", "export", "display", "what", "which"))


def looks_like_tag_alias_query(prompt: str) -> bool:
    low = prompt.lower()
    explicit = (
        "show learning aliases",
        "show learned aliases",
        "list learning aliases",
        "list learned aliases",
        "show tag aliases",
    )
    if any(phrase in low for phrase in explicit):
        return True
    if not _looks_like_query_request(low):
        return False
    if "alias" not in low and "aliases" not in low:
        return False
    return any(token in low for token in ("learning", "learned", "saved", "taught", "tag"))


def looks_like_learning_rules_query(prompt: str) -> bool:
    low = prompt.lower()
    explicit = (
        "show learning rules",
        "what are learning rules",
        "what can you learn",
        "learning guardrails",
        "show learning guardrails",
    )
    if any(phrase in low for phrase in explicit):
        return True
    if not any(token in low for token in ("learn", "learning")):
        return False
    if not _looks_like_query_request(low):
        return False
    return any(token in low for token in ("rule", "rules", "guardrail", "guardrails", "allowed", "disallowed"))


def _extract_teaching_body(prompt: str) -> str:
    text = prompt.strip()
    keyword = re.search(r"\b(teach|remember|learn)\b", text, flags=re.IGNORECASE)
    if keyword is None:
        return text
    body = text[keyword.end():].strip()
    that_match = re.search(r"\bthat\b", body, flags=re.IGNORECASE)
    if that_match is not None:
        body = body[that_match.end():].strip()
    return body


def _looks_like_alias_teaching_intent(prompt: str) -> bool:
    low = prompt.lower()
    if "alias" not in low:
        return False
    return any(token in low for token in ("learn", "teach", "remember", "add", "set", "define", "create", "map"))


def _parse_rule_clause(clause: str, last_tag: str | None) -> tuple[StateRule, bool] | None:
    full_match = re.match(
        r"^(?P<tag>[A-Za-z_][\w\.]*)\s*(?:(?:==|=)\s*)?(?P<value>true|false|-?\d+)\s*(?:(?:means|is|->|=>)\s*)?(?P<meaning>[A-Za-z][A-Za-z0-9 _-]*)$",
        clause,
        flags=re.IGNORECASE,
    )
    if full_match:
        tag = full_match.group("tag").strip()
        value = _parse_scalar_value(full_match.group("value"))
        meaning = _normalize_meaning(full_match.group("meaning"))
        return StateRule(tag=tag, value=value, meaning=meaning), True

    shorthand_match = re.match(
        r"^==?\s*(?P<value>true|false|-?\d+)\s*(?:(?:means|is|->|=>)\s*)?(?P<meaning>[A-Za-z][A-Za-z0-9 _-]*)$",
        clause,
        flags=re.IGNORECASE,
    )
    if shorthand_match and last_tag:
        value = _parse_scalar_value(shorthand_match.group("value"))
        meaning = _normalize_meaning(shorthand_match.group("meaning"))
        return StateRule(tag=last_tag, value=value, meaning=meaning), False
    return None


def _parse_alias_clause(clause: str) -> tuple[str, str] | None:
    text = " ".join(clause.strip().split())
    if not text:
        return None
    patterns = (
        r'^(?:tag\s+)?alias\s+(?P<alias>.+?)\s+(?:for|to|->|=>|maps to|is)\s+(?P<tag>[A-Za-z_][\w\.]*)$',
        r'^(?P<alias>.+?)\s+(?:alias\s+for|means|maps to|is alias for)\s+(?P<tag>[A-Za-z_][\w\.]*)$',
        r'^(?:call|name)\s+(?P<tag>[A-Za-z_][\w\.]*)\s+(?P<alias>.+?)$',
    )
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match is None:
            continue
        groups = match.groupdict()
        if "tag" in groups and groups.get("tag") and groups.get("alias"):
            alias = _strip_alias_quotes(groups["alias"])
            tag = groups["tag"].strip()
            if alias:
                return alias, tag
    return None


def _strip_alias_quotes(alias: str) -> str:
    cleaned = alias.strip()
    if len(cleaned) >= 2 and ((cleaned[0] == '"' and cleaned[-1] == '"') or (cleaned[0] == "'" and cleaned[-1] == "'")):
        cleaned = cleaned[1:-1].strip()
    return " ".join(cleaned.split())


def _parse_scalar_value(raw: str) -> bool | int:
    value = raw.strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    return int(value)


def _normalize_meaning(raw: str) -> str:
    return " ".join(raw.strip().split())


def _normalize_response_instruction(raw: str) -> str:
    text = " ".join(raw.strip().split())
    return text.rstrip(".")


def _extract_response_behavior_instruction(body: str) -> str | None:
    text = " ".join(body.strip().split())
    if not text:
        return None

    low = text.lower()
    # If the body clearly contains state-rule syntax, let state parsing own it.
    if re.search(r"[A-Za-z_][\w\.]*\s*(?:==|=)\s*(?:true|false|-?\d+)", text, flags=re.IGNORECASE):
        return None
    if re.search(r"\b(?:true|false|-?\d+)\s*(?:means|is|=>|->)\b", text, flags=re.IGNORECASE):
        return None

    normalized = text
    prefix_patterns = (
        r"^(?:that\s+)?(?:response behavior|response style|reply style|answer style)\s*[:\-]?\s*",
        r"^(?:that\s+)?(?:you|assistant)\s+should\s+",
        r"^(?:to\s+)?(?:respond|reply|answer)\s+(?:in|with|using)\s+",
    )
    for pattern in prefix_patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if match:
            normalized = normalized[match.end():].strip()
            break

    cue_tokens = ("response", "reply", "answer", "tone", "format", "concise", "brief", "step-by-step")
    starts_like_style = bool(re.match(r"^(be|keep|use|format|ask|include|explain)\b", normalized, flags=re.IGNORECASE))
    has_style_cue = any(token in low for token in cue_tokens) or starts_like_style
    if not has_style_cue:
        return None
    return normalized


def _dedupe_rules_preserve_order(rules: list[StateRule]) -> list[StateRule]:
    seen: set[tuple[str, str]] = set()
    deduped: list[StateRule] = []
    for rule in rules:
        key = _rule_key(rule)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped


def _rule_key(rule: StateRule) -> tuple[str, str]:
    return (rule.tag.lower(), _value_to_text(rule.value).lower())


def _response_rule_key(rule: ResponseBehaviorRule) -> str:
    return rule.instruction.strip().lower()


def _tag_alias_rule_key(rule: TagAliasRule) -> str:
    return normalize_alias(rule.alias_normalized)


def _dedupe_tag_alias_rules_preserve_order(rules: list[TagAliasRule]) -> list[TagAliasRule]:
    seen: set[str] = set()
    deduped: list[TagAliasRule] = []
    for rule in rules:
        key = _tag_alias_rule_key(rule)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped


def _value_to_text(value: bool | int | str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _resolve_memory_key(memory: dict[str, Any], rule_tag: str) -> str | None:
    if rule_tag in memory:
        return rule_tag
    low_rule_tag = rule_tag.lower()
    candidates = [
        key
        for key in memory.keys()
        if isinstance(key, str) and (key.lower() == low_rule_tag or key.lower().endswith(f".{low_rule_tag}"))
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _values_match(actual: Any, expected: bool | int | str) -> bool:
    if isinstance(expected, bool):
        return isinstance(actual, bool) and actual is expected
    if isinstance(expected, int):
        return isinstance(actual, int) and not isinstance(actual, bool) and actual == expected
    if isinstance(actual, str):
        return actual.strip().lower() == expected.strip().lower()
    return str(actual).strip().lower() == expected.strip().lower()


def _base_payload(machine_id: str) -> dict[str, Any]:
    return {
        "machine_id": machine_id,
        "state_rules": [],
        "response_rules": [],
        "tag_alias_rules": [],
        "learning_registry": [],
    }


def _parse_state_rules(raw_rules: Any) -> list[StateRule]:
    if not isinstance(raw_rules, list):
        return []
    parsed: list[StateRule] = []
    for item in raw_rules:
        if not isinstance(item, dict):
            continue
        tag = item.get("tag")
        value = item.get("value")
        meaning = item.get("meaning")
        if not isinstance(tag, str) or not tag.strip():
            continue
        if not isinstance(meaning, str) or not meaning.strip():
            continue
        if not isinstance(value, (bool, int, str)):
            continue
        parsed.append(StateRule(tag=tag.strip(), value=value, meaning=_normalize_meaning(meaning)))
    return parsed


def _serialize_state_rules(rules: list[StateRule]) -> list[dict[str, Any]]:
    return [{"tag": rule.tag, "value": rule.value, "meaning": rule.meaning} for rule in rules]


def _parse_response_rules(raw_rules: Any) -> list[ResponseBehaviorRule]:
    if not isinstance(raw_rules, list):
        return []
    parsed: list[ResponseBehaviorRule] = []
    for item in raw_rules:
        if isinstance(item, str):
            normalized = _normalize_response_instruction(item)
            if normalized:
                parsed.append(ResponseBehaviorRule(instruction=normalized))
            continue
        if not isinstance(item, dict):
            continue
        instruction = item.get("instruction")
        if not isinstance(instruction, str):
            continue
        normalized = _normalize_response_instruction(instruction)
        if normalized:
            parsed.append(ResponseBehaviorRule(instruction=normalized))
    deduped: list[ResponseBehaviorRule] = []
    seen: set[str] = set()
    for rule in parsed:
        key = _response_rule_key(rule)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped


def _serialize_response_rules(rules: list[ResponseBehaviorRule]) -> list[dict[str, Any]]:
    return [{"instruction": rule.instruction} for rule in rules]


def _parse_tag_alias_rules(raw_rules: Any) -> list[TagAliasRule]:
    if not isinstance(raw_rules, list):
        return []
    parsed: list[TagAliasRule] = []
    for item in raw_rules:
        if not isinstance(item, dict):
            continue
        alias_display = item.get("alias_display")
        alias_normalized = item.get("alias_normalized")
        target_tag = item.get("target_tag")
        if not isinstance(alias_display, str) or not alias_display.strip():
            continue
        if not isinstance(target_tag, str) or not target_tag.strip():
            continue
        normalized = normalize_alias(alias_normalized) if isinstance(alias_normalized, str) else normalize_alias(alias_display)
        if not normalized:
            continue
        parsed.append(
            TagAliasRule(
                alias_display=" ".join(alias_display.strip().split()),
                alias_normalized=normalized,
                target_tag=target_tag.strip(),
            )
        )
    return _dedupe_tag_alias_rules_preserve_order(parsed)


def _serialize_tag_alias_rules(rules: list[TagAliasRule]) -> list[dict[str, Any]]:
    return [
        {
            "alias_display": rule.alias_display,
            "alias_normalized": rule.alias_normalized,
            "target_tag": rule.target_tag,
        }
        for rule in rules
    ]


def _parse_learning_registry(raw_registry: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_registry, list):
        return []
    parsed: list[dict[str, Any]] = []
    for item in raw_registry:
        if not isinstance(item, dict):
            continue
        timestamp_utc = item.get("timestamp_utc")
        category = item.get("category")
        status = item.get("status")
        source_prompt = item.get("source_prompt")
        detail = item.get("detail")
        if not isinstance(timestamp_utc, str):
            continue
        if not isinstance(category, str):
            continue
        if not isinstance(status, str):
            continue
        if not isinstance(source_prompt, str):
            continue
        if not isinstance(detail, str):
            continue
        entry: dict[str, Any] = {
            "timestamp_utc": timestamp_utc,
            "category": category,
            "status": status,
            "source_prompt": source_prompt,
            "source_prompt_excerpt": _source_prompt_excerpt(source_prompt),
            "detail": detail,
            "reason_code": "none",
            "metadata": {},
        }
        if isinstance(item.get("source_prompt_excerpt"), str):
            entry["source_prompt_excerpt"] = _source_prompt_excerpt(item["source_prompt_excerpt"])
        if isinstance(item.get("reason_code"), str):
            entry["reason_code"] = item["reason_code"].strip() or "none"
        if isinstance(item.get("metadata"), dict):
            entry["metadata"] = _sanitize_metadata(item["metadata"])
        parsed.append(entry)
    return parsed


def _looks_like_query_request(low: str) -> bool:
    return any(token in low for token in ("show", "list", "what", "which", "display", "export"))


def _source_prompt_excerpt(source_prompt: str, max_len: int = 180) -> str:
    clean = " ".join(source_prompt.strip().split())
    if len(clean) <= max_len:
        return clean
    return f"{clean[:max_len - 3]}..."


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[key] = value
            continue
        if isinstance(value, list):
            clean[key] = [item for item in value if isinstance(item, (str, int, float, bool)) or item is None]
            continue
        if isinstance(value, dict):
            nested = {k: v for k, v in value.items() if isinstance(k, str) and isinstance(v, (str, int, float, bool))}
            clean[key] = nested
    return clean


def _build_registry_metadata(registry: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for event in registry:
        status = str(event.get("status", "unknown"))
        category = str(event.get("category", "unknown"))
        by_status[status] = by_status.get(status, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1
    return {
        "schema_version": "2",
        "event_count": len(registry),
        "counts_by_status": by_status,
        "counts_by_category": by_category,
    }
