#!/usr/bin/env python3
"""
调用 DeepSeek V4 API 对新闻进行中文总结（每条100-200字）。

分批处理避免单次请求数据量过大导致的 JSON 解析错误。
失败时自动保留上一次成功的数据。

环境变量:
    AI_API_KEY: DeepSeek API 密钥
"""
import os
import json
import sys
import math
import time
import shutil
from datetime import datetime

import requests

DATA_DIR = "data"
RAW_NEWS_FILE = os.path.join(DATA_DIR, "raw_news.json")
RSS_NEWS_FILE = os.path.join(DATA_DIR, "rss_news.json")
NEWS_DATA_FILE = os.path.join(DATA_DIR, "news_data.json")

API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-flash"
BATCH_SIZE = 10

API_KEY = os.environ.get("AI_API_KEY")
if not API_KEY:
    print("ERROR: AI_API_KEY environment variable not set")
    sys.exit(1)

# 读取原始新闻（合并 NewsAPI + RSS，按 url 去重）
articles = []
seen_urls = set()
any_file_found = False

for filepath in (RAW_NEWS_FILE, RSS_NEWS_FILE):
    if not os.path.exists(filepath):
        continue
    any_file_found = True
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            batch = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"WARNING: failed to read {filepath}: {e}")
        continue

    for a in batch:
        url = a.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            articles.append(a)

if not any_file_found:
    print("No raw news file found, skipping summarization")
    sys.exit(0)

if not articles:
    print("No articles to summarize, keeping existing data")
    sys.exit(0)

total_batches = math.ceil(len(articles) / BATCH_SIZE)
print(f"Total {len(articles)} articles, processing in {total_batches} batches (batch size: {BATCH_SIZE})")


def build_batch_prompt(batch_articles, batch_start_idx):
    """构建单批次的提示词。"""
    articles_text = ""
    for j, a in enumerate(batch_articles, 1):
        text = f"{a.get('title', '')}. {a.get('description', '')} {a.get('content', '')}"[:600]
        articles_text += f"""[{j}]
标题: {a['title']}
来源: {a['source']}
内容: {text}

"""

    return f"""你是一位专业的中文AI新闻编辑。请为以下{len(batch_articles)}条新闻各写一段中文总结。

要求：
- 每条总结 100-200 字
- 抓住核心信息和技术要点
- 语言简洁、专业、通顺
- 如原文信息不足，可基于已有内容合理概括

新闻列表：
{articles_text}
请严格按如下JSON格式返回（只返回JSON，不要任何其他文字）：
[
  {{"index": 1, "summary": "..."}},
  {{"index": 2, "summary": "..."}}
]"""


def call_api(prompt, retries=2):
    """调用 DeepSeek API，返回解析后的 summaries list。失败时重试。"""
    last_exc = None
    for attempt in range(1 + retries):
        try:
            resp = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": "你是专业的AI新闻编辑助手，严格按用户要求的JSON格式输出。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 8192,
                },
                timeout=120,
            )
            resp.raise_for_status()
            body = resp.json()

            raw = body["choices"][0]["message"]["content"]

            # 提取 JSON（处理可能包裹在 markdown 代码块中的情况）
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            return json.loads(raw)
        except Exception as e:
            last_exc = e
            if attempt < retries:
                wait = 2 ** attempt
                print(f"  API attempt {attempt + 1} failed, retrying in {wait}s...")
                time.sleep(wait)
    raise last_exc


# 备份旧数据
if os.path.exists(NEWS_DATA_FILE):
    shutil.copy2(NEWS_DATA_FILE, NEWS_DATA_FILE + ".bak")

# 分批处理
summary_map = {}  # global_index -> summary

for batch_idx in range(total_batches):
    start = batch_idx * BATCH_SIZE
    end = min(start + BATCH_SIZE, len(articles))
    batch_articles = articles[start:end]
    batch_num = batch_idx + 1

    print(f"Processing batch {batch_num}/{total_batches} (articles {start + 1}-{end})...")

    try:
        prompt = build_batch_prompt(batch_articles, start)
        summaries = call_api(prompt)

        for s in summaries:
            local_idx = s["index"]
            global_idx = start + local_idx
            summary_map[global_idx] = s["summary"]

        print(f"  Batch {batch_num}: OK, got {len(summaries)} summaries")

    except Exception as e:
        print(f"  Batch {batch_num}: FAILED — {e}")
        # 该批次所有文章标记为无摘要，继续处理下一批
        for j in range(len(batch_articles)):
            summary_map[start + j + 1] = "暂无摘要"

# 组装最终数据
news_data = []
for i, a in enumerate(articles, 1):
    news_data.append({
        "title": a.get("title", ""),
        "url": a.get("url", ""),
        "source": a.get("source", ""),
        "publishedAt": a.get("publishedAt", ""),
        "summary": summary_map.get(i, "暂无摘要"),
    })

with open(NEWS_DATA_FILE, "w", encoding="utf-8") as f:
    json.dump({
        "updatedAt": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "totalArticles": len(news_data),
        "articles": news_data,
    }, f, ensure_ascii=False, indent=2)

success_summaries = sum(1 for v in summary_map.values() if v != "暂无摘要")
print(f"OK: summarized {success_summaries}/{len(articles)} articles")

# 清理备份
for f_path in [NEWS_DATA_FILE + ".bak"]:
    if os.path.exists(f_path):
        os.remove(f_path)
