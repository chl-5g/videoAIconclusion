"""通过 OpenAI 兼容 Chat Completions API 生成摘要（支持 DeepSeek、Ollama 等）。"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def summarize_transcript(
    transcript: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = 120.0,
) -> str:
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("未设置 OPENAI_API_KEY，无法生成总结。")
        raise ValueError("未设置 OPENAI_API_KEY，无法调用大模型总结。")

    base = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model_name = model or os.environ.get("LLM_MODEL") or "gpt-4o-mini"
    url = f"{base}/chat/completions"
    logger.info("调用总结接口：base=%s model=%s", base, model_name)

    system = (
        "你是专业的音视频内容编辑。请根据用户提供的逐字稿，"
        "用中文输出：1) 一句话核心结论 2) 要点列表（带编号）3) 可选：关键术语或数字。"
        "不要编造逐字稿里没有的信息。"
    )
    user = "以下为视频/音频的转写文本，请总结：\n\n" + transcript

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, content=json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    logger.info("总结接口响应状态：%s", r.status_code)
    r.raise_for_status()
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        logger.error("无法解析 API 响应：%r", data)
        raise RuntimeError(f"无法解析 API 响应：{data!r}") from e
