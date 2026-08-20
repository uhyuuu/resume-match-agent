# 智能简历匹配 Agent

> 上传一份简历，自动完成「简历解析 → 智能分析 → 实时搜岗 → 报告生成」，输出一份 6 大模块的定制求职报告。

**在线体验**：https://resume-match-agent-ajdssphvnasocg3xmxyy3k.streamlit.app/
**代码仓库**：https://github.com/uhyuuu/resume-match-agent

---

## 这是什么

求职者上传简历（PDF / DOCX / TXT，或直接粘贴文字），填写目标岗位和城市，应用会自动完成：

1. **解析简历**：提取候选人画像、技能、经历、优劣势
2. **智能分析**：结合目标岗位自动生成搜索关键词与能力评估
3. **实时搜岗**：只保留「当前正在招聘」的真实岗位（智联招聘为主）
4. **生成报告**：输出 6 大模块求职报告（匹配度打分、薪资分析、能力差距、学习路线、投递计划）

## 核心亮点（给面试官的重点）

### 1. 解决「搜到的岗位一半已停止招聘」的真实痛点
- 第一版方案：搜索引擎收录的 BOSS 直聘缓存页 → **10 个岗位里 8 个已停止招聘**
- 定位问题：搜索引擎索引 ≠ 岗位实时状态，且 Google Jobs 对中国大陆岗位覆盖几乎为零
- 重构方案：通过百度索引找到智联招聘详情页 → 逐条打开并解析页面内嵌 JSON → 用「招聘中状态 + 发布时间新鲜度 + 关闭标记」三重校验，只保留真正在招的岗位
- 结果：返回岗位全部为近期发布的在招岗位，且带完整薪资 / 城市 / 职责描述，匹配打分更准确

### 2. 自动化匹配度打分（0-100 + 理由）
- 本地关键词 / 技能匹配打分，不依赖大模型，速度快、成本低
- 报告再由大模型生成个性化建议，两层结合

### 3. 云端可访问
- 部署到 Streamlit 云，有链接即可演示，不依赖本机在线

## 工作流程

```
简历上传 → 解析(PDF/DOCX/TXT) → DeepSeek 智能分析 → 实时搜岗(智联/BOSS) → 匹配打分 → 6 大模块报告
```

## 技术栈

- **界面 / 框架**：Streamlit
- **大模型**：DeepSeek（OpenAI 兼容接口）
- **实时搜岗**：SerpAPI（百度索引 → 智联招聘详情页核验，Google Jobs 补充）
- **文档解析**：pypdf / python-docx
- **部署**：Streamlit Community Cloud

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

环境变量见 `.env.example`：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`SERPAPI_API_KEY`。

## 目录结构

- `app.py` — 主程序（界面 + 流程编排）
- `job_search.py` — 实时在招岗位搜索与核验
- `analyzer.py` — 简历分析 + 匹配度打分
- `prompts.py` — 报告生成的提示词模板
- `config.py` — 密钥读取（本地 .env / 云端 Secrets）

## 安全说明

密钥通过环境变量 / Streamlit 云 Secrets 管理，`.env` 已被 `.gitignore` 忽略，不会提交到仓库。