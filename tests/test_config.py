"""config 测试:env > 配置文件 > 报错."""
import json

import pytest

from senza_knowledge_mcp.config import (
    MissingConfigError,
    Settings,
    load_settings,
    read_config_file,
    write_config_file,
)


@pytest.fixture
def cfg_file(monkeypatch, tmp_path):
    p = tmp_path / "config.json"
    monkeypatch.setenv("SENZA_KB_CONFIG_FILE", str(p))
    monkeypatch.delenv("SENZA_KB_API_KEY", raising=False)
    monkeypatch.delenv("SENZA_KB_BASE_URL", raising=False)
    monkeypatch.delenv("SENZA_KB_MODEL", raising=False)
    monkeypatch.delenv("SENZA_KB_RAW_DIR", raising=False)
    monkeypatch.delenv("SENZA_KB_DOMAINS", raising=False)
    monkeypatch.delenv("SENZA_KB_PROVIDER", raising=False)
    return p


def test_all_missing_raises(cfg_file):
    with pytest.raises(MissingConfigError) as e:
        load_settings()
    assert "SENZA_KB_API_KEY" in str(e.value)
    assert "SENZA_KB_BASE_URL" in str(e.value)
    assert "SENZA_KB_MODEL" in str(e.value)


def test_config_file_provides(cfg_file):
    write_config_file(
        {
            "api_key": "sk-f1le",
            "provider": "openai",
            "base_url": "https://file.example/v1",
            "model": "m-file",
            "raw_dir": "/tmp/kbraw",
            "domains": "litho",
            "provider": "openai",
        }
    )
    s = load_settings()
    assert s.api_key == "sk-f1le"
    assert s.base_url == "https://file.example/v1"
    assert s.model == "m-file"
    assert s.raw_dir.name == "kbraw"
    assert s.domains == ["litho"]


def test_env_overrides_file(cfg_file, monkeypatch):
    write_config_file({"api_key": "sk-f1le",
            "provider": "openai", "base_url": "https://file/v1", "model": "m-file"})
    monkeypatch.setenv("SENZA_KB_MODEL", "m-env")
    monkeypatch.setenv("SENZA_KB_PROVIDER", "openai")
    s = load_settings()
    assert s.model == "m-env"  # env 优先
    assert s.api_key == "sk-f1le"  # 文件兜底


def test_env_only_works(cfg_file, monkeypatch):
    monkeypatch.setenv("SENZA_KB_API_KEY", "sk-env")
    monkeypatch.setenv("SENZA_KB_BASE_URL", "https://env/v1")
    monkeypatch.setenv("SENZA_KB_MODEL", "m-env")
    monkeypatch.setenv("SENZA_KB_PROVIDER", "openai")
    s = load_settings()
    assert s.model == "m-env"
    assert s.api_key == "sk-env"


def test_write_and_read_roundtrip(cfg_file):
    write_config_file({"api_key": "sk-a", "base_url": "https://x/v1", "model": "m", "provider": "openai"})
    write_config_file({"raw_dir": "/tmp/d"})  # 增量更新不覆盖已有
    data = read_config_file()
    assert data["api_key"] == "sk-a"
    assert data["raw_dir"] == "/tmp/d"


def test_corrupt_file_treated_as_empty(cfg_file):
    cfg_file.write_text("{broken json")
    with pytest.raises(MissingConfigError):
        load_settings()


def test_settings_direct_construct():
    s = Settings(model="dummy")
    assert s.raw_dir is not None
