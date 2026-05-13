#!/usr/bin/env python3
"""
清理已过期的软删除文章。

从 articles.json 中彻底删除，从 deleted_queue.json 中移除记录。
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

DATA_DIR = "data"
DELETED_QUEUE_FILE = os.path.join(DATA_DIR, "deleted_queue.json")
ARTICLES_DB_FILE = os.path.join(DATA_DIR, "articles.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default


def save_json(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    queue = load_json(DELETED_QUEUE_FILE, {"deleted": []})
    if not queue["deleted"]:
        print("No deleted articles to process")
        return

    now = datetime.now(timezone.utc)

    # Filter expired entries
    expired = []
    remaining = []
    for entry in queue["deleted"]:
        try:
            expires_at = datetime.fromisoformat(entry["expiresAt"])
            if expires_at <= now:
                expired.append(entry)
            else:
                remaining.append(entry)
        except (ValueError, KeyError):
            remaining.append(entry)

    if not expired:
        print("No expired articles found")
        return

    expired_urls = {entry["url"] for entry in expired}
    print(f"Found {len(expired)} expired articles to clean")

    # Remove from articles.json
    articles_data = load_json(ARTICLES_DB_FILE, {"articles": [], "total": 0})
    original_count = len(articles_data["articles"])
    articles_data["articles"] = [
        a for a in articles_data["articles"] if a.get("url") not in expired_urls
    ]
    removed_count = original_count - len(articles_data["articles"])
    articles_data["total"] = len(articles_data["articles"])
    save_json(ARTICLES_DB_FILE, articles_data)

    # Update queue
    queue["deleted"] = remaining
    save_json(DELETED_QUEUE_FILE, queue)

    print(f"Cleaned {removed_count} expired articles from database")

    # Regenerate site
    subprocess.call([sys.executable, "scripts/generate_site.py"])


if __name__ == "__main__":
    main()
