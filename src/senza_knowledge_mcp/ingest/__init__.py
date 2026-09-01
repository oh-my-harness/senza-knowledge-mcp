"""入库管线:解析器抽象 + 原始层存储 + 索引。

解析器抽象层定义于 `parser.py`,默认后端 Docling(`docling_backend.py`)。
"""
from senza_knowledge_mcp.ingest import docling_backend  # noqa: F401 注册后端
from senza_knowledge_mcp.ingest.parser import ParseResult, create_parser

__all__ = ["ParseResult", "create_parser"]
