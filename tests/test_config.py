"""config 测试 — 三个 LLM 变量强制配置."""
import pytest

from senza_knowledge_mcp.config import Settings, MissingConfigError, load_settings


def test_missing_vars_raises(monkeypatch):
    for k in ("SENZA_KB_RAW_DIR", "SENZA_KB_MODEL", "SENZA_KB_BASE_URL", "SENZA_KB_API_KEY", "SENZA_KB_DOMAINS"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(MissingConfigError) as e:
        load_settings()
    # 三个都报
    assert "SENZA_KB_API_KEY" in str(e.value)
    assert "SENZA_KB_BASE_URL" in str(e.value)
    assert "SENZA_KB_MODEL" in str(e.value)


def test_partial_missing_raises(monkeypatch):
    monkeypatch.setenv("SENZA_KB_API_KEY", "sk-x")
    monkeypatch.delenv("SENZA_KB_BASE_URL", raising=False)
    monkeypatch.delenv("SENZA_KB_MODEL", raising=False)
    with pytest.raises(MissingConfigError):
        load_settings()


def test_all_set_loads(monkeypatch, tmp_path):
    monkeypatch.setenv("SENZA_KB_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.setenv("SENZA_KB_MODEL", "m1")
    monkeypatch.setenv("SENZA_KB_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("SENZA_KB_API_KEY", "sk-x")
    monkeypatch.setenv("SENZA_KB_DOMAINS", "litho, opc")
    s = load_settings()
    assert s.model == "m1"
    assert s.base_url == "https://example.com/v1"
    assert s.api_key == "sk-x"
    assert s.raw_dir == tmp_path / "raw"
    assert s.domains == ["litho", "opc"]


def test_settings_defaults_direct():
    # 直接构造(不经 load)不受强制约束——供测试/嵌入使用
    s = Settings(model="dummy")
    assert s.raw_dir is not None
