from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


Predicate = Callable[[str, str, int], tuple[bool, str]]


@dataclass(frozen=True)
class SmokeCase:
    name: str
    args: list[str]
    expected: Predicate
    description: str


@dataclass
class SmokeResult:
    case: SmokeCase
    command: str
    exit_code: int
    elapsed_seconds: float
    stdout: str
    stderr: str
    passed: bool
    detail: str


def contains_stdout(*needles: str) -> Predicate:
    def _check(stdout: str, stderr: str, exit_code: int) -> tuple[bool, str]:
        if exit_code != 0:
            return False, f"Expected exit code 0, got {exit_code}. stderr={stderr.strip()!r}"
        missing = [needle for needle in needles if needle not in stdout]
        if missing:
            return False, f"Missing stdout fragments: {missing!r}"
        return True, "Expected stdout fragments found."

    return _check


def contains_stdout_or_stderr(*needles: str) -> Predicate:
    def _check(stdout: str, stderr: str, exit_code: int) -> tuple[bool, str]:
        if exit_code != 0:
            return False, f"Expected exit code 0, got {exit_code}. stderr={stderr.strip()!r}"
        combined = stdout + "\n" + stderr
        missing = [needle for needle in needles if needle not in combined]
        if missing:
            return False, f"Missing output fragments: {missing!r}"
        return True, "Expected output fragments found."

    return _check


def build_cases(machine: str, model: str) -> list[SmokeCase]:
    return [
        SmokeCase(
            name="diagnose_model",
            args=["diagnose-model", "--model", model, "--no-think"],
            expected=contains_stdout('"content": "OK"'),
            description="Validate model connectivity with thinking disabled.",
        ),
        SmokeCase(
            name="model_chat",
            args=["model-chat", "--model", model, "--no-think", "--prompt", "Reply with one short sentence."],
            expected=contains_stdout("Response time:"),
            description="Validate direct chat completion and timing output.",
        ),
        SmokeCase(
            name="diagnose_mcp",
            args=["diagnose-mcp", "--machine", machine],
            expected=contains_stdout('"machine":', '"list_groups":', '"list_memory_tags":'),
            description="Validate MCP bridge connectivity.",
        ),
        SmokeCase(
            name="chat_state_trace",
            args=[
                "chat",
                "--machine",
                machine,
                "--model",
                model,
                "--no-think",
                "--prompt",
                "What is the machine state?",
                "--show-tool-trace",
            ],
            expected=contains_stdout('"tool_name": "read_memory"', "Response time:"),
            description="Validate broad state query with tool trace.",
        ),
        SmokeCase(
            name="chat_memory_pretty_trace",
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
            expected=contains_stdout("Tool Trace:", "read_memory [OK]"),
            description="Validate pretty tool trace formatting for memory reads.",
        ),
        SmokeCase(
            name="learning_rules",
            args=["chat", "--machine", machine, "--prompt", "Show learning rules"],
            expected=contains_stdout("Learning rules:", "tag aliases"),
            description="Validate direct learning rules shortcut.",
        ),
        SmokeCase(
            name="teach_response_behavior",
            args=["chat", "--machine", machine, "--prompt", "Teach response behavior: be concise and use bullet points."],
            expected=contains_stdout("Saved 1 response behavior rule(s)"),
            description="Validate response-behavior teaching flow.",
        ),
        SmokeCase(
            name="teach_alias",
            args=["chat", "--machine", machine, "--prompt", "Learn alias Good Parts for Globals.nGood."],
            expected=contains_stdout("Saved 1 tag alias rule(s)", "Good Parts"),
            description="Validate alias teaching flow.",
        ),
        SmokeCase(
            name="show_learning_aliases",
            args=["chat", "--machine", machine, "--prompt", "Show learning aliases"],
            expected=contains_stdout("Current learned tag aliases:", "Good Parts"),
            description="Validate learned alias display.",
        ),
        SmokeCase(
            name="show_learning_registry",
            args=["chat", "--machine", machine, "--prompt", "Show learning registry json"],
            expected=contains_stdout('"learning_registry"', '"tag_alias_rules"'),
            description="Validate learning registry output.",
        ),
        SmokeCase(
            name="write_auto_cancel",
            args=[
                "chat",
                "--machine",
                machine,
                "--model",
                model,
                "--no-think",
                "--prompt",
                "Set Globals.bStartButton to true",
                "--show-tool-trace",
            ],
            expected=contains_stdout_or_stderr(
                "Write confirmation requires interactive input. Auto-cancelling",
                '"tool_name": "request_tag_write"',
                '"tool_name": "confirm_tag_write"',
            ),
            description="Validate guarded write flow with safe non-interactive auto-cancel.",
        ),
        SmokeCase(
            name="chat_specific_tag_trace",
            args=[
                "chat",
                "--machine",
                machine,
                "--model",
                model,
                "--no-think",
                "--prompt",
                "Read Globals.bRun",
                "--show-tool-trace",
            ],
            expected=contains_stdout(
                '"tool_name": "read_tag"',
                "Globals.bRun",
            ),
            description="Validate specific tag read flow and tool selection.",
        ),
    ]


def shell_quote(parts: list[str]) -> str:
    rendered: list[str] = []
    for part in parts:
        if not part or any(ch.isspace() or ch in {'"', "'"} for ch in part):
            rendered.append(json.dumps(part))
        else:
            rendered.append(part)
    return " ".join(rendered)


def run_case(
    case: SmokeCase,
    *,
    base_command: list[str],
    env: dict[str, str],
    cwd: Path,
    timeout_seconds: float,
) -> SmokeResult:
    command_parts = [*base_command, *case.args]
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
    passed, detail = case.expected(completed.stdout, completed.stderr, completed.returncode)
    return SmokeResult(
        case=case,
        command=shell_quote(command_parts),
        exit_code=completed.returncode,
        elapsed_seconds=elapsed,
        stdout=completed.stdout,
        stderr=completed.stderr,
        passed=passed,
        detail=detail,
    )


def render_report(
    *,
    results: list[SmokeResult],
    started_at: str,
    machine: str,
    model: str,
    teaching_store_dir: Path,
    base_command: list[str],
) -> str:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    failed = total - passed
    lines = [
        "ads-mcp-agent-local Feature Smoke Test Report",
        "=" * 44,
        f"Started: {started_at}",
        f"Machine: {machine}",
        f"Model: {model}",
        f"Base command: {shell_quote(base_command)}",
        f"Teaching store dir: {teaching_store_dir}",
        f"Summary: passed={passed} failed={failed} total={total}",
        "",
    ]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"[{index:02d}] {result.case.name} - {'PASS' if result.passed else 'FAIL'}",
                f"Description: {result.case.description}",
                f"Command: {result.command}",
                f"Exit code: {result.exit_code}",
                f"Elapsed: {result.elapsed_seconds:.3f}s",
                f"Expectation: {result.detail}",
                "--- stdout ---",
                result.stdout.rstrip() or "<empty>",
                "--- stderr ---",
                result.stderr.rstrip() or "<empty>",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run documented end-user smoke tests and write a transcript report.")
    parser.add_argument("--machine", default="Machine1", help="Machine id to target. Default: Machine1")
    parser.add_argument("--model", default="gemma4:e4b", help="Model name to use for model-backed tests.")
    parser.add_argument(
        "--report-dir",
        default="artifacts/smoke-tests",
        help="Directory where transcript reports are written. Default: artifacts/smoke-tests",
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
    cases = build_cases(args.machine, args.model)
    results: list[SmokeResult] = []
    try:
        for case in cases:
            result = run_case(
                case,
                base_command=base_command,
                env=env,
                cwd=repo_root,
                timeout_seconds=args.timeout_seconds,
            )
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            print(f"[{status}] {case.name} ({result.elapsed_seconds:.2f}s)")
        report_text = render_report(
            results=results,
            started_at=started_at,
            machine=args.machine,
            model=args.model,
            teaching_store_dir=teaching_store_dir,
            base_command=base_command,
        )
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        report_path = report_dir / f"feature-smoke-report-{timestamp}.log"
        report_path.write_text(report_text, encoding="utf-8")
        passed = sum(1 for result in results if result.passed)
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
