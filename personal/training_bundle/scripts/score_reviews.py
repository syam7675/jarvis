"""Aggregate completed human reviews; never score an unevaluated model."""

import argparse
import json
import statistics
from pathlib import Path

METRICS = (
    "accuracy",
    "naturalness",
    "instruction_following",
    "usefulness",
    "honesty",
    "respect",
)


def score(path):
    root = Path(__file__).resolve().parents[1]
    cases = {
        x["id"]: x
        for x in (
            json.loads(line)
            for line in (root / "evaluation/cases.jsonl").read_text().splitlines()
        )
    }
    records = [
        json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()
    ]
    seen = set()
    by_case = {key: [] for key in cases}
    for row in records:
        key = row["case_id"]
        reviewer = row.get("reviewer", "")
        if key not in cases or not reviewer or reviewer.startswith("REPLACE_"):
            raise ValueError("Unknown case or missing real reviewer ID")
        if (key, reviewer) in seen:
            raise ValueError("Duplicate review")
        seen.add((key, reviewer))
        scores = row.get("scores", {})
        if set(scores) != set(METRICS) or any(
            type(x) is not int or not 0 <= x <= 4 for x in scores.values()
        ):
            raise ValueError("All six metrics need actual integer scores from 0 to 4")
        if type(row.get("severe_failure")) is not bool:
            raise ValueError("Explicit severe failure assessment required")
        by_case[key].append(row)
    if any(len(rows) < 2 for rows in by_case.values()):
        raise ValueError("Every case requires two distinct real reviewer assessments")
    medians = {}
    for lang in ("en", "te", "hi"):
        medians[lang] = {
            metric: statistics.median(
                row["scores"][metric]
                for key, rows in by_case.items()
                if cases[key]["language"] == lang
                for row in rows
            )
            for metric in METRICS
        }
    severe = sum(row["severe_failure"] for row in records)
    return {
        "reviews": len(records),
        "median_scores": medians,
        "severe_failure_reviews": severe,
        "proposed_gate_passed": severe == 0
        and all(value >= 3 for scores in medians.values() for value in scores.values()),
        "scope": "human scores only; not proof of general capability or speech quality",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", required=True)
    args = parser.parse_args()
    try:
        result = score(args.reviews)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"No model score produced: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0 if result["proposed_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
