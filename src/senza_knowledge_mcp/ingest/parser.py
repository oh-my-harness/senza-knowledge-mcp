"""解析器抽象层 — 输入 PDF 源文档,输出原始层产物(文档文本 + 图片)。

抽象目标:本阶段用 Docling 实现,预留切换接口接入 MinerU 云端服务。
任何解析器后端只要实现 `parse` 返回 `ParseResult` 即可替换。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class ImageAsset:
    """原始层中的一张图片(不可变原始数据)。"""

    rel_path: str          # 相对原始层的路径
    bytes: bytes           # 图片二进制
    mime_type: str = "image/png"
    description: str = ""  # 可选描述(如由解析器或后续多模态模型生成)


@dataclass
class ParseResult:
    """解析器输出:给原始层存储单元的最小契约。"""

    document_markdown: str
    images: list[ImageAsset] = field(default_factory=list)

    @property
    def text(self) -> str:
        return self.document_markdown


class PdfParser(Protocol):
    """解析器协议。实现方:DoclingParser(本地),未来 MinerUParser(云端/HTTP)。"""

    def parse(self, src: Path) -> ParseResult: ...


# 命名后端,便于按配置选择
BACKENDS: dict[str, type] = {}


def register_backend(name: str):
    """注册解析器后端工厂。"""

    def deco(cls):
        BACKENDS[name] = cls
        return cls

    return deco


def create_parser(backend: str, **kwargs) -> PdfParser:
    """按名创建解析器。backend ∈ {'docling', 'mineru'}。"""
    try:
        cls = BACKENDS[backend]
    except KeyError:
        raise ValueError(f"未知解析器后端: {backend!r} (可用: {sorted(BACKENDS)})")
    return cls(**kwargs)
