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

        Args:
            system_prompt: System message hướng dẫn vai trò LLM
            user_prompt: User message chứa dữ liệu cần xử lý

        Returns:
            LLM response text
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

        # Retry with backoff khi bị rate limit
        # Retry with backoff & API Key Rotation
        import time as _time
        import os
        from config.settings import get_next_gemini_key, get_next_groq_key
        
        # Nếu có chùm key dự phòng, cho phép retry đâm thủng rate limit nhiều lần hơn
        gemini_pool = os.getenv("GEMINI_POOL_KEYS", "")
        groq_pool = os.getenv("GROQ_POOL_KEYS", "")
        pool_size = len([k for k in gemini_pool.split(",") if k.strip()]) + len([k for k in groq_pool.split(",") if k.strip()])
        max_retries = max(20, pool_size + 15)

        for attempt in range(max_retries):
            try:
                response = self.llm.invoke(messages)
                result = str(response.content)
                log_agent_io(self.logger, self.name, user_prompt, result)
                return result
            except Exception as e:
                error_str = str(e).lower()
                if ("rate_limit" in error_str or "413" in error_str or "429" in error_str or "exhausted" in error_str) and attempt < max_retries - 1:
                    
                    # Cơ chế 1: Thử xoay vòng API Key thay vì ngủ chờ
                    model_name_str = str(getattr(self.llm, "model_name", getattr(self.llm, "model", ""))).lower()
                    
                    new_key = None
                    provider_name = ""
                    
                    if "gemini" in model_name_str:
                        new_key = get_next_gemini_key()
                        provider_name = "Gemini"
                    elif "llama" in model_name_str or "mixtral" in model_name_str or "deepseek" in model_name_str:
                        # Gọi mạng Groq
                        new_key = get_next_groq_key()
                        provider_name = "Groq"
                    
                    if new_key and attempt < max(1, pool_size):
                        self.logger.warning(
                            f"[{self.name}] Báo động Rate Limit (429)! Đang kích hoạt xoay vòng sang dự phòng {provider_name} API Key mới... (Lần thử {attempt + 1}/{max_retries})"
                        )
                        from langchain_openai import ChatOpenAI
                        self.llm = ChatOpenAI(
                            model=getattr(self.llm, "model_name", getattr(self.llm, "model", "")),
                            temperature=getattr(self.llm, "temperature", 0.1),
                            max_tokens=getattr(self.llm, "max_tokens", 4096),
                            base_url=getattr(self.llm, "openai_api_base", getattr(self.llm, "base_url", None)),
                            api_key=new_key
                        )
                        _time.sleep(2)  # Buffer nhẹ
                        continue  # Khởi động lại vòng lặp invoke không cần chờ
                    
                    # Cơ chế 2: Nếu vòng lặp cạn Key xoay dự phòng hoặc tất cả Key đều bị 429
                    import re
                    match = re.search(r'retry in (\d+\.?\d*)s', error_str)
                    wait = int(float(match.group(1))) + 5 if match else 30 * (attempt + 1)
                    if wait < 65:
                        wait = 65  # Ép ngủ đông tối thiểu 65s để đợi Google reset lại bucket (1 phút)
                    
                    self.logger.warning(
                        f"[{self.name}] Rate limit hit & Exhausted Key Pool, bắt buộc ngủ đông chờ {wait}s trước khi gọi lại ({attempt + 1}/{max_retries})..."
                    )
                    _time.sleep(wait)
                else:
                    raise

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
