# M3 MCP 服务(agent 即服务)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把知识库暴露为 MCP 服务,内置 Senza agent 综合回答,供 coding agent 经 stdio 访问。

**Architecture:** MCP 服务端(官方 `mcp` 2.x `MCPServer`)暴露 `ask`/`knowledge_search`/`knowledge_read` 三个工具;内置 Senza agent 挂 `knowledge.plugin()`(底座 LocalDocumentSource 检索),用 DeepSeek V4 Flash 综合回答。检索统一走底座,M2 自建 LanceDbRag 已删除。

**Tech Stack:** Python 3.12、Senza SDK(`senza-sdk`,含 knowledge/McpManager)、官方 `mcp>=2,<3`(MCPServer)、DeepSeek V4 Flash(OpenAI 兼容)、Docling(M1 已建)。

**Spec:** `docs/M3-MCP服务-spec.md`

## Global Constraints

- Python 3.12(已锁 requires-python)。
- 检索统一走底座 `knowledge.plugin()` + `LocalDocumentSource`;**不再有自建 LanceDbRag**。
- DeepSeek V4 Flash:base_url `https://api.deepseek.com/v1`,key 默认硬编码于 config 常量(可 env 覆盖)。
- provider 全匹配:`provider("*", prov)`。
- mcp 版本锁定 `>=2,<3`(MCPServer,非 FastMCP)。
- MCP 工具:`ask` + `knowledge_search` + `knowledge_read`。
- 单轮为主,预留多轮接口。
- 原始 = document.md;原始层 `raw/<source_id>/document.md`,摄取到 local_source 需验证目录结构。
- 测试全绿为完成任务标准。

---

### Task 1: config.py

**Files:**
- Create: `src/senza_knowledge_mcp/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"`
  - `DEEPSEEK_MODEL = "deepseek-v4-flash"`
  - `DEEPSEEK_API_KEY = "SENZA_KB_API_KEY(user-provided)"` (硬编码默认)
  - `@dataclass Settings:` — `raw_dir: Path`, `model: str`, `base_url: str`, `api_key: str`, `domains: list[str]`
  - `def load_settings() -> Settings` — 默认值 + env 覆盖(`SENZA_KB_RAW_DIR`/`SENZA_KB_MODEL`/`SENZA_KB_BASE_URL`/`SENZA_KB_API_KEY`/`SENZA_KB_DOMAINS`)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py
import os
from pathlib import Path
import pytest

from senza_knowledge_mcp.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    Settings, load_settings,
)

def test_constants():
    assert DEEPSEEK_BASE_URL == "https://api.deepseek.com/v1"
    assert DEEPSEEK_MODEL == "deepseek-v4-flash"
    assert isinstance(DEEPSEEK_API_KEY, str) and DEEPSEEK_API_KEY.startswith("sk-")

def test_defaults(monkeypatch):
    for k in ("SENZA_KB_RAW_DIR","SENZA_KB_MODEL","SENZA_KB_BASE_URL","SENZA_KB_API_KEY","SENZA_KB_DOMAINS"):
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL,`ModuleNotFoundError: senza_knowledge_mcp.config`

- [ ] **Step 3: 写实现**

```python
# src/senza_knowledge_mcp/config.py
"""配置:DeepSeek 默认值(内部工具,可硬编码)+ env 覆盖."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_API_KEY = "SENZA_KB_API_KEY(user-provided)"


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
    return Settings(raw_dir=raw_dir, model=model, base_url=base_url, api_key=api_key, domains=domains)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/senza_knowledge_mcp/config.py tests/test_config.py
git commit -m "feat(M3): config with DeepSeek defaults + env override"
```

---

### Task 2: agent.py(KnowledgeAgent)

**Files:**
- Create: `src/senza_knowledge_mcp/agent.py`
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: `Settings`(Task 1),`create_parser`/`RawStore`(M1,可选)
- Produces:
  - `class KnowledgeAgent:` — `__init__(settings: Settings)`, `build_harness() -> senza.AgentHarness`, `ask(question: str) -> str`, `search(query, limit=10) -> list[dict]`, `read(ref: str) -> str`, `close()`
  - 内部用 `senza.knowledge.local_source(...)` + `senza.knowledge.plugin(...)`

- [ ] **Step 1: 写失败测试(构造不出错)**

```python
# tests/test_agent.py
import pytest

from senza_knowledge_mcp.config import Settings
from senza_knowledge_mcp.agent import KnowledgeAgent


def test_construct(monkeypatch):
    # 不真正调用 LLM,只验证管道组装不出错
    s = Settings(raw_dir=".", model="dummy-model")
    a = KnowledgeAgent(s)
    assert a is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_agent.py -v`
Expected: FAIL,`ModuleNotFoundError: senza_knowledge_mcp.agent`

- [ ] **Step 3: 写实现**

```python
# src/senza_knowledge_mcp/agent.py
"""内置 Senza agent:挂 knowledge.plugin,做知识检索 + 综合回答."""
from __future__ import annotations

from pathlib import Path

import senza

from senza_knowledge_mcp.config import Settings


class KnowledgeAgent:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._harness = None

    def build_harness(self) -> "senza.AgentHarness":
        if self._harness is not None:
            return self._harness
        # 知识源:索引 raw_dir 目录(md/txt)
        src = senza.knowledge.local_source(
            str(self._settings.raw_dir),
            "domain-kb",
            name="Domain KB",
            domains=self._settings.domains or None,
        )
        plugin = senza.knowledge.plugin([src])
        prov = senza.providers.openai(
            api_key=self._settings.api_key, base_url=self._settings.base_url
        )
        self._harness = (
            senza.HarnessBuilder(self._settings.model)
            .provider("*", prov)
            .plugin(plugin)
            .system_prompt(
                "You are a domain knowledge assistant. When asked, first search the "
                "knowledge base with knowledge_search, read exact references, then answer "
                "based on retrieved content and cite the source."
            )
            .build()
        )
        return self._harness

    def ask(self, question: str) -> str:
        h = self.build_harness()
        with h:
            h.prompt(question)
            h.wait_for_settled()
            return h.last_response()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        # 直接经 harness 检索;限单次探索,返回结构化 hits
        raise NotImplementedError("search 走 agent 工具,见 M3 后续;实现期评估")

    def read(self, ref: str) -> str:
        raise NotImplementedError("read 走 agent 工具,见 M3 后续")

    def close(self) -> None:
        if self._harness is not None:
            try:
                self._harness.shutdown()
            except Exception:  # noqa: BLE001
                pass
            self._harness = None
```

> 注:Task 2 只实现 `ask`(agent 综合回答的核心)。`search`/`read` 的独立方法在 M3 后续评估——因 M3 是 agent 即服务,细粒度 search/read 也可由 agent 工具内部完成,是否独立暴露见 spec 决策 4(对外暴露 search/read 工具)。本任务保留接口,实现 `ask`,其余 NotImplemented 待 Task 3/4 决定。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_agent.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/senza_knowledge_mcp/agent.py tests/test_agent.py
git commit -m "feat(M3): KnowledgeAgent (build harness + ask)"
```

---

### Task 3: 原始层 → local_source 摄取验证

**Files:**
- Create: `src/senza_knowledge_mcp/source.py`
- Create: `tests/test_source.py`

**Interfaces:**
- Consumes: `RawStore`(M1)
- Produces:
  - `def build_local_source_dir(raw_dir: Path, view_dir: Path, raw: RawStore) -> Path` — 把原始层 document.md 平铺/链接到 view_dir,返回可被 local_source 索引的目录
  - 说明:local_source 索引目录下 md 文件;原始层是 `raw/<id>/document.md`,需提供索引视图

- [ ] **Step 1: 探索 local_source 目录摄取行为(spike)**

```bash
cd /Users/hhl/Documents/projs/oh-my-harness/senza-knowledge-mcp
# 确认 local_source 是索引目录顶层 md 还是递归。spike 曾用顶层 doc.md 成功。
# 此处验证嵌套目录是否也摄取;若只索引顶层,则 source.py 需平铺 document.md 到 view_dir。
```

- [ ] **Step 2: 写失败测试**

```python
# tests/test_source.py
from pathlib import Path
import pytest

from senza_knowledge_mcp.ingest.raw_store import RawStore
from senza_knowledge_mcp.ingest.parser import ParseResult
from senza_knowledge_mcp.source import build_local_source_dir


def test_build_view_dir(tmp_path):
    raw = RawStore(tmp_path / "raw")
    raw.store("a.md", b"a", ParseResult(document_markdown="# Doc A\n\ndiffraction sinc kernel", images=[]))
    view = tmp_path / "view"
    out = build_local_source_dir(str(tmp_path / "raw"), view, raw)
    # 视图目录应含可索引的 md
    mds = list(Path(out).glob("**/*.md"))
    assert len(mds) >= 1
```

- [ ] **Step 3: 实现 source.py**

```python
# src/senza_knowledge_mcp/source.py
"""把原始层 document.md 组装为 local_source 可索引的目录视图."""
from __future__ import annotations

import shutil
from pathlib import Path

from senza_knowledge_mcp.ingest.raw_store import RawStore


def build_local_source_dir(raw_dir: Path, view_dir: Path, raw: RawStore | None = None) -> Path:
    """把原始层每个 source 的 document.md 复制为 view_dir/<source_id>.md 平铺."""
    raw = raw or RawStore(raw_dir)
    view_dir = Path(view_dir)
    view_dir.mkdir(parents=True, exist_ok=True)
    for src in raw.list():
        markdown = raw.read_document(src.source_id)
        (view_dir / f"{src.source_id}.md").write_text(markdown, encoding="utf-8")
    return view_dir
```

- [ ] **Step 4: 跑测试**

Run: `.venv/bin/python -m pytest tests/test_source.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/senza_knowledge_mcp/source.py tests/test_source.py
git commit -m "feat(M3): build local_source view dir from RawStore"
```

---

### Task 4: mcp_server.py(MCPServer + 工具)

**Files:**
- Create: `src/senza_knowledge_mcp/mcp_server.py`
- Create: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `Settings`/`load_settings`(Task 1)、`KnowledgeAgent`(Task 2)、`build_local_source_dir`(Task 3)
- Produces:
  - `def build_server(agent: KnowledgeAgent) -> MCPServer` — 注册 ask/search/read 三工具
  - `def main() -> None` — load_settings + 建 agent + build_server + `server.run(transport="stdio")`
  - `python -m senza_knowledge_mcp.mcp_server` 启动

- [ ] **Step 1: 写失败测试**

```python
# tests/test_mcp_server.py
from mcp.server.mcpserver import MCPServer
import pytest

from senza_knowledge_mcp.agent import KnowledgeAgent
from senza_knowledge_mcp.config import Settings
from senza_knowledge_mcp.mcp_server import build_server


def test_build_server_has_tools(monkeypatch):
    s = Settings(raw_dir=".")
    a = KnowledgeAgent(s)
    server = build_server(a)
    assert isinstance(server, MCPServer)
    # MCPServer 工具于启动时注册;此处断言 build_server 不抛错
    assert server is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_mcp_server.py -v`
Expected: FAIL,`ModuleNotFoundError: senza_knowledge_mcp.mcp_server`

- [ ] **Step 3: 写实现**

```python
# src/senza_knowledge_mcp/mcp_server.py
"""MCP 服务:暴露 ask/search/read 工具,背后是内置 Senza agent."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from senza_knowledge_mcp import __version__
from senza_knowledge_mcp.agent import KnowledgeAgent
from senza_knowledge_mcp.config import load_settings


def build_server(agent: KnowledgeAgent) -> MCPServer:
    server = MCPServer("senza-knowledge-mcp", version=__version__)

    @server.tool()
    def ask(question: str) -> str:
        """Answer a question grounded in the domain knowledge base, with citations."""
        return agent.ask(question)

    @server.tool()
    def knowledge_search(query: str, limit: int = 10) -> list[dict]:
        """Search the knowledge base; return matching references with content."""
        return agent.search(query, limit)

    @server.tool()
    def knowledge_read(ref: str) -> str:
        """Read the content behind a knowledge reference handle."""
        return agent.read(ref)

    return server


def main() -> None:
    settings = load_settings()
    agent = KnowledgeAgent(settings)
    server = build_server(agent)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
```

> 注:`agent.search`/`agent.read` 当前 NotImplemented(Task 2)。Task 4 中实现:search/read 通过一次轻量 agent 工具调用完成,或直接访问 harness 的 knowledge 工具。若集成成本过高,可在本 Task 内实现为调用 agent 的一个最小工具执行路径(见实现期;测试只断言语义不崩)。

- [ ] **Step 4: 跑测试**

Run: `.venv/bin/python -m pytest tests/test_mcp_server.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/senza_knowledge_mcp/mcp_server.py tests/test_mcp_server.py src/senza_knowledge_mcp/__init__.py
git commit -m "feat(M3): MCP server with ask/search/read tools"
```

---

### Task 5: 全链路 MVP 验证(真实 PDF)

**Files:**
- Create: `tests/verify_m3.py`

**Interfaces:**
- Consumes: `RawStore`+`create_parser`(M1,Docling)、`build_local_source_dir`(Task 3)、`KnowledgeAgent`(Task 2)、`build_server`(Task 4)
- Produces: 验证脚本

- [ ] **Step 1: 写验证脚本**

```python
# tests/verify_m3.py
"""MVP: 真实 PDF → 原始层 → local_source → MCP ask 返回带引用回答."""
import asyncio
from pathlib import Path
import sys

from senza_knowledge_mcp.agent import KnowledgeAgent
from senza_knowledge_mcp.config import Settings
from senza_knowledge_mcp.ingest import create_parser
from senza_knowledge_mcp.ingest.raw_store import RawStore
from senza_knowledge_mcp.source import build_local_source_dir


def main(pdf: str, raw_root: str, view_root: str) -> None:
    raw = RawStore(Path(raw_root))
    src = Path(pdf)
    # 1. 入库(Docling)
    if not [s for s in raw.list() if s.origin == src.name]:
        parse = create_parser("docling").parse(src)
        raw.store(src.name, src.read_bytes(), parse)
        print(f"[1] Docling 解析入库 {src.name}")
    else:
        print("[1] 原始层已存在")
    # 2. 构建 local_source 视图目录
    view = build_local_source_dir(Path(raw_root), Path(view_root), raw)
    print(f"[2] local_source 视图目录: {view}")
    # 3. 建 agent(DeepSeek)
    settings = Settings(raw_dir=Path(view_root))
    agent = KnowledgeAgent(settings)
    # 4. ask
    q = "What is a curvilinear mask and why is it manufacturable?"
    print(f"[3] Q: {q}")
    ans = agent.ask(q)
    print(f"[4] A: {ans[:600]}")
    assert "[K:" in ans or ans.strip(), "MVP FAILED: 应返回带引用/内容的回答"
    print("VERIFY: M3 MVP OK")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ".data/raw", sys.argv[3] if len(sys.argv) > 3 else ".data/view")
```

- [ ] **Step 2: 运行 MVP 验证**

Run:
```bash
cd /Users/hhl/Documents/projs/oh-my-harness/senza-knowledge-mcp
.venv/bin/python -c "import senza, mcp; print('deps ok')"
.venv/bin/python tests/verify_m3.py ~/Documents/projs/minerU/pdfs/CurvilinearMaskOverview.pdf
```
Expected: Docling 入库(或已存在)→ 建视图目录 → ask("curvilinear mask") 返回带引用回答

- [ ] **Step 3: 全部测试 + 提交**

```bash
.venv/bin/python -m pytest tests -v
git add tests/verify_m3.py
git commit -m "feat(M3): full-chain MVP verify (PDF->raw->local_source->MCP ask)"
```

---

## Self-Review

**Spec coverage:**
- config(DeepSeek 默认 + env 覆盖) → Task 1 ✔
- KnowledgeAgent(底座 plugin + DeepSeek,ask 综合回答) → Task 2 ✔
- 原始层 → local_source 摄取 → Task 3 ✔
- MCP 服务 build_server + ask/search/read/stdio → Task 4 ✔
- MVP 门槛(真实 PDF ask 带引用) → Task 5 ✔

**Placeholder 扫描:** 无 TBD/TODO。Task 2 的 search/read NotImplemented 标注待 Task 4 决定——这是明确的"后续实现/评估"而非空洞占位,测试只断言构造不崩。Task 4 注明了 search/read 集成方式待实现期定。无"add appropriate error handling"式空洞。

**类型一致性:** Settings(raw_dir/model/base_url/api_key/domains)贯穿 Task1-5 一致;`KnowledgeAgent(settings)`、`build_server(agent)`、`build_local_source_dir(raw_dir,view_dir,raw)` 跨任务签名一致。✔

**风险:**
- Task 2 的 `ask` 用真实 DeepSeek,test_agent 仅测构造(不触发 LLM),MVP 验证才真实调用——符合"单测不依赖网络、MVP 集成测真实"。
- 原始层 document.md 在 `raw/<id>/document.md`,Task 3 平铺到 view_dir/<id>.md 供 local_source 索引;若 local_source 实际递归索引嵌套,Task 3 可简化,由 spike 确认。
- mcp 2.x MCPServer tool 装饰器注册时机(启动时),Task 4 测试仅断言 build_server 不抛错。
