---
date: 2026-09-01
status: spec
scope: M2
project: senza-knowledge-mcp
repo: oh-my-harness/senza-knowledge-mcp
---

# M2 Spec · 自建知识检索(RAG)

## 背景与目标

M1 已完成:原始层存储(不可变文档)+ Docling 解析器抽象(文档+图片)。M2 在原始层之上**自建检索能力**,提供"把文档转成可检索索引、按语义查询返回带引用的 chunk"。检索是知识库服务的核心能力,由本仓库自己实现,**不依赖底座现成的 `LocalDocumentSource`**——本项目是提供方本体,不是调用方。

### 目标
- 在原始层的 `document.md` 之上,自建 LanceDB 向量索引。
- 提供检索:给定 query,返回相关 chunk + 引用(source/ordinal/文档位置)。
- 检索逻辑本项目自建,设计对齐 Folumi 的 `LanceDbRag`(切分、溯源、引用语义)。

### 非目标(边界)
- 不做 LLM 综合回答(M2 只做检索;回答交给调用方/后续里程碑)。
- 不做多源联邦/权限/多用户(二阶段)。
- 图片检索(M2 只索引文本;图片使用时按需送多模态)。

## 架构位置

```
原始层 document.md
        │  M2 入库indexing
        ▼
LanceDB 索引(LanceDbRag 移植)
        │  检索
        ▼
检索 API:search(query, limit) -> 带引用 chunk
        │   (M3 将暴露为 MCP 工具 / M4 管理后台)
```

## 设计与数据模型(对齐 Folumi 设计)

### 数据库/存储
- **LanceDB** 向量库,每文档一个 source,chunk 粒度。
- 存储位置:`.data/index/`(派生数据,可重建)。

### 数据结构(chunk 行)
对齐 Folumi `KnowledgeRow` 语义:
- `item_id`(稳定,由 kb/source/ordinal 派生)
- `revision`(内容哈希,变更可检测→重排)
- `document_id`(原始层 source_id)
- `ordinal`(chunk 序号)
- `text`(chunk 文本)
- `embedding`(向量)
- `knowledge_uri`(溯源 URI,kb/source/ordinal)

### 切分
- `chunk_text(text, max_chars, overlap_chars)` 带重叠切分(Folumi 设计)。

### Embedding
- `EmbeddingConfig` 抽象 embedding 来源(模型/维度)。
- 生产:调外部 embedding API(OpenAI/DeepSeek 兼容,模型可选)。
- 测试:hash 伪嵌入(Folumi `hash_embedding` 思想)。

## 组件(本项目自建,Python)

### `src/senza_knowledge_mcp/index/lancedb_rag.py`
移植 Folumi `LanceDbRag` 的 Python 实现:
- `LanceDbRag(root, embedding)` — 连接/建库
- `ingest(document_id, text) -> count` — 切分→embed→写 LanceDB(item_id/revision 溯源)
- `search(query, limit) -> list[SearchHit]` — 语义检索,返回带引用
- `delete_source / chunks_for_source` — 管理与重建
- `chunk_text` / `stable_item_id` / `knowledge_uri` / `revision_digest` — 内部工具
- `EmbeddingConfig` + `embed_texts` — embedding 抽象(API 实现 + hash 测试实现)

依赖:LanceDB Python、embedding 客户端(OpenAI 兼容)。

## 接口

```python
class EmbeddingConfig:
    provider: str      # "openai" | "deepseek" | "hash"(测试) 等
    model: str
    dimensions: int

class SearchHit:
    document_id: str     # 原始层 source_id
    ordinal: int
    text: str
    score: float

class LanceDbRag:
    def __init__(self, root: Path, embedding: EmbeddingConfig): ...
    async def ingest(self, document_id: str, text: str) -> int: ...
    async def search(self, query: str, limit: int = 10) -> list[SearchHit]: ...
    async def delete_source(self, document_id: str) -> int: ...
    async def chunks_for_source(self, document_id: str) -> list[SourceChunk]: ...
```

## 测试(TDD)

1. 切分: `chunk_text` 边界(长度/重叠/单段)。
2. 入库→检索: ingest 一段文本 → search 相关 query 命中,无关不命中。
3. 溯源: chunk 的 document_id/ordinal 正确,匹配原始层。
4. 哈希嵌入下,语义检索的确定性(测试用 hash embedding)。
5. 重建: delete_source → 重 ingestion → 索引一致。
6. 与 M1 原始层对接: pre-processing 原始层 `document.md` → ingest → 检索命中。

## 里程碑内的验证(MVP 门槛)

- 对已入库的 CurvilinearMaskOverview PDF(原始层有 document.md),ingest 后 `search("curvilinear mask manufacturable")` 返回含相关文本 + 引用(doc/ordinal)。
- 无关 query 返回低相关/空。
- 全部测试绿。

## 风险
1. embedding API 成本/可用性:需 API Key;离线需本地模型。
2. embedding 质量对领域英文是否够用:MVP 先通用 API,后续可换领域模型。
3. LanceDB Python 与大索引性能:MVP 规模小,后续关注。

## 相关
- `docs/领域知识库-一阶段设计.md`
- Folumi `crates/tutor-rag/src/lib.rs`(设计参考)
- M1: `src/senza_knowledge_mcp/ingest/`
