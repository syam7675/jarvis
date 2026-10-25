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
    for line in (root / "data" / f"{split}.jsonl").read_text().splitlines():
        row = json.loads(line)
        assert row["id"] not in seen
        seen.add(row["id"])
        assert [x["role"] for x in row["messages"]] == ["system", "user", "assistant"]
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
