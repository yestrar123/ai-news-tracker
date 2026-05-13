#!/usr/bin/env python3
"""
文章删除/恢复管理脚本。

用法:
  python scripts/manage_article.py --action delete --url "https://..." --title "optional"
  python scripts/manage_article.py --action restore --url "https://..."
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

DATA_DIR = "data"
DELETED_QUEUE_FILE = os.path.join(DATA_DIR, "deleted_queue.json")


def load_queue():
    if not os.path.exists(DELETED_QUEUE_FILE):
        return {"deleted": []}
    try:
        with open(DELETED_QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"deleted": []}


def save_queue(queue):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DELETED_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def action_delete(url, title=""):
    queue = load_queue()
    for entry in queue["deleted"]:
        if entry["url"] == url:
            print(f"Already in delete queue: {url}")
            return
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=3)
    queue["deleted"].append({
        "url": url,
        "title": title or "",
        "deletedAt": now.isoformat(),
        "expiresAt": expiry.isoformat(),
    })
    save_queue(queue)
    print(f"Added to delete queue: {url}")
    subprocess.call([sys.executable, "scripts/generate_site.py"])


def action_restore(url):
    queue = load_queue()
    before = len(queue["deleted"])
    queue["deleted"] = [entry for entry in queue["deleted"] if entry["url"] != url]
    removed = before - len(queue["deleted"])
    save_queue(queue)
    if removed:
        print(f"Restored: {url}")
        subprocess.call([sys.executable, "scripts/generate_site.py"])
    else:
        print(f"Not found in delete queue: {url}")


def main():
    parser = argparse.ArgumentParser(description="Manage article deletion/restoration")
    parser.add_argument("--action", required=True, choices=["delete", "restore"])
    parser.add_argument("--url", required=True, help="Article URL")
    parser.add_argument("--title", default="", help="Article title (optional)")
    args = parser.parse_args()

    if args.action == "delete":
        action_delete(args.url, args.title)
    elif args.action == "restore":
        action_restore(args.url)


if __name__ == "__main__":
    main()
