#!/usr/bin/env python3
"""
清理 data/articles.json 的历史文章。

两种运行模式：
  交互式（无参数）:     python scripts/clean_articles.py
  非交互式（命令行参数）: python scripts/clean_articles.py --keep-days 90
                        python scripts/clean_articles.py --keep-count 500

清理前自动备份到 data/backup/cleaned_YYYYMMDD_HHMMSS.json。
清理后提醒用户手动 git push。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

DATA_DIR = "data"
BACKUP_DIR = os.path.join(DATA_DIR, "backup")
ARTICLES_FILE = os.path.join(DATA_DIR, "articles.json")


def load_articles():
    """加载 articles.json，返回文章列表。"""
    if not os.path.exists(ARTICLES_FILE):
        print("articles.json not found, nothing to clean")
        sys.exit(0)
    try:
        with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("articles", [])
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"ERROR: failed to read articles.json: {e}")
        sys.exit(1)


def save_articles(articles):
    """保存 articles.json，重新编号 ID。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    for i, a in enumerate(articles, 1):
        a["id"] = str(i)
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump({"articles": articles, "total": len(articles)}, f, ensure_ascii=False, indent=2)


def backup_articles(articles):
    """备份当前 articles.json 到 data/backup/。"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"cleaned_{ts}.json")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump({"articles": articles, "total": len(articles)}, f, ensure_ascii=False, indent=2)
    print(f"Backup saved: {backup_path}")
    return backup_path


def parse_date(ds):
    """尝试解析 publishedAt 为 datetime，失败返回 None。"""
    if not ds:
        return None
    try:
        return datetime.fromisoformat(ds.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def get_date_range(articles):
    """获取文章日期范围（基于 publishedAt）。"""
    dates = []
    for a in articles:
        dt = parse_date(a.get("publishedAt", ""))
        if dt:
            dates.append(dt)
    if not dates:
        return "（无有效日期）"
    return f"{min(dates).strftime('%Y-%m-%d')} ~ {max(dates).strftime('%Y-%m-%d')}"


def clean_by_days(articles, keep_days):
    """保留最近 keep_days 天的文章。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    kept = [a for a in articles if parse_date(a.get("publishedAt", "")) and parse_date(a.get("publishedAt", "")) >= cutoff]
    return kept


def clean_by_count(articles, keep_count):
    """保留最近 keep_count 篇文章（按 publishedAt 降序）。"""
    sorted_articles = sorted(articles, key=lambda a: parse_date(a.get("publishedAt", "")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return sorted_articles[:keep_count]


def interactive_mode():
    """交互式清理菜单。"""
    articles = load_articles()
    if not articles:
        print("articles.json is empty, nothing to clean")
        return

    total = len(articles)
    date_range = get_date_range(articles)
    print(f"\nCurrent articles: {total}")
    print(f"Date range: {date_range}\n")
    print("Select cleanup mode:")
    print("  1) Keep last N days")
    print("  2) Keep last N articles")
    print("  3) Clear all")
    print("  4) Cancel")

    choice = input("\nEnter choice (1-4): ").strip()

    if choice == "1":
        try:
            days = int(input("Keep how many days? ").strip())
        except ValueError:
            print("Invalid number")
            return
        kept = clean_by_days(articles, days)
    elif choice == "2":
        try:
            count = int(input("Keep how many articles? ").strip())
        except ValueError:
            print("Invalid number")
            return
        kept = clean_by_count(articles, count)
    elif choice == "3":
        kept = []
    elif choice == "4":
        print("Cancelled")
        return
    else:
        print("Invalid choice")
        return

    deleted = len(articles) - len(kept)
    if deleted == 0:
        print("Nothing to delete")
        return

    print(f"\nWill delete {deleted} articles, {len(kept)} remaining")
    confirm = input('Type YES to confirm: ').strip()
    if confirm != "YES":
        print("Cancelled")
        return

    backup_articles(articles)
    save_articles(kept)
    print(f"\nDone: {total} → {len(kept)} (deleted {deleted})")
    print("Please run: git add data/ && git commit -m 'clean old articles' && git push")


def noninteractive_mode(keep_days=None, keep_count=None):
    """非交互式清理。"""
    articles = load_articles()
    if not articles:
        print("articles.json is empty, nothing to clean")
        return

    total = len(articles)
    if keep_days:
        kept = clean_by_days(articles, keep_days)
        label = f"keeping last {keep_days} days"
    elif keep_count:
        kept = clean_by_count(articles, keep_count)
        label = f"keeping last {keep_count} articles"
    else:
        return

    deleted = total - len(kept)
    backup_articles(articles)
    save_articles(kept)
    print(f"Done ({label}): {total} → {len(kept)} (deleted {deleted})")
    print("Please run: git add data/ && git commit -m 'clean old articles' && git push")


def main():
    parser = argparse.ArgumentParser(description="Clean old articles from articles.json")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--keep-days", type=int, help="Keep articles from last N days")
    group.add_argument("--keep-count", type=int, help="Keep last N articles")
    args = parser.parse_args()

    if args.keep_days:
        noninteractive_mode(keep_days=args.keep_days)
    elif args.keep_count:
        noninteractive_mode(keep_count=args.keep_count)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
