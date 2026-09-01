"""M1 链路验证 — 解析器抽象层 + 原始层存储 端到端。

用法: .venv/bin/python tests/run_ingest.py <pdf_path> [raw_root]
"""
from pathlib import Path
import sys

from senza_knowledge_mcp.ingest import create_parser, ParseResult
from senza_knowledge_mcp.ingest.raw_store import RawStore


def main(pdf_path: str, raw_root: str | None = None) -> None:
    src = Path(pdf_path)
    root = Path(raw_root) if raw_root else Path(".data/raw")

    parser = create_parser("docling")
    store = RawStore(root)

    print(f"[1/2] 解析 {src.name} ...")
    parse = parser.parse(src)
    print(f"      markdown {len(parse.text)} chars, {len(parse.images)} images")

    print(f"[2/2] 写入原始层 {root} ...")
    origin_bytes = src.read_bytes()
    stored = store.store(src.name, origin_bytes, parse)
    print(f"      source_id={stored.source_id}")
    print(f"      raw_bytes={stored.raw_bytes} images={stored.image_count}")

    # 重放校验:已入库文档可读
    doc = store.read_document(stored.source_id)
    print(f"      重读 document.md: {len(doc)} chars OK")
    print("VERIFY: ingest pipeline OK")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
