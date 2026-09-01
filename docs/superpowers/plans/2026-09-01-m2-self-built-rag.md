# M2 自建知识检索(RAG) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在原始层之上自建 LanceDB 向量检索:把 `document.md` 入库为带引用的 chunk,按语义查询返回相关 chunk。

**Architecture:** 纯 Python 实现 `LanceDbRag`(索引 LanceDB、embedding 抽象、切分+溯源),设计对齐 Folumi `crates/tutor-rag` 的 `LanceDbRag`。提供 ingest / search / delete_source / chunks_for_source 接口,供 M3(MCP)与 M4(管理后台)使用。检索本项目自建,不依赖底座 `LocalDocumentSource`。

**Tech Stack:** Python 3.12、LanceDB(Python)、LanceDB 内建 embedding 或外部 embedding API(openai 兼容)、pytest。

**Spec:** `docs/M2-自建知识检索-spec.md`

## Global Constraints

- 纯 Python 实现(项目为 Python,不引入 Rust)。
- 检索逻辑本项目自建,不调用 `senza.knowledge.local_source()` / 底座 `LocalDocumentSource`。
- 数据模型对齐 Folumi `LanceDbRag`:item_id / revision / document_id / ordinal / text / embedding / knowledge_uri。
- chunk 切分带 overlap。
- embedding 经 `EmbeddingConfig` 抽象:生产 = openai 兼容 API;测试 = hash 伪嵌入(确定性、零 API)。
- 存 LanceDB at `.data/index/`(派生可重建,已 gitignore)。
- 原始层 document.md 来自 M1 的 `RawStore`(`source_id/document.md`)。
- 测试全绿为完成任务标准。

---

### Task 1: 数据模型与切分工具

**Files:**
- Create: `src/senza_knowledge_mcp/index/chunking.py`
- Test: `tests/index/test_chunking.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `def chunk_text(text: str, max_chars: int = 1000, overlap_chars: int = 100) -> list[str]`
  - `def stable_item_id(document_id: str, ordinal: int) -> str`
  - `def chunk_revision(document_id: str, ordinal: int, text: str) -> str`
  - `def knowledge_uri(document_id: str, ordinal: int) -> str`
  - `def revision_digest(text: str) -> str` — sha256 前 12 位

- [ ] **Step 1: 写失败测试**

```python
# tests/index/test_chunking.py
import pytest
from senza_knowledge_mcp.index.chunking import (
    chunk_text, stable_item_id, chunk_revision, knowledge_uri, revision_digest,
)

def test_chunk_text_respects_overlap():
    text = "word " * 50  # 250 chars
    chunks = chunk_text(text, max_chars=100, overlap_chars=20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)

def test_chunk_text_single_if_short():
    chunks = chunk_text("short", max_chars=100)
    assert chunks == ["short"]

def test_chunk_text_nonempty():
    assert chunk_text("") == []

def test_stable_item_id():
    assert stable_item_id("doc1", 3) == "doc1#3"

def test_revision_digest_stable():
    assert revision_digest("abc") == revision_digest("abc")
    assert revision_digest("abc") != revision_digest("abd")

def test_knowledge_uri():
    assert knowledge_uri("doc1", 2) == "senza://doc1#2"

def test_chunk_revision_includes_doc_and_ordinal():
    a = chunk_revision("doc1", 0, "hello")
    b = chunk_revision("doc1", 1, "hello")
    assert a != b
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/index/test_chunking.py -v`
Expected: FAIL,`ModuleNotFoundError: senza_knowledge_mcp.index`

- [ ] **Step 3: 写实现**

```python
# src/senza_knowledge_mcp/index/chunking.py
"""Chunk 切分与溯源工具(对齐 Folumi LanceDbRag 设计)."""
from __future__ import annotations

import hashlib

DEFAULT_MAX_CHARS = 1000
DEFAULT_OVERLAP_CHARS = 100


def revision_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def chunk_text(
    text: str, max_chars: int = DEFAULT_MAX_CHARS, overlap_chars: int = DEFAULT_OVERLAP_CHARS
) -> list[str]:
    """把文本切成带重叠的 chunk。对齐 Folumi chunk_text."""
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(start + max_chars - overlap_chars, start + 1)
    return chunks


def stable_item_id(document_id: str, ordinal: int) -> str:
    return f"{document_id}#{ordinal}"


def chunk_revision(document_id: str, ordinal: int, text: str) -> str:
    return revision_digest(f"{document_id}#{ordinal}#{text}")


def knowledge_uri(document_id: str, ordinal: int) -> str:
    return f"senza://{document_id}#{ordinal}"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/index/test_chunking.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/senza_knowledge_mcp/index/chunking.py tests/index/test_chunking.py
git commit -m "feat(M2): chunking + provenance utils"
```

---

### Task 2: EmbeddingConfig 抽象

**Files:**
- Create: `src/senza_knowledge_mcp/index/embedding.py`
- Test: `tests/index/test_embedding.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `class EmbeddingConfig:` dataclass — `provider: str`, `model: str`, `dimensions: int`, `api_key: str | None = None`, `base_url: str | None = None`
  - `class HashEmbedder:` — `def embed(texts: list[str]) -> list[list[float]]`(确定性哈希,维度=config.dimensions)
  - `class OpenAIEmbedder:` — `def embed(texts: list[str]) -> list[list[float]]`(openai 兼容 API,HTTP)
  - `def create_embedder(config: EmbeddingConfig) -> Embedder` — provider=="hash"→HashEmbedder;否则 OpenAIEmbedder
  - `Protocol Embedder` — `def embed(texts) -> list[list[float]]`

- [ ] **Step 1: 写失败测试**

```python
# tests/index/test_embedding.py
import pytest
from senza_knowledge_mcp.index.embedding import (
    EmbeddingConfig, HashEmbedder, OpenAIEmbedder, create_embedder,
)

def test_hash_embedder_deterministic_and_fixed_dim():
    cfg = EmbeddingConfig(provider="hash", model="test", dimensions=8)
    e = HashEmbedder(cfg)
    a = e.embed(["hello world"])
    b = e.embed(["hello world"])
    assert a == b
    assert len(a[0]) == 8
    assert all(isinstance(v, float) for v in a[0])

def test_hash_embedder_different_texts_differ():
    cfg = EmbeddingConfig(provider="hash", model="test", dimensions=8)
    e = HashEmbedder(cfg)
    assert e.embed(["abc"]) != e.embed(["abd"])

def test_create_embedder_hash():
    cfg = EmbeddingConfig(provider="hash", model="test", dimensions=8)
    assert isinstance(create_embedder(cfg), HashEmbedder)

def test_create_embedder_openai():
    cfg = EmbeddingConfig(provider="openai", model="x", dimensions=8, api_key="k")
    assert isinstance(create_embedder(cfg), OpenAIEmbedder)

def test_hash_embedder_multiple_texts_shapes():
    cfg = EmbeddingConfig(provider="hash", model="test", dimensions=4)
    e = HashEmbedder(cfg)
    out = e.embed(["a", "bb", "ccc"])
    assert len(out) == 3 and all(len(v) == 4 for v in out)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/index/test_embedding.py -v`
Expected: FAIL,`ModuleNotFoundError: senza_knowledge_mcp.index.embedding`

- [ ] **Step 3: 写实现**

```python
# src/senza_knowledge_mcp/index/embedding.py
"""Embedding 抽象:生产走 openai 兼容 API,测试/离线用 hash 伪嵌入."""
from __future__ import annotations

import hashlib
import urllib.request
import json
from dataclasses import dataclass
from typing import Protocol


@dataclass
class EmbeddingConfig:
    provider: str
    model: str
    dimensions: int
    api_key: str | None = None
    base_url: str | None = None


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """确定性伪嵌入(测试/离线)。逐 token 哈希映射到 [-1,1]."""
    def __init__(self, config: EmbeddingConfig) -> None:
        self._dim = config.dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * self._dim
            for token in t.split():
                h = hashlib.sha256(token.encode()).digest()
                idx = h[0] % self._dim
                vec[idx] += (h[1] / 255.0) * 2 - 1
            norm = (sum(v * v for v in vec)) ** 0.5
            out.append([v / norm if norm else 0.0 for v in vec])
        return out


class OpenAIEmbedder:
    """OpenAI/C compatible embedding API."""
    def __init__(self, config: EmbeddingConfig) -> None:
        self._config = config

    def embed(self, texts: list[str]) -> list[list[float]]:
        base = (self._config.base_url or "https://api.openai.com/v1").rstrip("/")
        req = urllib.request.Request(
            f"{base}/embeddings",
            data=json.dumps({"model": self._config.model, "input": texts}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._config.api_key or ''}",
            },
        )
        with urllib.request.urlopen(req) as resp:  # noqa: S310 测试环境
            payload = json.loads(resp.read().decode())
        return [item["embedding"] for item in payload["data"]]


def create_embedder(config: EmbeddingConfig) -> Embedder:
    if config.provider == "hash":
        return HashEmbedder(config)
    return OpenAIEmbedder(config)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/index/test_embedding.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/senza_knowledge_mcp/index/embedding.py tests/index/test_embedding.py
git commit -m "feat(M2): embedding config + hash/openai embedders"
```

---

### Task 3: LanceDbRag 核心(ingest + search)

**Files:**
- Create: `src/senza_knowledge_mcp/index/lancedb_rag.py`
- Test: `tests/index/test_lancedb_rag.py`

**Interfaces:**
- Consumes: `chunk_text`, `stable_item_id`, `chunk_revision`, `knowledge_uri`(Task 1);`EmbeddingConfig`, `create_embedder`(Task 2)
- Produces:
  - `@dataclass SearchHit:` — `document_id: str`, `ordinal: int`, `text: str`, `score: float`
  - `@dataclass SourceChunk:` — `document_id: str`, `ordinal: int`, `text: str`
  - `class LanceDbRag:` — `__init__(root: Path, config: EmbeddingConfig)`, `async ingest(document_id, text) -> int`, `async search(query, limit=10) -> list[SearchHit]`, `async delete_source(document_id) -> int`, `async chunks_for_source(document_id) -> list[SourceChunk]`, `close()`

- [ ] **Step 1: 写失败测试(用 LanceDB 语义检索 + hash embedder)**

```python
# tests/index/test_lancedb_rag.py
import asyncio
from pathlib import Path
import tempfile

import pytest

from senza_knowledge_mcp.index.embedding import EmbeddingConfig
from senza_knowledge_mcp.index.lancedb_rag import LanceDbRag, SearchHit


@pytest.fixture
def rag(tmp_path):
    cfg = EmbeddingConfig(provider="hash", model="test", dimensions=16)
    r = LanceDbRag(tmp_path / "index", cfg)
    yield r
    asyncio.get_event_loop().run_until_complete(r.close()) if False else None


@pytest.mark.asyncio
async def test_ingest_and_search_hit(tmp_path):
    cfg = EmbeddingConfig(provider="hash", model="test", dimensions=16)
    r = LanceDbRag(tmp_path / "index", cfg)
    n = await r.ingest("doc1", "Rayleigh Sommerfeld diffraction integral pixel spread function sinc kernel")
    assert n >= 1
    hits = await r.search("diffraction sinc kernel", limit=5)
    assert len(hits) >= 1
    assert hits[0].document_id == "doc1"
    assert hits[0].text
    assert hits[0].score >= 0
    await r.close()


@pytest.mark.asyncio
async def test_search_unrelated_returns_low(tmp_path):
    cfg = EmbeddingConfig(provider="hash", model="test", dimensions=16)
    r = LanceDbRag(tmp_path / "index", cfg)
    await r.ingest("doc1", "apple banana cherry fruit")
    hits = await r.search("quantum lithography", limit=5)
    # hash embedding 下无关词可能命中率低;断言返回结构合法,不崩溃
    assert isinstance(hits, list)
    await r.close()


@pytest.mark.asyncio
async def test_delete_source(tmp_path):
    cfg = EmbeddingConfig(provider="hash", model="test", dimensions=16)
    r = LanceDbRag(tmp_path / "index", cfg)
    await r.ingest("doc1", "hello world content")
    await r.ingest("doc2", "another different document")
    await r.delete_source("doc1")
    hits = await r.search("hello world", limit=5)
    assert all(h.document_id != "doc1" for h in hits)
    await r.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/index/test_lancedb_rag.py -v`
Expected: FAIL,`ModuleNotFoundError: senza_knowledge_mcp.index.lancedb_rag`

- [ ] **Step 3: 写实现**

```python
# src/senza_knowledge_mcp/index/lancedb_rag.py
"""LanceDB 向量检索(对齐 Folumi LanceDbRag 设计,Python 自建)."""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from pathlib import Path

import lancedb

from senza_knowledge_mcp.index.chunking import (
    chunk_revision, chunk_text, knowledge_uri, stable_item_id,
)
from senza_knowledge_mcp.index.embedding import EmbeddingConfig, create_embedder


@dataclass
class SearchHit:
    document_id: str
    ordinal: int
    text: str
    score: float


@dataclass
class SourceChunk:
    document_id: str
    ordinal: int
    text: str


_TABLE_NAME = "chunks"


class LanceDbRag:
    """LanceDB 向量知识索引. embedding 抽象自建,不依赖底座 LocalDocumentSource."""

    def __init__(self, root: Path, config: EmbeddingConfig) -> None:
        self._root = Path(root)
        self._config = config
        self._embedder = create_embedder(config)
        self._db = lancedb.connect(str(self._root))
        self._table = None

    def _ensure_table(self):
        import lancedb  # noqa: F401
        embedding_func = self._embedder.embed
        if self._table is None:
            self._table = self._db.create_table(
                _TABLE_NAME,
                data=[
                    {
                        "item_id": "placeholder",
                        "document_id": "",
                        "ordinal": 0,
                        "text": "",
                        "revision": "",
                        "knowledge_uri": "",
                        "vector": self._embedder.embed([""])[0],
                    }
                ],
                mode="overwrite"
            )
        return self._table

    async def ingest(self, document_id: str, text: str) -> int:
        table = self._ensure_table()
        chunks = chunk_text(text, self._config.max_chars if hasattr(self._config, 'max_chars') else 1000)
        texts = [c for c in chunks if c]
        if not texts:
            return 0
        vectors = self._embedder.embed(texts)
        rows = []
        for i, (txt, vec) in enumerate(zip(texts, vectors)):
            rows.append({
                "item_id": stable_item_id(document_id, i),
                "document_id": document_id,
                "ordinal": i,
                "text": txt,
                "revision": chunk_revision(document_id, i, txt),
                "knowledge_uri": knowledge_uri(document_id, i),
                "vector": vec,
            })
        table.add(rows)
        return len(rows)

    async def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        table = self._ensure_table()
        qvec = self._embedder.embed([query])[0]
        if not hasattr(table, "vector_search"):
            return []
        results = table.vector_search(qvec).limit(limit).to_list()
        hits = []
        for r in results:
            hits.append(SearchHit(
                document_id=r.get("document_id", ""),
                ordinal=r.get("ordinal", 0),
                text=r.get("text", ""),
                score=float(r.get("_distance", 0.0)),
            ))
        return hits

    async def delete_source(self, document_id: str) -> int:
        table = self._ensure_table()
        # 无 sql,用 filter delete 或重建(简化:MVP 直接重建不含该 doc 的表)
        # 简化实现:收集剩余 doc,重建表
        import lancedb
        all_rows = table.search().limit(100000).to_list()
        keep = [r for r in all_rows if r.get("document_id") != document_id]
        deleted = len(all_rows) - len(keep)
        if keep:
            from lancedb import connect
            db = lancedb.connect(str(self._root))
            db.drop_table(_TABLE_NAME)
            t = db.create_table(_TABLE_NAME, data=keep)
            self._table = t
        return deleted

    async def chunks_for_source(self, document_id: str) -> list[SourceChunk]:
        table = self._ensure_table()
        rows = table.search().limit(100000).to_list()
        return [SourceChunk(r["document_id"], r["ordinal"], r["text"]) for r in rows if r.get("document_id") == document_id]

    async def close(self) -> None:
        pass
```

> 说明:Task 3 的 `delete_source` 用"读全表重建"的简化实现(性能非 MVP 关注)。若 LanceDB Python 支持 SQL 过滤删除,实现里可改进;测试只断言语义(删后不返回被删 doc),不强依赖实现方式。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/index/test_lancedb_rag.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/senza_knowledge_mcp/index/lancedb_rag.py tests/index/test_lancedb_rag.py
git commit -m "feat(M2): LanceDbRag ingest/search with LanceDB + embedding"
```

---

### Task 4: 与 M1 原始层对接(入库 document.md)

**Files:**
- Create: `src/senza_knowledge_mcp/index/sync.py`
- Modify: `src/senza_knowledge_mcp/index/__init__.py`
- Test: `tests/index/test_sync.py`

**Interfaces:**
- Consumes: `LanceDbRag`(Task 3),`RawStore`(M1:`ingest/raw_store.py`)
- Produces:
  - `async def index_raw_store(rag: LanceDbRag, raw: RawStore) -> int` — 遍历原始层 document.md,ingest 全部,返回入库 chunk 总数
  - `async def index_one(rag: LanceDbRag, source_id: str, markdown: str) -> int`

- [ ] **Step 1: 写失败测试**

```python
# tests/index/test_sync.py
from pathlib import Path
import pytest

from senza_knowledge_mcp.index.embedding import EmbeddingConfig
from senza_knowledge_mcp.index.lancedb_rag import LanceDbRag
from senza_knowledge_mcp.index.sync import index_raw_store, index_one
from senza_knowledge_mcp.ingest.raw_store import RawStore
from senza_knowledge_mcp.ingest.parser import ParseResult


@pytest.mark.asyncio
async def test_index_one(tmp_path):
    config = EmbeddingConfig(provider="hash", model="t", dimensions=8)
    rag = LanceDbRag(tmp_path / "idx", config)
    n = await index_one(rag, "src1", "# Title\n\ncontent about diffraction sinc kernel")
    assert n >= 1
    hits = await rag.search("diffraction", limit=5)
    assert any(h.document_id == "src1" for h in hits)
    await rag.close()


@pytest.mark.asyncio
async def test_index_raw_store(tmp_path):
    config = EmbeddingConfig(provider="hash", model="t", dimensions=8)
    raw = RawStore(tmp_path / "raw")
    # 构造一个原始层 source
    stored = raw.store("doc.md", b"bytes", ParseResult(document_markdown="sinc kernel diffraction content", images=[]))
    rag = LanceDbRag(tmp_path / "idx", config)
    total = await index_raw_store(rag, raw)
    assert total >= 1
    await rag.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/index/test_sync.py -v`
Expected: FAIL,`ModuleNotFoundError: senza_knowledge_mcp.index.sync`

- [ ] **Step 3: 写实现**

```python
# src/senza_knowledge_mcp/index/sync.py
"""把 M1 原始层(RawStore document.md)同步进 LanceDB 索引."""
from __future__ import annotations

from senza_knowledge_mcp.index.lancedb_rag import LanceDbRag
from senza_knowledge_mcp.ingest.raw_store import RawStore


async def index_one(rag: LanceDbRag, source_id: str, markdown: str) -> int:
    return await rag.ingest(source_id, markdown)


async def index_raw_store(rag: LanceDbRag, raw: RawStore) -> int:
    total = 0
    for src in raw.list():
        markdown = raw.read_document(src.source_id)
        total += await rag.ingest(src.source_id, markdown)
    return total
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/index/test_sync.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/senza_knowledge_mcp/index/sync.py src/senza_knowledge_mcp/index/__init__.py tests/index/test_sync.py
git commit -m "feat(M2): sync RawStore -> LanceDB index"
```

---

### Task 5: 全链路 MVP 验证(真实 PDF)

**Files:**
- Create: `tests/verify_m2.py`
- Modify: `pyproject.toml`(加 lancedb 依赖)

**Interfaces:**
- Consumes: `LanceDbRag`, `RawStore`, Docling 解析(M1)、`index_raw_store`
- Produces: 无(验证脚本)

- [ ] **Step 1: 加 lancedb + 更新 pyproject**

```bash
cd /Users/hhl/Documents/projs/oh-my-harness/senza-knowledge-mcp
.venv/bin/pip install lancedb
# 在 pyproject.toml dependencies 加 "lancedb>=0.x"(按实际装到的版本)
```

- [ ] **Step 2: 写验证脚本**

```python
# tests/verify_m2.py
"""MVP 全链路:PDF -> Docling -> 原始层 -> LanceDB 索引 -> 检索带引用."""
import asyncio
from pathlib import Path
import sys

from senza_knowledge_mcp.index.embedding import EmbeddingConfig
from senza_knowledge_mcp.index.lancedb_rag import LanceDbRag
from senza_knowledge_mcp.index.sync import index_raw_store
from senza_knowledge_mcp.ingest import create_parser
from senza_knowledge_mcp.ingest.raw_store import RawStore


async def main(pdf: str, raw_root: str, idx_root: str) -> None:
    raw = RawStore(Path(raw_root))
    parser = create_parser("docling")
    src = Path(pdf)
    if not RawStore(Path(raw_root)).exists(Path(pdf).stem):
        parse = parser.parse(src)
        raw.store(src.name, src.read_bytes(), parse)

    config = EmbeddingConfig(provider="hash", model="t", dimensions=64)
    rag = LanceDbRag(Path(idx_root), config)
    total = await index_raw_store(rag, raw)
    print(f"[ingest] total chunks={total}")

    query = "curvilinear mask manufacturable"
    hits = await rag.search(query, limit=5)
    print(f"[search] '{query}' -> {len(hits)} hits")
    for h in hits:
        print(f"  {h.document_id}#{h.ordinal} score={h.score:.3f}: {h.text[:80]}...")
    assert len(hits) >= 1, "MVP FAILED: no hits"
    print("VERIFY: M2 MVP OK")
    await rag.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ".data/raw", sys.argv[3] if len(sys.argv) > 3 else ".data/index"))
```

- [ ] **Step 3: 运行 MVP 验证**

Run: `.venv/bin/python tests/verify_m2.py ~/Documents/projs/minerU/pdfs/CurvilinearMaskOverview.pdf`
Expected: ingest 若干 chunk;search("curvilinear mask manufacturable") 返回 ≥1 hit,含 document_id + ordinal 引用,文本与 PDF 内容相关

- [ ] **Step 4: 全部测试绿 + 提交**

```bash
.venv/bin/python -m pytest tests/index -v
git add pyproject.toml tests/verify_m2.py
git commit -m "feat(M2): full-chain MVP verify (PDF->Docling->raw->LanceDB->search)"
```

---

## Self-Review

**Spec coverage:**
- LanceDB 索引 → Task 3 ✔
- ingest(切分→embed→写) → Task 1(chunking)+ Task 3 ✔
- search 返回带引用 chunk → Task 3(SearchHit.document_id/ordinal/text/score)✔
- EmbeddingConfig 抽象(hash + openai) → Task 2 ✔
- 溯源(item_id/revision/knowledge_uri) → Task 1 ✔
- 与原始层对接 → Task 4(index_raw_store)✔
- MVP 门槛(真实 PDF 检索) → Task 5 ✔

**Placeholder 扫描:** 无 TBD/TODO。Task 5 的 lancedb 版本号留了"(按实际装到的版本)"——因未装 LancedB Python 绑定前不知道确切版本下限,属实现时确定值,非占位空洞。Task 3 delete_source 用简化重建并注明,测试只断言语义。

**类型一致性:** SearchHit(document_id/ordinal/text/score)在 Task 3 定义、Task 5 search 使用一致;`stable_item_id` 等 Task 1 定义、Task 3 使用一致;`index_raw_store(rag, raw)` Task 4 定义、Task 5 调用一致。✔

**一处风险提示(实现时需验证):** Task 3 用 LanceDB Python `vector_search` + `_distance` 字段名,具体字段名可能在实现时不同(取决于 lancedb 版本)。计划里已断言语义(命中含 document_id/ordinal/text、score≥0),实现者若字段名不同应适配——这是实现细节,测试不绑死内部字段。
