"""Build a portable lexical reference index from authored cards."""

import json
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "knowledge" / "knowledge.sqlite3"
db = sqlite3.connect(path)
with db:
    db.execute("DROP TABLE IF EXISTS cards")
    db.execute(
        "CREATE VIRTUAL TABLE cards USING "
        "fts5(id UNINDEXED, title, text, tags, source UNINDEXED)"
    )
    for line in (root / "knowledge" / "cards.jsonl").read_text().splitlines():
        c = json.loads(line)
        db.execute(
            "INSERT INTO cards VALUES(?,?,?,?,?)",
            tuple(c[k] for k in ("id", "title", "text", "tags", "source")),
        )
db.close()
print(path)
