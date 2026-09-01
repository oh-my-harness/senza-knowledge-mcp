---
date: 2026-09-01
status: spec
scope: M4
project: senza-knowledge-mcp
repo: oh-my-harness/senza-knowledge-mcp
---

# M4 Spec · 管理后台(文档入库 + 知识库查看)

## 背景与目标

M3 已完成:MCP 服务(agent 即服务,coding agent 经 stdio 检索/问答)。M4 提供**管理后台**:人(而非 coding agent)通过浏览器管理知识库——**上传文档(触发入库) + 查看知识库内容**。归纳审批(human-on-the-loop)属一阶段后半段(M6),不在 M4。

### 目标
- 浏览器上传 PDF/文本 → Docling 解析 → 原始层入库。
- 查看知识库:列出所有 source(名称/时间/图片数/大小),可看 document.md 内容。
- 独立 FastAPI 进程,轻量 HTML 页面(服务端渲染)。

### 非目标(边界)
- 不做归纳审批(M6)、不做问答(M3 已做,聊天在 coding agent 侧)。
- 不做多用户/权限(二阶段)。
- 不做前端工程(React/Vite),轻量 HTML + REST 底座。
- MCP 服务(M3)与管理后台(M4)为独立进程,共享原始层目录。

## 架构

```
浏览器(人) ──HTTP──► 管理后台(FastAPI, M4, 独立进程)
                        ├─ POST /api/upload   → Docling 解析 → RawStore 入库
                        ├─ GET  /api/sources  → 列出原始层 source
                        ├─ GET  /api/sources/{id} → 单个 source 内容(dataset)
                        └─ 页面: /upload 、/sources 、/sources/{id}(轻量 HTML)

原始层 raw/ (不可变)  ← 与 M3 MCP 服务共享同一目录
```

## 组件

### `src/senza_knowledge_mcp/admin_app.py` (FastAPI 应用)
- `create_app(raw_dir: Path) -> FastAPI` — 组装路由,返回 app
- `main()` — uvicorn 启动(`python -m senza_knowledge_mcp.admin_app`)
- 挂载静态/模板(内联 HTML 或 Jinja2)

### `src/senza_knowledge_mcp/admin_routes.py` (路由 + 入库逻辑)
- `POST /api/upload` — 接收 multipart 文件 → 判断 PDF/文本 → `create_parser("docling").parse()` → `RawStore.store()` → 返回 source 描述
- `GET /api/sources` — `RawStore.list()` → 列表
- `GET /api/sources/{source_id}` — `RawStore.read_document()` → 内容 + 元信息
- 页面路由:`GET /`(入口)、`GET /upload`、`GET /sources`、`GET /sources/{id}`

### 复用
- `ingest/raw_store.py`(`RawStore.list/read_document/store`)
- `ingest/parser.py`(`create_parser("docling")`)
- `config.py`(`Settings.raw_dir`)
- M3 已建原始层;M4 直接读写同一 raw/ 目录。

## 接口

```python
# admin_app.py
def create_app(raw_dir: Path) -> FastAPI: ...
def main() -> None: ...   # uvicorn.run(create_app(...), host, port)

# admin_routes.py
async def handle_upload(file: UploadFile, raw: RawStore) -> dict: ...
def list_sources(raw: RawStore) -> list[dict]: ...
def get_source(raw: RawStore, source_id: str) -> dict: ...
```

HTML 页面用 FastAPI 返回 `HTMLResponse`(内联简单页面),数据接口走 `/api/*` JSON。

## 数据流

1. 浏览器 `POST /api/upload` 传文件。
2. `handle_upload`:解析(multipart container) → 判断类型 → Docling parse → RawStore.store。
3. 返回 source(含 source_id/name/image_count/raw_bytes)。
4. 浏览器 `GET /sources` → 列表;`GET /sources/{id}` → 看内容。
5. 上传成功后,知识库内容变化,用户可刷新列表看到新 source;MCP 服务(M3)对同一 raw/ 目录,新 source 可被检索(重新启动 MCP 或底座索引刷新)。

## 测试(TDD)

1. upload: 上传 PDF → 入库 → raw_source 存在(用真实小 PDF 或文本)。
2. upload 文本: 传 .txt → 入库。
3. list_sources: 有/无 source 时的列表。
4. get_source: 取 document.md 内容。
5. create_app 路由: `GET /api/sources`、`POST /api/upload` 存在(TestClient)。
6. 页面: `GET /sources` 返回 HTML。

## 里程碑内的验证(MVP 门槛)

- 浏览器打开管理后台,上传 CurvilinearMaskOverview.pdf → 知识库列表出现该 source → 能查看其 document.md 内容。
- `GET /api/sources` 反映入库结果。
- 与 M3 协同:入库的新 source 可被 MCP agent 检索到(集成验证)。

## 风险
1. 上传大 PDF / Docling 慢:同步解析可能阻塞请求;MVP 先用同步 + 超时,后续可转后台任务/队列。
2. local_source 索引刷新:M4 入库后,已在跑的 MCP local_source 可能不自动发现新文件(取决于底座索引时机)。MVP 先重启 MCP 或等待索引刷新;作为可接受限制记录。
3. 文件类型校验:仅接受 PDF + 文本,拒绝其他。
4. 安全:本地单用户工具,不做鉴权;二阶段云端再加。

## 相关
- `docs/领域知识库-一阶段设计.md`(职责分工表:文档入库走管理后台/CLI)
- `docs/M3-MCP服务-spec.md`(共享原始层、独立进程)
- M1 `ingest/raw_store.py`、`ingest/parser.py`
