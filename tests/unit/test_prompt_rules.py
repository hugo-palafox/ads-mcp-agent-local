from __future__ import annotations

from agent.prompts import build_system_prompt


def test_include_read_only_instructions() -> None:
    prompt = build_system_prompt("M1")
    assert "read-only" in prompt


def test_include_no_invented_tags_rule() -> None:
    prompt = build_system_prompt("M1")
    assert "Do not invent tag names" in prompt


def test_include_prefer_memory_first_rule() -> None:
    prompt = build_system_prompt("M1")
    assert "Prefer read_memory before broad raw reads" in prompt
