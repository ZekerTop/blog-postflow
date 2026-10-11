import json
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS publishes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  post_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
  publish_id INTEGER NOT NULL REFERENCES publishes(id),
  blog_id TEXT NOT NULL,
  path TEXT NOT NULL,
  ok INTEGER NOT NULL,
  commit_sha TEXT,
  commit_url TEXT,
  error TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (publish_id, blog_id)
);
"""


class PublishStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def new_publish(self, post: dict) -> int:
        cur = self.db.execute(
            "INSERT INTO publishes (created_at, post_json) VALUES (?, ?)",
            (datetime.now().isoformat(timespec="seconds"), json.dumps(post, ensure_ascii=False, default=str)),
        )
        self.db.commit()
        return cur.lastrowid

    def save_result(self, publish_id: int, blog_id: str, path: str, ok: bool,
                    commit_sha: str | None = None, commit_url: str | None = None, error: str | None = None) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (publish_id, blog_id, path, int(ok), commit_sha, commit_url, error,
             datetime.now().isoformat(timespec="seconds")),
        )
        self.db.commit()

    def get(self, publish_id: int) -> dict | None:
        row = self.db.execute("SELECT * FROM publishes WHERE id = ?", (publish_id,)).fetchone()
        if not row:
            return None
        results = self.db.execute("SELECT * FROM results WHERE publish_id = ?", (publish_id,)).fetchall()
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "post": json.loads(row["post_json"]),
            "results": [dict(r) | {"ok": bool(r["ok"])} for r in results],
        }

    def history(self, limit: int = 50) -> list[dict]:
        ids = [r["id"] for r in self.db.execute("SELECT id FROM publishes ORDER BY id DESC LIMIT ?", (limit,))]
        return [self.get(i) for i in ids]
