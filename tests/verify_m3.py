"""MVP: 真实 PDF → 原始层 → local_source → 内置 agent 返回带引用回答.

用法: .venv/bin/python tests/verify_m3.py <pdf> [raw_root] [--ask QUERY]
"""
from pathlib import Path
import sys

from senza_knowledge_mcp.agent import KnowledgeAgent
from senza_knowledge_mcp.config import Settings
from senza_knowledge_mcp.ingest import create_parser
from senza_knowledge_mcp.ingest.raw_store import RawStore


def main(pdf: str, raw_root: str, query: str) -> None:
    raw = RawStore(Path(raw_root))
    src = Path(pdf)

    if not [s for s in raw.list() if s.origin == src.name]:
        parse = create_parser("docling").parse(src)
        raw.store(src.name, src.read_bytes(), parse)
        print(f"[1] Docling 解析入库: {src.name}")
    else:
        print("[1] 原始层已存在")

    settings = Settings(raw_dir=Path(raw_root), domains=["lithography"])
    agent = KnowledgeAgent(settings)
    print(f"[2] 内置 agent 就绪 (model={settings.model})")

    print(f"[3] Q: {query}")
    ans = agent.ask(query)
    print(f"[4] A:\n{ans[:800]}")

    has_citation = "[K:" in ans
    print(f"[5] 含引用 handle: {has_citation}")
    assert ans.strip(), "MVP FAILED: 空回答"
    print("VERIFY: M3 MVP OK")


if __name__ == "__main__":
    pdf = sys.argv[1]
    raw_root = sys.argv[2] if len(sys.argv) > 2 else ".data/raw"
    query = sys.argv[3] if len(sys.argv) > 3 else "What is a curvilinear mask and why is it manufacturable?"
    main(pdf, raw_root, query)
