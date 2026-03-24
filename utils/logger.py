"""
Logger utility cho hệ thống Multi-Agent.
Cung cấp structured logging cho từng agent step,
hữu ích cho nghiên cứu và debug.
"""

import logging
import sys
from datetime import datetime


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Tạo logger với format đẹp cho từng module/agent.

    Args:
        name: Tên module (VD: 'Agent1.QueryClarifier')
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Tránh duplicate handlers nếu gọi nhiều lần
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Console handler với color formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def log_agent_step(logger: logging.Logger, agent_name: str, step: str, detail: str = ""):
    """
    Log một bước xử lý của agent với format chuẩn.

    Args:
        logger: Logger instance
        agent_name: Tên agent (VD: 'QueryAgent')
        step: Tên bước (VD: 'Clarifying query')
        detail: Chi tiết thêm (optional)
    """
    msg = f"[{agent_name}] {step}"
    if detail:
        # Truncate detail nếu quá dài
        if len(detail) > 500:
            detail = detail[:500] + "... (truncated)"
        msg += f"\n    → {detail}"
    logger.info(msg)


def log_agent_io(logger: logging.Logger, agent_name: str, input_data: str, output_data: str):
    """
    Log input/output của agent (hữu ích cho nghiên cứu).

    Args:
        logger: Logger instance
        agent_name: Tên agent
        input_data: Dữ liệu đầu vào (sẽ được truncate nếu quá dài)
        output_data: Dữ liệu đầu ra (sẽ được truncate nếu quá dài)
    """
    max_len = 300
    input_preview = input_data[:max_len] + "..." if len(input_data) > max_len else input_data
    output_preview = output_data[:max_len] + "..." if len(output_data) > max_len else output_data

    logger.info(
        f"[{agent_name}] I/O Summary\n"
        f"    📥 Input:  {input_preview}\n"
        f"    📤 Output: {output_preview}"
    )
