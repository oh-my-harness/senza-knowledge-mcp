# senza-knowledge-mcp

Team domain knowledge base — **MCP-first** service built on [Senza](https://github.com/oh-my-harness/Senza).

Coding agents (Claude Code, oh-my-pi, any MCP client) query your team's domain
documents through MCP; a built-in Senza agent searches and synthesizes grounded,
citation-backed answers. A lightweight admin web handles document ingestion and
browsing.

## How it works

```
coding agent (MCP client) ──MCP stdio──► senza-knowledge-mcp
                                            ├─ kb_ask    ask a question → grounded answer w/ citations
                                            ├─ kb_search semantic search → source + snippet
                                            ├─ kb_get    fetch full document (fast, no LLM)
                                            └─ kb_list   list knowledge base contents
                                            (kb_ask / kb_search run an internal Senza agent
                                             with the base knowledge plugin)

admin web settings page ──► ~/.senza-knowledge-mcp/config.json (shared config)

browser ──► admin web (FastAPI)            upload PDF/text → parse → raw store
```

**Data model**: an immutable raw layer (documents / documents+images, parsed with
[Docling](https://github.com/docling-project/docling); pluggable backend — swap in a
cloud MinerU service later) + derived layers. Images are understood on use by a
multimodal model, not at ingest time.

## Install

Requires Python 3.12+.

```bash
git clone https://github.com/oh-my-harness/senza-knowledge-mcp.git
cd senza-knowledge-mcp
uv sync --extra dev        # or: pip install -e . (runtime deps only)
```

No provider configuration ships with the source — the source binds to no
provider. **Configure once, in either of two ways:**

- **Admin web (recommended)**: start the admin web → open **Settings** → pick
  Provider (`openai` or `anthropic`) → fill in API key / Base URL / Model →
  Save. Persisted to `~/.senza-knowledge-mcp/config.json`.
- **Environment variables**: `SENZA_KB_PROVIDER` (`openai` | `anthropic`),
  `SENZA_KB_API_KEY`, `SENZA_KB_BASE_URL`, `SENZA_KB_MODEL` (all four required;
  env takes precedence over the config file).

`kb_ask` / `kb_search` need the LLM; `kb_get` / `kb_list` are pure data tools and
work without any configuration.

## Quick start

**1. Start the admin web** (configuration + document ingestion):

```bash
python -m senza_knowledge_mcp.admin_app
# open http://127.0.0.1:8081 → Settings: fill API key / Base URL / Model → Save
```

**2. Ingest documents**: admin web → Upload → pick a PDF or UTF-8
text/markdown file. The document is parsed and stored in the raw layer, ready
to be searched.

**3. Wire the MCP server into your coding agent** (see next section) and start
asking.

## Wire it into your coding agent

oh-my-pi (`.omp/mcp.json`, project level):

```json
{
  "mcpServers": {
    "kb": {
      "type": "stdio",
      "command": "/abs/path/to/senza-knowledge-mcp/.venv/bin/python",
      "args": ["-m", "senza_knowledge_mcp.mcp_server"],
      "env": { "SENZA_KB_RAW_DIR": "/abs/path/to/kb/raw" }
    }
  }
}
```

Any other MCP client works the same way — the server speaks standard MCP over stdio
with four tools: `kb_ask`, `kb_search`, `kb_get`, `kb_list`.

## Tools

| Tool | Kind | What it does |
|------|------|--------------|
| `kb_ask(question)` | smart, ~10s | internal agent searches + synthesizes a cited answer |
| `kb_search(query)` | smart | semantic search → source identification + snippets |
| `kb_get(doc)` | fast, ms | full markdown of a document by `source_id` or file name |
| `kb_list()` | fast, ms | all documents in the knowledge base |

Fast tools read the immutable raw layer directly — no LLM involved, no timeouts.
Smart tools run the internal Senza agent through whichever provider you
configure (Anthropic or OpenAI-compatible).

## Configuration

| Env var | Required | Meaning |
|---------|----------|---------|
| `SENZA_KB_PROVIDER` | **yes** | `openai` (OpenAI-compatible: DeepSeek, GLM, SiliconFlow, ...) or `anthropic` |
| `SENZA_KB_API_KEY` | **yes** | provider API key |
| `SENZA_KB_BASE_URL` | **yes** | provider endpoint |
| `SENZA_KB_MODEL` | **yes** | model id (e.g. `deepseek-v4-flash`, `claude-sonnet-4-5`) |
| `SENZA_KB_RAW_DIR` | no (default `.`) | raw layer directory |
| `SENZA_KB_DOMAINS` | no | comma-separated domain tags |

## Milestones

- ✅ M0 scaffold · M1 ingest pipeline (Docling → raw layer) · M3 MCP service · M4 admin web
- Planned: M5 relation layer (heartbeat agent) · M6 distilled knowledge pages + llm-wiki write-back · M7 cloud MinerU parser (swap-in via the parser abstraction) · M8 phase-2 shared knowledge base (single cloud instance, MCP over HTTP, multi-user permissions via the base `KnowledgeAccessControl`)

## License

MIT
