"""原始层存储 — 不可变文档源。

原始层是权威数据,规则如下:
- 每个入库文档一个目录,含 document.md 与图片子目录。
- 原样存储,永不改动(不可变)。
- 关联层、检索索引均为派生数据,可随时从原始层重建。

目录结构:
    <root>/<source_id>/
        source.json      # 元数据
        document.md      # 解析出的文档 markdown
        images/          # 图片列表
            <rel>.png
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from senza_knowledge_mcp.ingest.parser import ImageAsset, ParseResult


@dataclass
class StoredSource:
    source_id: str
    name: str
    created_at: float
    raw_bytes: int
    image_count: int
    origin: str  # 原始文件名

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StoredSource":
        return cls(**d)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


class RawStore:
    """原始层存储单元。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, name: str, origin_bytes: bytes, parse: ParseResult) -> StoredSource:
        """写入一个解析结果到原始层,返回存储描述。"""
        source_id = f"{time.strftime('%Y%m%d')}-{_sha256(origin_bytes)}"
        dir = self.root / source_id

        # 不可变:若已存在则视为重复入库,直接返回
        if dir.exists():
            meta = json.loads((dir / "source.json").read_text(encoding="utf-8"))
            return StoredSource.from_dict(meta)

        img_dir = dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        (dir / "document.md").write_text(
            parse.document_markdown, encoding="utf-8"
        )
        for img in parse.images:
            (img_dir / img.rel_path).write_bytes(img.bytes)

        src = StoredSource(
            source_id=source_id,
            name=name,
            created_at=time.time(),
            raw_bytes=len(origin_bytes),
            image_count=len(parse.images),
            origin=Path(name).name,
        )
        (dir / "source.json").write_text(
            json.dumps(src.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return src

    def list(self) -> list[StoredSource]:
        out = []
        for d in sorted(self.root.iterdir()):
            if not d.is_dir():
                continue
            meta = d / "source.json"
            if meta.exists():
                out.append(StoredSource.from_dict(json.loads(meta.read_text(encoding="utf-8"))))
        return out

    def read_document(self, source_id: str) -> str:
        return (self.root / source_id / "document.md").read_text(encoding="utf-8")

    def read_source(self, source_id: str) -> StoredSource:
        meta = self.root / source_id / "source.json"
        return StoredSource.from_dict(json.loads(meta.read_text(encoding="utf-8")))

    def exists(self, source_id: str) -> bool:
        return (self.root / source_id).exists()
