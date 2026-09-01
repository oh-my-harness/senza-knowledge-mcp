"""配置 — 三个 LLM 变量(SENZA_KB_API_KEY / BASE_URL / MODEL)全部强制用户配置.

源码不绑定任何 provider:不设默认端点、不设默认模型、不带 key。
kb_get / kb_list(纯数据工具)不依赖这些变量;kb_ask / kb_search 需要。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_REQUIRED_LLM_VARS = ("SENZA_KB_API_KEY", "SENZA_KB_BASE_URL", "SENZA_KB_MODEL")


class MissingConfigError(RuntimeError):
    """缺少强制配置项."""


@dataclass
class Settings:
    raw_dir: Path = field(default_factory=lambda: Path("."))
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    domains: list[str] = field(default_factory=list)


def load_settings() -> Settings:
    missing = [v for v in _REQUIRED_LLM_VARS if not os.environ.get(v)]
    if missing:
        raise MissingConfigError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + " — set them before starting the MCP server (LLM tools need a provider)."
        )
    raw_dir = Path(os.environ.get("SENZA_KB_RAW_DIR", "."))
    model = os.environ["SENZA_KB_MODEL"]
    base_url = os.environ["SENZA_KB_BASE_URL"]
    api_key = os.environ["SENZA_KB_API_KEY"]
    raw_domains = os.environ.get("SENZA_KB_DOMAINS", "")
    domains = [d.strip() for d in raw_domains.split(",") if d.strip()]
    return Settings(
        raw_dir=raw_dir,
        model=model,
        base_url=base_url,
        api_key=api_key,
        domains=domains,
    )
