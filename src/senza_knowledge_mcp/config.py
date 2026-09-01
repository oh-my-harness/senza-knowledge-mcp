"""配置解析:env > ~/.senza-knowledge-mcp/config.json > 报错.

三个 LLM 变量(SENZA_KB_API_KEY / BASE_URL / MODEL)必须能从其中之一解析到;
源码零绑定,不设任何 provider 默认值。配置文件由管理后台设置页维护。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path.home() / ".senza-knowledge-mcp" / "config.json"
REQUIRED_LLM_VARS = (
    "SENZA_KB_API_KEY",
    "SENZA_KB_BASE_URL",
    "SENZA_KB_MODEL",
    "SENZA_KB_PROVIDER",
)
_VALID_PROVIDERS = ("openai", "anthropic")
# env 变量名 -> 配置文件字段名
_ENV_TO_FILE = {
    "SENZA_KB_PROVIDER": "provider",
    "SENZA_KB_API_KEY": "api_key",
    "SENZA_KB_BASE_URL": "base_url",
    "SENZA_KB_MODEL": "model",
    "SENZA_KB_RAW_DIR": "raw_dir",
    "SENZA_KB_DOMAINS": "domains",
}


class MissingConfigError(RuntimeError):
    """缺少强制配置项(env 与配置文件都未提供)."""


@dataclass
class Settings:
    raw_dir: Path = field(default_factory=lambda: Path("."))
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    provider: str = "openai"  # "openai" | "anthropic"
    domains: list[str] = field(default_factory=list)


def config_path() -> Path:
    """配置文件路径(可被 SENZA_KB_CONFIG_FILE 覆盖,便于测试)."""
    return Path(os.environ.get("SENZA_KB_CONFIG_FILE", str(CONFIG_PATH)))


def read_config_file() -> dict:
    """读配置文件;不存在/损坏返回空 dict."""
    p = config_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:  # noqa: BLE001 损坏文件当作未配置
        return {}


def write_config_file(values: dict) -> Path:
    """写配置文件(设置页保存用)。父目录自动创建。"""
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = read_config_file()
    existing.update({k: v for k, v in values.items() if v is not None})
    p.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load_settings() -> Settings:
    file_cfg = read_config_file()

    def resolve(env_var: str) -> str:
        # 优先级:env > 配置文件
        v = os.environ.get(env_var) or str(file_cfg.get(_ENV_TO_FILE[env_var], "") or "")
        return v

    values = {k: resolve(k) for k in _ENV_TO_FILE}
    missing = [k for k in REQUIRED_LLM_VARS if not values[k]]
    if values["SENZA_KB_PROVIDER"] and values["SENZA_KB_PROVIDER"] not in _VALID_PROVIDERS:
        raise MissingConfigError(
            f"SENZA_KB_PROVIDER must be one of {_VALID_PROVIDERS}, got {values['SENZA_KB_PROVIDER']!r}"
        )
    if missing:
        raise MissingConfigError(
            "Missing required configuration: "
            + ", ".join(missing)
            + " — set them in the admin web settings page ("
            + str(config_path())
            + ") or via environment variables."
        )
    raw_domains = values["SENZA_KB_DOMAINS"]
    domains = [d.strip() for d in raw_domains.split(",") if d.strip()]
    return Settings(
        raw_dir=Path(values["SENZA_KB_RAW_DIR"] or "."),
        model=values["SENZA_KB_MODEL"],
        base_url=values["SENZA_KB_BASE_URL"],
        api_key=values["SENZA_KB_API_KEY"],
        provider=values["SENZA_KB_PROVIDER"],
        domains=domains,
    )
