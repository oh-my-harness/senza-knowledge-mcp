"""Task 2: admin_app(create_app)测试."""
import pytest
from fastapi.testclient import TestClient

from senza_knowledge_mcp.admin_app import create_app
from senza_knowledge_mcp.admin_routes import is_supported
from senza_knowledge_mcp.ingest.parser import ParseResult
from senza_knowledge_mcp.ingest.raw_store import RawStore


def test_upload_text(tmp_path):
    app = create_app(tmp_path / "raw")
    c = TestClient(app)
    r = c.post(
        "/api/upload",
        files={"file": ("hello.txt", b"# Hello\n\ndiffraction sinc kernel", "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source_id"]
    assert body["origin"] == "hello.txt"


def test_upload_rejects_non_supported(tmp_path):
    app = create_app(tmp_path / "raw")
    c = TestClient(app)
    r = c.post("/api/upload", files={"file": ("x.png", b"\x89PNG", "image/png")})
    assert r.status_code == 400


def test_upload_md(tmp_path):
    app = create_app(tmp_path / "raw")
    c = TestClient(app)
    r = c.post(
        "/api/upload",
        files={"file": ("note.md", b"# Note\n\ncurvilinear mask diffraction", "text/markdown")},
    )
    assert r.status_code == 200


def test_sources_page_html(tmp_path):
    raw = RawStore(tmp_path / "raw")
    raw.store("a.md", b"a", ParseResult(document_markdown="# A\n\ncontent", images=[]))
    app = create_app(tmp_path / "raw")
    c = TestClient(app)
    r = c.get("/sources")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "a.md" in r.text


def test_index_page(tmp_path):
    app = create_app(tmp_path / "raw")
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_upload_page(tmp_path):
    app = create_app(tmp_path / "raw")
    c = TestClient(app)
    r = c.get("/upload")
    assert r.status_code == 200
    assert 'method="post"' in r.text
