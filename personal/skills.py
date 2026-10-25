"""Find maintained local skills without installing or executing unknown code."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    instructions: str
    path: Path


def catalog(root: Path = SKILLS_DIR) -> list[Skill]:
    result = []
    for path in sorted(root.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            raise ValueError(f"Missing skill metadata: {path}")
        _, metadata, body = text.split("---", 2)
        fields = dict(
            line.split(":", 1) for line in metadata.splitlines() if ":" in line
        )
        result.append(
            Skill(
                fields["name"].strip(),
                fields["description"].strip(),
                body.strip(),
                path,
            )
        )
    return result


def find(query: str, *, root: Path = SKILLS_DIR) -> list[Skill]:
    """Rank genuine keyword matches; an empty query lists the catalog."""
    tokens = set(re.findall(r"[\w]+", query.casefold()))
    scored = []
    for skill in catalog(root):
        words = set(
            re.findall(r"[\w]+", f"{skill.name} {skill.description}".casefold())
        )
        score = len(tokens & words)
        if score or not tokens:
            scored.append((score, skill))
    return [
        skill for _, skill in sorted(scored, key=lambda row: (-row[0], row[1].name))
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "query", nargs="*", help="keywords; omit to list all local skills"
    )
    args = parser.parse_args(argv)
    matches = find(" ".join(args.query))
    for skill in matches:
        print(f"{skill.name}: {skill.description}\n  {skill.path}")
    if not matches:
        print(
            "No matching local skills. Discover community skills with: jarvis "
            "skill search QUERY"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
