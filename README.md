# 智能简历匹配 Agent

一句话简介：上传简历后，自动完成「简历解析 → 智能分析 → 实时搜岗 → 报告生成」的一站式求职工具，最终输出 6 大模块 Markdown 求职报告。

## 功能列表

- **上传简历**：支持 PDF / DOCX / TXT，也可直接粘贴简历文字
- **智能解析**：提取候选人画像、技能、经历、优劣势，并自动生成岗位搜索关键词
- **实时搜岗**：通过 SerpAPI + Google 实时搜索 BOSS 直聘岗位（最多 10 条），自动过滤「已停止/已关闭/已下架」等失效岗位和 SEO 模板页，只保留仍在招的真实岗位
- **6 大模块报告**（由 DeepSeek 生成，支持 Markdown 表格渲染）：
  1. 简历经历速览
  2. Top 5 最匹配岗位（含 0-100 匹配度打分与理由）
  3. 薪资档位分析（低 / 中 / 高 + 影响因素）
  4. 能力差距矩阵（6-8 项能力，标出差距最大 3 项）
  5. 分级学习路线图（P0 本周 / P1 本月 / P2 1-3 个月 / P3 长期）
  6. 本周可投递行动计划（5 个岗位 + 投递渠道 + 建议时间 + 3 条简历优化建议）

## 技术栈

- **Streamlit**：网页界面
- **openai**：调用 DeepSeek（OpenAI 兼容接口，模型 `deepseek-v4-flash`）
- **SerpAPI + requests**：Google Jobs 实时岗位搜索
- **pypdf / python-docx**：PDF / DOCX 简历解析
- **python-dotenv**：读取 `.env` 环境变量

## 环境要求

- Python 3.13
- 网络可访问 DeepSeek 与 SerpAPI 接口

## 安装与运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

启动后浏览器会自动打开应用页面。

## .env 配置说明

在项目根目录创建 `.env` 文件（参考 `.env.example` 模板），填写以下变量：

```ini
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://xcode.best/v1
SERPAPI_API_KEY=你的 SerpAPI API Key
```

> 提示：`.env` 包含真实密钥，已被 `.gitignore` 忽略，请勿提交到版本库；代码统一通过 `config.py` 读取环境变量，不硬编码任何密钥。



## 部署到 Streamlit 云（无需电脑在线，用链接随处访问）

本应用已适配云端：密钥优先读 Streamlit 云 Secrets，本地自动回退到 `.env`，代码无需改动。

### 第 1 步：把代码推到 GitHub

```bash
git init
git add .
git commit -m "初始化智能简历匹配 Agent"
git branch -M main
git remote add origin https://github.com/<你的GitHub用户名>/resume-match-agent.git
git push -u origin main
```

> 注意：`.env`（真实密钥）和 `开发需求*.txt`（含密钥的历史文档）已被 `.gitignore` 排除，不会上传到 GitHub。

### 第 2 步：在 Streamlit 云创建应用

1. 打开 <https://share.streamlit.io>，用 GitHub 账号登录；
2. 点击 **New app** → 选择刚推上去的仓库 `resume-match-agent`；
3. 分支选 `main`，主文件填 `app.py`，点击 **Deploy**；
4. 部署完成后进入 **Settings → Secrets**，填入以下内容（值换成你自己的密钥）：

```toml
DEEPSEEK_API_KEY = "你的 DeepSeek API Key"
DEEPSEEK_BASE_URL = "https://xcode.best/v1"
SERPAPI_API_KEY = "你的 SerpAPI Key"
```

5. 保存 Secrets 后点 **Rerun**（或重新打开应用），即可获得公网链接，任何设备都能访问。
