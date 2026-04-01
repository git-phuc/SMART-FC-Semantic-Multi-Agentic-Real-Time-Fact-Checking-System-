"""
Cấu hình hệ thống Multi-Agent Fake News Verification.

Thiết kế đơn giản: chỉ cần 3 biến để cấu hình LLM:
  - LLM_BASE_URL: Endpoint API (đổi URL = đổi provider)
  - LLM_API_KEY:  API key tương ứng
  - LLM_MODEL:    Tên model

Hầu hết providers đều hỗ trợ OpenAI-compatible API,
nên chỉ cần 1 class ChatOpenAI là chạy được tất cả.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from dotenv import load_dotenv

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI  # type: ignore[import-untyped]

# Load .env file
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


# ============================================================
# Cấu hình LLM — Gọi thông qua get_llm_for_agent
# ============================================================

def get_llm_for_agent(agent_type: str = "AGENT1") -> ChatOpenAI:
    """
    Khởi tạo LLM client riêng cho từng Agent, lách Rate Limit bằng cách mix AI.
    Đọc biến môi trường theo prefix (VD: AGENT1_BASE_URL, AGENT2_API_KEY).
    Hỗ trợ mọi Provider có chuẩn OpenAI-compatible (Groq, HuggingFace, Gemini via OpenAI SDK).
    """
    base_url = os.getenv(f"{agent_type}_BASE_URL", "https://api.groq.com/openai/v1")
    api_key = os.getenv(f"{agent_type}_API_KEY", "")
    model = os.getenv(f"{agent_type}_MODEL", "llama-3.1-8b-instant")
    temperature = float(os.getenv(f"{agent_type}_TEMPERATURE", "0.1"))
    max_tokens = int(os.getenv(f"{agent_type}_MAX_TOKENS", "4096"))

    # Fallback back compatibility cũ nếu chưa update .env kịp
    if not api_key:
        api_key = os.getenv("LLM_API_KEY", "")

    if not api_key:
        raise ValueError(
            f"{agent_type}_API_KEY chưa được cấu hình.\n"
            f"Mở file .env và bảo đảm đã khai báo API key cho {agent_type}."
        )

    from langchain_openai import ChatOpenAI  # type: ignore[import-untyped]

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        base_url=base_url,
        api_key=api_key,
    )

_gemini_pool_keys = []
_gemini_key_index = 0

_groq_pool_keys = []
_groq_key_index = 0

_hf_pool_keys = []
_hf_key_index = 0

_openrouter_pool_keys = []
_openrouter_key_index = 0

_openai_pool_keys = []
_openai_key_index = 0

def get_next_groq_key() -> Optional[str]:
    """Rút API Key Groq theo cơ chế xoay vòng."""
    global _groq_pool_keys, _groq_key_index
    
    if not _groq_pool_keys:
        import os
        keys_str = os.getenv("GROQ_POOL_KEYS", "")
        if keys_str:
            _groq_pool_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            
    if _groq_pool_keys:
        key = _groq_pool_keys[_groq_key_index % len(_groq_pool_keys)]
        _groq_key_index += 1
        return key

    return None

def get_next_gemini_key() -> Optional[str]:
    """
    Rút API Key từ rổ GEMINI_POOL_KEYS theo cơ chế vòng lặp xoay vòng (Round-Robin).
    Sử dụng khi gặp Rate Limit (429) để tự động đổi Key mà không cần chờ.
    """
    global _gemini_pool_keys, _gemini_key_index
    
    # Load pool key 1 lần duy nhất
    if not _gemini_pool_keys:
        import os
        keys_str = os.getenv("GEMINI_POOL_KEYS", "")
        if keys_str:
            _gemini_pool_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            
    # Lấy key và xoay vòng
    if _gemini_pool_keys:
        key = _gemini_pool_keys[_gemini_key_index % len(_gemini_pool_keys)]
        _gemini_key_index += 1
        return key

    return None

def get_next_hf_key() -> Optional[str]:
    """Rút API Key HuggingFace theo cơ chế xoay vòng."""
    global _hf_pool_keys, _hf_key_index
    
    if not _hf_pool_keys:
        import os
        keys_str = os.getenv("HF_POOL_KEYS", "")
        if keys_str:
            _hf_pool_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            
    if _hf_pool_keys:
        key = _hf_pool_keys[_hf_key_index % len(_hf_pool_keys)]
        _hf_key_index += 1
        return key

    return None

def get_next_openrouter_key() -> Optional[str]:
    """Rút API Key OpenRouter theo cơ chế xoay vòng."""
    global _openrouter_pool_keys, _openrouter_key_index
    
    if not _openrouter_pool_keys:
        import os
        keys_str = os.getenv("OPENROUTER_POOL_KEYS", "")
        if keys_str:
            _openrouter_pool_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            
    if _openrouter_pool_keys:
        key = _openrouter_pool_keys[_openrouter_key_index % len(_openrouter_pool_keys)]
        _openrouter_key_index += 1
        return key

    return None


def get_next_openai_key() -> Optional[str]:
    """Rút API Key OpenAI Native theo cơ chế vòng lặp."""
    global _openai_pool_keys, _openai_key_index
    
    if not _openai_pool_keys:
        import os
        keys_str = os.getenv("OPENAI_POOL_KEYS", "")
        if keys_str:
            _openai_pool_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            
    if _openai_pool_keys:
        key = _openai_pool_keys[_openai_key_index % len(_openai_pool_keys)]
        _openai_key_index += 1
        return key

    return None
