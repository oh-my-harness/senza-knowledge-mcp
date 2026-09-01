"""管理后台业务纯函数:知识库列表与详情组装.

设计为纯函数(依赖传入 RawStore),便于测试;路由薄壳在 admin_app.py 组装。
"""
from __future__ import annotations

from pathlib import Path

from senza_knowledge_mcp.ingest.raw_store import RawStore

_SUPPORTED = {".pdf", ".txt", ".md"}


def is_supported(filename: str) -> bool:
    """是否支持的文档类型(PDF / 文本)."""
    return Path(filename).suffix.lower() in _SUPPORTED


def sources_json(raw: RawStore) -> list[dict]:
    """返回知识库所有 source 的元信息列表."""
    return [s.to_dict() for s in raw.list()]


def source_json(raw: RawStore, source_id: str) -> dict:
    """返回单个 source 的元信息 + 文档内容."""
    if not raw.exists(source_id):
        raise KeyError(source_id)
    doc = raw.read_document(source_id)
    meta = raw.read_source(source_id).to_dict()
    meta["document"] = doc
    return meta
