from __future__ import annotations

from agent.prompts import build_system_prompt
from agent.teaching import ResponseBehaviorRule, StateRule, TagAliasRule


def test_include_read_only_instructions() -> None:
    prompt = build_system_prompt("M1")
    assert "safety-first" in prompt


def test_include_no_invented_tags_rule() -> None:
    prompt = build_system_prompt("M1")
    assert "Do not invent tag names" in prompt


def test_include_prefer_memory_first_rule() -> None:
    prompt = build_system_prompt("M1")
    assert "Prefer read_memory before broad raw reads" in prompt


def test_include_write_confirmation_rule() -> None:
    prompt = build_system_prompt("M1")
    assert "request_tag_write first" in prompt


def test_include_ambiguity_context_checklist_rule() -> None:
    prompt = build_system_prompt("M1")
    assert "If the user request is ambiguous" in prompt
    assert "What is the MCP PLC Agent in your setup" in prompt


def test_include_user_taught_state_mappings_when_present() -> None:
    prompt = build_system_prompt("M1", [StateRule(tag="bRun", value=True, meaning="running")])
    assert "User-taught state mappings for this machine" in prompt
    assert "bRun == true means running" in prompt


def test_include_user_taught_response_behavior_rules_when_present() -> None:
    prompt = build_system_prompt(
        "M1",
        [StateRule(tag="bRun", value=True, meaning="running")],
        [ResponseBehaviorRule(instruction="be concise and use bullet points")],
    )
    assert "User-taught response behavior preferences for this machine" in prompt
    assert "be concise and use bullet points" in prompt


def test_include_user_taught_tag_alias_rules_when_present() -> None:
    prompt = build_system_prompt(
        "M1",
        [StateRule(tag="bRun", value=True, meaning="running")],
        [ResponseBehaviorRule(instruction="be concise and use bullet points")],
        [TagAliasRule(alias_display="Good Parts", alias_normalized="good parts", target_tag="Globals.nGood")],
    )
    assert "User-taught tag aliases for this machine" in prompt
    assert '"Good Parts" maps to Globals.nGood' in prompt
