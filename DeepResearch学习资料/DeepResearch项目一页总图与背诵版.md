# DeepResearch 项目一页总图与背诵版

目标项目：`D:\课\s4-6\industry_information_assistant`

## 1. 项目解决什么问题

这是一个行业信息助手，包含：

```text
普通聊天
DeepResearch 多 Agent 研究
知识库和 RAG
长期记忆
Text2SQL 数据分析
行业新闻和招投标
股票行情
```

## 2. DeepResearch 主链路

```text
React 聊天页
  ↓ deepsearch()
POST /research/stream
  ↓
research_router.stream_research
  ↓
DeepResearchV2Service
  ↓
DeepResearchGraph.run
  ↓
_run_simplified
  ↓
ResearchState
  ↓
ChiefArchitect
  ↓
DeepScout
  ↓
DataAnalyst
  ↓
CodeWizard
  ↓
LeadWriter
  ↓
CriticMaster
  ↓
asyncio.Queue
  ↓
SSE text/event-stream
  ↓
ReadableStream
  ↓
React 研究步骤、来源、图表、图谱、报告
```

当前 POST 默认 V2；当前 V2 默认进入 `_run_simplified()`。代码中的 LangGraph 是设计路径，不能直接当作当前默认执行器。

## 3. 六个 Agent 记忆表

| Agent | 核心问题 | 主要写入 |
|---|---|---|
| ChiefArchitect | 研究什么 | `outline`、`research_questions`、`key_entities`、`hypotheses` |
| DeepScout | 证据在哪里 | `raw_sources`、`facts`、`data_points`、`references` |
| DataAnalyst | 数据说明什么 | `insights`、`knowledge_graph`、结构化 `charts` |
| CodeWizard | 如何用代码验证 | `code_executions`、图片型 `charts` |
| LeadWriter | 如何写成报告 | `draft_sections`、`final_report` |
| CriticMaster | 是否完整可信 | `critic_feedback`、`quality_score`、`pending_search_queries` |

## 4. ResearchState 是什么

它是 Agent 共享的后端工作台，保存：

```text
请求：query、session_id、search_web、search_local
规划：outline、research_questions、hypotheses
证据：raw_sources、facts、references
分析：data_points、insights、charts、knowledge_graph
写作：draft_sections、final_report
审核：critic_feedback、quality_score、unresolved_issues
运行：phase、iteration、logs、errors、messages
```

记忆顺序：

```text
outline → facts → data_points/insights/charts → final_report
```

## 5. 三种核心存储

| 存储 | 保存什么 | 记忆方式 |
|---|---|---|
| PostgreSQL | 用户、正式会话、消息、文档元数据、检查点、新闻、招投标 | 业务事实 |
| Redis | 旧短期会话、缓存、取消标志 | 短期状态 |
| Milvus | 文档切片向量、长期记忆向量 | 语义相似检索 |

```text
PostgreSQL 记业务事实
Redis       记短期控制状态
Milvus      记可相似搜索的向量
```

## 6. RAG 链路

```text
上传文件
→ Document pending
→ BackgroundTasks
→ DocMind 解析
→ chunk_size=500、overlap=50
→ text-embedding-v4
→ 1024 维向量
→ Milvus
→ 问题向量化
→ COSINE Top-K
→ DeepScout 或普通聊天使用片段
```

PostgreSQL 的 `Document(completed)` 只说明业务状态完成，不能单独证明 Milvus 可召回。

重点风险：上传通常使用 `kb_<知识库名称>`，DeepScout 本地搜索当前固定使用 `knowledge_base`。

## 7. CodeWizard 链路

```text
data_points
→ LLM 生成 Python
→ 清理
→ compile() 语法检查
→ 正则危险模式检查
→ 受限 globals
→ exec()
→ stdout/stderr/PNG
→ code_executions/charts
→ chart/code_result SSE
```

```text
LLM 决定写什么代码
执行环境决定代码能否运行和能访问什么
```

当前进程内 `exec()` 是简化沙箱，生产环境需要独立容器或专用执行服务。

## 8. 检查点、取消、恢复

```text
检查点：PostgreSQL ResearchCheckpoint
  state_json    后端研究状态
  ui_state_json 前端研究状态
  final_report  报告

取消：
reader.cancel()
→ POST /research/cancel/{session_id}
→ Redis research:cancel:<session_id>
→ Graph 协作式检查

恢复：
GET /research/checkpoint/{session_id}/full
→ 页面恢复展示
POST /research/resume/{session_id}
→ 加载 state_json
→ 当前仍进入 _run_simplified()
```

当前实现支持状态和页面恢复，不能直接描述为精确节点级断点续跑。

## 9. 普通聊天、长期记忆、Text2SQL

```text
普通聊天：检索 → 重排 → 历史 → LLM 流式回答

长期记忆：对话 → LLM 摘要 → PostgreSQL + Milvus → user_id 过滤召回

Text2SQL：自然语言 → LLM SQL → SELECT/危险词校验 → PostgreSQL → 表格/图表建议
```

Text2SQL 数据库不可用时可能进入 Mock 数据路径。

## 10. 行业业务数据域

```text
IndustryConfig.news_keywords
→ Bocha
→ source_url 去重
→ IndustryNews

IndustryConfig.bidding_keywords
→ 81API
→ bid_id 去重
→ BiddingInfo

每日 12:00 APScheduler
启动无数据时立即采集
```

股票行情是独立即时链：

```text
用户问题 → 公司识别 → 聚合数据 API → stock_quote → StockCard
```

## 11. 最小排错顺序

```text
浏览器请求
→ SSE/Network
→ FastAPI Router
→ Service/Agent 日志
→ ResearchState 字段
→ PostgreSQL/Redis/Milvus
→ LLM/外部 API
```

先找“最后一个有证据的层”，再找“第一个没有证据的层”。

## 12. 必须诚实说明的限制

```text
Docker、PostgreSQL、Redis、Milvus、DocMind、真实 LLM 和外部搜索尚未在当前机器完成完整端到端验证。
飞书正文受复制/导出限制，不能声称逐字读取全部内容。
项目目录没有 Git 元数据，不能从提交历史判断版本演进。
```

## 13. 90 秒项目介绍模板

> 这是一个面向行业信息分析的智能助手，前端使用 React，后端使用 FastAPI，数据层使用 PostgreSQL、Redis 和 Milvus。核心 DeepResearch V2 通过 ResearchState 协调规划、搜索、分析、代码执行、写作和审核六个 Agent，并使用 asyncio.Queue 和 SSE 把过程实时推送到前端。知识库文档经过 DocMind 解析、切片和 Embedding 后写入 Milvus，普通聊天、长期记忆和 Text2SQL 作为外围能力补充问答和数据分析。当前实现中，V2 默认走 `_run_simplified()`，CodeWizard 是进程内简化执行环境，检查点支持状态和 UI 恢复，但还不能直接称为精确节点级断点续跑。

