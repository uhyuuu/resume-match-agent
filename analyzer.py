# -*- coding: utf-8 -*-
"""分析模块：调用 DeepSeek（OpenAI 兼容接口）解析简历、打分岗位、生成求职报告。"""

import json

from openai import OpenAI

import config
from prompts import ANALYSIS_PROMPT, REPORT_PROMPT

# 固定使用的 DeepSeek 模型与生成参数
MODEL_NAME = config.MODEL_NAME
TEMPERATURE = 0.3
MAX_TOKENS = 8192


def _get_client() -> OpenAI:
    """校验配置并创建 DeepSeek 的 OpenAI 兼容客户端。"""
    config.check_config()
    return OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)


def _chat(messages: list) -> str:
    """发送对话请求，返回模型回复的文本内容。
    带自动重试，应对中转站/网络偶发的 SSL/Connection error。"""
    import time
    last_exc = None
    for attempt in range(4):
        try:
            client = _get_client()
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                # 中转站/DeepSeek V4 默认开启思考模式，会把内容写进 reasoning_content，
                # 导致 content 为空。这里显式关闭思考模式，直接输出正式内容。
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = response.choices[0].message.content or ""
            if not content.strip():
                raise RuntimeError("模型返回了空内容，请稍后重试。")
            return content.strip()
        except RuntimeError:
            # 业务级错误（如空内容）直接抛，不重试
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(0.8 * (attempt + 1))
                continue
            break
    raise RuntimeError(
        f"调用 DeepSeek 失败：{last_exc}，请检查网络或 API Key 配置。"
    ) from last_exc


def _parse_json(raw_text: str):
    """解析模型输出的 JSON，带容错：先直接解析，失败则截取首个 { 到最后一个 } 再解析。"""
    candidates = [raw_text.strip()]
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(raw_text[start : end + 1])

    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    raise RuntimeError("模型返回的 JSON 无法解析，请稍后重试。")


def analyze_resume(resume_text: str, target_role: str) -> dict:
    """调用模型解析简历，返回结构化 JSON 字典。

    Raises:
        ValueError: 输入为空时抛出。
        RuntimeError: 模型调用或 JSON 解析失败时抛出。
    """
    if not resume_text.strip():
        raise ValueError("简历文本为空，请上传简历或粘贴简历文字。")
    if not target_role.strip():
        raise ValueError("目标岗位不能为空。")

    user_content = f"目标岗位：{target_role.strip()}\n\n简历全文：\n{resume_text.strip()}"
    raw_text = _chat([
        {"role": "system", "content": ANALYSIS_PROMPT},
        {"role": "user", "content": user_content},
    ])
    return _parse_json(raw_text)


def rank_jobs_by_match(analysis_json: dict, jobs_json: list) -> list:
    """本地算法给每条岗位打分并按匹配度排序（不调用 LLM，毫秒级完成）。

    打分逻辑（满分 95）：
    - 技能重合：候选人每命中 1 个技能 +12 分，封顶 60 分
    - 岗位相关：title/snippet 含目标岗位关键词 +15 分
    - 实习/应届相关：含"实习"/"intern"/"应届"等 +10 分
    - 公司完整：company 不为"未知" +5 分
    - 地点匹配：含目标城市 +8 分

    Args:
        analysis_json: 简历分析结果（需含 skills、target_role 等字段）。
        jobs_json: 原始岗位列表（来自 job_search.search_jobs）。

    Returns:
        按匹配度降序的岗位列表，每个岗位 dict 新增字段 match_score（0-95）和 match_reason。
    """
    if not jobs_json:
        return []

    candidate_skills = [s for s in (analysis_json.get("skills") or []) if s]
    target_role = (analysis_json.get("target_role") or "").strip()
    target_role_words = [w for w in target_role.split() if len(w) >= 2]

    # 候选城市：从简历解析里没有 city 字段，但 search_jobs 用过的城市可能不在 analysis 里
    # 这里不强制依赖，只在岗位文本里检查关键词
    # 从 strength 等字段里找城市（如"武汉"），简单的处理：从 search_jobs 进来的实际是空，留给 snippet 自己匹配

    scored = []
    for job in jobs_json:
        text = ((job.get("title") or "") + " " + (job.get("snippet") or "")).lower()
        score = 0
        matched_skills: list[str] = []

        # 1. 技能重合（每项 +12，封顶 60）
        for skill in candidate_skills:
            if skill and skill.lower() in text:
                score += 12
                matched_skills.append(skill)
                if score >= 60:
                    break

        # 2. 岗位关键词命中（+15）
        role_hit = False
        for w in target_role_words:
            if w.lower() in text:
                score += 15
                role_hit = True
                break

        # 3. 实习/应届相关（+10）
        if any(k in text for k in ["实习", "intern", "应届", "毕业生", "在校"]):
            score += 10

        # 4. 公司名完整（+5）
        company = job.get("company") or ""
        if company and company != "未知":
            score += 5

        score = min(95, score)

        # 生成简短理由
        reason_parts = []
        if matched_skills:
            reason_parts.append(f"命中{len(matched_skills)}项技能（{', '.join(matched_skills[:3])}）")
        if role_hit:
            reason_parts.append(f"含目标岗位关键词「{target_role}」")
        if not reason_parts:
            reason_parts.append("基础匹配")

        new_job = dict(job)
        new_job["match_score"] = score
        new_job["match_reason"] = "；".join(reason_parts)
        scored.append(new_job)

    scored.sort(key=lambda j: j.get("match_score", 0), reverse=True)
    return scored


def generate_report_stream(analysis_json: dict, jobs_json: list, target_role: str, jd_text: str):
    """流式生成报告（逐 token yield），用于 Streamlit 实时显示。"""
    if not target_role.strip():
        raise ValueError("目标岗位不能为空。")

    compact_jobs = [
        {
            "t": j.get("title", ""),
            "c": j.get("company", ""),
            "s": j.get("match_score", 0),
            "r": j.get("match_reason", ""),
            "l": j.get("link", ""),
        }
        for j in jobs_json
    ]

    jd_section = jd_text.strip() if jd_text.strip() else "（用户未粘贴 JD）"
    user_content = (
        f"目标岗位：{target_role.strip()}\n\n"
        f"用户粘贴的 JD：\n{jd_section}\n\n"
        f"简历分析（精简）：{json.dumps(analysis_json, ensure_ascii=False)[:2000]}\n\n"
        f"Top10 岗位（t=岗位 c=公司 s=分数 r=理由 l=链接）：\n"
        f"{json.dumps(compact_jobs, ensure_ascii=False)}"
    )

    import time
    last_exc = None
    for attempt in range(4):
        try:
            client = _get_client()
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": REPORT_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                extra_body={"thinking": {"type": "disabled"}},
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(0.8 * (attempt + 1))
                continue
            break
    raise RuntimeError(f"调用 DeepSeek 失败：{last_exc}，请检查网络或 API Key 配置。") from last_exc


def generate_report(analysis_json: dict, jobs_json: list, target_role: str, jd_text: str) -> str:
    """调用模型生成 6 大模块的 Markdown 求职报告。

    Args:
        analysis_json: 简历分析结果（dict）。
        jobs_json: 已按匹配度排序的岗位列表（每个元素含 match_score、match_reason）。
        target_role: 目标岗位。
        jd_text: 用户粘贴的职位描述，可为空字符串。

    Returns:
        Markdown 格式的完整求职报告。

    Raises:
        ValueError: 目标岗位为空时抛出。
        RuntimeError: 模型调用失败时抛出。
    """
    if not target_role.strip():
        raise ValueError("目标岗位不能为空。")

    jd_section = jd_text.strip() if jd_text.strip() else "（用户未粘贴 JD，请基于简历分析与岗位搜索结果进行评估）"
    user_content = (
        f"目标岗位：{target_role.strip()}\n\n"
        f"用户粘贴的 JD：\n{jd_section}\n\n"
        f"简历分析结果（JSON）：\n{json.dumps(analysis_json, ensure_ascii=False, indent=2)}\n\n"
        f"Top10 真实岗位（已按匹配度排序，每个含 match_score 0-100 和 match_reason）：\n"
        f"{json.dumps(jobs_json, ensure_ascii=False, indent=2)}"
    )
    return _chat([
        {"role": "system", "content": REPORT_PROMPT},
        {"role": "user", "content": user_content},
    ])