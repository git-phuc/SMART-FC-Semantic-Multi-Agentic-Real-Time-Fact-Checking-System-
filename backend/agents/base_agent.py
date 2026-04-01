"""
Base Agent - Abstract base class cho tất cả agents trong hệ thống.
Cung cấp shared interface và utility methods.
"""

import json
import re
from abc import ABC, abstractmethod
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore[import-untyped]

from config.settings import get_llm_for_agent
from utils.logger import get_logger, log_agent_step, log_agent_io


class BaseAgent(ABC):
    """
    Abstract base class cho mọi agent.
    Mỗi agent kế thừa class này và implement method `run()`.
    """

    # Giới hạn ký tự tối đa cho prompt (mặc định cho Groq free tier)
    # ~4 chars ≈ 1 token. Agent 2 (Gemini) sẽ override thành giá trị lớn hơn.
    DEFAULT_MAX_PROMPT_CHARS = 12000

    def __init__(self, name: str, agent_type_config: str = "AGENT1", max_prompt_chars: Optional[int] = None):
        """
        Khởi tạo agent.

        Args:
            name: Tên agent (VD: 'QueryAgent', 'ExtractorAgent')
            agent_type_config: Prefix cấu hình trong .env (VD: 'AGENT1', 'AGENT2')
            max_prompt_chars: Giới hạn ký tự tối đa cho prompt. None = dùng default 12000.
        """
        self.name = name
        self.logger = get_logger(f"Agent.{name}")
        self.llm = get_llm_for_agent(agent_type_config)
        self.max_prompt_chars = max_prompt_chars or self.DEFAULT_MAX_PROMPT_CHARS

    @abstractmethod
    def run(self, state: dict) -> dict:
        """
        Chạy agent với state hiện tại và trả về state đã cập nhật.
        Mỗi agent con phải implement method này.

        Args:
            state: Shared state dictionary chứa toàn bộ dữ liệu pipeline

        Returns:
            Updated state dictionary
        """
        pass

    def call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Gọi LLM với system prompt và user prompt.
        Có cơ chế xoay vòng API Key thông minh:
          - Vòng 1: Thử lần lượt TẤT CẢ key trong pool (không ngủ)
          - Nếu tất cả key đều bị 429 → Ngủ đúng 65s (chờ Google reset bucket)
          - Vòng 2: Thử lại TẤT CẢ key 1 lần nữa (key đã được reset)
          - Tối đa 3 vòng ngủ (3 × 65s = ~3 phút) trước khi bỏ cuộc
        """
        # Truncate prompt nếu quá dài (tránh Groq TPM limit)
        if len(user_prompt) > self.max_prompt_chars:
            truncated_len = len(user_prompt)
            user_prompt = user_prompt[:self.max_prompt_chars] + \
                f"\n\n[... Đã cắt bớt {truncated_len - self.max_prompt_chars} ký tự để tránh vượt giới hạn API ...]"
            self.logger.warning(
                f"[{self.name}] Prompt truncated: {truncated_len} → {self.max_prompt_chars} chars"
            )

        log_agent_step(self.logger, self.name, "Calling LLM")

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        import time as _time
        import os
        from config.settings import get_next_gemini_key, get_next_groq_key

        # Xác định provider hiện tại
        model_name_str = str(getattr(self.llm, "model_name", getattr(self.llm, "model", ""))).lower()
        base_url_str_check = str(getattr(self.llm, "openai_api_base", getattr(self.llm, "base_url", ""))).lower()
        is_gemini = "gemini" in model_name_str or "google" in base_url_str_check
        is_groq = "groq" in base_url_str_check
        is_hf = "huggingface" in base_url_str_check
        is_openrouter = "openrouter" in base_url_str_check
        is_openai = "api.openai.com" in base_url_str_check

        # Load pool keys
        if is_gemini:
            pool_keys_str = os.getenv("GEMINI_POOL_KEYS", "")
            get_next_key = get_next_gemini_key
            provider_name = "Gemini"
        elif is_groq:
            pool_keys_str = os.getenv("GROQ_POOL_KEYS", "")
            get_next_key = get_next_groq_key
            provider_name = "Groq"
        elif is_hf:
            from config.settings import get_next_hf_key
            pool_keys_str = os.getenv("HF_POOL_KEYS", "")
            get_next_key = get_next_hf_key
            provider_name = "HuggingFace"
        elif is_openrouter:
            from config.settings import get_next_openrouter_key
            pool_keys_str = os.getenv("OPENROUTER_POOL_KEYS", "")
            get_next_key = get_next_openrouter_key
            provider_name = "OpenRouter"
        elif is_openai:
            from config.settings import get_next_openai_key
            pool_keys_str = os.getenv("OPENAI_POOL_KEYS", "")
            get_next_key = get_next_openai_key
            provider_name = "OpenAI"
        else:
            pool_keys_str = ""
            get_next_key = lambda: None
            provider_name = "Unknown"

        pool_keys = [k.strip() for k in pool_keys_str.split(",") if k.strip()]
        pool_size = len(pool_keys) if pool_keys else 1

        # DEBUG: In ra để biết chính xác đang dùng model/provider nào
        base_url_str = str(getattr(self.llm, "openai_api_base", getattr(self.llm, "base_url", "N/A")))
        self.logger.info(
            f"[{self.name}] 🔧 DEBUG: model={model_name_str} | provider={provider_name} | "
            f"base_url={base_url_str} | pool_size={pool_size}"
        )

        # === CHIẾN LƯỢC XOAY VÒNG ===
        # Tối đa 3 "sleep cycles". Mỗi cycle:
        #   1) Thử tất cả key trong pool (mỗi key thử 1 lần)
        #   2) Nếu hết key mà vẫn 429 → ngủ 65s rồi thử vòng mới
        MAX_SLEEP_CYCLES = 3
        last_error = None

        for cycle in range(MAX_SLEEP_CYCLES + 1):
            # Nếu đây là cycle > 0 (tức là đã thất bại ở vòng trước), ngủ 65s
            if cycle > 0:
                self.logger.warning(
                    f"[{self.name}] 💤 Ngủ đông 65s — chờ {provider_name} reset rate-limit bucket "
                    f"(Vòng ngủ {cycle}/{MAX_SLEEP_CYCLES})"
                )
                _time.sleep(65)

            # Thử tất cả key trong pool
            for key_idx in range(pool_size):
                # Lấy key tiếp theo từ pool (round-robin)
                new_key = get_next_key()
                if new_key:
                    from langchain_openai import ChatOpenAI  # type: ignore[import-untyped]
                    self.llm = ChatOpenAI(
                        model=getattr(self.llm, "model_name", getattr(self.llm, "model", "")),
                        temperature=getattr(self.llm, "temperature", 0.1),
                        max_tokens=getattr(self.llm, "max_tokens", 4096),
                        base_url=getattr(self.llm, "openai_api_base", getattr(self.llm, "base_url", None)),
                        api_key=new_key,
                    )

                try:
                    response = self.llm.invoke(messages)
                    result = str(response.content)

                    if cycle > 0 or key_idx > 0:
                        self.logger.info(
                            f"[{self.name}] ✅ Thành công với {provider_name} key #{key_idx + 1} "
                            f"(sau {cycle} vòng ngủ)"
                        )

                    log_agent_io(self.logger, self.name, user_prompt, result)
                    return result

                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    is_rate_limit = any(kw in error_str for kw in
                                       ["rate_limit", "429", "413", "exhausted", "resource_exhausted", "402", "depleted", "503", "unavailable", "high demand"])

                    if is_rate_limit:
                        # Lấy snippet lỗi gốc để debug
                        err_snippet = str(e)[:200]
                        self.logger.warning(
                            f"[{self.name}] ⚠️ Key #{key_idx + 1}/{pool_size} bị 429 "
                            f"(cycle {cycle}) — thử key tiếp... | Lỗi: {err_snippet}"
                        )
                        _time.sleep(1)  # Delay nhẹ giữa các key
                        continue
                    else:
                        # Lỗi khác (không phải rate limit) → raise ngay
                        raise

            # Nếu đã ở cycle cuối mà vẫn không thành công
            if cycle == MAX_SLEEP_CYCLES:
                self.logger.error(
                    f"[{self.name}] ❌ Đã thử {pool_size} keys × {MAX_SLEEP_CYCLES + 1} vòng "
                    f"= {pool_size * (MAX_SLEEP_CYCLES + 1)} lần gọi mà vẫn bị Rate Limit. "
                    f"Bỏ cuộc."
                )
                raise last_error  # type: ignore[misc]

    @staticmethod
    def _clean_json(text: str) -> str:
        """Sửa các lỗi JSON phổ biến từ LLM (trailing comma, text thừa)."""
        # Xóa trailing commas: ,] → ] và ,} → }
        text = re.sub(r",\s*([}\]])", r"\1", text)
        return text.strip()

    def parse_json_response(self, response: str) -> dict:
        """
        Parse JSON từ LLM response. Xử lý trường hợp LLM trả về
        markdown code block, text thừa quanh JSON, hoặc trailing commas.

        Args:
            response: Raw text response từ LLM

        Returns:
            Parsed dictionary
        """
        # Thử parse trực tiếp
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Thử tìm JSON trong markdown code block
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", response, re.DOTALL)
        if json_match:
            cleaned = self._clean_json(json_match.group(1))
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        # Thử tìm JSON object trong text (greedy)
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            cleaned = self._clean_json(json_match.group(0))
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        # Thử sửa JSON bị cắt giữa chừng (Gemini hay bị)
        json_match = re.search(r"\{.*", response, re.DOTALL)
        if json_match:
            truncated = self._clean_json(json_match.group(0))
            repaired = self._repair_truncated_json(truncated)
            if repaired:
                return repaired

        # Nếu không parse được, trả về raw text trong dict
        self.logger.warning(f"[{self.name}] Could not parse JSON from LLM response")
        return {"raw_response": response, "parse_error": True}

    @staticmethod
    def _repair_truncated_json(text: str) -> dict | None:
        """Thử sửa JSON bị cắt giữa chừng bằng cách đóng ngoặc thiếu."""
        # Đếm ngoặc chưa đóng
        open_braces = text.count("{") - text.count("}")
        open_brackets = text.count("[") - text.count("]")

        if open_braces <= 0 and open_brackets <= 0:
            return None

        # Cắt bỏ value dở dang cuối cùng (sau dấu , hoặc : cuối)
        last_comma = max(text.rfind(","), text.rfind(":"))
        if last_comma > text.rfind("}") and last_comma > text.rfind("]"):
            text = text[:last_comma]

        # Đóng ngoặc thiếu
        text += "]" * max(0, open_brackets) + "}" * max(0, open_braces)

        try:
            import json as _json
            return _json.loads(text)
        except Exception:
            return None

    def add_log(self, state: dict, message: str) -> None:
        """
        Thêm log message vào state để tracking pipeline.

        Args:
            state: Current state dictionary
            message: Log message
        """
        if "agent_logs" not in state:
            state["agent_logs"] = []
        state["agent_logs"].append(f"[{self.name}] {message}")
