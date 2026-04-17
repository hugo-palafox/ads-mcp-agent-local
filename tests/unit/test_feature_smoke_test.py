from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "feature_smoke_test.py"
    spec = importlib.util.spec_from_file_location("feature_smoke_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_arg_parser_defaults_to_smoke_mode() -> None:
    module = _load_module()
    parser = module.build_arg_parser()
    args = parser.parse_args([])
    assert args.mode == "smoke"


def test_build_demo_steps_resets_learning_first_and_only_once() -> None:
    module = _load_module()
    steps = module.build_demo_steps("Machine1", "gemma4:e4b")
    assert steps[0].id == "learning_reset_start"
    assert sum(1 for step in steps if step.kind == "learning_reset") == 1


def test_demo_steps_include_unknown_term_before_and_after_learning() -> None:
    module = _load_module()
    steps = module.build_demo_steps("Machine1", "gemma4:e4b")
    ids = [step.id for step in steps]
    assert "unknown_term_before_learning" in ids
    assert "unknown_term_after_learning" in ids
    assert ids.index("unknown_term_before_learning") < ids.index("teach_alias") < ids.index("unknown_term_after_learning")


def test_demo_learning_improvement_evaluator_accepts_learned_alias_response() -> None:
    module = _load_module()
    step = module.build_demo_steps("Machine1", "gemma4:e4b")[-3]
    classification, observation, success = module._demo_learning_improvement(
        step,
        'The "Throughput Bucket" alias refers to the tag `Globals.nGood`.\n',
        "",
        0,
    )
    assert classification == "success"
    assert success is True
    assert "learned alias" in observation.lower()


def test_render_demo_replay_contains_operator_notes_and_commands() -> None:
    module = _load_module()
    step = module.StepDefinition(
        id="demo",
        name="Demo Step",
        category="demo",
        kind="chat",
        args=["chat", "--machine", "Machine1", "--prompt", "Hello"],
        prompt="Hello",
        intent=None,
        description="Demo description",
        why_it_matters="Demo why",
        replay_note="Look for the answer.",
        expected_classification="success",
        hard_failure=False,
        evaluator=None,
    )
    result = module.StepResult(
        step=step,
        command='python -m cli.main chat --machine Machine1 --prompt "Hello"',
        exit_code=0,
        elapsed_seconds=1.23,
        stdout="Hi",
        stderr="",
        classification="success",
        observation="Worked",
        success=True,
    )
    replay = module.render_demo_replay([result])
    assert "What to look for" in replay
    assert "python -m cli.main chat" in replay


def test_render_demo_transcript_contains_top_level_sections() -> None:
    module = _load_module()
    step = module.StepDefinition(
        id="demo",
        name="Demo Step",
        category="demo",
        kind="chat",
        args=["chat", "--machine", "Machine1", "--prompt", "Hello"],
        prompt="Hello",
        intent=None,
        description="Demo description",
        why_it_matters="Demo why",
        replay_note="Look for the answer.",
        expected_classification="success",
        hard_failure=False,
        evaluator=None,
    )
    result = module.StepResult(
        step=step,
        command='python -m cli.main chat --machine Machine1 --prompt "Hello"',
        exit_code=0,
        elapsed_seconds=1.23,
        stdout="Hi",
        stderr="",
        classification="success",
        observation="Worked",
        success=True,
    )
    transcript = module.render_demo_transcript(
        results=[result],
        started_at="2026-04-17 00:00:00 MST",
        machine="Machine1",
        model="gemma4:e4b",
        teaching_store_dir=Path("/tmp/demo"),
        base_command=["python", "-m", "cli.main"],
    )
    assert "## Demo Summary" in transcript
    assert "## Capability Map" in transcript
    assert "## Live Operator Notes" in transcript
    assert "## Suggested Talking Points" in transcript
