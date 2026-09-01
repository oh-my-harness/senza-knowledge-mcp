"""管理后台 FastAPI 应用:上传入库 + 知识库查看(轻量 HTML).

独立进程(M3 MCP 服务共享原始层但各自运行),port 8081。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import HTMLResponse

from senza_knowledge_mcp.admin_routes import is_supported
from senza_knowledge_mcp.config import load_settings, read_config_file, write_config_file
from senza_knowledge_mcp.ingest import create_parser
from senza_knowledge_mcp.ingest.raw_store import RawStore

_PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>领域知识库管理</title></head>
<body><h1>领域知识库</h1>
<ul><li><a href="/upload">上传文档</a></li><li><a href="/sources">知识库列表</a></li><li><a href="/settings">设置</a></li></ul>
{body}</body></html>"""


def _store_upload(file: UploadFile, raw: RawStore) -> dict:
    data = file.file.read()
    name = file.filename or "upload"
    suffix = Path(name).suffix.lower()
    if suffix in (".txt", ".md"):
        from senza_knowledge_mcp.ingest.parser import ParseResult

        parse = ParseResult(
            document_markdown=data.decode("utf-8", errors="ignore"), images=[]
        )
    else:  # .pdf
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmppath = tmp.name
        try:
            parse = create_parser("docling").parse(Path(tmppath))
        finally:
            Path(tmppath).unlink(missing_ok=True)
    return raw.store(name, data, parse).to_dict()


_FIELDS = [
    ("api_key", "API Key"),
    ("base_url", "Base URL"),
    ("model", "Model"),
    ("raw_dir", "Raw 目录"),
    ("domains", "Domains(逗号分隔)"),
]
_PROVIDERS = ("openai", "anthropic")


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return value[:6] + "****" + value[-4:]


def _settings_form(message: str = "") -> str:
    cfg = read_config_file()
    provider_val = str(cfg.get("provider", "openai") or "openai")
    opts = "".join(
        f'<option value="{p}" {"selected" if p == provider_val else ""}>{p}</option>'
        for p in _PROVIDERS
    )
    rows = [f'<label>Provider<br><select name="provider">{opts}</select></label><br><br>']
    for key, label in _FIELDS:
        raw_val = str(cfg.get(key, "") or "")
        shown = _mask(raw_val) if key == "api_key" and raw_val else raw_val
        rows.append(
            f'<label>{label}<br><input name="{key}" value="{shown}" '
            f'style="width:420px"></label><br><br>'
        )
    msg = f'<p style="color:green">{message}</p>' if message else ""
    return (
        '<form method="post" action="/settings">'
        + "".join(rows)
        + "<button>保存</button></form>"
        + msg
    )




def create_app(raw_dir: Path) -> FastAPI:
    app = FastAPI(title="senza-knowledge-mcp admin")
    app.state.raw = RawStore(raw_dir)

    @app.post("/api/upload")
    async def upload(request: Request, file: UploadFile):
        if not is_supported(file.filename or ""):
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="仅支持 PDF/文本")
        return _store_upload(file, request.app.state.raw)

    @app.get("/api/sources")
    def api_sources(request: Request):
        from senza_knowledge_mcp.admin_routes import sources_json

        return sources_json(request.app.state.raw)

    @app.get("/api/sources/{source_id}")
    def api_source(request: Request, source_id: str):
        from fastapi import HTTPException

        try:
            from senza_knowledge_mcp.admin_routes import source_json

            return source_json(request.app.state.raw, source_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="source not found")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _PAGE.format(body="<p>选择一个操作。</p>")

    @app.get("/upload", response_class=HTMLResponse)
    def upload_page():
        form = (
            '<form method="post" action="/api/upload" enctype="multipart/form-data">'
            '<input type="file" name="file"><button>上传</button></form>'
        )
        return _PAGE.format(body=form)

    @app.get("/sources", response_class=HTMLResponse)
    def sources_page(request: Request):
        raw = request.app.state.raw
        items = [
            f'<li><a href="/sources/{s.source_id}">{s.name} ({s.source_id})</a></li>'
            for s in raw.list()
        ]
        return _PAGE.format(body="<ul>" + "".join(items) + "</ul>")

    @app.get("/sources/{source_id}", response_class=HTMLResponse)
    def source_page(request: Request, source_id: str):
        raw = request.app.state.raw
        try:
            doc = raw.read_document(source_id)
        except FileNotFoundError:
            return _PAGE.format(body="<p>source 不存在</p>")
        return _PAGE.format(body=f"<h2>{source_id}</h2><pre>{doc}</pre>")

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page():
        return _PAGE.format(body=_settings_form())

    @app.post("/settings", response_class=HTMLResponse)
    async def settings_save(request: Request):
        form = await request.form()
        updates = {}
        pv = str(form.get("provider", "") or "").strip()
        if pv in _PROVIDERS:
            updates["provider"] = pv
        for key, _label in _FIELDS:
            v = str(form.get(key, "") or "").strip()
            if v and "****" not in v:  # 打码值不回写
                updates[key] = v
        if updates:
            write_config_file(updates)
        return _PAGE.format(body=_settings_form("已保存"))

    return app


def main() -> None:
    settings = load_settings()
    app = create_app(settings.raw_dir)
    uvicorn.run(app, host="127.0.0.1", port=8081)


if __name__ == "__main__":
    main()
