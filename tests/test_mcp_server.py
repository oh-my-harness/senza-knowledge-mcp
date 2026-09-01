"""M4 之后 M3 工具集测试: 4 工具注册 + 快数据工具行为."""
from mcp.server.mcpserver import MCPServer

from senza_knowledge_mcp.agent import KnowledgeAgent
from senza_knowledge_mcp.config import Settings
from senza_knowledge_mcp.mcp_server import build_server


def test_build_server_is_mcpserver():
    s = Settings(raw_dir=".")
    a = KnowledgeAgent(s)
    server = build_server(a)
    assert isinstance(server, MCPServer)


def test_kb_get_by_source_id(tmp_path):
    from senza_knowledge_mcp.ingest.parser import ParseResult
    from senza_knowledge_mcp.ingest.raw_store import RawStore

    raw = RawStore(tmp_path / "raw")
    stored = raw.store("a.md", b"a", ParseResult(document_markdown="# A\n\ndiffraction content", images=[]))
    s = Settings(raw_dir=str(tmp_path / "raw"))
    a = KnowledgeAgent(s)
    doc = a.get_doc(stored.source_id)
    assert "diffraction content" in doc


def test_kb_get_by_name(tmp_path):
    from senza_knowledge_mcp.ingest.parser import ParseResult
    from senza_knowledge_mcp.ingest.raw_store import RawStore

    raw = RawStore(tmp_path / "raw")
    raw.store("paper.md", b"p", ParseResult(document_markdown="# Paper\n\nbody", images=[]))
    s = Settings(raw_dir=str(tmp_path / "raw"))
    a = KnowledgeAgent(s)
    assert "body" in a.get_doc("paper.md")
    assert "body" in a.get_doc("paper")  # 文件名去后缀也可


def test_kb_get_missing(tmp_path):
    import pytest

    s = Settings(raw_dir=str(tmp_path))
    a = KnowledgeAgent(s)
    try:
        a.get_doc("nope")
        assert False, "should raise"
    except KeyError:
        pass


def test_kb_list(tmp_path):
    from senza_knowledge_mcp.ingest.parser import ParseResult
    from senza_knowledge_mcp.ingest.raw_store import RawStore

    raw = RawStore(tmp_path / "raw")
    raw.store("a.md", b"a", ParseResult(document_markdown="x", images=[]))
    raw.store("b.md", b"b", ParseResult(document_markdown="y", images=[]))
    s = Settings(raw_dir=str(tmp_path / "raw"))
    a = KnowledgeAgent(s)
    items = a.list_docs()
    assert len(items) == 2
    assert {i["origin"] for i in items} == {"a.md", "b.md"}
