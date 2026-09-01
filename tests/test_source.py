"""Task 3: source root 解析 + local_source 索引 raw 根 测试."""
from pathlib import Path

import pytest
import senza

from senza_knowledge_mcp.source import resolve_source_root


def test_resolve_source_root_creates(tmp_path):
    root = resolve_source_root(tmp_path / "raw")
    assert root == tmp_path / "raw"
    assert root.is_dir()


def test_resolve_source_root_existing(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    assert resolve_source_root(d) == d


def test_local_source_indexes_raw_root(tmp_path):
    """local_source 能对 raw 根(含 document.md + 无关 json/png)建源而不抛错.

    真实检索命中(能搜到 document.md 内容)由 M3 MVP verify_m3 验证——
    因检索需 DeepSeek agent,此处仅断言底座索引 raw 根可用。
    """
    raw = tmp_path / "raw"
    (raw / "20260901-x").mkdir(parents=True)
    (raw / "20260901-x" / "document.md").write_text("# Cal\n\ndiffraction sinc kernel", encoding="utf-8")
    (raw / "20260901-x" / "source.json").write_text('{"m":1}')
    src = senza.knowledge.local_source(str(raw), "kb-test", domains=["litho"])
    assert src is not None
