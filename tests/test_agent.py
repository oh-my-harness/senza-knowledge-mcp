"""Task 2: KnowledgeAgent 测试(构造验证,不触发真实 LLM)."""
from senza_knowledge_mcp.agent import KnowledgeAgent
from senza_knowledge_mcp.config import Settings


def test_construct():
    s = Settings(raw_dir=".", model="dummy-model")
    a = KnowledgeAgent(s)
    assert a is not None
    assert a._settings.raw_dir is not None


def test_close_without_harness():
    s = Settings(raw_dir=".")
    a = KnowledgeAgent(s)
    a.close()  # 未 build,close 不应抛错
