"""Run purpose-specific agents and a research → critique → report workflow."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from personal.skills import find


@dataclass(frozen=True)
class Role:
    description: str
    prompt: str
    tools: tuple[str, ...] = ()


ROLES = {
    "planner": Role(
        "Turn a goal into a practical implementation plan",
        "Create a prioritized plan with concrete steps, dependencies, "
        "acceptance checks, and unresolved questions.",
    ),
    "researcher": Role(
        "Find sources and research a question",
        "Research the question using web_search and read primary sources "
        "with http_request. Record URLs and supporting evidence. "
        "Distinguish observations, claims, uncertainties, and missing "
        "evidence. Never invent sources.",
        ("web_search", "http_request"),
    ),
    "critic": Role(
        "Check evidence and challenge a proposed solution",
        "Review the supplied evidence. Identify unsupported claims, "
        "conflicting sources, gaps, and weaknesses. Do not claim to verify "
        "URLs you have not fetched. Recommend corrections.",
    ),
    "reporter": Role(
        "Write a cited report and recommend a solution",
        "Write a useful Markdown report: recommendation, evidence with "
        "inline source URLs, tradeoffs, uncertainty, and next actions. Use "
        "only supplied evidence. Preserve the critic's caveats. Never "
        "fabricate citations or claim live checks were performed.",
    ),
    "coder": Role(
        "Advise on implementation, debugging, and tests",
        "Propose concrete code, debugging steps, and meaningful tests. You "
        "are an advisory coding agent with no filesystem or shell tools; "
        "clearly distinguish proposed changes from changes actually made.",
    ),
    "call_assistant": Role(
        "Prepare call scripts and meeting follow-ups",
        "Prepare call briefs, questions, scripts, and follow-up drafts. "
        "You cannot dial, send messages, or claim a call occurred. The "
        "separate calls adapter handles explicit dialing requests when "
        "configured.",
    ),
}


class AgentUnavailable(RuntimeError):
    """A real inference or dependency prerequisite is unavailable."""


def choose_role(task: str) -> str:
    words = set(task.casefold().replace("-", " ").split())
    if words & {"call", "calls", "phone", "meeting", "dial"}:
        return "call_assistant"
    if words & {"code", "coding", "debug", "bug", "implement", "python", "test"}:
        return "coder"
    if words & {"research", "compare", "sources", "investigate", "study"}:
        return "researcher"
    if words & {"report", "summarize", "summary"}:
        return "reporter"
    if words & {"review", "critique", "verify", "audit"}:
        return "critic"
    return "planner"


def run_agent(
    role: str,
    task: str,
    *,
    sdk_factory: Callable[..., Any] | None = None,
    config: Any = None,
    engine: str | None = None,
    model: str | None = None,
) -> dict:
    """Invoke the actual SDK unless an explicit test double was supplied."""
    spec = ROLES[role]
    try:
        if sdk_factory is None:
            from openjarvis import Jarvis
            from openjarvis.core.config import load_config

            sdk_factory = Jarvis
            if config is None:
                config = load_config()
        if config is None:
            raise ValueError("A configuration is required with a custom SDK factory")
        cfg = copy.deepcopy(config)
        cfg.agent.max_turns = 12
        cfg.agent.default_system_prompt = spec.prompt
        cfg.agent.context_from_memory = False
        # A role cannot acquire tools from configured community skills.
        cfg.skills.enabled = False
        selected = find(task)[:2]
        guidance = "\n\n".join(f"Skill {s.name}:\n{s.instructions}" for s in selected)
        prompt = f"{spec.prompt}\n\n{guidance}\n\nTask:\n{task}"
        with sdk_factory(
            config=cfg,
            engine_key=engine or os.getenv("JARVIS_ENGINE") or cfg.engine.default,
            model=model or os.getenv("JARVIS_MODEL") or None,
        ) as client:
            result = client.ask_full(
                prompt,
                agent="orchestrator",
                tools=list(spec.tools),
                temperature=0.3,
                max_tokens=4096,
                context=False,
            )
        content = result.get("content", "")
        if not content or not content.strip():
            raise AgentUnavailable(f"{role} returned no answer")
        return {
            "role": role,
            "content": content,
            "usage": result.get("usage", {}),
            "tool_results": result.get("tool_results", []),
        }
    except AgentUnavailable:
        raise
    except Exception as exc:
        # Exception strings can include request headers or tokens; omit them.
        raise AgentUnavailable(
            f"{role} could not complete inference ({type(exc).__name__}). "
            "Check the configured engine/model with jarvis doctor. For local "
            "inference,"
            "start Ollama and pull the selected model; for cloud inference, configure "
            "the provider credential securely. No completed result is claimed."
        ) from exc


def report_directory() -> Path:
    root = Path(os.getenv("OPENJARVIS_HOME", "~/.openjarvis")).expanduser().resolve()
    checkout = Path(__file__).resolve().parents[1]
    if root == checkout or checkout in root.parents:
        raise ValueError("OPENJARVIS_HOME must be outside the repository")
    return root / "reports"


def research(
    task: str, *, runner: Callable[..., dict] = run_agent, **kwargs: Any
) -> Path:
    findings = runner("researcher", task, **kwargs)
    critique = runner(
        "critic", f"Question: {task}\n\nEvidence:\n{findings['content']}", **kwargs
    )
    report = runner(
        "reporter",
        f"Question: {task}\n\nEvidence:\n{findings['content']}\n\n"
        f"Critique:\n{critique['content']}",
        **kwargs,
    )
    directory = report_directory()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"research-{stamp}-{uuid4().hex[:8]}.md"
    # Keep provenance in the report without claiming unperformed verification.
    path.write_text(
        f"# Research report\n\nQuestion: {task}\n\nGenerated: {stamp} (UTC)\n\n"
        f"{report['content']}\n\n---\n\n## Reviewer notes\n\n{critique['content']}\n",
        encoding="utf-8",
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="show available agent profiles")
    for name in ("run", "research"):
        sub = commands.add_parser(name)
        sub.add_argument("task")
        sub.add_argument("--engine")
        sub.add_argument("--model")
        if name == "run":
            sub.add_argument("--agent", choices=sorted(ROLES))
    args = parser.parse_args(argv)
    if args.command == "list":
        print(
            json.dumps(
                {
                    name: {"description": role.description, "tools": role.tools}
                    for name, role in ROLES.items()
                },
                indent=2,
            )
        )
        return 0
    try:
        if args.command == "research":
            print(research(args.task, engine=args.engine, model=args.model))
        else:
            print(
                run_agent(
                    args.agent or choose_role(args.task),
                    args.task,
                    engine=args.engine,
                    model=args.model,
                )["content"]
            )
        return 0
    except (AgentUnavailable, ValueError, OSError) as exc:
        print(f"Jarvis: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
