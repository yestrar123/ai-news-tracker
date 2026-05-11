#!/usr/bin/env python3
"""
从 news_data.json 读取数据，生成最终的 index.html 静态页面。

环境变量:
    GITHUB_REPOSITORY: GitHub 仓库名（如 "user/repo"），在 Actions 中自动传入
"""
import json
import os
from datetime import datetime

DATA_DIR = "data"
NEWS_DATA_FILE = os.path.join(DATA_DIR, "news_data.json")
INDEX_FILE = "index.html"

# 读取新闻数据
articles = []
updated_at = "暂无"

if os.path.exists(NEWS_DATA_FILE):
    try:
        with open(NEWS_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        articles = data.get("articles", [])
        updated_at = data.get("updatedAt", "暂无")
    except (json.JSONDecodeError, FileNotFoundError):
        pass

# GitHub 仓库信息（在 Actions 中通过环境变量传入）
repo = os.environ.get("GITHUB_REPOSITORY", "your-username/your-repo")
actions_url = f"https://github.com/{repo}/actions/workflows/update.yml"

# 构建新闻卡片 HTML
cards_html = ""
if not articles:
    cards_html = f"""
    <div class="empty-state">
        <div class="empty-icon">📡</div>
        <h2>暂无新闻</h2>
        <p>数据尚未生成，请等待首次自动更新。</p>
        <p>首次部署后，GitHub Actions 将在 6 小时内自动运行。</p>
        <p>你也可以前往 <a href="{actions_url}" target="_blank">GitHub Actions</a> 手动触发更新。</p>
    </div>"""
else:
    for a in articles:
        title = a.get("title", "无标题")
        url = a.get("url", "#")
        source = a.get("source", "")
        pub = a.get("publishedAt", "")
        summary = a.get("summary", "暂无摘要")

        # 格式化时间
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            pub = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            pub = pub[:16] if pub else ""

        cards_html += f"""
    <article class="news-card">
        <div class="card-header">
            <span class="card-source">{source}</span>
            <span class="card-time">{pub}</span>
        </div>
        <h2 class="card-title"><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h2>
        <p class="card-summary">{summary}</p>
    </article>"""

# 组装完整 HTML
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 热点新闻追踪</title>
    <meta name="description" content="AI 热点新闻自动追踪与总结，每 6 小时自动更新">
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <header class="site-header">
            <div class="header-top">
                <h1 class="site-title">AI 热点新闻</h1>
                <a href="{actions_url}" class="refresh-btn" target="_blank">↻ 手动刷新</a>
            </div>
            <p class="site-subtitle">自动追踪 &amp; AI 总结 · 每 6 小时更新</p>
            <p class="update-info">上次更新：{updated_at} · 共 {len(articles)} 条新闻</p>
        </header>

        <main class="news-grid">
            {cards_html}
        </main>

        <footer class="site-footer">
            <p>由 GitHub Actions 定时驱动 · AI 总结由 DeepSeek V4 生成</p>
            <p><a href="{actions_url}" target="_blank">手动触发更新</a></p>
        </footer>
    </div>
</body>
</html>"""

with open(INDEX_FILE, "w", encoding="utf-8") as f:
    f.write(html)

print(f"OK: generated {INDEX_FILE} with {len(articles)} articles")
