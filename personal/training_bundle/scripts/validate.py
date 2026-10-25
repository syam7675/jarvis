"""Validate authored examples and exercise real memory isolation; no model needed."""

import json
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from jarvis_profile.memory import Memory  # noqa: E402

seen = set()
groups = []
counts = {}
for split in ("train", "validation", "test"):
    intents = set()
    langs = set()
    n = 0
    paths = [root / "data" / f"{split}.jsonl"]
    if split == "train":
        paths.append(root / "data" / "advanced_train.jsonl")
    for line in [line for path in paths for line in path.read_text().splitlines()]:
        row = json.loads(line)
        assert row["id"] not in seen
        seen.add(row["id"])
        roles = [x["role"] for x in row["messages"]]
        assert roles[0] == "system" and roles[-1] == "assistant"
        assert roles[1:] == ["user", "assistant"] * ((len(roles) - 1) // 2)
        assert all(x["content"].strip() for x in row["messages"])
        assert row["review_status"] == "requires_native_speaker_review"
        langs.add(row["language"])
        intents.add(row["intent"])
        n += 1
    assert langs == {"en", "te", "hi"}
    assert not any(intents & previous for previous in groups)
    groups.append(intents)
    counts[split] = n
with tempfile.TemporaryDirectory() as d:
    m = Memory(str(Path(d) / "memory.db"))
    try:
        m.put("a", "language", "te")
    except ValueError:
        pass
    else:
        raise AssertionError("Consent was not enforced")
    m.put("a", "language", "te", consent=True)
    assert m.inspect("b") == []
    assert json.loads(m.export("a"))[0]["value"] == "te"
    m.put("a", "language", "hi", consent=True)
    assert m.inspect("a")[0]["value"] == "hi"
    m.forget("b")
    assert len(m.inspect("a")) == 1
    m.forget("a", "language")
    assert m.inspect("a") == []
    m.close()
print(
    json.dumps(
        {
            "dataset_counts": counts,
            "intent_split_isolation": "passed",
            "memory_consent_isolation_export_correction_deletion": "passed",
        }
    )
)

from jarvis_profile.knowledge import search  # noqa: E402

assert search("retry timeout")[0]["source"].startswith("original authored")
assert search('" * --') == []
assert len(search('" OR * --')) <= 5
assert len(search("memory", limit=2)) <= 2
for name in ("preferences", "tool_traces"):
    for line in (root / "data" / f"{name}.jsonl").read_text().splitlines():
        record = json.loads(line)
        assert record["provenance"].startswith("original_")
        if name == "preferences":
            assert record["chosen"] != record["rejected"]
        else:
            messages = record["messages"]
            assert messages[2]["tool_calls"][0]["id"] == messages[3]["tool_call_id"]
            assert messages[-1]["role"] == "assistant"
print("Knowledge retrieval, bounded search and supplementary datasets: passed")

training_questions = set()
for name in ("train", "advanced_train", "validation", "test"):
    for line in (root / "data" / f"{name}.jsonl").read_text().splitlines():
        for message in json.loads(line)["messages"]:
            if message["role"] == "user":
                training_questions.add(message["content"].strip().casefold())
eval_cases = [
    json.loads(line)
    for line in (root / "evaluation/cases.jsonl").read_text().splitlines()
]
assert len({case["id"] for case in eval_cases}) == 18
assert all(
    case["prompt"].strip().casefold() not in training_questions for case in eval_cases
)
assert {
    lang: sum(c["language"] == lang for c in eval_cases) for lang in ("en", "te", "hi")
} == {"en": 6, "te": 6, "hi": 6}
# Test the scoring mechanics using explicitly synthetic fixtures, not model responses.
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "review_scoring", root / "scripts/score_reviews.py"
)
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)
try:
    scoring.score(root / "evaluation/reviews_template.jsonl")
except ValueError:
    pass
else:
    raise AssertionError("Uncompleted model reviews must not produce scores")
with tempfile.TemporaryDirectory() as d:
    path = Path(d) / "synthetic_mechanics_test.jsonl"
    records = [
        {
            "case_id": c["id"],
            "reviewer": reviewer,
            "scores": {metric: 4 for metric in scoring.METRICS},
            "severe_failure": False,
        }
        for c in eval_cases
        for reviewer in ("test_fixture_a", "test_fixture_b")
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in records))
    assert scoring.score(path)["proposed_gate_passed"]
    records[0]["severe_failure"] = True
    path.write_text("".join(json.dumps(row) + "\n" for row in records))
    assert not scoring.score(path)["proposed_gate_passed"]
print(
    "Independent evaluation schema and scoring mechanics: passed (no model evaluated)"
)
