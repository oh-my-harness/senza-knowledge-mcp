"""MCP 服务:针对性工具集,背后是内置 Senza agent + 原始层快读.

工具分两类:
- 慢·智能(走内置 agent):kb_ask(综合回答)、kb_search(底座检索)
- 快·数据(直接读原始层,毫秒级):kb_get(按 source_id/文档名读全文)、kb_list(列 source)
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from senza_knowledge_mcp import __version__
from senza_knowledge_mcp.agent import KnowledgeAgent
from senza_knowledge_mcp.config import load_settings


def build_server(agent: KnowledgeAgent) -> MCPServer:
    server = MCPServer("senza-knowledge-mcp", version=__version__)

    @server.tool()
    def kb_ask(question: str) -> str:
        """Answer a question grounded in the domain knowledge base (uses an internal
        agent to search and synthesize; may take ~10s)."""
        return agent.ask(question)

    @server.tool()
    def kb_search(query: str, limit: int = 5) -> list[dict]:
        """Search the knowledge base (semantic, via internal agent); returns matching
        source identification + snippets. Use kb_get to fetch full text."""
        return agent.search(query, limit)

    @server.tool()
    def kb_get(doc: str) -> str:
        """Fetch the full markdown of a knowledge document by source_id or file name
        (fast, no LLM involved)."""
        return agent.get_doc(doc)

    @server.tool()
    def kb_list() -> list[dict]:
        """List all documents in the knowledge base (source_id, name, size, dates)."""
        return agent.list_docs()

    return server


def main() -> None:
    settings = load_settings()
    agent = KnowledgeAgent(settings)
    server = build_server(agent)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
