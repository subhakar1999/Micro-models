"""Tenant-scoped lexical retrieval: no encoder or graph database is needed."""
import re
import sqlite3
from pathlib import Path


class Memory:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(tenant UNINDEXED, source UNINDEXED, text)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def ingest(self, tenant: str, source: str, text: str) -> int:
        chunks = [text[i:i + 1400] for i in range(0, len(text), 1200)]
        with self.connect() as db:
            db.execute("DELETE FROM chunks WHERE tenant=? AND source=?", (tenant, source))
            db.executemany("INSERT INTO chunks VALUES (?, ?, ?)", [(tenant, source, c) for c in chunks])
        return len(chunks)

    def search(self, tenant: str, query: str, budget: int = 1800) -> list[dict]:
        tokens = list(dict.fromkeys(re.findall(r"\w+", query.lower())))[:20]
        if not tokens:
            return []
        expression = " OR ".join('"' + token + '"' for token in tokens)
        with self.connect() as db:
            rows = db.execute("SELECT source,text FROM chunks WHERE chunks MATCH ? AND tenant=? "
                              "ORDER BY bm25(chunks) LIMIT 4", (expression, tenant)).fetchall()
        result = []
        for source, text in rows:
            if budget <= 0:
                break
            result.append({"source": source, "text": text[:budget]})
            budget -= len(result[-1]["text"])
        return result
