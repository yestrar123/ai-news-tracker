#!/usr/bin/env python3
"""
读取 news_data.json，追加到 data/articles.json（简易数据库，按 URL 去重），
生成 index.html（分页首页 + 搜索）和 archive.html（按日期归档）。
"""
import json
import os
import math
from datetime import datetime, date

DATA_DIR = "data"
NEWS_DATA_FILE = os.path.join(DATA_DIR, "news_data.json")
ARTICLES_DB_FILE = os.path.join(DATA_DIR, "articles.json")
INDEX_FILE = "index.html"
ARCHIVE_FILE = "archive.html"
ITEMS_PER_PAGE = 20


def load_news_data():
    """从 news_data.json 读取新文章"""
    if not os.path.exists(NEWS_DATA_FILE):
        return None, []
    try:
        with open(NEWS_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("updatedAt"), data.get("articles", [])
    except (json.JSONDecodeError, FileNotFoundError):
        return None, []


def load_articles_db():
    """加载 articles.json 历史数据库"""
    if not os.path.exists(ARTICLES_DB_FILE):
        return []
    try:
        with open(ARTICLES_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("articles", [])
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_articles_db(articles):
    """保存 articles.json"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ARTICLES_DB_FILE, "w", encoding="utf-8") as f:
        json.dump({"articles": articles, "total": len(articles)}, f, ensure_ascii=False, indent=2)


def merge_articles(existing, new_articles):
    """合并新文章到历史库，按 url 去重，返回 (合并后列表, 新增数)"""
    existing_urls = {a["url"] for a in existing}
    max_id = max((int(a.get("id", 0)) for a in existing), default=0)
    today = date.today().isoformat()
    added = 0
    for a in new_articles:
        url = a.get("url", "")
        if url and url not in existing_urls:
            max_id += 1
            existing.append({
                "id": str(max_id),
                "title": a.get("title", ""),
                "url": url,
                "source": a.get("source", ""),
                "publishedAt": a.get("publishedAt", ""),
                "summary": a.get("summary", "暂无摘要"),
                "fetchDate": today,
            })
            existing_urls.add(url)
            added += 1
    return existing, added


def get_covered_days(articles):
    """统计文章覆盖了多少天"""
    dates = set()
    for a in articles:
        try:
            dt = datetime.fromisoformat(a.get("publishedAt", "").replace("Z", "+00:00"))
            dates.add(dt.date().isoformat())
        except (ValueError, AttributeError):
            pass
    return len(dates)


# ── JS 辅助函数（避免在 f-string 中使用 JS 模板字面量） ──────────────────

def _js_escape(s):
    """转义 HTML 特殊字符（生成 JS 字符串用）"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _js_globals():
    """返回 JS 中全局辅助函数的定义"""
    return """
function _f(pub) {
    if (!pub) return '';
    try { var d = new Date(pub.replace('Z','+00:00')); return d.toISOString().slice(0,10)+' '+d.toISOString().slice(11,16); } catch(e) { return pub.slice(0,16); }
}
function _e(s) {
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function _h(text, kw) {
    if (!kw) return _e(text);
    var re = new RegExp(_re(kw), 'gi');
    return _e(text).replace(re, function(m) { return '<mark class="hl">'+m+'</mark>'; });
}
function _re(s) {
    return s.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
}
"""


def _render_article_js():
    """返回 JS 渲染单条新闻卡片的函数"""
    return """
function _card(a, kw) {
    return '<article class="news-card">'
        + '<div class="card-header"><span class="card-source">'+_e(a.source)+'</span><span class="card-time">'+_f(a.publishedAt)+'</span></div>'
        + '<h2 class="card-title"><a href="'+_e(a.url)+'" target="_blank" rel="noopener noreferrer">'+_h(a.title, kw)+'</a></h2>'
        + '<p class="card-summary">'+_e(a.summary||'暂无摘要')+'</p>'
        + '</article>';
}
"""


# ── HTML 生成 ────────────────────────────────────────────────────

def generate_ssr_first_page(articles):
    """服务端渲染第一页文章"""
    cards = []
    for a in articles[:ITEMS_PER_PAGE]:
        t = a.get("title", "无标题")
        u = a.get("url", "#")
        s = a.get("source", "")
        p = a.get("publishedAt", "")
        sm = a.get("summary", "暂无摘要")
        try:
            dt = datetime.fromisoformat(p.replace("Z", "+00:00"))
            p = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            p = p[:16] if p else ""
        cards.append(
            """    <article class="news-card">
        <div class="card-header">
            <span class="card-source">{source}</span>
            <span class="card-time">{pub}</span>
        </div>
        <h2 class="card-title"><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h2>
        <p class="card-summary">{summary}</p>
    </article>""".format(
                source=_js_escape(s), pub=_js_escape(p),
                url=_js_escape(u), title=_js_escape(t), summary=_js_escape(sm)
            )
        )
    return "\n".join(cards)


def build_index(articles, updated_at, actions_url):
    """生成首页 HTML"""
    total = len(articles)
    total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
    days = get_covered_days(articles)
    articles_json = json.dumps(articles, ensure_ascii=False)
    ssr = generate_ssr_first_page(articles) if articles else ""
    empty_html = ""
    if not articles:
        empty_html = """
    <div class="empty-state">
        <div class="empty-icon">&#x1F4E1;</div>
        <h2>暂无新闻</h2>
        <p>数据尚未生成，请等待首次自动更新。</p>
        <p>首次部署后，GitHub Actions 将在 6 小时内自动运行。</p>
        <p>你也可以前往 <a href="{actions_url}" target="_blank">GitHub Actions</a> 手动触发更新。</p>
    </div>""".format(actions_url=actions_url)

    return """<!DOCTYPE html>
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
            <div class="header-actions">
                <a href="archive.html" class="archive-link">&#x1F4C2; 归档</a>
                <a href="{actions_url}" class="refresh-btn" target="_blank">&#x21BB; 手动刷新</a>
            </div>
        </div>
        <p class="site-subtitle">自动追踪 &amp; AI 总结 · 每 6 小时更新</p>
        <p class="update-info">上次更新：{updated_at} · 共 <span id="totalArticles">{total}</span> 篇文章 · 覆盖 <span id="totalDays">{days}</span> 天</p>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="搜索文章标题..." autocomplete="off">
        </div>
    </header>

    <main class="news-grid" id="newsGrid">
        {ssr}
        {empty_html}
    </main>

    <div class="pagination" id="pagination"></div>

    <footer class="site-footer">
        <p>由 GitHub Actions 定时驱动 · AI 总结由 AI 生成</p>
        <p><a href="{actions_url}" target="_blank">手动触发更新</a> · <a href="archive.html">查看归档</a></p>
    </footer>
</div>

<script>
var ALL = {articles_json};
var PS = {items_per_page};
var cp = 1;
var fa = ALL;

{globals}
{card_func}

function rp(p, aa) {{
    var st = (p-1)*PS, en = st+PS;
    var pa = aa.slice(st, en);
    var g = document.getElementById('newsGrid');
    var kw = document.getElementById('searchInput').value.trim();
    if (pa.length===0) {{
        g.innerHTML = '<div class="empty-state"><div class="empty-icon">&#x1F50D;</div><h2>暂无匹配文章</h2><p>请尝试其他关键词</p></div>';
        return;
    }}
    g.innerHTML = pa.map(function(a){{ return _card(a, kw); }}).join('');
}}

function rpgn(aa) {{
    var tp = Math.max(1, Math.ceil(aa.length/PS));
    var el = document.getElementById('pagination');
    if (tp<=1) {{ el.innerHTML = ''; return; }}
    var h = '';
    if (cp>1) h += '<button class="page-btn" onclick="gp('+(cp-1)+')">&#x2039; 上一页</button>';
    h += '<span class="page-info">第 '+cp+' / 共 '+tp+' 页</span>';
    if (cp<tp) h += '<button class="page-btn" onclick="gp('+(cp+1)+')">下一页 &#x203A;</button>';
    el.innerHTML = h;
}}

function gp(p) {{
    var tp = Math.max(1, Math.ceil(fa.length/PS));
    if (p<1||p>tp) return;
    cp = p;
    rp(cp, fa);
    rpgn(fa);
    window.scrollTo({{top:0,behavior:'smooth'}});
}}

function ds() {{
    var kw = document.getElementById('searchInput').value.trim().toLowerCase();
    fa = kw ? ALL.filter(function(a){{return (a.title||'').toLowerCase().indexOf(kw)!==-1;}}) : ALL;
    cp = 1;
    rp(1, fa);
    rpgn(fa);
    document.getElementById('totalArticles').textContent = fa.length;
}}

var st;
document.getElementById('searchInput').addEventListener('input', function() {{
    clearTimeout(st);
    st = setTimeout(ds, 300);
}});
</script>
</body>
</html>""".format(
        actions_url=actions_url,
        updated_at=updated_at or "暂无",
        total=total,
        days=days,
        ssr=ssr,
        empty_html=empty_html,
        articles_json=articles_json,
        items_per_page=ITEMS_PER_PAGE,
        globals=_js_globals(),
        card_func=_render_article_js(),
    )


def build_archive(articles, actions_url):
    """生成归档页面 HTML"""
    total = len(articles)
    articles_json = json.dumps(articles, ensure_ascii=False)

    # SSR 日期分组（用于初始展示，JS 会接管）
    date_groups = {}
    for a in articles:
        try:
            dt = datetime.fromisoformat(a.get("publishedAt", "").replace("Z", "+00:00"))
            d = dt.date().isoformat()
        except (ValueError, AttributeError):
            d = "未知日期"
        date_groups.setdefault(d, []).append(a)
    sorted_dates = sorted(date_groups.keys(), reverse=True)
    total_dates = len(sorted_dates)

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>文章归档 - AI 热点新闻</title>
<meta name="description" content="AI 热点新闻历史归档">
<link rel="stylesheet" href="style.css">
</head>
<body>
<div class="container">
    <header class="site-header">
        <div class="header-top">
            <h1 class="site-title">&#x1F4C2; 文章归档</h1>
            <div class="header-actions">
                <a href="index.html" class="archive-link">&#x2190; 返回首页</a>
                <a href="{actions_url}" class="refresh-btn" target="_blank">&#x21BB; 手动刷新</a>
            </div>
        </div>
        <p class="site-subtitle">所有历史文章按日期归档</p>
        <p class="update-info">共 <span id="totalDates">{total_dates}</span> 个归档日期 · <span id="totalArticles">{total}</span> 篇文章</p>
    </header>

    <main class="archive-list" id="archiveList">
        <div class="empty-state" id="archiveEmpty">
            <div class="empty-icon">&#x1F4E1;</div>
            <h2>暂无归档</h2>
            <p>等待首次数据更新。</p>
        </div>
    </main>

    <footer class="site-footer">
        <p>由 GitHub Actions 定时驱动 · AI 总结由 AI 生成</p>
        <p><a href="index.html">返回首页</a> · <a href="{actions_url}" target="_blank">手动触发更新</a></p>
    </footer>
</div>

<script>
var ALL = {articles_json};
{globals}

function ra() {{
    var gr = {{}}, keys = [];
    ALL.forEach(function(a) {{
        var d = '\\u672a\\u77e5\\u65e5\\u671f';
        try {{ d = new Date(a.publishedAt.replace('Z','+00:00')).toISOString().slice(0,10); }} catch(e) {{}}
        if (!gr[d]) {{ gr[d] = []; keys.push(d); }}
        gr[d].push(a);
    }});
    keys.sort().reverse();
    document.getElementById('totalDates').textContent = keys.length;
    document.getElementById('totalArticles').textContent = ALL.length;
    document.getElementById('archiveEmpty').style.display = 'none';

    var list = document.getElementById('archiveList');
    list.innerHTML = keys.map(function(d) {{
        var aa = gr[d];
        var cards = aa.map(function(a) {{ return _card(a, ''); }}).join('');
        return '<div class="archive-group">'
            + '<div class="archive-group-header" onclick="tg(this)">'
            + '<span class="archive-date">'+d+'</span>'
            + '<span class="archive-count">'+aa.length+'\\u7bc7</span>'
            + '<span class="archive-toggle">\\u25B6</span>'
            + '</div>'
            + '<div class="archive-group-body">'+cards+'</div>'
            + '</div>';
    }}).join('');
}}

function tg(h) {{
    var b = h.nextElementSibling;
    var to = h.querySelector('.archive-toggle');
    b.classList.toggle('expanded');
    to.textContent = b.classList.contains('expanded') ? '\\u25BC' : '\\u25B6';
}}

{card_func}
ra();
</script>
</body>
</html>""".format(
        actions_url=actions_url,
        total_dates=total_dates,
        total=total,
        articles_json=articles_json,
        globals=_js_globals(),
        card_func=_render_article_js(),
    )


def main():
    updated_at, new_articles = load_news_data()
    if not new_articles:
        print("No new articles to process")
        updated_at = "暂无"

    db_articles = load_articles_db()
    all_articles, added = merge_articles(db_articles, new_articles)
    save_articles_db(all_articles)

    repo = os.environ.get("GITHUB_REPOSITORY", "your-username/your-repo")
    actions_url = f"https://github.com/{repo}/actions/workflows/update.yml"

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(build_index(all_articles, updated_at, actions_url))

    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        f.write(build_archive(all_articles, actions_url))

    print(f"OK: index.html ({len(all_articles)} articles, {added} new)")
    print(f"OK: archive.html ({len(all_articles)} articles)")


if __name__ == "__main__":
    main()
