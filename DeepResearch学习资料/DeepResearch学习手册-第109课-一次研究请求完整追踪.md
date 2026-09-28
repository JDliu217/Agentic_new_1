# DeepResearch 学习手册·第 109 课：一次研究请求的完整追踪

## 1. 本课要解决的问题

看到一个项目时，不要只记住“它有六个 Agent”。真正的工程理解是：给定一个用户动作，能够沿着真实代码说明：

```text
谁发请求
→ 请求进入哪个路由
→ 路由创建哪个服务
→ 服务创建或恢复什么状态
→ 每个 Agent 读写什么
→ 中间结果怎样流回前端
→ 检查点在哪里保存
→ 最终报告怎样到达页面
```

下面用问题“新能源汽车行业未来三年的竞争格局”做示范。

## 2. 第一步：前端构造请求

文件：`frontend/src/api/session.ts:129-146`

`deepsearch()` 向 `/research/stream` 发 POST 请求，请求体的核心字段是：

```json
{
  "query": "新能源汽车行业未来三年的竞争格局",
  "session_id": "会话 ID",
  "search_modes": ["web", "local"]
}
```

请求把 `Accept` 设置为 `text/event-stream`，把 `responseType` 设置为 `stream`，并使用 fetch adapter。这里没有直接等待一个完整 JSON，而是准备读取一个持续到研究结束的字节流。

聊天页在 `frontend/src/pages/chat/index.tsx:233-260` 调用这个 API，然后拿到 `ReadableStream` 的 reader。

## 3. 第二步：Router 选择 V2

文件：`backend/app/router/research_router.py:28-78, 80-150`

FastAPI 先把 JSON 解析为 `ResearchRequest`。`version` 默认是 `v2`。`search_modes` 会通过：

```python
get_search_web()
get_search_local()
```

转为两个布尔值。然后路由创建 `DeepResearchV2Service`，调用它的 `research()`。

关键事实：

- POST `/research/stream` 默认走 V2；
- GET `/research/stream` 默认走 V1；
- 所以不能只看到 URL 相同，就假设 GET 和 POST 执行同一条链路。

## 4. 第三步：Service 创建会话 ID 并进入 Graph

文件：`backend/app/service/deep_research_v2/service.py:85-142`

如果请求没有 `session_id`，服务使用 `uuid.uuid4()` 创建一个。然后调用：

```python
self.graph.run(
    query,
    session_id,
    resume=resume,
    user_id=user_id,
    search_web=search_web,
    search_local=search_local,
)
```

Graph 产生一个个事件，Service 用 `_format_sse()` 格式化为：

```text
data: <JSON>\n\n
```

异常也被转换为 `type=error` 事件，最后发送 `data: [DONE]\n\n`。

## 5. 第四步：Graph 初始化六个 Agent

文件：`backend/app/service/deep_research_v2/graph.py:70-145`

Graph 初始化：

```text
ChiefArchitect：规划问题和研究大纲
DeepScout：搜索网络和本地知识库
DataAnalyst：提取数据、洞察和结构化图表
CodeWizard：生成并执行 Python，补充分析图表
LeadWriter：章节写作和最终报告整合
CriticMaster：审核报告，决定完成、修订或补充研究
```

每个 Agent 可以使用不同的模型配置，但它们共享同一个 `ResearchState`。

## 6. 第五步：初始化或恢复 ResearchState

文件：`backend/app/service/deep_research_v2/graph.py:316-356`

执行顺序是：

```text
resume=True 且有 session_id
  -> 尝试加载检查点
  -> 成功则发送 research_resumed

没有检查点
  -> create_initial_state(query, session_id, ...)
  -> 设置 max_iterations
  -> 发送 research_start
```

然后把 `user_id` 放进内部状态 `_user_id`，并始终进入 `_run_simplified()`。当前默认运行路径是手写的异步流程，不是 LangGraph 的 `astream()` 路径。

## 7. 第六步：规划阶段

文件：`graph.py:570-587` 和 `agents/architect.py`

Graph 先发送：

```json
{"type":"phase","phase":"planning","content":"开始规划研究..."}
```

然后调用 `self.architect.process(state)`。ChiefArchitect 读取 `query`，通过 LLM 生成 `outline`、`research_questions`、关键实体和研究假设。完成后 Graph 保存一次检查点，记录规划步骤和章节数量。

此时的状态大致是：

```text
outline：有值
research_questions：有值
facts：通常为空或很少
charts：为空
final_report：为空
```

## 8. 第七步：搜索阶段

文件：`graph.py:589-608` 和 `agents/scout.py`

Graph 把 `phase` 设置为 `researching`，调用 DeepScout。DeepScout 根据大纲和搜索开关调用网络搜索、本地向量检索以及必要的股票或行业数据能力。

搜索结果会写入：

```text
facts：结构化事实
raw_sources：原始网页或来源内容
references：可展示的引用
data_points：后续分析所需的数据
```

完成后保存检查点，统计事实和来源数量。

如果用户只开启 `web`，`search_local` 为 `False`，则本地知识库不会被调用；这不是 Milvus 故障，而是请求配置决定的行为。

## 9. 第八步：分析阶段

文件：`graph.py:610-629`、`agents/data_analyst.py`、`agents/wizard.py`

项目实际顺序是：

```text
DataAnalyst.process(state)
→ CodeWizard.process(state)
```

DataAnalyst 负责从事实和数据点中提取结构化分析、洞察、知识图谱和 ECharts 配置。CodeWizard 可能让 LLM 生成 Python，进行语法检查、危险模式检查和进程内执行，再把执行结果、stdout/stderr 和 PNG 写入 `code_executions`、`charts`。

如果数据点少，CodeWizard 会跳过分析。此时 `facts` 可能有值，但 `charts` 为空，这是正常的条件分支，不一定是 SSE 或前端错误。

## 10. 第九步：写作阶段

文件：`graph.py:631-647` 和 `agents/writer.py`

LeadWriter 读取：

```text
outline
facts
insights
charts
references
```

先产生 `draft_sections`，再整合成 `final_report`。Graph 保存检查点时，把报告长度写进步骤统计。

此时不要把“有章节草稿”与“页面已经显示最终报告”混为一谈：还需要后续事件通过 SSE 到达前端，并由 React 的事件分支更新报告状态。

## 11. 第十步：审核、补充研究或修订

文件：`graph.py:649-687` 和 `agents/critic.py`

Graph 根据 `state["iteration"] < state["max_iterations"]` 进入审核循环。CriticMaster 读取报告和证据，更新：

```text
critic_feedback
quality_score
unresolved_issues
pending_search_queries
phase
iteration
```

可能的路径：

```text
审核通过 -> completed
需要补充证据 -> re_researching -> DeepScout -> LeadWriter
只需修改表达 -> revising -> LeadWriter
```

因此“多 Agent”不是简单的固定流水线，还包含审核结果驱动的分支。

## 12. 第十一步：完成事件和前端解析

文件：`graph.py:689-741`、`service.py:127-142`、`frontend/src/pages/chat/index.tsx:270-308`

Graph 将检查点状态更新为 `completed`，发送 `research_complete`，其中包含：

```text
final_report
quality_score
facts_count
charts_count
iterations
references
```

Service 包装成 SSE。前端 `reader.read()` 每次只得到一段字节，先通过 `TextDecoder` 拼入临时缓冲区，找到完整换行后才取出 `data: {...}` 并 `JSON.parse()`。

前端按事件类型更新研究步骤、搜索结果、图表、引用和报告。网络读完后收到 `[DONE]` 或 `done=true`，才结束读取状态。

## 13. 第十二步：检查点到底保存什么

Graph 每个阶段调用 `save_checkpoint_async()`：

```text
state_json：后端 ResearchState
ui_state_json：研究步骤、搜索结果、图表和前端报告状态
final_report：当前最终报告
phase/status：恢复和列表所需的元数据
```

检查点是“保存过的状态”，不是严格的节点级暂停点。当前 `resume=True` 会加载状态后重新进入 `_run_simplified()`，因此需要区分：

```text
能恢复已有数据：是
一定从上次中断的精确 Agent 行继续：不能由当前代码证明
```

## 14. 一张完整追踪图

```text
React Chat
  -> api.session.deepsearch()
  -> POST /research/stream
  -> ResearchRequest
  -> DeepResearchV2Service.research()
  -> DeepResearchGraph.run()
  -> create_initial_state()/load_checkpoint()
  -> ChiefArchitect
  -> DeepScout
  -> DataAnalyst
  -> CodeWizard
  -> LeadWriter
  -> CriticMaster
  -> asyncio.Queue
  -> StreamingResponse(text/event-stream)
  -> ReadableStream + TextDecoder
  -> researchDetailsRef / React state
  -> 研究步骤、图表、引用、最终报告
```

## 15. 这条链路的五个排错问题

1. 页面没有发送请求：看 `deepsearch()` 是否被调用、请求体是否含 `query`。
2. 返回 404/422：看 Router 路径和 `ResearchRequest` 字段。
3. 只收到 `research_start`：看 Graph 初始化、LLM 配置和 Architect。
4. facts 有值但 charts 为空：看数据点数量、DataAnalyst 和 CodeWizard 的跳过条件。
5. 后端有 `research_complete` 但页面无报告：看 SSE 分块解析、事件类型分支和 React 状态更新。

## 16. 课后作业

请你自己完成下面这段复述：

```text
用户输入问题后，前端通过 ______ 发起 ______ 请求。
后端由 ______ 路由接收，默认选择 ______ 版本。
服务调用 ______，先创建或恢复 ______。
六个 Agent 的顺序是 ______。
Agent 的中间结果写入 ______，实时事件进入 ______，最后通过 ______ 返回浏览器。
```

再回答两个判断题：

1. `ResearchState` 中的 `final_report` 有值，就代表浏览器页面一定已经显示报告。
2. `resume=True` 有检查点，就代表一定从上次停止的那个 Agent 的下一行继续。

请分别说明理由，并指出你依据的文件。
