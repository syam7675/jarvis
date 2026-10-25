"""Exercise the updater against local Git repositories without any pushes."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "update.sh"


def git(path, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=check,
        text=True,
        capture_output=True,
    )


def commit(path, filename, text):
    target = path / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    git(path, "add", filename)
    git(path, "commit", "-m", filename)


@pytest.fixture
def repositories(tmp_path):
    upstream = tmp_path / "upstream"
    subprocess.run(
        ["git", "init", "-b", "main", str(upstream)], check=True, capture_output=True
    )
    for key, value in (("user.name", "Test"), ("user.email", "test@example.test")):
        git(upstream, "config", key, value)
    commit(upstream, "app.txt", "original\n")
    local = tmp_path / "local"
    subprocess.run(
        ["git", "clone", str(upstream), str(local)], check=True, capture_output=True
    )
    for key, value in (("user.name", "Test"), ("user.email", "test@example.test")):
        git(local, "config", key, value)
    commit(local, "personal/ours.txt", "custom agents\n")
    for filename in ("jarvis-ci.yml", "jarvis-update.yml"):
        commit(local, f".github/workflows/{filename}", "our reviewed workflow\n")
    return upstream, local


def update(local, upstream, mode="--prepare"):
    env = dict(os.environ, JARVIS_UPSTREAM_REMOTE=str(upstream))
    return subprocess.run(
        ["bash", str(SCRIPT), mode],
        cwd=local,
        env=env,
        text=True,
        capture_output=True,
    )


def test_merge_retains_personal_work_and_removes_publisher_workflows(repositories):
    upstream, local = repositories
    commit(upstream, "new-feature.txt", "upstream feature\n")
    commit(upstream, ".github/workflows/pypi-publish.yml", "publish upstream\n")
    result = update(local, upstream)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        git(local, "branch", "--show-current").stdout.strip() == "automation/upstream"
    )
    assert (local / "new-feature.txt").exists()
    assert (local / "personal/ours.txt").read_text() == "custom agents\n"
    assert sorted(p.name for p in (local / ".github/workflows").iterdir()) == [
        "jarvis-ci.yml",
        "jarvis-update.yml",
    ]
    assert git(local, "status", "--porcelain").stdout == ""
    assert git(local, "rev-list", "--parents", "-n", "1", "HEAD").stdout.count(" ") == 2


def test_check_does_not_change_checkout(repositories):
    upstream, local = repositories
    before = git(local, "rev-parse", "HEAD").stdout
    commit(upstream, "new-feature.txt", "new\n")
    result = update(local, upstream, "--check")
    assert result.returncode == 0
    assert "update available" in result.stdout
    assert git(local, "rev-parse", "HEAD").stdout == before
    assert git(local, "branch", "--show-current").stdout.strip() == "main"


def test_conflict_restores_original_clean_checkout(repositories):
    upstream, local = repositories
    commit(local, "app.txt", "our incompatible change\n")
    before = git(local, "rev-parse", "HEAD").stdout
    commit(upstream, "app.txt", "their incompatible change\n")
    result = update(local, upstream)
    assert result.returncode != 0
    assert "merge conflicts" in result.stderr
    assert git(local, "branch", "--show-current").stdout.strip() == "main"
    assert git(local, "rev-parse", "HEAD").stdout == before
    assert git(local, "status", "--porcelain").stdout == ""
    assert (
        git(
            local, "show-ref", "--verify", "refs/heads/automation/upstream", check=False
        ).returncode
        != 0
    )


def test_dirty_checkout_not_modified(repositories):
    upstream, local = repositories
    (local / "app.txt").write_text("uncommitted work\n")
    result = update(local, upstream)
    assert result.returncode != 0
    assert "local changes" in result.stderr
    assert (local / "app.txt").read_text() == "uncommitted work\n"


def test_existing_update_branch_not_overwritten(repositories):
    upstream, local = repositories
    git(local, "branch", "automation/upstream")
    before = git(local, "rev-parse", "automation/upstream").stdout
    commit(upstream, "new-feature.txt", "new\n")
    result = update(local, upstream)
    assert result.returncode != 0
    assert "Refusing to overwrite" in result.stderr
    assert git(local, "rev-parse", "automation/upstream").stdout == before


def test_no_update_leaves_main_unchanged(repositories):
    upstream, local = repositories
    before = git(local, "rev-parse", "HEAD").stdout
    result = update(local, upstream)
    assert result.returncode == 0
    assert "Already up to date" in result.stdout
    assert git(local, "rev-parse", "HEAD").stdout == before


def test_upstream_modifies_workflow_deleted_by_personal_fork(repositories):
    upstream, local = repositories
    workflow = ".github/workflows/pypi-publish.yml"
    commit(upstream, workflow, "upstream original publisher\n")
    git(local, "fetch", "origin", "main")
    git(local, "merge", "--no-edit", "origin/main")
    git(local, "rm", workflow)
    git(local, "commit", "-m", "remove inherited publisher")
    commit(upstream, workflow, "upstream changed publisher\n")
    result = update(local, upstream)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (local / workflow).exists()
    assert (local / "personal/ours.txt").read_text() == "custom agents\n"
    for name in ("jarvis-ci.yml", "jarvis-update.yml"):
        assert (local / ".github/workflows" / name).read_text() == (
            "our reviewed workflow\n"
        )
    assert git(local, "status", "--porcelain").stdout == ""
