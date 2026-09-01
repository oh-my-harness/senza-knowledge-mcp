"""Docling 解析器后端 — 本地纯 Python 实现(解析器抽象层的默认后端)。

输出文档 markdown + 图片。文档与图片分离,图片存原始层,使用时按需送多模态模型。
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from senza_knowledge_mcp.ingest.parser import (
    ImageAsset,
    ParseResult,
    PdfParser,
    register_backend,
)


@register_backend("docling")
class DoclingParser(PdfParser):
    """使用 Docling 解析 PDF。lazy 导入,避免 CLI 无 Docling 时 import 失败。"""

    def __init__(self, use_ocr: bool = True) -> None:
        self._use_ocr = use_ocr
        self._converter = None

    def _ensure_converter(self):
        if self._converter is None:
            from docling.document_converter import DocumentConverter

            self._converter = DocumentConverter()
        return self._converter

    def parse(self, src: Path) -> ParseResult:
        converter = self._ensure_converter()
        result = converter.convert(src)
        doc = result.document

        markdown = doc.export_to_markdown()

        images: list[ImageAsset] = []
        for i, pic in enumerate(doc.pictures):
            image = pic.get_image(doc)
            if image is None:
                continue
            buf = BytesIO()
            image.save(buf, format="PNG")
            images.append(
                ImageAsset(
                    rel_path=f"page{pic.prov[0].page_no if pic.prov else i+1}_img{i+1}.png",
                    bytes=buf.getvalue(),
                    mime_type="image/png",
                )
            )

        return ParseResult(document_markdown=markdown, images=images)
