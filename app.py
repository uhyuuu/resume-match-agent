# -*- coding: utf-8 -*-
"""智能简历匹配 Agent：Streamlit 网页应用主程序（极简黑白设计语言）。"""

import streamlit as st

import config
import importlib
import job_search
from analyzer import analyze_resume, generate_report, generate_report_stream, rank_jobs_by_match
from resume_parser import parse_resume

# 云端密钥/代码更新后，确保每次运行都重新读取最新配置（避免进程缓存旧值）
importlib.reload(config)

# ---------- 页面配置 ----------
st.set_page_config(
    page_title="智能简历匹配 Agent",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- 全局 CSS（注入一次） ----------
CSS_STYLES = """
<style>
:root {
    --bg: #ffffff;
    --bg-soft: #fafafa;
    --ink: #0a0a0a;
    --ink-2: #525252;
    --ink-3: #a3a3a3;
    --border: #e5e5e5;
    --radius: 12px;
    --font: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", "PingFang SC",
            "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
}

html, body, .stApp {
    background: var(--bg);
    color: var(--ink-2);
    font-family: var(--font);
    font-size: 15px;
    line-height: 1.6;
}

.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    color: var(--ink) !important;
    font-weight: 500 !important;
    letter-spacing: -0.01em;
}

/* ---------- Hero：左侧大标题 + 右侧极简状态，纯白底 ---------- */
.hero {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 40px;
    padding: 12px 0 40px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 48px;
}
.hero-title {
    font-size: 30px !important;
    font-weight: 500 !important;
    letter-spacing: -0.02em;
    color: var(--ink) !important;
    margin: 0 0 10px;
}
.hero-sub {
    font-size: 15px !important;
    color: var(--ink-2) !important;
    margin: 0;
}
.hero-status { text-align: right; flex-shrink: 0; }
.status-row {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    font-size: 13px;
    font-weight: 500;
    color: var(--ink-2);
}
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: #000; }
.status-meta { font-size: 12px; color: var(--ink-3); margin-top: 6px; }

/* ---------- 卡片：白底 + 1px 边框，hover 时才出淡阴影 ---------- */
.card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px 32px;
    margin-bottom: 40px;
    transition: box-shadow 0.2s ease;
}
.card:hover { box-shadow: 0 10px 30px rgba(0, 0, 0, 0.06); }

/* 区块标题：序号 + 标题 + 底部细线 */
.section-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-bottom: 14px;
    margin-bottom: 24px;
    border-bottom: 1px solid var(--border);
}
.section-num {
    font-size: 12px;
    color: var(--ink-2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1px 7px;
}
.section-title { font-size: 16px; font-weight: 500; color: var(--ink); }

/* ---------- 进度条：横向 4 步，灰底细线，完成=纯黑 ---------- */
.step-track {
    display: flex;
    align-items: center;
    margin: 8px 0 48px;
}
.step {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--ink-3);
    white-space: nowrap;
}
.step.done, .step.current { color: var(--ink); font-weight: 500; }
.step-dot {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 1px solid var(--border);
    background: var(--bg);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: var(--ink-3);
    flex-shrink: 0;
}
.step.done .step-dot { background: #000; border-color: #000; color: #fff; }
.step.current .step-dot { border-color: #000; color: #000; }
.step-line { flex: 1; height: 1px; background: var(--border); margin: 0 14px; min-width: 24px; }
.step-line.done { background: #000; }

/* ---------- 候选人画像 ---------- */
.candidate-card {
    display: flex;
    gap: 24px;
    align-items: flex-start;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px 32px;
    margin-bottom: 40px;
    transition: box-shadow 0.2s ease;
}
.candidate-card:hover { box-shadow: 0 10px 30px rgba(0, 0, 0, 0.06); }
.candidate-avatar {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: #000;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    font-weight: 500;
    flex-shrink: 0;
}
.candidate-name { font-size: 24px; font-weight: 500; color: var(--ink); margin: 0 0 6px; }
.candidate-meta { color: var(--ink-2); font-size: 14px; margin: 0 0 18px; }
.candidate-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 14px 28px;
}
.candidate-field { border-top: 1px solid var(--border); padding-top: 10px; }
.candidate-field-label { font-size: 12px; color: var(--ink-3); margin-bottom: 3px; }
.candidate-field-value { font-size: 14px; font-weight: 500; color: var(--ink); }

/* ---------- 岗位卡片：左侧 4px 黑条 + 纯黑徽章 ---------- */
.job-card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-left: 4px solid #000;
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 16px;
    position: relative;
    transition: box-shadow 0.2s ease;
}
.job-card:hover { box-shadow: 0 10px 30px rgba(0, 0, 0, 0.06); }
.job-card-rank {
    position: absolute;
    top: 20px;
    right: 24px;
    background: #000;
    color: #fff;
    font-size: 12px;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: 6px;
}
.job-title { font-size: 17px; font-weight: 500; color: var(--ink); margin: 0 0 6px; }
.job-meta { color: var(--ink-3); font-size: 13px; margin-bottom: 12px; }
.job-meta-item { display: inline-flex; align-items: center; }
.job-meta-sep { margin: 0 10px; color: var(--border); }
.job-reason {
    font-size: 13px;
    color: var(--ink-2);
    line-height: 1.7;
    padding: 4px 0 4px 14px;
    border-left: 2px solid var(--border);
    margin-bottom: 4px;
}
.job-reason .quote-mark { color: var(--ink-3); margin-right: 6px; }
.job-reason b { color: var(--ink); font-weight: 500; }
.job-snippet {
    font-size: 13px;
    color: var(--ink-2);
    line-height: 1.7;
    border-top: 1px solid var(--border);
    padding-top: 12px;
    margin-top: 12px;
}
.job-link { color: #000; font-size: 13px; font-weight: 500; text-decoration: none; }
.job-link:hover { text-decoration: underline; }

/* ---------- 报告区：白底 + 1px 边框，无阴影 ---------- */
.report-card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 40px 44px;
    margin-bottom: 40px;
    box-shadow: none;
}
.stApp .report-card h1 { font-size: 26px !important; }
.stApp .report-card h2 {
    color: var(--ink) !important;
    font-size: 22px !important;
    font-weight: 600 !important;
    border-bottom: 1px solid var(--border);
    padding-bottom: 12px;
    margin: 36px 0 20px;
}
.stApp .report-card h3 {
    color: var(--ink) !important;
    font-size: 16px !important;
    font-weight: 500 !important;
    margin: 24px 0 10px;
}
.report-card table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 14px;
}
.report-card th {
    background: var(--bg-soft);
    color: var(--ink);
    font-weight: 500;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid var(--border);
}
.report-card td {
    border-bottom: 1px solid var(--border);
    padding: 10px 14px;
    color: var(--ink-2);
}
.report-card tr:nth-child(even) td { background: #f5f5f5; }
.report-card ul, .report-card ol { padding-left: 22px; }
.report-card li { margin-bottom: 6px; line-height: 1.7; }
.report-card blockquote {
    border-left: 2px solid #000;
    margin: 16px 0;
    padding: 6px 16px;
    color: var(--ink-2);
    background: transparent;
}
.report-card strong { color: var(--ink); font-weight: 600; }
.report-card hr { border: none; border-top: 1px solid var(--border); margin: 28px 0; }

/* ---------- 空状态 ---------- */
.empty-state { text-align: center; padding: 80px 20px; }
.empty-state-icon { font-size: 56px; margin-bottom: 20px; opacity: 0.35; }
.empty-state-title { font-size: 17px; font-weight: 500; color: var(--ink); margin-bottom: 8px; }
.empty-state-desc { font-size: 13px; color: var(--ink-3); }

/* ---------- 侧边栏 ---------- */
[data-testid="stSidebar"] {
    background: var(--bg-soft);
    border-right: 1px solid var(--border);
}
.sidebar-brand {
    text-align: center;
    padding: 14px 0;
    color: var(--ink);
    font-size: 15px;
    font-weight: 500;
    letter-spacing: -0.01em;
}

/* ---------- 按钮：纯黑底白字，hover 深灰，通栏 ---------- */
div[data-testid="stElementContainer"]:has(div[data-testid="stButton"]) {
    width: 100% !important;
}
div[data-testid="stButton"] { width: 100% !important; }
div.stButton > button,
div.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {
    background: #000 !important;
    color: #fff !important;
    border: 1px solid #000 !important;
    border-radius: var(--radius) !important;
    padding: 10px 24px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    width: 100% !important;
    transition: background 0.15s ease, border-color 0.15s ease;
}
div.stButton > button:hover,
div.stButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {
    background: #333 !important;
    border-color: #333 !important;
    color: #fff !important;
}
div.stButton > button:focus,
div.stButton > button[kind="primary"]:focus {
    box-shadow: none !important;
}

/* ---------- 输入控件：细边框 + 12px 圆角 ---------- */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: transparent !important;
    color: var(--ink) !important;
    font-size: 14px !important;
    border: none !important;
    box-shadow: none !important;
}
[data-testid="stTextInputRootElement"],
[data-testid="stTextAreaRootElement"] {
    background: var(--bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    transition: border-color 0.15s ease;
}
[data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stTextAreaRootElement"]:focus-within {
    border-color: #000 !important;
    box-shadow: none !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
    color: var(--ink-3) !important;
}

/* 文件上传 */
[data-testid="stFileUploaderDropzone"] {
    background: var(--bg) !important;
    border: 1px dashed var(--border) !important;
    border-radius: var(--radius) !important;
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: #000 !important; }
[data-testid="stFileUploaderDropzone"] button {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--ink);
}
[data-testid="stFileUploaderDropzone"] button:hover {
    border-color: #000;
    color: var(--ink);
}

/* 提示 / 代码块：去彩色，灰底细边框 */
.stAlert {
    background-color: var(--bg-soft) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--ink-2) !important;
}
[data-testid="stCodeBlock"] pre {
    background: var(--bg-soft) !important;
    color: var(--ink-2) !important;
    border: 1px solid var(--border);
    border-radius: var(--radius);
}

/* 分隔线 */
hr { border-color: var(--border); }
</style>
"""

st.markdown(CSS_STYLES, unsafe_allow_html=True)


# ---------- 业务函数 ----------
def run_pipeline(uploaded_file, resume_text_input: str, target_role: str, target_city: str, jd_text: str) -> None:
    """依次执行：解析 → 分析 → 搜岗 → 匹配度打分 → 报告，并在页面中实时展示进度与结果。"""
    progress = st.session_state.get("progress")
    if progress is None:
        progress = [False] * 4
        st.session_state.progress = progress

    try:
        # 第一步：解析简历
        if uploaded_file is not None:
            resume_text = parse_resume(uploaded_file.getvalue(), uploaded_file.name)
        else:
            resume_text = resume_text_input.strip()
            if len(resume_text) < 50:
                raise ValueError("粘贴的简历文字过短，请粘贴完整内容。")
        progress[0] = True
        render_progress(0)

        # 第二步：调用 DeepSeek 分析简历
        analysis = analyze_resume(resume_text, target_role.strip())
        progress[1] = True
        render_progress(1)

        # 第三步：实时搜岗（Google Jobs 实时在招，BOSS 直聘优先）+ 本地匹配度打分
        jobs, used_query = job_search.search_jobs_with_fallback(
            analysis, target_role, target_city
        )
        ranked_jobs = rank_jobs_by_match(analysis, jobs)
        progress[2] = True
        render_progress(2)

        # 第四步：流式生成 6 大模块求职报告（实时显示）
        report_placeholder = st.empty()
        full_report = ""
        with st.spinner("正在生成求职报告（实时显示中）……"):
            for chunk in generate_report_stream(
                analysis, ranked_jobs, target_role.strip(), jd_text.strip()
            ):
                full_report += chunk
                report_placeholder.markdown(full_report + "▌")
        report_placeholder.markdown(full_report)
        report = full_report
        progress[3] = True
        render_progress(3)

        # 渲染结果
        render_results(analysis, ranked_jobs, used_query, report)

    except ValueError as exc:
        st.error(f"输入有误：{exc}")
    except RuntimeError as exc:
        st.error(f"处理失败：{exc}")
    except Exception as exc:
        st.error(f"发生未知错误：{exc}")


def render_progress(current: int) -> None:
    """渲染顶部 4 步进度条。"""
    labels = ["简历解析", "智能分析", "实时搜岗", "生成报告"]
    html = '<div class="step-track">'
    for i, label in enumerate(labels):
        cls = "done" if i < current else ("current" if i == current else "")
        icon = "✓" if i < current else ("●" if i == current else str(i + 1))
        html += (
            f'<div class="step {cls}">'
            f'<span class="step-dot">{icon}</span>'
            f"<span>{label}</span>"
            f"</div>"
        )
        if i < len(labels) - 1:
            line_cls = "done" if i < current else ""
            html += f'<div class="step-line {line_cls}"></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_results(analysis: dict, jobs: list, used_query: str, report: str) -> None:
    """渲染完整结果：候选人画像 + 岗位卡片 + 6 大模块报告。"""
    # 候选人画像卡片
    candidate = analysis.get("candidate") or {}
    name = candidate.get("name") or "候选人"
    avatar = name[0] if name and name != "候选人" else "👤"
    info_lines = []
    if candidate.get("school"):
        info_lines.append(candidate["school"])
    if candidate.get("major"):
        info_lines.append(candidate["major"])
    info_text = " · ".join(info_lines) if info_lines else "信息暂缺"

    fields = []
    if candidate.get("education"):
        fields.append(("学历", candidate["education"]))
    if candidate.get("graduation_year"):
        fields.append(("毕业时间", candidate["graduation_year"]))
    skills = analysis.get("skills") or []
    if skills:
        fields.append(("核心技能", " · ".join(skills[:4])))
    target_role_v = analysis.get("target_role") or ""
    if target_role_v:
        fields.append(("目标岗位", target_role_v))

    field_html = "".join(
        f'<div class="candidate-field"><div class="candidate-field-label">{label}</div>'
        f'<div class="candidate-field-value">{value}</div></div>'
        for label, value in fields
    )
    st.markdown(
        f"""<div class="candidate-card">
            <div class="candidate-avatar">{avatar}</div>
            <div class="candidate-info">
                <p class="candidate-name">{name}</p>
                <p class="candidate-meta">{info_text}</p>
                <div class="candidate-grid">{field_html}</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # 岗位搜索结果
    render_jobs_section(jobs, used_query)

    # 6 大模块报告（Markdown，包在白底细边框容器内）
    st.markdown(
        f'<div class="report-card">## 6 大模块求职报告\n\n{report}\n\n</div>',
        unsafe_allow_html=True,
    )


def render_jobs_section(jobs: list, used_query: str) -> None:
    """渲染岗位搜索结果卡片区（按匹配度排序，展示 Top10）。"""
    if jobs:
        top_jobs = jobs[:10]
        st.markdown(
            f'<div class="section-head" style="margin-top:8px">'
            f'<span class="section-num">Top {len(top_jobs)}</span>'
            f'<span class="section-title">最匹配岗位（按匹配度排序）· 实时在招（BOSS直聘等平台）</span></div>',
            unsafe_allow_html=True,
        )
        for idx, job in enumerate(top_jobs, start=1):
            render_job_card(idx, job)
    else:
        st.warning("搜索结果为空，可能是关键词太具体；建议尝试更通用的岗位名，或在粘贴 JD 处提供具体岗位。")


def render_job_card(rank: int, job: dict) -> None:
    """渲染单个岗位卡片：标题 + 元信息 + 匹配理由 + 摘要 + 链接。"""
    title = job.get("title") or "未命名岗位"
    company = job.get("company") or "未知公司"
    location = job.get("location") or "地点未披露"
    salary = job.get("salary") or "薪资面议"
    snippet = job.get("snippet") or ""
    link = job.get("link") or ""
    score = int(job.get("match_score") or 0)
    reason = job.get("match_reason") or ""

    badge_text = f"#{rank} · {score}分"

    meta_parts = [location]
    if salary:
        meta_parts.append(salary)
    meta_parts.append(company)
    platform = job.get("platform") or ""
    if platform and platform != "Google Jobs":
        meta_parts.append(platform)
    meta_html = ""
    for i, part in enumerate(meta_parts):
        if i:
            meta_html += '<span class="job-meta-sep">·</span>'
        meta_html += f'<span class="job-meta-item">{part}</span>'

    reason_html = (
        f'<div class="job-reason"><span class="quote-mark">“</span>'
        f'<b>匹配理由：</b>{reason}</div>'
        if reason else ""
    )

    link_html = (
        f'<a class="job-link" href="{link}" target="_blank">查看详情 →</a>' if link else ""
    )

    st.markdown(
        f"""<div class="job-card">
            <span class="job-card-rank">{badge_text}</span>
            <p class="job-title">{title}</p>
            <div class="job-meta">{meta_html}</div>
            {reason_html}
            <div class="job-snippet">{snippet}</div>
            {link_html}
        </div>""",
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    """未生成报告时的占位图。"""
    st.markdown(
        """<div class="empty-state">
            <div class="empty-state-icon">📄</div>
            <div class="empty-state-title">填写左侧信息，开始你的求职分析</div>
            <div class="empty-state-desc">上传简历 → 填写目标岗位 → 点击「生成求职报告」，即可获得 6 大模块个性化求职方案</div>
        </div>""",
        unsafe_allow_html=True,
    )


# ---------- 侧边栏 ----------
with st.sidebar:
    st.markdown('<div class="sidebar-brand">配置中心</div>', unsafe_allow_html=True)
    st.divider()
    st.subheader("使用说明")
    st.markdown(
        "1. 上传简历文件（PDF / DOCX / TXT）或粘贴简历文字\n\n"
        "2. 填写目标岗位（必填）\n\n"
        "3. 选填：目标城市 + 粘贴 JD\n\n"
        "4. 点击「生成求职报告」"
    )
    st.divider()
    st.subheader("配置状态")
    try:
        config.check_config()
        st.success("密钥齐全（本地 .env / 云端 Secrets）")
        with st.expander("当前配置详情"):
            st.code(
                f"模型: {config.MODEL_NAME}\n"
                f"DEEPSEEK_BASE_URL: {config.DEEPSEEK_BASE_URL}\n"
                f"DEEPSEEK_API_KEY: ****{config.DEEPSEEK_API_KEY[-6:]}\n"
                f"SERPAPI_API_KEY: ****{config.SERPAPI_API_KEY[-6:]}",
                language="text",
            )
    except RuntimeError as exc:
        st.error(str(exc))

    st.divider()
    with st.expander("调试信息（排障用）"):
        st.write("密钥来源检查：")
        import os as _os
        try:
            _secret_keys = list(st.secrets.keys())
            st.write("st.secrets 中的键:", _secret_keys if _secret_keys else "（空）")
        except Exception as _e:
            st.write("st.secrets 读取失败:", repr(_e))
        for _k in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "SERPAPI_API_KEY", "MODEL_NAME"):
            _src = ""
            _v = ""
            try:
                _v = st.secrets.get(_k, "")
                if _v:
                    _src = "st.secrets"
            except Exception:
                pass
            if not _v:
                _v = _os.getenv(_k, "")
                if _v:
                    _src = "环境变量"
            st.write(f"{_k}: {'✅ 已设置(' + _src + ')' if _v else '❌ 未设置'}")
        st.write("---")
        try:
            config.refresh()
            st.write("config 重新读取后：")
            st.write(f"DEEPSEEK_API_KEY: {'✅ 已设置' if config.DEEPSEEK_API_KEY else '❌ 空'}")
            st.write(f"DEEPSEEK_BASE_URL: {'✅ 已设置' if config.DEEPSEEK_BASE_URL else '❌ 空'}")
            st.write(f"SERPAPI_API_KEY: {'✅ 已设置' if config.SERPAPI_API_KEY else '❌ 空'}")
            st.write(f"MODEL_NAME: {config.MODEL_NAME}")
        except Exception as _e2:
            st.write("config.refresh 失败:", repr(_e2))


# ---------- 顶部 Hero：左侧标题 + 右侧状态 ----------
st.markdown(
    """<div class="hero">
        <div>
            <h1 class="hero-title">智能简历匹配 Agent</h1>
            <p class="hero-sub">上传简历 → 智能解析 → 实时搜岗 → 一键生成 6 大模块求职报告</p>
        </div>
        <div class="hero-status">
            <div class="status-row"><span class="status-dot"></span>系统就绪</div>
            <div class="status-meta">DeepSeek · 实时在招岗位</div>
        </div>
    </div>""",
    unsafe_allow_html=True,
)


# ---------- 主表单区 ----------
left_col, right_col = st.columns(2, gap="large")

with left_col:
    st.markdown(
        '<div class="section-head"><span class="section-num">01</span>'
        '<span class="section-title">简历输入</span></div>',
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader(
        "上传简历文件",
        type=["pdf", "docx", "txt"],
        help="支持 PDF / DOCX / TXT；扫描件请直接粘贴简历文字。",
    )
    st.markdown("**或**")
    resume_text_input = st.text_area(
        "直接粘贴简历文字",
        height=240,
        placeholder="将简历文字粘贴到这里…",
    )

with right_col:
    st.markdown(
        '<div class="section-head"><span class="section-num">02</span>'
        '<span class="section-title">求职信息</span></div>',
        unsafe_allow_html=True,
    )
    target_role = st.text_input(
        "目标岗位（必填）",
        placeholder="例如：AI 产品经理实习生",
    )
    target_city = st.text_input(
        "目标城市（选填，可让搜岗更精准）",
        placeholder="例如：武汉 / 北京 / 远程",
    )
    jd_text = st.text_area(
        "粘贴 JD（选填，粘贴后报告将按 JD 优先打分）",
        height=160,
        placeholder="如有心仪岗位的 JD，粘贴到这里，匹配度更精准。",
    )

st.markdown("---")
start_button = st.button("生成求职报告", type="primary")

if start_button:
    st.session_state.progress = None
    if not target_role.strip():
        st.error("请先填写「目标岗位」（必填项）。")
    elif uploaded_file is None and not resume_text_input.strip():
        st.error("请上传简历文件，或直接粘贴简历文字。")
    else:
        run_pipeline(uploaded_file, resume_text_input, target_role, target_city, jd_text)
elif "progress" not in st.session_state or not any(st.session_state.progress or []):
    render_empty_state()
else:
    # 刷新或重新进入时，根据 progress 状态重绘进度条
    current = sum(1 for p in st.session_state.progress if p)
    render_progress(current - 1 if current > 0 else 0)
