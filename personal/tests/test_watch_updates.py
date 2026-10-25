"""Mock Git/process checks; no remote writes or running services."""

import subprocess
from unittest.mock import Mock

import pytest
from personal import watch_updates as updates


def git_responder(*, dirty=False, diverged=False, same=False, branch="main"):
    def run(_root, *args):
        value, code = "", 0
        if args[0] == "symbolic-ref":
            value = branch
        elif args[0] == "status":
            value = "?? precious-local-file" if dirty else ""
        elif args[0] == "rev-parse":
            value = "old" if args[1] == "HEAD" or same else "new"
        elif args[0] == "merge-base":
            code = 1 if diverged else 0
        return subprocess.CompletedProcess(["git", *args], code, value, "")

    return run


@pytest.mark.parametrize(
    "state", [{"dirty": True}, {"diverged": True}, {"same": True}, {"branch": "work"}]
)
def test_skip_preserves_files_and_does_not_stop_services(monkeypatch, state):
    git = Mock(side_effect=git_responder(**state))
    monkeypatch.setattr(updates, "_git", git)
    setup = Mock()
    monkeypatch.setattr(updates.subprocess, "run", setup)
    stop, start = Mock(), Mock()
    assert not updates.refresh(stop=stop, start=start)
    stop.assert_not_called()
    start.assert_not_called()
    setup.assert_not_called()
    assert not any(call.args[1] == "merge" for call in git.call_args_list)


def test_clean_fast_forward_stops_installs_restarts_in_order(monkeypatch):
    events = []
    responder = git_responder()

    def git(root, *args):
        if args[0] == "merge":
            events.append("merge")
            assert args == ("merge", "--ff-only", "new")
        return responder(root, *args)

    monkeypatch.setattr(updates, "_git", git)

    def setup(command, **kwargs):
        assert command == ["bash", "personal/setup.sh"]
        assert kwargs["cwd"] == updates.ROOT
        events.append("setup")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(updates.subprocess, "run", setup)
    assert updates.refresh(
        stop=lambda: events.append("stop"), start=lambda: events.append("start")
    )
    assert events == ["stop", "merge", "setup", "start"]


def test_failed_install_does_not_restart_or_reset(monkeypatch):
    git = Mock(side_effect=git_responder())
    monkeypatch.setattr(updates, "_git", git)
    monkeypatch.setattr(
        updates.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 3))
    )
    start = Mock()
    with pytest.raises(updates.UpdateFailure, match="services remain stopped"):
        updates.refresh(start=start)
    start.assert_not_called()
    assert not any("reset" in call.args for call in git.call_args_list)


def test_child_exit_is_a_visible_failure():
    services = updates.Services(updates.ROOT, False)
    services.children = [Mock(poll=Mock(return_value=7))]
    with pytest.raises(updates.UpdateFailure, match="status 7"):
        services.check()


def test_git_errors_do_not_echo_stderr_or_remote_credentials(monkeypatch):
    monkeypatch.setattr(
        updates,
        "_git",
        Mock(return_value=subprocess.CompletedProcess([], 128, "", "secret-token")),
    )
    with pytest.raises(updates.UpdateFailure) as caught:
        updates.refresh()
    assert "secret-token" not in str(caught.value)
