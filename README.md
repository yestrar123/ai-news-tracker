# AI 热点新闻追踪

自动抓取 AI 领域热点新闻，调用 DeepSeek V4 进行中文总结，生成静态网站部署在 GitHub Pages。

## 功能

- **定时更新**：每 6 小时自动抓取并总结 AI 热点新闻
- **AI 总结**：使用 DeepSeek V4 Flash 模型对每条新闻进行 100-200 字中文总结
- **手动触发**：通过 GitHub Actions 页面手动触发更新
- **静态部署**：纯静态网站，托管在 GitHub Pages，无需后端服务器
- **响应式设计**：支持桌面和移动端浏览

## 目录结构

```
.
├── .github/workflows/update.yml   # GitHub Actions 定时任务
├── scripts/
│   ├── fetch_news.py              # 从 NewsAPI 抓取新闻
│   ├── summarize.py               # 调用 DeepSeek API 总结
│   └── generate_site.py           # 生成静态 index.html
├── data/
│   ├── raw_news.json              # 原始新闻数据
│   └── news_data.json             # 总结后的新闻数据
├── index.html                     # 生成的网站主页
├── style.css                      # 网站样式
└── README.md
```

## 部署步骤

### 1. Fork / Clone 仓库

将本项目推送到你的 GitHub 仓库。

### 2. 申请 API Key

#### NewsAPI
1. 前往 [newsapi.org](https://newsapi.org/register) 注册账号
2. 免费套餐每天 100 次请求，本项目每 6 小时运行一次，每天 4 次，完全够用

#### DeepSeek
1. 前往 [platform.deepseek.com](https://platform.deepseek.com/) 注册并获取 API Key
2. 使用 `deepseek-v4-flash` 模型

### 3. 配置 GitHub Secrets

在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 中添加：

| Secret 名称 | 说明 |
|---|---|
| `NEWS_API_KEY` | NewsAPI 的 API Key |
| `AI_API_KEY` | DeepSeek 的 API Key（调用 deepseek-v4-flash 模型） |

### 4. 启用 GitHub Pages

1. 进入仓库 **Settings → Pages**
2. **Source** 选择 **Deploy from a branch**
3. **Branch** 选择 `main`（或你的默认分支），目录选 `/ (root)`
4. 点击 **Save**

等待几分钟，你的网站将在 `https://<用户名>.github.io/<仓库名>/` 上线。

### 5. 手动触发首次更新

1. 进入仓库的 **Actions** 页面
2. 找到 **AI News Auto Update** 工作流
3. 点击 **Run workflow → Run**
4. 等待运行完成，刷新 GitHub Pages 页面即可看到新闻

## 手动触发更新

在网站顶部点击 **手动刷新** 按钮，将跳转到 GitHub Actions 页面，点击 **Run workflow** 即可触发更新。

## 工作原理

```
NewsAPI (抓取英文新闻)
    ↓
fetch_news.py (筛选 AI 相关新闻，保存为 raw_news.json)
    ↓
summarize.py (调用 DeepSeek V4 生成中文总结，保存为 news_data.json)
    ↓
generate_site.py (读取数据，生成 index.html)
    ↓
GitHub Actions (git commit + push)
    ↓
GitHub Pages (自动部署更新后的页面)
```

- 定时任务使用 GitHub Actions 的 `schedule` 事件，通过 cron 表达式 `0 */6 * * *` 每 6 小时运行一次
- `workflow_dispatch` 事件支持手动触发
- 若 fetch 或 summarize 某一步失败，不会覆盖已有数据，网站保持上一次正常更新的内容
- 生成的 `index.html` 为纯静态页面，不依赖任何后端服务

## 技术栈

- **数据源**: NewsAPI
- **AI 模型**: DeepSeek V4 Flash (deepseek-v4-flash)
- **自动化**: GitHub Actions (schedule + workflow_dispatch)
- **托管**: GitHub Pages
- **脚本语言**: Python 3
- **HTTP 库**: requests
- **前端**: 纯 CSS + HTML（无前端框架依赖）

## 自定义

- 修改 `.github/workflows/update.yml` 中的 cron 表达式可调整更新频率
- 修改 `scripts/fetch_news.py` 中的搜索关键词可调整新闻来源范围
- 修改 `scripts/summarize.py` 中的 prompt 可调整总结风格
- 修改 `style.css` 可调整网站外观

## License

MIT
