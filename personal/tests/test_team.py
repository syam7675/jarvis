"""Orchestration tests with an explicit fake SDK; these are NOT live inference."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from personal.team import (
    AgentUnavailable,
    choose_role,
    report_directory,
    research,
    run_agent,
)


def config():
    return SimpleNamespace(
        agent=SimpleNamespace(
            max_turns=1, default_system_prompt="original", context_from_memory=True
        ),
        engine=SimpleNamespace(default="ollama"),
        skills=SimpleNamespace(enabled=True),
    )


class FakeSDK:
    calls = []

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def ask_full(self, prompt, **kwargs):
        type(self).calls.append((self.init_kwargs, prompt, kwargs))
        return {
            "content": "Explicit test-double response",
            "usage": {"total_tokens": 1},
        }


def test_roles_are_selected_from_task():
    assert choose_role("research local models") == "researcher"
    assert choose_role("debug python bug") == "coder"
    assert choose_role("prepare phone call") == "call_assistant"
    assert choose_role("organize my project") == "planner"


def test_sdk_receives_role_config_and_only_role_tools():
    cfg = config()
    result = run_agent("researcher", "research models", sdk_factory=FakeSDK, config=cfg)
    init, prompt, kwargs = FakeSDK.calls[-1]
    assert result["role"] == "researcher"
    assert kwargs["tools"] == ["web_search", "http_request"]
    assert kwargs["agent"] == "orchestrator"
    assert kwargs["context"] is False
    assert not init["config"].skills.enabled
    assert init["config"].agent.max_turns == 12
    assert "Never invent sources" in prompt
    assert cfg.skills.enabled and cfg.agent.default_system_prompt == "original"


def test_coding_profile_has_no_shell_or_filesystem_tools():
    run_agent("coder", "write code", sdk_factory=FakeSDK, config=config())
    assert FakeSDK.calls[-1][2]["tools"] == []


def test_inference_failure_is_explicit_and_does_not_echo_secrets():
    class BrokenSDK(FakeSDK):
        def ask_full(self, *args, **kwargs):
            raise ConnectionError("secret-token-should-not-be-printed")

    with pytest.raises(AgentUnavailable) as caught:
        run_agent("planner", "a task", sdk_factory=BrokenSDK, config=config())
    assert "No completed result is claimed" in str(caught.value)
    assert "secret-token" not in str(caught.value)


def test_research_stages_pass_evidence_and_critique_and_write_report(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    calls = []

    def runner(role, task, **kwargs):
        calls.append((role, task))
        return {
            "content": {
                "researcher": "Evidence https://example.com/source",
                "critic": "Source is incomplete",
                "reporter": "Recommendation with caveat",
            }[role]
        }

    path = research("choose a solution", runner=runner)
    assert [role for role, _ in calls] == ["researcher", "critic", "reporter"]
    assert "https://example.com/source" in calls[1][1]
    assert "Source is incomplete" in calls[2][1]
    assert path.parent == tmp_path / "reports"
    assert "Recommendation with caveat" in path.read_text()
    assert "Source is incomplete" in path.read_text()


def test_failed_research_does_not_write_a_completed_report(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))

    def runner(*args, **kwargs):
        raise AgentUnavailable("No model")

    with pytest.raises(AgentUnavailable):
        research("question", runner=runner)
    assert not (tmp_path / "reports").exists()


def test_report_home_rejects_checkout(monkeypatch):
    monkeypatch.setenv(
        "OPENJARVIS_HOME", str(Path(__file__).resolve().parents[2] / "state")
    )
    with pytest.raises(ValueError, match="outside"):
        report_directory()
