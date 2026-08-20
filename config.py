# -*- coding: utf-8 -*-
"""配置模块：统一读取 API 密钥。
取值顺序：Streamlit 云 Secrets（st.secrets）→ 系统环境变量 → 项目根目录 .env 文件。
本地开发用 .env；部署到 Streamlit 云后改为云端 Secrets，本模块自动兼容两者。"""

import os
from pathlib import Path

from dotenv import load_dotenv

try:
    import streamlit as st
except Exception:  # 非 Streamlit 环境（如命令行脚本）时不影响
    st = None

# 项目根目录（config.py 所在目录）
BASE_DIR = Path(__file__).resolve().parent

# 加载 .env 文件（本地开发用；云端由 Secrets 提供，无需 .env）
load_dotenv(BASE_DIR / ".env")


def _get_secret(name: str) -> str:
    """按 Streamlit Secrets → 环境变量 的顺序取值。"""
    if st is not None:
        try:
            value = st.secrets.get(name, "")
            if value:
                return str(value).strip()
        except Exception:
            pass
    return os.getenv(name, "").strip()


DEEPSEEK_API_KEY = _get_secret("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = _get_secret("DEEPSEEK_BASE_URL")
SERPAPI_API_KEY = _get_secret("SERPAPI_API_KEY")

# 可选：DeepSeek 模型名。若中转站提示「模型未部署 / No available channel」，
# 可到中转站控制台查可用的模型名，在这里（或云端 Secrets 的 MODEL_NAME）替换。
MODEL_NAME = _get_secret("MODEL_NAME") or "deepseek-v4-flash"


def refresh() -> None:
    """重新读取所有密钥。

    云端在应用运行期间才保存 Secrets 时，模块级变量可能还是旧值；
    每次检查前 refresh 一次，确保拿到最新密钥。
    """
    global DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, SERPAPI_API_KEY, MODEL_NAME
    DEEPSEEK_API_KEY = _get_secret("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = _get_secret("DEEPSEEK_BASE_URL")
    SERPAPI_API_KEY = _get_secret("SERPAPI_API_KEY")
    MODEL_NAME = _get_secret("MODEL_NAME") or "deepseek-v4-flash"


def check_config() -> bool:
    """检查必需的密钥是否齐全，缺失时抛出清晰的中文报错提示。"""
    refresh()
    missing = []
    if not DEEPSEEK_API_KEY:
        missing.append("DEEPSEEK_API_KEY（DeepSeek API Key）")
    if not DEEPSEEK_BASE_URL:
        missing.append("DEEPSEEK_BASE_URL（DeepSeek 接口地址）")
    if not SERPAPI_API_KEY:
        missing.append("SERPAPI_API_KEY（SerpAPI Key）")

    if missing:
        raise RuntimeError(
            "缺少必需的环境变量：" + "、".join(missing)
            + "。本地请在项目根目录的 .env 文件中填写；"
            + "部署到 Streamlit 云后请在云端 Secrets 中填写，然后刷新页面重试。"
        )
    return True
