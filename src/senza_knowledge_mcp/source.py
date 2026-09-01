"""知识源根解析 — 原始层 raw 根可直接作为 local_source 索引目录.

底座 LocalDocumentSource 递归遍历目录,只索引解析器支持的扩展名
(Markdown/Text)。原始层 raw/<source_id>/document.md 位于嵌套子目录,
source.json / images/*.png 等非支持扩展会被自动跳过。因此直接把 raw 根
交给 `senza.knowledge.local_source()` 即可,无需平铺视图目录。
"""
from __future__ import annotations

from pathlib import Path


def resolve_source_root(raw_dir: str | Path) -> Path:
    """返回可作为 local_source 索引根的目录(即原始层根).

    底座递归 + 扩展过滤已满足索引 document.md 的需求,不需额外视图目录。
    保留此函数以明确"知识源根 = 原始层根"这一约定,便于后续扩展
    (如将来需排除某些子目录时在此定义)。
    """
    root = Path(raw_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root
