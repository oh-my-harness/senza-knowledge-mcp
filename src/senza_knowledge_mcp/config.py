"""配置:DeepSeek 默认值(内部工具,可硬编码)+ env 覆盖."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_API_KEY = ""  # set via SENZA_KB_API_KEY (no key ships with source)


@dataclass
class Settings:
    raw_dir: Path = field(default_factory=lambda: Path("."))
    model: str = DEEPSEEK_MODEL
    base_url: str = DEEPSEEK_BASE_URL
    api_key: str = DEEPSEEK_API_KEY
    domains: list[str] = field(default_factory=list)


def load_settings() -> Settings:
    raw_dir = Path(os.environ.get("SENZA_KB_RAW_DIR", "."))
    model = os.environ.get("SENZA_KB_MODEL", DEEPSEEK_MODEL)
    base_url = os.environ.get("SENZA_KB_BASE_URL", DEEPSEEK_BASE_URL)
    api_key = os.environ.get("SENZA_KB_API_KEY", DEEPSEEK_API_KEY)
    raw_domains = os.environ.get("SENZA_KB_DOMAINS", "")
    domains = [d.strip() for d in raw_domains.split(",") if d.strip()]
    return Settings(
        raw_dir=raw_dir,
        model=model,
        base_url=base_url,
        api_key=api_key,
        domains=domains,
    )
