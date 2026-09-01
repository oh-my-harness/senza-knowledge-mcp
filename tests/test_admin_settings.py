"""admin 设置页测试(配置文件真相源)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from senza_knowledge_mcp.admin_app import create_app
from senza_knowledge_mcp.config import (
    load_settings,
    read_config_file,
)


@pytest.fixture
def cfg_file(monkeypatch, tmp_path):
    p = tmp_path / "config.json"
    monkeypatch.setenv("SENZA_KB_CONFIG_FILE", str(p))
    for k in ("SENZA_KB_API_KEY", "SENZA_KB_BASE_URL", "SENZA_KB_MODEL"):
        monkeypatch.delenv(k, raising=False)
    return p


def test_settings_page_get(tmp_path, cfg_file):
    app = create_app(tmp_path / "raw")
    c = TestClient(app)
    r = c.get("/settings")
    assert r.status_code == 200
    assert "api_key" in r.text


def test_settings_save_writes_config(tmp_path, cfg_file):
    app = create_app(tmp_path / "raw")
    c = TestClient(app)
    r = c.post(
        "/settings",
        data={
            "api_key": "sk-newkey",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-v4-flash",
            "raw_dir": str(tmp_path / "raw"),
            "domains": "litho",
        },
    )
    assert r.status_code == 200
    data = read_config_file()
    assert data["api_key"] == "sk-newkey"
    assert data["model"] == "deepseek-v4-flash"
    assert data["domains"] == "litho"


def test_saved_config_feeds_load_settings(tmp_path, cfg_file):
    app = create_app(tmp_path / "raw")
    c = TestClient(app)
    c.post(
        "/settings",
        data={
            "api_key": "sk-newkey",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-v4-flash",
            "raw_dir": str(tmp_path / "raw"),
        },
    )
    s = load_settings()  # 无 env,纯靠配置文件
    assert s.model == "deepseek-v4-flash"
    assert s.api_key == "sk-newkey"


def test_masked_key_not_overwritten(tmp_path, cfg_file):
    # 先存真实 key
    app = create_app(tmp_path / "raw")
    c = TestClient(app)
    c.post("/settings", data={"api_key": "sk-real12345", "base_url": "https://x/v1", "model": "m"})
    # 表单回显打码,再提交打码值不应覆盖
    page = c.get("/settings").text
    assert "sk-rea****2345" in page  # 打码回显
    c.post("/settings", data={"api_key": "sk-6****k3y", "base_url": "https://x/v1", "model": "m2"})
    data = read_config_file()
    assert data["api_key"] == "sk-real12345"  # 打码提交未覆盖真实 key
