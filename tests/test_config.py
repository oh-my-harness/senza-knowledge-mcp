"""Task 1: config 测试."""
import os
from pathlib import Path

from senza_knowledge_mcp.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    Settings,
    load_settings,
)


def test_constants():
    assert DEEPSEEK_BASE_URL == "https://api.deepseek.com/v1"
    assert DEEPSEEK_MODEL == "deepseek-v4-flash"
    assert DEEPSEEK_API_KEY == ""  # no key ships with source


def test_defaults(monkeypatch):
    for k in (
        "SENZA_KB_RAW_DIR",
        "SENZA_KB_MODEL",
        "SENZA_KB_BASE_URL",
        "SENZA_KB_API_KEY",
        "SENZA_KB_DOMAINS",
    ):
        monkeypatch.delenv(k, raising=False)
    s = load_settings()
    assert s.model == DEEPSEEK_MODEL
    assert s.base_url == DEEPSEEK_BASE_URL
    assert s.api_key == DEEPSEEK_API_KEY
    assert s.raw_dir == Path(".")
    assert s.domains == []


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SENZA_KB_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.setenv("SENZA_KB_MODEL", "other-model")
    monkeypatch.setenv("SENZA_KB_DOMAINS", "litho, opc")
    s = load_settings()
    assert s.raw_dir == tmp_path / "raw"
    assert s.model == "other-model"
    assert s.domains == ["litho", "opc"]
