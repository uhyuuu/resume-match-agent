# -*- coding: utf-8 -*-
"""搜岗模块：通过 SerpAPI 的 Google 搜索引擎 + site:www.zhipin.com 限定，
实时搜索 BOSS 直聘上的国内岗位（无需爬虫，搜索结果是公开的）。"""

import datetime
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

# SerpAPI 请求地址与默认参数
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
MAX_JOBS = 15
SNIPPET_MAX_LENGTH = 200
REQUEST_TIMEOUT = 30

# 最终希望返回的在招岗位条数（Google 对 site: 限定每页最多约 10 条）
TARGET_JOBS = 10

# 页面距今天数超过该值视为"过时"：长期未被搜索引擎重新收录的岗位页，大概率已停止招聘
STALE_DAYS = 90

# 追加到搜索词里的负向关键词，让搜索引擎直接排除明显"已停止招聘"的结果
_NEGATIVE_QUERY_TERMS = (
    "已停止", "已关闭", "已下架", "停止招聘",
    "招聘已结束", "已失效", "暂停招聘",
)

# 默认限定站点（可改成 lagou.com、51job.com 等其他招聘平台）
DEFAULT_SITE = "www.zhipin.com"


def _create_session() -> requests.Session:
    """创建带自动重试的 requests Session，应对海外 API 的间歇性 SSL/网络抖动。"""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.6,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = _create_session()


def search_jobs(query: str, site: str = DEFAULT_SITE) -> list:
    """按搜索词调用 SerpAPI（Google 引擎 + site 限定），返回精简后的岗位列表。

    Args:
        query: 岗位搜索关键词，例如"产品经理 武汉"。
        site: 限定搜索的招聘网站域名，默认 www.zhipin.com（BOSS 直聘）。

    Returns:
        岗位信息列表，每条包含 title（岗位名）、company（公司名）、
        location（地点）、salary（薪资）、link（详情链接）、snippet（摘要）。

    Raises:
        ValueError: 搜索词为空时抛出。
        RuntimeError: 网络请求失败时抛出。
    """
    query = (query or "").strip()
    if not query:
        raise ValueError("岗位搜索词不能为空，请先填写目标岗位。")

    # 限定到 BOSS 直聘的具体岗位详情页（/job_detail/...），避免搜到聚合列表页；
    # 同时追加负向关键词，让搜索引擎直接排除"已停止/已关闭/已下架"这类结果。
    negative_terms = " ".join(f"-{term}" for term in _NEGATIVE_QUERY_TERMS)
    full_query = f"site:{site}/job_detail {query} {negative_terms}".strip()
    base_params = {
        "engine": "google",
        "q": full_query,
        "api_key": config.SERPAPI_API_KEY,
        "hl": "zh-cn",
        "gl": "cn",
        "num": MAX_JOBS,
    }

    # 第一页：拉取搜索引擎收录的岗位详情页
    results = _fetch_organic_results(base_params, start=0)
    simplified: list[dict] = []
    for item in results:
        result = _simplify_result(item)
        if result is not None:
            simplified.append(result)

    # 过滤后不够时，翻到第二页补充候选（Google 对 site: 限定每页约 10 条）
    if len(simplified) < TARGET_JOBS:
        try:
            more_results = _fetch_organic_results(base_params, start=10)
        except RuntimeError:
            more_results = []
        for item in more_results:
            if len(simplified) >= TARGET_JOBS:
                break
            result = _simplify_result(item)
            if result is not None:
                simplified.append(result)

    # 并发访问每个 job_detail URL 二次确认（能打开且无"已关闭"字样才算在招）
    with ThreadPoolExecutor(max_workers=6) as pool:
        active_flags = list(pool.map(
            lambda job: _verify_job_active(
                job.get("link", ""), session=_create_session()
            ),
            simplified,
        ))
    verified = [job for job, active in zip(simplified, active_flags) if active]
    return verified[:MAX_JOBS]


def _fetch_organic_results(params: dict, start: int = 0) -> list:
    """调用 SerpAPI 拉取 Google 搜索结果，返回 organic_results 列表。"""
    request_params = dict(params)
    if start:
        request_params["start"] = start
    try:
        response = SESSION.get(SERPAPI_ENDPOINT, params=request_params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"岗位搜索请求失败：{exc}，请检查网络连接或 SerpAPI 配置。") from exc
    except ValueError as exc:
        raise RuntimeError("岗位搜索接口返回的数据无法解析，请稍后重试。") from exc

    if isinstance(data, dict) and data.get("error"):
        return []
    return (data.get("organic_results") or []) if isinstance(data, dict) else []


def _verify_job_active(
    url: str, timeout: int = 3, session: requests.Session | None = None
) -> bool:
    """访问 BOSS 详情页验证岗位是否仍在招（True=仍在招，False=已关闭）。
    注意：BOSS 直聘会对普通请求一律 302 跳转到"安全校验页"，此时拿不到真实
    岗位状态，只能保守保留，交给搜索关键词与新鲜度过滤来兜底。
    """
    if not url or "/job_detail/" not in url:
        return True  # 非 job_detail URL 跳过验证
    try:
        sess = session or SESSION
        resp = sess.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            timeout=timeout,
            allow_redirects=False,
        )
        if resp.status_code == 404:
            return False  # 页面已不存在，视为已停止招聘
        if resp.status_code != 200:
            return True  # 302 安全校验页等无法判断，保守保留
        body = resp.text
        for kw in ("职位已关闭", "已停止招聘", "停止招聘", "招聘已结束",
                   "该职位已下线", "已失效", "已下架"):
            if kw in body:
                return False
        return True
    except Exception:
        return True  # 网络异常时保守保留


# 已关闭/过期岗位的关键词（出现在标题或摘要中即视为不可投）
_CLOSED_KEYWORDS = (
    "职位已关闭", "已关闭", "已停止", "已停止招聘", "停止招聘", "招聘已结束",
    "该职位已下线", "已过期", "已结束招聘", "已失效", "暂停招聘", "已下架", "下架",
)


def _is_closed_job(full_text: str, title: str) -> bool:
    """判断岗位是否已关闭/过期。"""
    for kw in _CLOSED_KEYWORDS:
        if kw in full_text:
            return True
    return False


# BOSS 直聘为做 SEO 生成的"模板页"标题特征（如"什么是产品经理""XX岗位职责""XX工资待遇"）。
# 这类页面不是真实的在招岗位详情，点进去往往是已停止招聘的内容，一律过滤掉。
_SEO_TITLE_MARKERS = (
    "什么是", "是什么职位", "是什么", "是做什么的", "有前途", "怎么样",
    "前景", "岗位职责", "工作职责", "任职要求", "工资待遇", "招聘工资",
    "招聘要求", "工作内容", "面试经验", "薪资待遇", "职业发展",
)


def _is_seo_page(title: str) -> bool:
    """判断标题是否为 BOSS 生成的 SEO 模板页（非真实在招岗位）。"""
    title = (title or "").strip()
    if not title:
        return False
    if title.endswith("职责"):  # 如"阿里国际-产品经理(AI产品方向)-杭州职责"
        return True
    return any(marker in title for marker in _SEO_TITLE_MARKERS)


def _parse_recency_days(date_str: str) -> int | None:
    """把 Google 结果的日期字段（如"5天前""2026年8月5日"）换算为距今天数，解析失败返回 None。"""
    s = (date_str or "").strip()
    if not s:
        return None
    today = datetime.date.today()
    for pattern, unit in (("天前", 1), ("周前", 7), ("个月前", 30)):
        match = re.search(rf"(\d+)\s*{pattern}", s)
        if match:
            return int(match.group(1)) * unit
    if s in ("今天", "昨日", "昨天"):
        return 0 if s == "今天" else 1
    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return (today - datetime.date(year, month, day)).days
        except ValueError:
            return None
    return None


def _simplify_result(item: dict) -> dict | None:
    """从 Google 搜索结果中提取岗位关键字段。
    返回 None 表示该岗位已关闭/过期/不是真实在招岗位，应过滤掉。"""
    raw_title = (item.get("title") or "").strip()
    link = (item.get("link") or "").strip()
    snippet = (item.get("snippet") or "").strip()

    # 只保留 BOSS 岗位详情页，过滤聚合列表页等其他链接
    if "/job_detail/" not in link:
        return None

    # 过滤 SEO 模板页（不是真实在招岗位）
    if _is_seo_page(raw_title):
        return None

    # 过滤已关闭/过期岗位（标题或摘要含"已停止/已关闭/已下架"等）
    full_text = raw_title + " " + snippet
    if _is_closed_job(full_text, raw_title):
        return None

    # 过滤过时页面：距今天数超过阈值，大概率已停止招聘
    recency_days = _parse_recency_days(item.get("date") or "")
    if recency_days is not None and recency_days > STALE_DAYS:
        return None

    if len(snippet) > SNIPPET_MAX_LENGTH:
        snippet = snippet[:SNIPPET_MAX_LENGTH] + "……"

    job_title, company = _split_title_and_company(raw_title)
    salary = _extract_salary(snippet)
    location = _extract_location(snippet, raw_title)

    return {
        "title": job_title,
        "company": company or "未知",
        "location": location,
        "salary": salary,
        "link": link,
        "snippet": snippet,
        "date": (item.get("date") or ""),
    }


_JOB_KEYWORDS = (
    "经理", "主管", "总监", "实习生", "助理", "专员", "工程师", "设计师",
    "运营", "产品", "研发", "市场", "销售", "客服", "编辑", "策划", "顾问",
    "Architect", "Manager", "Engineer", "Intern",
)


def _looks_like_job(text: str) -> bool:
    """判断一段文本是否更像"岗位名"而非"公司名"。"""
    return any(kw in text for kw in _JOB_KEYWORDS)


def _split_title_and_company(raw_title: str) -> tuple[str, str]:
    """智能拆分标题为 (岗位名, 公司名)。

    Google 搜索 BOSS 岗位的结果标题常见格式：
      "AI产品经理—武汉- 小米招聘"          ← 岗位—城市—公司
      "产品经理实习生 - 字节跳动 - Boss直聘" ← 岗位—公司—平台
      "产品经理实习生_腾讯招聘_BOSS直聘"     ← 下划线分隔
      "产品/解决方案实习生-武汉"            ← 岗位-城市（无公司信息）
    """
    if not raw_title:
        return "", ""

    # 去掉末尾的招聘平台/招聘后缀
    cleaned = re.sub(r"[-_｜|·\s]*(BOSS\s*直聘|Boss\s*直聘|boss\s*直聘|招聘)$", "", raw_title)

    # 用正则统一拆分：所有可能的分隔符都识别（包括无空格情况）
    parts = [p.strip() for p in re.split(
        r"\s*[\-—–—_-]\s*|\s*[｜|]\s*|\s*[·]\s*",
        cleaned,
    ) if p.strip()]

    if len(parts) < 2:
        return cleaned, ""

    # 规则 1：3 段及以上
    if len(parts) >= 3:
        # 公司名候选：最后一段，若最后一段是城市则用倒数第二段
        last = parts[-1]
        company = parts[-2] if _is_city(last) else last
        # 如果候选还是像岗位名（如"产品/解决方案"），说明标题里没有公司
        if _looks_like_job(company):
            company = ""
        job_title = _strip_trailing_city(parts[0]) or parts[0]
        return job_title, company

    # 规则 2：恰好 2 段
    head, tail = parts[0], parts[1]
    if _is_city(tail):
        # 格式是"岗位—城市"，无公司信息
        return _strip_trailing_city(head) or head, ""
    # 尾段不是城市 → 尾段就是公司
    return _strip_trailing_city(head) or head, tail


_CITY_RE_TAIL = re.compile(
    r"[-_]\s*(?:北京|上海|广州|深圳|杭州|成都|武汉|南京|苏州|西安|重庆|天津|厦门|福州|青岛|济南|合肥|郑州|长沙|东莞|佛山|宁波|无锡|沈阳|大连|哈尔滨|长春|石家庄|太原|南昌|南宁|昆明|贵阳|海口|兰州|银川|西宁|乌鲁木齐|拉萨|香港|远程)(?:[·-][^-\s]{0,8})?\s*$"
)


def _strip_trailing_city(text: str) -> str:
    """从岗位文本尾部去掉城市部分。"""
    return _CITY_RE_TAIL.sub("", text).strip(" -—_")


_KNOWN_CITY_SET = frozenset({
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "苏州",
    "西安", "重庆", "天津", "厦门", "福州", "青岛", "济南", "合肥", "郑州",
    "长沙", "东莞", "佛山", "宁波", "无锡", "沈阳", "大连", "哈尔滨", "长春",
    "石家庄", "太原", "南昌", "南宁", "昆明", "贵阳", "海口", "兰州", "银川",
    "西宁", "乌鲁木齐", "拉萨", "香港", "远程",
})


def _is_city(text: str) -> bool:
    """判断一段文本是否就是城市名（用于从标题里排除城市，提取公司名）。"""
    base = text.split("-")[0].split("·")[0].strip()
    return base in _KNOWN_CITY_SET


_SALARY_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?\s*[-~到至]\s*\d+(?:\.\d+)?\s*[Kk万])\s*·?\s*(\d+\s*薪)?"
    r"|(\d+(?:\.\d+)?\s*元\s*/\s*[天小时月年])"
    r"|(\d+\s*[-~到至]\s*\d+\s*元\s*/\s*[天小时月年])"
)


def _extract_salary(snippet: str) -> str:
    """从摘要中提取薪资信息。"""
    if not snippet:
        return ""
    match = _SALARY_PATTERN.search(snippet)
    if match:
        return match.group(0).strip()
    return ""


_KNOWN_CITIES = (
    "北京|上海|广州|深圳|杭州|成都|武汉|南京|苏州|西安|重庆|天津|厦门|福州|青岛|济南|合肥|郑州|长沙|东莞|佛山|宁波|无锡|沈阳|大连|哈尔滨|长春|石家庄|太原|南昌|南宁|昆明|贵阳|海口|兰州|银川|西宁|乌鲁木齐|拉萨|香港"
)
_LOCATION_PATTERN = re.compile(
    rf"((?:{_KNOWN_CITIES})(?:[-·][^-\s,，]{{0,8}})?)"
)


def _extract_location(snippet: str, title: str) -> str:
    """从摘要或标题中提取地点。"""
    for text in (title, snippet):
        if not text:
            continue
        match = _LOCATION_PATTERN.search(text)
        if match:
            return match.group(1).strip()
    return ""


# ================= 实时在招岗位搜索（SerpAPI Google Jobs 引擎） =================
# Google Jobs 聚合的是各招聘平台【仍在招聘】的岗位，过期岗位会被移除；
# 配合 date_posted 只取最近发布的岗位，能大幅减少"已停止招聘"的结果。
# 结果优先保留 BOSS 直聘，不足时用其他平台的实时岗位补齐（全部为在招）。

GOOGLE_JOBS_LIMIT = 20


def _fetch_serpapi(params: dict) -> dict:
    """统一的 SerpAPI 请求封装：返回 dict，出错时抛 RuntimeError。"""
    try:
        response = SESSION.get(SERPAPI_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"岗位搜索请求失败：{exc}，请检查网络连接或 SerpAPI 配置。") from exc
    except ValueError as exc:
        raise RuntimeError("岗位搜索接口返回的数据无法解析，请稍后重试。") from exc
    if not isinstance(data, dict):
        return {}
    if data.get("error"):
        raise RuntimeError(f"岗位搜索接口返回错误：{data['error']}")
    return data


def _fetch_google_jobs(query: str, city: str = "", date_posted: str = "week") -> list:
    """调用 SerpAPI google_jobs 引擎，返回原始岗位条目列表。"""
    params = {
        "engine": "google_jobs",
        "q": query,
        "api_key": config.SERPAPI_API_KEY,
        "hl": "zh-cn",
        "gl": "cn",
        "google_domain": "google.com",
        "date_posted": date_posted,
        "limit": GOOGLE_JOBS_LIMIT,
    }
    if city and city.strip():
        params["location"] = city.strip()
    data = _fetch_serpapi(params)
    return data.get("jobs") or []


def _simplify_google_job(item: dict) -> dict | None:
    """把 Google Jobs 结果转换为统一岗位字段；已关闭/无效岗位返回 None。"""
    title = (item.get("title") or "").strip()
    if not title:
        return None
    company = (item.get("company_name") or "").strip()
    location = (item.get("location") or "").strip()
    description = (item.get("description") or "").strip()
    ext = item.get("detected_extensions") or {}
    posted_at = str(ext.get("posted_at") or "").strip()
    salary = str(ext.get("salary") or "").strip() or _extract_salary(description)
    via = (item.get("via_page") or "").strip()

    # 详情链接：优先 BOSS 直聘链接（apply_link 可能是 Google 跳转链接）
    apply_link = (item.get("apply_link") or "").strip()
    if "zhipin" not in apply_link.lower():
        for rel in (item.get("related_links") or []):
            url = (rel.get("link") or "").strip()
            if "zhipin" in url.lower():
                apply_link = url
                break

    # 防御性过滤：标题/描述含"已停止/已关闭"等字样
    if _is_closed_job(f"{title} {description}", title):
        return None

    recency_days = _parse_recency_days(posted_at)
    if recency_days is not None and recency_days > STALE_DAYS:
        return None

    return {
        "title": title,
        "company": company or "未知",
        "location": location,
        "salary": salary,
        "link": apply_link,
        "snippet": _make_snippet(description),
        "description": description[:1200],
        "date": posted_at,
        "platform": via or "Google Jobs",
    }


def _make_snippet(description: str, max_len: int = 220) -> str:
    """把岗位描述压缩成单行摘要。"""
    text = re.sub(r"\s+", " ", description or "").strip()
    if len(text) > max_len:
        return text[:max_len] + "……"
    return text


def _is_boss_result(job: dict) -> bool:
    """判断岗位是否来自 BOSS 直聘。"""
    link = (job.get("link") or "").lower()
    platform = (job.get("platform") or "").lower()
    return "zhipin" in link or "boss" in platform or "直聘" in platform


def _dedupe_jobs(jobs: list) -> list:
    """按 (岗位名, 公司名) 去重。"""
    seen = set()
    result = []
    for job in jobs:
        key = (
            (job.get("title") or "").strip().lower(),
            (job.get("company") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(job)
    return result


def search_jobs_live(query: str, city: str = "") -> list:
    """用 Google Jobs 引擎搜索【实时在招】岗位：BOSS 直聘优先，其余平台补齐。

    Args:
        query: 岗位搜索关键词。
        city: 目标城市（可空）。

    Returns:
        岗位信息列表，每条含 title/company/location/salary/link/snippet/
        description/date/platform 字段；优先 BOSS 直聘，按发布时间较新的靠前。
    """
    query = (query or "").strip()
    if not query:
        raise ValueError("岗位搜索词不能为空，请先填写目标岗位。")

    jobs: list[dict] = []
    try:
        raw_items = _fetch_google_jobs(query, city, date_posted="week")
    except RuntimeError:
        raw_items = []
    for item in raw_items:
        job = _simplify_google_job(item)
        if job is not None:
            jobs.append(job)

    # 最近 7 天没有结果时，放宽到最近 1 个月
    if not jobs:
        try:
            raw_items = _fetch_google_jobs(query, city, date_posted="month")
        except RuntimeError:
            raw_items = []
        for item in raw_items:
            job = _simplify_google_job(item)
            if job is not None:
                jobs.append(job)

    jobs = _dedupe_jobs(jobs)
    boss_jobs = [j for j in jobs if _is_boss_result(j)]
    other_jobs = [j for j in jobs if not _is_boss_result(j)]
    return (boss_jobs + other_jobs)[:MAX_JOBS]


def search_jobs_with_fallback(analysis: dict, target_role: str, target_city: str) -> tuple[list, str]:
    """实时在招搜索为主（Google Jobs），旧方案兜底。返回 (岗位列表, 实际使用的搜索词)。"""
    base_query = analysis.get("search_query") or _build_query(target_role, target_city)
    if target_city.strip() and target_city.strip() not in base_query:
        base_query = f"{base_query} {target_city.strip()}".strip()

    # 1) Google Jobs 实时在招（BOSS 直聘优先）
    jobs = search_jobs_live(base_query, target_city)
    if jobs:
        return jobs, base_query

    # 2) 中文没有 → 用英文关键词再试
    en_query = analysis.get("search_query_en")
    if en_query and en_query.strip():
        jobs = search_jobs_live(en_query, target_city)
        if jobs:
            return jobs, en_query

    # 3) 都为空 → 退回搜索引擎收录的 BOSS 详情页方案
    jobs = search_jobs(base_query)
    if jobs:
        return jobs, base_query

    return [], base_query


def _build_query(target_role: str, target_city: str) -> str:
    parts = [target_role.strip()]
    if target_city.strip():
        parts.append(target_city.strip())
    return " ".join(parts)
