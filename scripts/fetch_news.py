#!/usr/bin/env python3
"""
从 NewsAPI 获取最近6小时的 AI/科技热点新闻。

环境变量:
    NEWS_API_KEY: NewsAPI API 密钥
"""
import os
import json
import sys
from datetime import datetime, timedelta

import requests

DATA_DIR = "data"
RAW_NEWS_FILE = os.path.join(DATA_DIR, "raw_news.json")

os.makedirs(DATA_DIR, exist_ok=True)

API_KEY = os.environ.get("NEWS_API_KEY")
if not API_KEY:
    print("ERROR: NEWS_API_KEY environment variable not set")
    sys.exit(1)

# 计算6小时前的时间
since_time = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S")

# 请求 NewsAPI
try:
    response = requests.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": '"AI" OR "artificial intelligence" OR "machine learning" OR "LLM" OR "deep learning"',
            "from": since_time,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": API_KEY,
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "ok":
        print(f"API error: {data.get('message', 'Unknown error')}")
        sys.exit(1)

    # 提取需要的字段
    articles = []
    seen_urls = set()

    for article in data.get("articles", []):
        url = article.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            articles.append({
                "title": article.get("title", "").strip(),
                "url": url,
                "source": article.get("source", {}).get("name", "Unknown"),
                "publishedAt": article.get("publishedAt", ""),
                "description": (article.get("description") or "").strip(),
                "content": (article.get("content") or "").strip(),
            })

    # 按发布时间排序
    articles.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)

    with open(RAW_NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"OK: fetched {len(articles)} articles, saved to {RAW_NEWS_FILE}")

except requests.exceptions.RequestException as e:
    print(f"ERROR: network request failed: {e}")
    sys.exit(1)
except (json.JSONDecodeError, KeyError, ValueError) as e:
    print(f"ERROR: data processing failed: {e}")
    sys.exit(1)
