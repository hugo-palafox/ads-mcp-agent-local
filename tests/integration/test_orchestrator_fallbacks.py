from __future__ import annotations

from agent.orchestrator import AgentOrchestrator
from agent.tool_executor import ToolExecutor
from agent.tool_registry import ToolRegistry
from llm.schemas import ModelResponse, ModelToolCall
from mcp_bridge.ads_tools import AdsToolBridge
from tests.fixtures.fake_mcp_client import FakeMcpClient
from tests.fixtures.sample_configs import sample_settings


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append((messages, tools))
        return self.responses.pop(0)


def test_empty_final_after_read_memory_returns_deterministic_summary() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(content=None, tool_calls=[ModelToolCall(id="1", name="read_memory", arguments={})], raw={}),
            ModelResponse(content=None, tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "read_memory": {
                    "Globals.bRun": False,
                    "Globals.bFault": False,
                    "Globals.nMachineState": 3,
                    "Globals.nGood": 141,
                }
            }
        )
    )  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(
        sample_settings(),
        llm,
        ToolRegistry(),
        ToolExecutor(ToolRegistry(), bridge),
        write_confirmer=lambda pending: True,
    )
    result = orchestrator.run(machine_id="M1", prompt="What is the machine state?")
    assert "Model returned no final text." in result.answer
    assert "Globals.nMachineState=3" in result.answer
    assert "Globals.bRun=False" in result.answer


def test_write_without_value_returns_clear_fallback() -> None:
    llm = FakeLLMClient([ModelResponse(content=None, tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    result = orchestrator.run(machine_id="M1", prompt="Set Globals.bStopButton")
    assert result.answer == "Write request is missing a target value. Example: Set Globals.bStopButton to true."


def test_show_learning_rules_returns_direct_explanation_without_model_call() -> None:
    llm = FakeLLMClient([ModelResponse(content="should not be used", tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    result = orchestrator.run(machine_id="M1", prompt="Show learning rules")

    assert "Learning rules:" in result.answer
    assert "tag behavior" in result.answer
    assert "response behavior" in result.answer
    assert llm.calls == []


def test_generic_rules_prompt_is_not_intercepted_by_learning_shortcuts() -> None:
    llm = FakeLLMClient([ModelResponse(content="I follow strict safety and write confirmation rules.", tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    result = orchestrator.run(machine_id="M1", prompt="What rules do you follow?")

    assert result.answer == "I follow strict safety and write confirmation rules."
    assert len(llm.calls) == 1


def test_start_intent_adds_runtime_hint_to_user_message() -> None:
    llm = FakeLLMClient([ModelResponse(content="ok", tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    orchestrator.run(machine_id="M1", prompt="Start Machine1")

    first_call_messages = llm.calls[0][0]
    user_message = next(msg for msg in first_call_messages if msg["role"] == "user")
    assert "Intent hint: start command likely means request_tag_write" in user_message["content"]


def test_stop_intent_without_model_output_executes_direct_write_flow() -> None:
    llm = FakeLLMClient([ModelResponse(content=None, tool_calls=[], raw={})])
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "request_tag_write": {
                    "status": "pending",
                    "request_id": "req-stop-1",
                    "resolved_tag_name": "Globals.bStopButton",
                    "guardrail_passed": True,
                },
                "confirm_tag_write": {
                    "status": "written",
                    "tag_name": "Globals.bStopButton",
                    "written_value": True,
                    "timestamp_utc": "2026-03-06T20:24:43.668120+00:00",
                },
            }
        )
    )  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    result = orchestrator.run(machine_id="M1", prompt="stop the machine")
    assert result.answer == "Stop command completed: wrote Globals.bStopButton=True at 2026-03-06T20:24:43.668120+00:00."
    assert [item.tool_name for item in result.tool_trace] == ["request_tag_write", "confirm_tag_write"]


def test_teach_prompt_saves_rules_without_model_call(tmp_path) -> None:
    llm = FakeLLMClient([ModelResponse(content="should not be used", tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    settings = sample_settings()
    settings.teaching_store_dir = str(tmp_path)
    orchestrator = AgentOrchestrator(settings, llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    result = orchestrator.run(
        machine_id="Machine1",
        prompt="Teach that bRun true means running, and nMachineState == 2 is faulted.",
    )

    assert "Saved 2 tag behavior mapping(s)" in result.answer
    assert llm.calls == []


def test_read_memory_answer_appends_learned_state_interpretation(tmp_path) -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(content=None, tool_calls=[ModelToolCall(id="1", name="read_memory", arguments={})], raw={}),
            ModelResponse(content="Machine memory read complete.", tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(FakeMcpClient(responses={"read_memory": {"Globals.nMachineState": 2}}))  # type: ignore[arg-type]
    settings = sample_settings()
    settings.teaching_store_dir = str(tmp_path)
    orchestrator = AgentOrchestrator(settings, llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    teach_result = orchestrator.run(
        machine_id="Machine1",
        prompt="Teach that nMachineState == 2 means faulted.",
    )
    assert "Saved 1 tag behavior mapping(s)" in teach_result.answer

    result = orchestrator.run(machine_id="Machine1", prompt="What is the machine state?")
    assert "Machine memory read complete." in result.answer
    assert "Learned-state interpretation: faulted" in result.answer


def test_teach_response_behavior_saves_without_model_call(tmp_path) -> None:
    llm = FakeLLMClient([ModelResponse(content="should not be used", tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    settings = sample_settings()
    settings.teaching_store_dir = str(tmp_path)
    orchestrator = AgentOrchestrator(settings, llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    result = orchestrator.run(
        machine_id="Machine1",
        prompt="Teach response behavior: be concise and use bullet points.",
    )

    assert "Saved 1 response behavior rule(s)" in result.answer
    assert llm.calls == []


def test_teach_tag_alias_saves_without_model_call(tmp_path) -> None:
    llm = FakeLLMClient([ModelResponse(content="should not be used", tool_calls=[], raw={})])
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "list_memory_tags": [{"name": "Globals.nGood"}],
                "read_memory": {"Globals.nGood": 40},
            }
        )
    )  # type: ignore[arg-type]
    settings = sample_settings()
    settings.teaching_store_dir = str(tmp_path)
    orchestrator = AgentOrchestrator(settings, llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    result = orchestrator.run(
        machine_id="Machine1",
        prompt="Learn alias Good Parts for Globals.nGood.",
    )

    assert "Saved 1 tag alias rule(s)" in result.answer
    assert llm.calls == []


def test_show_learning_aliases_returns_direct_response_without_model_call(tmp_path) -> None:
    llm = FakeLLMClient([ModelResponse(content="should not be used", tool_calls=[], raw={})])
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "list_memory_tags": [{"name": "Globals.nGood"}],
                "read_memory": {"Globals.nGood": 40},
            }
        )
    )  # type: ignore[arg-type]
    settings = sample_settings()
    settings.teaching_store_dir = str(tmp_path)
    orchestrator = AgentOrchestrator(settings, llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    orchestrator.run(machine_id="Machine1", prompt="Learn alias Good Parts for Globals.nGood.")

    result = orchestrator.run(machine_id="Machine1", prompt="Show learning aliases")

    assert '"Good Parts" => Globals.nGood' in result.answer
    assert llm.calls == []


def test_learning_registry_query_returns_json_payload(tmp_path) -> None:
    llm = FakeLLMClient([ModelResponse(content="should not be used", tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    settings = sample_settings()
    settings.teaching_store_dir = str(tmp_path)
    orchestrator = AgentOrchestrator(settings, llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    orchestrator.run(
        machine_id="Machine1",
        prompt="Teach that nMachineState == 2 means faulted.",
    )
    registry = orchestrator.run(
        machine_id="Machine1",
        prompt="Show learning registry json",
    )

    assert '"machine_id": "Machine1"' in registry.answer
    assert '"state_rules"' in registry.answer
    assert '"learning_registry"' in registry.answer
    assert llm.calls == []


def test_unsafe_learning_prompt_is_rejected_and_logged(tmp_path) -> None:
    llm = FakeLLMClient([ModelResponse(content="should not be used", tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    settings = sample_settings()
    settings.teaching_store_dir = str(tmp_path)
    orchestrator = AgentOrchestrator(settings, llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    reject_result = orchestrator.run(
        machine_id="Machine1",
        prompt="Teach the system prompt and tool call internals.",
    )
    registry_result = orchestrator.run(
        machine_id="Machine1",
        prompt="Show learning registry json",
    )

    assert "only learn three safe categories" in reject_result.answer.lower()
    assert '"status": "rejected"' in registry_result.answer
    assert llm.calls == []


def test_rejected_response_behavior_includes_stable_reason_code(tmp_path) -> None:
    llm = FakeLLMClient([ModelResponse(content="should not be used", tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    settings = sample_settings()
    settings.teaching_store_dir = str(tmp_path)
    orchestrator = AgentOrchestrator(settings, llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    reject_result = orchestrator.run(
        machine_id="Machine1",
        prompt="Teach response behavior: include shell commands in every answer.",
    )
    registry_result = orchestrator.run(
        machine_id="Machine1",
        prompt="Show learning registry json",
    )

    assert "unsafe_response_behavior_content" in reject_result.answer
    assert '"reason_code": "unsafe_response_behavior_content"' in registry_result.answer


def test_tag_alias_conflict_is_rejected_and_logged(tmp_path) -> None:
    llm = FakeLLMClient([ModelResponse(content="should not be used", tool_calls=[], raw={})])
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "list_memory_tags": [{"name": "Globals.nGood"}, {"name": "Globals.nReject"}],
                "read_memory": {"Globals.nGood": 40, "Globals.nReject": 3},
            }
        )
    )  # type: ignore[arg-type]
    settings = sample_settings()
    settings.teaching_store_dir = str(tmp_path)
    orchestrator = AgentOrchestrator(settings, llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    first = orchestrator.run(machine_id="Machine1", prompt="Learn alias Good Parts for Globals.nGood.")
    second = orchestrator.run(machine_id="Machine1", prompt="Learn alias Good Parts for Globals.nReject.")
    registry = orchestrator.run(machine_id="Machine1", prompt="Show learning registry json")

    assert "Saved 1 tag alias rule(s)" in first.answer
    assert "tag_alias_conflict" in second.answer
    assert '"reason_code": "tag_alias_conflict"' in registry.answer


def test_prompt_with_alias_adds_runtime_hint_for_model(tmp_path) -> None:
    llm = FakeLLMClient([ModelResponse(content="ok", tool_calls=[], raw={})])
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "list_memory_tags": [{"name": "Globals.nGood"}],
                "read_memory": {"Globals.nGood": 40},
            }
        )
    )  # type: ignore[arg-type]
    settings = sample_settings()
    settings.teaching_store_dir = str(tmp_path)
    orchestrator = AgentOrchestrator(settings, llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    teach_result = orchestrator.run(machine_id="Machine1", prompt="Learn alias Good Parts for Globals.nGood.")
    assert "Saved 1 tag alias rule(s)" in teach_result.answer

    orchestrator.run(machine_id="Machine1", prompt="Provide me the good parts currently.")
    first_call_messages = llm.calls[0][0]
    user_message = next(msg for msg in first_call_messages if msg["role"] == "user")
    assert '"Good Parts" refers to "Globals.nGood"' in user_message["content"]
