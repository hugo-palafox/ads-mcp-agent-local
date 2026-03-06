from __future__ import annotations

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
