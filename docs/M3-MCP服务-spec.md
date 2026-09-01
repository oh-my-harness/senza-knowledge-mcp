---
date: 2026-09-01
status: spec
scope: M3
project: senza-knowledge-mcp
repo: oh-my-harness/senza-knowledge-mcp
---

# M3 Spec · MCP 服务(agent 即服务)

## 背景与目标

M2 已完成基础(M1 原始层 + 解析器;M2 曾自建 LanceDbRag 检索)。M3 的目标:把知识库暴露为 **MCP 服务**,让 coding agent(Claude Code、senza-coder 等)通过 MCP 访问。**M3 采用「agent 即服务」**:MCP 服务端内置一个 Senza agent,它挂知识插件、能做综合回答,调用方拿到的直接是答案(而非裸 chunk)。

### Spike 已验证(2026-09-01)
- Senza `knowledge.local_source()` + `knowledge.plugin()` 在 **Python 侧完全可用**。
- 内置 Senza agent 挂 `knowledge.plugin()` + DeepSeek V4 Flash 后,提问 → agent 调 `knowledge_search` 检索 → **基于检索内容回答并带引用**(`[K:source:chunk]`)。
- mcp 2.x:`MCPServer` + `@tool` 注册 + `run(transport='stdio')` / `run_streamable_http_async`(云端)。

### 检索策略(重要决策)
- **统一走底座 `knowledge.plugin()` + `LocalDocumentSource`**。
- **M2 自建的 `LanceDbRag` 检索作废**——不保留两套检索实现;知识检索只留底座一套(通过插件进 agent)。

## 架构

```
coding agent(MCP client)
        │  MCP (stdio)
        ▼
MCP 服务(M3)
├─ MCPServer (mcp 2.x) — 4 个针对性工具
│     ├─ kb_ask(question)            慢·智能:内置 agent 检索+综合回答(带引用)
│     ├─ kb_search(query, limit)     慢·智能:底座检索,返回 source 识别 + snippet
│     ├─ kb_get(doc)                 快·数据:按 source_id/文档名直读 document.md 全量(毫秒,不超时)
│     └─ kb_list()                   快·数据:列出知识库所有 source(我们的原始层身份)
├─ 内置 Senza agent (DeepSeek V4 Flash)
│     └─ knowledge.plugin() 挂底座 LocalDocumentSource(仅 kb_ask/kb_search 使用)
└─ 原始层(RawStore) document.md(供 local_source 索引 + kb_get/kb_list 直读)
```

## 关键决策(已确认)

1. **agent 即服务**:MCP 服务端内置 Senza agent,综合回答;调用方拿答案。
2. **检索用底座**:内置 agent 挂 `knowledge.plugin()` → `LocalDocumentSource`(底座检索)。**不保留 M2 自建 LanceDbRag**。
3. **MCP 工具(多工具、针对性)**:`kb_ask`(慢·智能,综合回答) + `kb_search`(慢·智能,底座检索) + `kb_get`(快·数据,按 source_id/文档名直读原始层) + `kb_list`(快·数据,列原始层 source)。快数据工具不经 agent、毫秒级、不超时;引用体系用**我们原始层的 source_id**(不再用底座 opaque item_id)。
4. **单轮为主,预留多轮**:会话状态用 Senza agent `prompt`/`chat`;M3 先单轮,预留多轮接口。
5. provider 全匹配(`provider("*", prov)`——模型名非 openai 开头)。

## 组件与职责

### `src/senza_knowledge_mcp/mcp_server.py`
MCP 服务入口。
- `MCPServer("senza-knowledge-mcp")`
- `@server.tool()` 注册三个工具。
- 工具内部维护一个 `KnowledgeAgent`(内置 Senza agent)实例,处理各工具调用。
- `main()` → `server.run(transport="stdio")`。

### `src/senza_knowledge_mcp/agent.py`
内置 Senza agent 封装。
- `class KnowledgeAgent:` — 封装 Senza AgentHarness + knowledge.plugin
  - `__init__(raw_dir, model, base_url, api_key, domains=None)`
  - `def build_harness()` → AgentHarness(builder 挂 provider + knowledge.plugin + system_prompt)
  - `def ask(question) -> str` — prompt + wait_for_settled + last_response
  - `def search(query, limit) -> list[dict]` — 直接调底座检索(经 harness 或知识工具)
  - `def read(ref) -> str`
  - `def close()`

### `src/senza_knowledge_mcp/config.py`
- 配置默认值含 DeepSeek key(base_url `https://api.deepseek.com/v1`、api_key 常量),可被环境变量覆盖(RAW_DIR、MODEL、BASE_URL、API_KEY、DOMAINS)。

## 数据流

1. MCP client 调 `ask("…问题")`。
2. MCPServer → `KnowledgeAgent.ask`。
3. 内置 Senza agent 挂 knowledge.plugin → 检索 LocalDocumentSource(原始层 document.md 目录)。
4. agent 综合 + 带引用回答。
5. 返回给 MCP client。

## 接口

```python
# config.py
@dataclass
class Settings:
    raw_dir: Path      # env SENZA_KB_RAW_DIR
    model: str         # default DEEPSEEK_MODEL 常量,可 env SENZA_KB_MODEL 覆盖
    base_url: str      # default https://api.deepseek.com/v1,可 env 覆盖
    api_key: str       # default 常量(内部工具 key 可硬编码),可 env SENZA_KB_API_KEY 覆盖
    domains: list[str] # env SENZA_KB_DOMAINS (comma), default []
    def load() -> Settings
# agent.py
class KnowledgeAgent:
    def __init__(self, settings: Settings): ...
    def ask(self, question: str) -> str: ...
    def search(self, query: str, limit: int = 10) -> list[dict]: ...
    def read(self, ref: str) -> str: ...
    def close(self) -> None: ...

# mcp_server.py
def build_server(agent: KnowledgeAgent) -> MCPServer: ...
def main() -> None: ...   # python -m senza_knowledge_mcp.mcp_server
```

## 测试(TDD)

1. config: 默认值常量 + env 覆盖解析(default 值、DOMAINS 逗号切分)。
2. agent 构造: mock/最小 provider 建 harness 不崩。
3. ask: 注入知识源(测试目录),问相关 query,返回含引用 handle(`[K:…]`)的回答(需 DeepSeek key,标集成测试)。
4. MCP 工具注册: build_server 后 tools 列表含 ask/search/read。
5. MCP 往返(stdio): 可跳过真实 stdio,直接调 MCPServer 内工具函数断言输出。
6. 原始层 → local_source:document.md 目录可被 local_source 索引并检索命中。

## 里程碑内的验证(MVP 门槛)

- 内置 agent 用 DeepSeek V4 Flash,对原始层索引的 CurvilinearMaskOverview 内容,`ask("curvilinear mask")` 返回带引用的相关回答。
- MCP 服务经 stdio 可启动,三个工具注册齐全。
- 单用户本机闭环:cd `python -m senza_knowledge_mcp.mcp_server` 起服务,MCP client 能 ask/search/read。

## 风险
1. **DeepSeek key**:内部工具,key 默认硬编码于 config 常量(可 env 覆盖);不入公共渠道。
2. **底座插件引用 handle 与 M2 数据模型不一致**:M3 统一走底座检索,引用格式为底座 `[K:src:idx]`,M2 的 knowledge_uri 不再用于检索(原始层 document.md 仍作为底座源)。
3. **MCP 2.x API 变更**:FastMCP→MCPServer 已确认;实现锁定 mcp>=2,<3。
4. **会话状态**:单轮为主;多轮需 Senza session 持久化,预留接口。
5. **性能**:每次 ask 一次 LLM 往返(约 10s),可接受;高并发需后续(agent-team / 池化)。

## 相关
- `docs/领域知识库-一阶段设计.md`
- `docs/senza-knowledge-mcp-一阶段实施计划.md`
- `llm-harness-runtime/crates/llm-harness-knowledge`(底座检索)
- M2 曾自建检索,但 M3 决策统一到底座
