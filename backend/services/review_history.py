import json
import sqlite3
from pathlib import Path

from backend.schemas import ReviewResponse


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "review_history.sqlite3"
MAX_HISTORY = 500


def save_review(review: ReviewResponse) -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, reviewed_at TEXT NOT NULL, response_json TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT OR REPLACE INTO reviews (id, reviewed_at, response_json) VALUES (?, ?, ?)",
            (review.id, review.reviewed_at, review.model_dump_json()),
        )
        connection.execute(
            "DELETE FROM reviews WHERE id NOT IN (SELECT id FROM reviews ORDER BY reviewed_at DESC LIMIT ?)",
            (MAX_HISTORY,),
        )


def list_reviews() -> list[ReviewResponse]:
    if not DATABASE_PATH.exists():
        return []
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, reviewed_at TEXT NOT NULL, response_json TEXT NOT NULL)"
        )
        rows = connection.execute(
            "SELECT response_json FROM reviews ORDER BY reviewed_at DESC, rowid DESC LIMIT ?",
            (MAX_HISTORY,),
        ).fetchall()
    return [ReviewResponse.model_validate_json(row[0]) for row in rows]


def clear_reviews() -> int:
    if not DATABASE_PATH.exists():
        return 0
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, reviewed_at TEXT NOT NULL, response_json TEXT NOT NULL)"
        )
        cursor = connection.execute("DELETE FROM reviews")
        return cursor.rowcount
