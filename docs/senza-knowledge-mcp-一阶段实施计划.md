---
date: 2026-09-01
status: plan
scope: 一阶段
repo: oh-my-harness/senza-knowledge-mcp
related: "docs/领域知识库-一阶段设计.md"
---

# senza-knowledge-mcp · 一阶段实施计划

> 领域知识库(MCP 优先 + 管理后台)。本文件固化整体计划与里程碑,先整体定死、再按序执行。MV**P 先行**,关联层等作为一阶段后半段。

---

## 一、仓库与形态

- 仓库:`oh-my-harness/senza-knowledge-mcp`(Python 项目,uv 管理)
- 依赖:senza-sdk(本地 wheel)、lancedb、fastapi、uvicorn、pydantic
- 复用:从 Folumi `crates/tutor-rag` 移植 LanceDB `KnowledgeSource`(基于 `llm-harness-runtime-knowledge`);不重建平行 runtime
- 解析器抽象层:本阶段用 **Docling**(IBM 开源,文本+图片+表格+公式,纯 Python,16GB M5 无压力);预留切换接口,后续 MinerU 云端服务就绪后替换后端

## 二、整体架构(目标态,一阶段全集)

```
coding agent(MCP 客户端) ──MCP──►  MCP 服务(search/read/upsert + skill prompts)
                                          │
人工 ──管理后台(FastAPI)──► 知识库核心
                              ├─ 原始层(不可变: 文档/文档+图片)
                              ├─ 关联层(派生: ①关联索引 ②归纳知识页)
                              ├─ 入库管线(解析器抽象 → 原始层 → LanceDB)
                              ├─ RAG(knowledge.local_source)
                              └─ 关联层维护器(heartbeat agent)
```

## 三、里程碑(MVP 先行,整体顺序)

### M0 · 仓库骨架
- 建 `oh-my-harness/senza-knowledge-mcp`(pyproject、uv、git init+commit)
- 搭最小结构:src/ + tests/ + config
- **验证**:`uv sync` 成功,`senza-sdk` 可 import

### M1 · 数据层 + 入库管线(MVP 核心 1)
- 原始层存储(文档/文档+图片,不可变)
- 入库管线:管理后台上传 → 解析器抽象层(Docling)→ 原始层 → 切分/embedding → LanceDB
- Docling 可用性 spike:装 Docling,解析 `~/Documents/projs/minerU/pdfs/` 一个真实光刻 PDF,确认产出文本+图片+表格
- **验证**:上传一个 PDF/文本,能入库,Docling 产出文档+图片;解析接口可切换(Docling/MinerU 占位)

### M2 · RAG 检索(MVP 核心 2)
- 移植 Folumi `tutor-rag` 的 `KnowledgeSource` → `knowledge.local_source()`
- 检索返回带引用依据
- **验证**:对已入库文档检索,返回相关 chunk + 引用

### M3 · MCP 服务(MVP 核心 3)
- `McpManager`/`McpServerConfig` 暴露 search/read/upsert 工具 + 领域 skill prompts
- coding agent(如 senza-coder)经 MCP 检索/读取/写回
- **验证**:MCP 客户端调用 search 拿到结果,upsert 写入成功

### M4 · 管理后台
- FastAPI:文档上传(触发入库)、知识库查看、归纳审批入口
- **验证**:浏览器上传文档成功入库;查看知识库列表

### —— MVP 完成标志 ——
> 单机运行:MCP 服务 + 文档入库 + RAG 检索 + 管理后台上传,一条链路跑通。
> coding agent 能经 MCP 检索到一个已入库 PDF 的知识,并显示引用。

### M5 · 关联层维护器(一阶段后半段)
- heartbeat agent 定时扫描原始层 → 生成关联索引(知识页/概念关联)
- **验证**:定时任务产生关联索引,可查

### M6 · 归纳知识页 + llm-wiki(一阶段后半段)
- 归纳知识页:trigger 触发 + human-on-the-loop 审批(管理后台)
- llm-wiki:agent 经 MCP upsert 把对拍教训/正确方案写回知识层
- **验证**:归纳产出知识页,人工审批后可见;教训写回并可检索

---

## 四、关键决策(已确认)
- MCP 优先(主接口给 coding agent),管理后台只做文档上传/查看/审批,不做问答主入口
- 文档入库走管理后台/CLI(不走 MCP);检索/读取/写回走 MCP
- 数据分层:原始层(权威不可变)+ 关联层(派生可重建),关联索引与归纳拆开
- 解析器抽象层:本阶段 Docling,预留切换接口接 MinerU 云端服务(GPL-3.0 隔离,可替换)
- MinerU 进程隔离调用(GPL-3.0);可替换
- 核心与形态解耦,为二阶段云端(团队 MCP 访问 + 权限)打地基
- 复用 Folumi tutor-rag 代码,不重建平行 runtime

---

## 五、风险(设计文档同步保存)
1. GPL: MinerU 进程隔离
2. 图片按需理解:需多模态模型可用性;离线需本地视觉模型
3. 关联层可重建,写回需审计留痕
4. 归纳知识页 human-on-the-loop,防 agent 自信出错
5. skill 要薄,深内容下沉 wiki
6. MCP upsert 写回留审计,为二阶段 KnowledgeAccessControl 预留

---

## 相关
- `docs/领域知识库-一阶段设计.md`(设计)
- Folumi `crates/tutor-rag`(移植参考)
- `llm-harness-runtime/crates/llm-harness-knowledge`(二阶段地基)
