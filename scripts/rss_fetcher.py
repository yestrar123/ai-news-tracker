#!/usr/bin/env python3
"""
从 RSS 源抓取最近 6 小时的 AI/科技新闻。

容错设计：某个源失败不影响其他源。
输出格式与 fetch_news.py 一致，存入 data/rss_news.json。
"""
import json
import os
import ssl
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser

DATA_DIR = "data"
RSS_NEWS_FILE = os.path.join(DATA_DIR, "rss_news.json")

RSS_FEEDS = [
    ("Google News AI", "https://news.google.com/rss/search?q=AI+artificial+intelligence&hl=en-US&gl=US&ceid=US:en"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("MIT Tech Review AI", "https://www.technologyreview.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
]

os.makedirs(DATA_DIR, exist_ok=True)

cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
cutoff_ts = cutoff.timestamp()

all_articles = []
seen_urls = set()


def parse_rss_date(entry):
    """从 RSS entry 提取发布时间，返回 datetime (UTC)。"""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
            except Exception:
                continue
    return None


def parse_pubdate_str(date_str):
    """解析 RSS pubDate 字符串为 UTC datetime。"""
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def process_entry(entry, source_name, cutoff_ts, seen_urls):
    """处理单个 feedparser entry，返回 article dict 或 None。"""
    pub_date = parse_rss_date(entry)
    if pub_date and pub_date.timestamp() < cutoff_ts:
        return None

    url = entry.get("link", "").strip()
    if not url or url in seen_urls:
        return None
    seen_urls.add(url)

    title = (entry.get("title") or "").strip()
    description = ""
    if hasattr(entry, "summary"):
        description = (entry.summary or "").strip()
    elif hasattr(entry, "description"):
        description = (entry.description or "").strip()

    content = ""
    if hasattr(entry, "content") and entry.content:
        content = entry.content[0].get("value", "")

    published_at = pub_date.strftime("%Y-%m-%dT%H:%M:%SZ") if pub_date else ""

    return {
        "title": title,
        "url": url,
        "source": source_name,
        "publishedAt": published_at,
        "description": description,
        "content": content,
    }


def fetch_google_news(source_name, feed_url):
    """Google News RSS 专用处理：feedparser + XML ElementTree 备选。"""
    articles = []

    # Step 1: 尝试 feedparser 解析
    feed = feedparser.parse(feed_url)
    print(f"[rss] DEBUG {source_name}: len(entries)={len(feed.entries)}, bozo={feed.bozo}")
    print(f"[rss] DEBUG {source_name}: keys={list(feed.keys())}")
    if feed.bozo:
        print(f"[rss] DEBUG {source_name}: bozo_exception={getattr(feed, 'bozo_exception', 'N/A')}")

    if feed.entries:
        print(f"[rss] {source_name}: feedparser parsed {len(feed.entries)} entries")
        for entry in feed.entries:
            article = process_entry(entry, source_name, cutoff_ts, seen_urls)
            if article:
                articles.append(article)
        if articles:
            return articles
        print(f"[rss] {source_name}: all {len(feed.entries)} entries filtered (outside time window)")

    # Step 2: XML ElementTree 备选解析
    print(f"[rss] {source_name}: trying XML ElementTree fallback...")
    try:
        req = urllib.request.Request(feed_url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; RSSReader/1.0)'
        })
        ssl_ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:
            raw_xml = resp.read().decode('utf-8')

        root = ET.fromstring(raw_xml)
        channel = root.find('channel')
        if channel is None:
            print(f"[rss] {source_name}: no <channel> in XML")
            return articles

        items = channel.findall('item')
        print(f"[rss] {source_name}: XML found {len(items)} <item> elements")

        for item in items:
            title = (item.findtext('title') or '').strip()
            link = (item.findtext('link') or '').strip()
            pub_date_str = (item.findtext('pubDate') or '').strip()
            description = (item.findtext('description') or '').strip()

            if not link or link in seen_urls:
                continue
            seen_urls.add(link)

            pub_date = parse_pubdate_str(pub_date_str)
            published_at = pub_date.strftime("%Y-%m-%dT%H:%M:%SZ") if pub_date else ""

            articles.append({
                "title": title,
                "url": link,
                "source": source_name,
                "publishedAt": published_at,
                "description": description,
                "content": "",
            })

        print(f"[rss] {source_name}: XML fallback produced {len(articles)} articles")

    except Exception as e:
        print(f"[rss] {source_name}: XML fallback error: {e}")

    # 如果还是没有文章，返回 XML 解析到的所有条目（不带时间过滤）
    return articles


for source_name, feed_url in RSS_FEEDS:
    print(f"[rss] Fetching: {source_name} ({feed_url})")
    try:
        if source_name.startswith("Google News"):
            feed_articles = fetch_google_news(source_name, feed_url)
        else:
            feed = feedparser.parse(feed_url)
            print(f"[rss] DEBUG {source_name}: len(entries)={len(feed.entries)}, bozo={feed.bozo}")
            if feed.bozo and not feed.entries:
                print(f"[rss] WARNING: {source_name} — parse error, skipping")
                continue

            feed_articles = []
            for entry in feed.entries:
                article = process_entry(entry, source_name, cutoff_ts, seen_urls)
                if article:
                    feed_articles.append(article)

        all_articles.extend(feed_articles)
        print(f"[rss] OK: {source_name} — got {len(feed_articles)} articles")

    except Exception as e:
        print(f"[rss] ERROR: {source_name} — {e}")
        continue

all_articles.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)

with open(RSS_NEWS_FILE, "w", encoding="utf-8") as f:
    json.dump(all_articles, f, ensure_ascii=False, indent=2)

print(f"[rss] Done: total {len(all_articles)} articles saved to {RSS_NEWS_FILE}")
