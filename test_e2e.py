# -*- coding: utf-8 -*-
"""端到端自测脚本：不依赖 Streamlit UI，直接验证核心链路。"""
import json

import config
import job_search
from analyzer import analyze_resume, generate_report

print("=" * 60)
print("第 1 步：检查配置")
config.check_config()
print("✅ 配置齐全（DeepSeek + SerpAPI）")

print("=" * 60)
print("第 2 步：简历分析（DeepSeek）")
RESUME = """张三，XX大学信息管理与信息系统专业本科，2027年毕业。
技能：Axure、Figma、SQL、Python、用户调研、数据分析。
项目经历：校园二手交易平台产品设计，负责需求调研与原型设计，用户量500+；
小程序电商实习，负责竞品分析与功能迭代，转化率提升15%。
优势：需求分析能力、数据分析能力；不足：无大厂实习经历、项目管理经验少。"""

analysis = analyze_resume(RESUME, "产品经理实习生")
print("✅ 分析结果:")
print(json.dumps(analysis, ensure_ascii=False, indent=2))

print("=" * 60)
print("第 3 步：实时搜岗（SerpAPI）")
search_query = analysis.get("search_query") or "产品经理实习"
print(f"搜索词：{search_query}")
jobs = job_search.search_jobs(search_query)
if not jobs:
    en_query = analysis.get("search_query_en") or "product manager intern"
    print(f"中文关键词无结果，改用英文关键词：{en_query}")
    jobs = job_search.search_jobs(en_query)
print(f"✅ 获取到 {len(jobs)} 条岗位")
if jobs:
    for j in jobs[:3]:
        print(f"  - {j['title']} | {j['company_name']} | {j['location']}")

print("=" * 60)
print("第 4 步：生成 6 大模块报告（DeepSeek）")
report = generate_report(analysis, jobs, "产品经理实习生", "")
print("✅ 报告生成完毕，长度:", len(report))
print(report[:1500])
print("...（报告较长，已截断显示）")

print("=" * 60)
print("🎉 端到端测试全部通过！")
