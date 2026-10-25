"""Local lexical retrieval. This is not semantic multilingual search."""

import re
import sqlite3
from pathlib import Path


def search(query, *, path=None, limit=5):
    if not isinstance(query, str) or len(query) > 4000:
        raise ValueError("Query must be a string of at most 4000 characters")
    if not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError("Limit must be 1 to 10")
    terms = re.findall(r"\w+", query, flags=re.UNICODE)[:32]
    if not terms:
        return []
    # Quote tokens, not arbitrary FTS operators from the caller.
    expression = " OR ".join('"' + word + '"' for word in terms)
    p = (
        Path(path)
        if path
        else Path(__file__).resolve().parents[1] / "knowledge/knowledge.sqlite3"
    )
    db = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = db.execute(
            "SELECT id,title,text,source FROM cards "
            "WHERE cards MATCH ? ORDER BY rank LIMIT ?",
            (expression, limit),
        ).fetchall()
        return [dict(zip(("id", "title", "text", "source"), row)) for row in rows]
    finally:
        db.close()
