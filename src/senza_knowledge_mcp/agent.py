"""内置 Senza agent:挂 knowledge.plugin,做知识检索 + 综合回答.

M3 是 agent 即服务:检索统一走底座 knowledge.plugin()(LocalDocumentSource),
综合由内置 Senza agent 完成。不保留 M2 自建 LanceDbRag。

关键实现点:
- harness 长驻复用(不每调用 `with` —— `with` 退出会 abort prompt,导致后续调用挂起)。
- 用线程锁串行化工具调用,避免 MCP 并发冲突。
- close() 时才 shutdown。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import senza

from senza_knowledge_mcp.config import Settings
from senza_knowledge_mcp.ingest.raw_store import RawStore


def _parse_hits(text: str, limit: int) -> list[dict]:
    """解析 agent 返回的检索 hits(尽力 JSON;失败则整段作为一条)."""
    try:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end > start:
            data = json.loads(text[start : end + 1])
            if isinstance(data, list):
                return [{"ref": d.get("ref", ""), "text": d.get("text", "")} for d in data][:limit]
    except Exception:  # noqa: BLE001
        pass
    return [{"ref": "", "text": text[:2000]}]


class KnowledgeAgent:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._harness = None
        self._lock = threading.Lock()
        self._raw = RawStore(Path(settings.raw_dir))

    # ---- 快数据工具(不经 agent,毫秒级) ----

    def list_docs(self) -> list[dict]:
        """列出知识库所有 source(原始层身份)."""
        return [s.to_dict() for s in self._raw.list()]

    def get_doc(self, doc: str) -> str:
        """按 source_id 或文档名直读 document.md 全量."""
        # 先按 source_id
        if self._raw.exists(doc):
            return self._raw.read_document(doc)
        # 再按文档名(origin)匹配
        for s in self._raw.list():
            if s.origin == doc or Path(s.origin).stem == doc:
                return self._raw.read_document(s.source_id)
        raise KeyError(f"no such doc: {doc}")

    def build_harness(self) -> "senza.AgentHarness":
        if self._harness is not None:
            return self._harness
        # 知识源:索引 raw_dir 目录(md/txt 文档);底座递归 + 扩展过滤
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
                "knowledge base with knowledge_search, read exact references, then "
                "answer based on retrieved content and cite the source."
            )
            .build()
        )
        return self._harness

    def ask(self, question: str) -> str:
        h = self.build_harness()
        with self._lock:
            h.prompt(question)
            h.wait_for_settled()
            return h.last_response()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """让内置 agent 检索知识库,返回结构化 hits(引用 + 片段)."""
        q = (
            f"Search the knowledge base for: {query}\n"
            f"Return up to {limit} results as a JSON list, each item with keys "
            '"ref", "text". Base only on knowledge_search results; never invent refs.'
        )
        h = self.build_harness()
        with self._lock:
            h.prompt(q)
            h.wait_for_settled()
            return _parse_hits(h.last_response(), limit)

    def read(self, ref: str) -> str:
        """让内置 agent 读取指定引用句柄的内容."""
        q = f'Read the knowledge reference "{ref}" and return its exact content.'
        h = self.build_harness()
        with self._lock:
            h.prompt(q)
            h.wait_for_settled()
            return h.last_response()

    def close(self) -> None:
        if self._harness is not None:
            with self._lock:
                try:
                    self._harness.abort()
                    self._harness.shutdown()
                except Exception:  # noqa: BLE001
                    pass
            self._harness = None
