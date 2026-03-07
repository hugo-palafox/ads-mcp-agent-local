from __future__ import annotations

from agent.models import AgentRunResult, ToolExecutionResult
from cli import main as cli_main
from llm.schemas import ModelResponse


class _FakeOrchestrator:
    def run(self, *, machine_id: str, prompt: str):
        raise RuntimeError("Model request timed out")


def test_chat_runtime_error_returns_clean_exit(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_main, "build_orchestrator", lambda settings, write_confirmer=None: _FakeOrchestrator())
    exit_code = cli_main.main(["chat", "--machine", "Machine1", "--prompt", "What is the machine state?"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "ERROR: Model request timed out" in captured.err


class _FakeLLMClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    def complete(self, messages, tools):
        return ModelResponse(content="Direct model reply.", tool_calls=[], raw={})


class _FakeFailingLLMClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    def complete(self, messages, tools):
        raise RuntimeError("Model request timed out")


def test_model_chat_returns_plain_model_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_main, "LLMClient", _FakeLLMClient)
    exit_code = cli_main.main(["model-chat", "--prompt", "Hello"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "Direct model reply."
    assert captured.err == ""


def test_model_chat_runtime_error_returns_clean_exit(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_main, "LLMClient", _FakeFailingLLMClient)
    exit_code = cli_main.main(["model-chat", "--prompt", "Hello"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "ERROR: Model request timed out" in captured.err


def test_model_chat_show_timing_prints_elapsed_seconds(monkeypatch, capsys) -> None:
    class _FakeTime:
        values = iter([10.0, 11.2345])

        @staticmethod
        def perf_counter():
            return next(_FakeTime.values)

    monkeypatch.setattr(cli_main, "LLMClient", _FakeLLMClient)
    monkeypatch.setattr(cli_main, "time", _FakeTime)
    exit_code = cli_main.main(["model-chat", "--prompt", "Hello", "--show-timing"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Direct model reply." in captured.out
    assert "Response time: 1.235s" in captured.out
    assert captured.err == ""


class _FakeGoodOrchestrator:
    def run(self, *, machine_id: str, prompt: str):
        return AgentRunResult(answer="Machine is running.", messages=[], tool_trace=[], iterations=1)


class _FakeTraceOrchestrator:
    def run(self, *, machine_id: str, prompt: str):
        return AgentRunResult(
            answer="ok",
            messages=[],
            tool_trace=[
                ToolExecutionResult(
                    tool_name="read_memory",
                    arguments={"machine_id": machine_id},
                    ok=True,
                    output={"Globals.bRun": False, "Globals.nMachineState": 3},
                )
            ],
            iterations=1,
        )


def test_chat_show_timing_prints_elapsed_seconds(monkeypatch, capsys) -> None:
    class _FakeTime:
        values = iter([1.0, 2.5])

        @staticmethod
        def perf_counter():
            return next(_FakeTime.values)

    monkeypatch.setattr(cli_main, "build_orchestrator", lambda settings, write_confirmer=None: _FakeGoodOrchestrator())
    monkeypatch.setattr(cli_main, "time", _FakeTime)
    exit_code = cli_main.main(["chat", "--machine", "Machine1", "--prompt", "status", "--show-timing"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Machine is running." in captured.out
    assert "Response time: 1.500s" in captured.out
    assert captured.err == ""


def test_chat_show_tool_trace_pretty_prints_human_readable_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_main, "build_orchestrator", lambda settings, write_confirmer=None: _FakeTraceOrchestrator())
    exit_code = cli_main.main(
        [
            "chat",
            "--machine",
            "Machine1",
            "--prompt",
            "status",
            "--show-tool-trace",
            "--tool-trace-format",
            "pretty",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Tool Trace:" in captured.out
    assert "read_memory [OK]" in captured.out
    assert "Globals.nMachineState=3" in captured.out
