"""网页里改的配置：键值设置（密码哈希、Token、Key、模型）和博客列表。与发布历史同一个 SQLite 文件。"""
import json
import sqlite3
from pathlib import Path

from ..core.config import BlogConfig

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blogs (
  id TEXT PRIMARY KEY,
  position INTEGER NOT NULL,
  data TEXT NOT NULL
);
"""


class ConfigStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        path.chmod(0o600)  # 库里有 Token，只给本用户读写

    def get(self, key: str) -> str:
        row = self.db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else ""

    def set(self, key: str, value: str) -> None:
        if value:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, value))
        else:
            self.db.execute("DELETE FROM settings WHERE key = ?", (key,))
        self.db.commit()

    def blogs(self) -> list[BlogConfig]:
        rows = self.db.execute("SELECT data FROM blogs ORDER BY position, id").fetchall()
        return [BlogConfig(**json.loads(r["data"])) for r in rows]

    def save_blog(self, blog: BlogConfig) -> None:
        row = self.db.execute("SELECT position FROM blogs WHERE id = ?", (blog.id,)).fetchone()
        if row:
            pos = row["position"]
        else:
            pos = self.db.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM blogs").fetchone()[0]
        self.db.execute("INSERT OR REPLACE INTO blogs VALUES (?, ?, ?)",
                        (blog.id, pos, json.dumps(blog.model_dump(), ensure_ascii=False)))
        self.db.commit()

    def delete_blog(self, blog_id: str) -> bool:
        cur = self.db.execute("DELETE FROM blogs WHERE id = ?", (blog_id,))
        self.db.commit()
        return cur.rowcount > 0
