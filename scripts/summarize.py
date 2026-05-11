#!/usr/bin/env python3
"""
调用 DeepSeek V4 API 对新闻进行中文总结（每条100-200字）。

失败时自动保留上一次成功的数据。

环境变量:
    AI_API_KEY: DeepSeek API 密钥
"""
import os
import json
import sys
import shutil
from datetime import datetime

import requests

DATA_DIR = "data"
RAW_NEWS_FILE = os.path.join(DATA_DIR, "raw_news.json")
NEWS_DATA_FILE = os.path.join(DATA_DIR, "news_data.json")

API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-flash"

API_KEY = os.environ.get("AI_API_KEY")
if not API_KEY:
    print("ERROR: AI_API_KEY environment variable not set")
    sys.exit(1)

# 读取原始新闻
if not os.path.exists(RAW_NEWS_FILE):
    print("No raw news file found, skipping summarization")
    sys.exit(0)

try:
    with open(RAW_NEWS_FILE, "r", encoding="utf-8") as f:
        articles = json.load(f)
except (json.JSONDecodeError, FileNotFoundError) as e:
    print(f"ERROR: failed to read raw news: {e}")
    sys.exit(1)

if not articles:
    print("No articles to summarize, keeping existing data")
    sys.exit(0)

# 构建提示词
articles_text = ""
for i, a in enumerate(articles, 1):
    text = f"{a.get('title', '')}. {a.get('description', '')} {a.get('content', '')}"[:600]
    articles_text += f"""[{i}]
标题: {a['title']}
来源: {a['source']}
内容: {text}

"""

prompt = f"""你是一位专业的中文AI新闻编辑。请为以下{len(articles)}条新闻各写一段中文总结。

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

# 备份旧数据
if os.path.exists(NEWS_DATA_FILE):
    shutil.copy2(NEWS_DATA_FILE, NEWS_DATA_FILE + ".bak")

# 调用 DeepSeek API
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
            "max_tokens": 4096,
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

    summaries = json.loads(raw)
    summary_map = {s["index"]: s["summary"] for s in summaries}

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

    print(f"OK: summarized {len(news_data)} articles")

except Exception as e:
    print(f"ERROR: summarization failed: {e}")
    # 恢复备份
    if os.path.exists(NEWS_DATA_FILE + ".bak"):
        shutil.copy2(NEWS_DATA_FILE + ".bak", NEWS_DATA_FILE)
        print("Restored previous data from backup")
    sys.exit(1)
finally:
    for f in [NEWS_DATA_FILE + ".bak"]:
        if os.path.exists(f):
            os.remove(f)
