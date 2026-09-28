# DeepResearch 学习手册：第 91 课

## 第一轮综合验收：从会看代码到能定位故障

前 90 课已经覆盖项目的主要模块。本课不新增业务功能，而是检查是否能把各层连起来。正式进入大厂面试模拟前，至少要通过本轮验收。

## 1. 验收等级

### A：能复述主链路

能够从用户点击发送开始，依次说出：

```text
React
→ deepsearch
→ POST /research/stream
→ FastAPI Router
→ V2 Service
→ Graph
→ ResearchState
→ 六个 Agent
→ SSE
→ React
```

### B：能解释字段变化

能够说明：

```text
outline、facts、data_points、charts、final_report、critic_feedback
```

分别在哪个阶段生成、被谁使用。

### C：能定位故障层级

遇到空结果、500、页面不更新、文档搜不到或图表缺失时，能提出下一条可验证证据。

### D：能区分源码事实和运行证据

知道 `compileall`、`npm run build` 只能证明静态构建；没有 Docker、数据库、Redis、Milvus 和外部 API 的真实运行结果时，不能声称完整端到端通过。

## 2. 必答题

### 题 1：完整请求链

从用户在 DeepResearch 页面点击发送开始，写出一次 V2 请求的完整调用链，并说明 SSE 在哪一层形成。

源码证据：

```text
frontend/src/pages/chat/index.tsx::sendChat
frontend/src/api/session.ts::deepsearch
backend/app/router/research_router.py::stream_research
backend/app/service/deep_research_v2/service.py::research
backend/app/service/deep_research_v2/graph.py::run/_run_simplified
```

### 题 2：真实执行分支

当前 V2 为什么默认执行 `_run_simplified()`，而不是 `_run_with_langgraph()`？简述两者的关系。

合格答案必须提到：`run()` 中 LangGraph 分支被注释，简化流程用 `asyncio.Queue` 支持实时输出。

### 题 3：状态交接

说明 `ChiefArchitect`、`DeepScout`、`DataAnalyst`、`CodeWizard`、`LeadWriter`、`CriticMaster` 各自主要写入哪些状态字段。

### 题 4：事件通道

解释下面的链条：

```text
add_message
→ asyncio.Queue
→ Graph yield
→ StreamingResponse
→ ReadableStream
→ React json.type 分支
```

### 题 5：RAG 完整链

从知识库上传到 DeepScout 本地召回，写出 PostgreSQL、DocMind、Embedding 和 Milvus 各自负责什么。

### 题 6：RAG 集合名风险

为什么 `Document.status = completed` 仍不能证明 DeepResearch 能召回文档？必须指出上传写入集合和 DeepScout 查询集合的当前差异。

### 题 7：CodeWizard

解释：

```text
LLM → _clean_code → compile → _is_code_safe → exec → stdout/stderr/PNG
```

并说明为什么这不是生产级沙箱。

### 题 8：控制面

比较 `reader.cancel()`、Redis 取消 key、`state_json`、`ui_state_json` 和 `resume=True` 的作用和边界。

### 题 9：认证和会话

解释 JWT、`session_id`、`ChatSession`、`ChatMessage` 和 `ResearchCheckpoint` 的关系。

### 题 10：外围能力

分别概括普通聊天、长期记忆、Text2SQL、行业资讯和股票行情的主要链路，并指出它们为什么不是同一条 DeepResearch 链。

## 3. 场景题

### 场景 A：页面没有研究步骤

后端日志出现 Agent 已经把 `research_step` 放入队列，但浏览器没有步骤。

合格排查顺序至少包含：Graph 是否 yield、响应是否是 `text/event-stream`、浏览器是否收到字节、前端是否解析完整行、`json.type` 是否有对应分支。

### 场景 B：知识库显示完成但研究无本地来源

依次核对：

```text
Document 状态
DocMind 文本和切片数量
Embedding 数量
Milvus 实际写入集合
DeepScout 实际查询集合
查询向量和 search 返回值
```

### 场景 C：研究 500

先区分：

```text
401/422 请求边界
应用导入和数据库连接
LLM 配置
外部搜索或 Milvus
具体 Agent JSON 解析或执行
```

不能只凭状态码判断是哪一层。

## 4. 评分建议

| 维度 | 分值 | 合格表现 |
|---|---:|---|
| 主链路 | 20 | 能说清谁调用谁 |
| ResearchState | 20 | 能说清字段怎样变化 |
| Agent 责任 | 15 | 能区分六个 Agent |
| SSE 前端 | 15 | 能从队列追到 React |
| RAG 和存储 | 15 | 能区分 PostgreSQL、Redis、Milvus |
| 工程排错 | 10 | 每个现象能提出下一证据 |
| 证据边界 | 5 | 不把静态检查说成端到端运行 |

建议总分达到 80 分后，再进入模拟面试。低于 80 分，先针对错误层补课。

## 5. 当前状态

源码覆盖和课程材料已经完成第一轮整理，但用户尚未提交本轮自由回答，因此“已经教会并通过验收”目前还没有证据。下一步应先完成题 1、题 5、题 7 三道核心题，再根据答案逐项评分。
