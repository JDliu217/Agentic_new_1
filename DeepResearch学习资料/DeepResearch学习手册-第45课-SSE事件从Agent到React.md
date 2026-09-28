# DeepResearch 学习手册：第 45 课

## SSE 事件：从 Agent 到 React

本课把“后端流式返回”拆成五个动作：请求选择版本、Agent 产生事件、消息进入队列、Router 包装成 SSE、React 解析并更新状态。

## 1. 请求先决定走 V1 还是 V2

前端 `api/session.ts` 的 `deepsearch()` 将请求发到：

```text
POST /research/stream
```

请求模型 `ResearchRequest` 默认 `version="v2"`。`search_modes` 会被转换为 `search_web` 和 `search_local`：

```text
['web', 'local']
  → search_web=True
  → search_local=True
```

`research_router.py` 根据 `version` 选择 V2 服务或旧 V1 服务。V2 的生成器调用 `service_v2.research(...)`，并把每个事件逐个 yield。

## 2. Agent 如何产生事件

每个 V2 Agent 继承 `BaseAgent`，通过 `add_message(state, event_type, content)` 产生结构化事件。例如：

```text
ChiefArchitect → research_step / outline / thought
DeepScout      → research_step / search_results / stock_quote
DataAnalyst    → knowledge_graph / charts / research_step
CodeWizard     → code / code_result / chart
LeadWriter     → section_content / report_draft
CriticMaster   → review / critic_feedback
```

这些事件一方面写入 `state["messages"]`，另一方面在图流程创建了消息队列时放入 `_message_queue`。

## 3. 队列为什么存在

`_run_simplified()` 创建：

```python
message_queue = asyncio.Queue()
state["_message_queue"] = message_queue
```

然后启动 Agent 任务，同时每 0.5 秒从队列读取事件。这样 Agent 可以继续运行，Router 也可以及时把已经产生的事件发给浏览器。

```text
Agent.process(state)
      ↓ add_message()
asyncio.Queue
      ↓ graph yield
research_router.generate_sse_v2()
      ↓ StreamingResponse
浏览器 ReadableStream
```

队列不是数据库，也不是最终状态。它只是一次请求期间的实时传输通道；长期状态仍写入 `ResearchState`、检查点或会话消息。

## 4. SSE 的文本格式

Router 最终发送类似：

```text
data: {"type":"research_step","content":{...}}\n\n
```

`data:` 是 SSE 字段前缀，空行表示一条事件结束。项目没有直接把整个 SSE 事件交给浏览器 JSON 解析，而是先在前端缓冲字符串，再按换行切分。

## 5. 前端为什么需要缓冲区

网络分块不保证一次 `reader.read()` 正好得到一条完整事件。一条事件可能被拆成多次读取，也可能一次读到多条事件：

```text
第一次读取：data: {"type":"research_
第二次读取：step"...}\n\ndata: ...
```

因此 `chat/index.tsx` 把每次读取内容追加到 `temp`，只有找到换行后才取出完整行，再判断是否以 `data: ` 开头并调用 `JSON.parse()`。

## 6. 事件如何变成 React 状态

核心映射：

| 事件 | React 处理 |
|---|---|
| `research_start` | 进入 Deepsearch 模式，清空旧详情 |
| `research_step` | 更新 `researchSteps` 和详情 Map |
| `search_results` | 写入搜索结果 |
| `knowledge_graph` | 写入知识图谱 |
| `charts` / `chart` | 写入图表数组 |
| `report_draft` / 报告事件 | 更新流式报告 |
| `research_complete` | 保存引用、完成步骤并递增 `researchDataVersion` |
| `research_cancelled` | 停止加载并显示取消状态 |

`researchDetailsRef` 负责保存每个步骤的详情，`researchDataVersion` 用来强制触发聚合数据重新计算。因为详情存放在 ref 中，单独修改 ref 不会自动触发 React 重渲染，所以需要版本计数器配合。

## 7. 事件流和持久化不是一回事

```text
SSE 队列：当前请求实时传输
ResearchState：当前研究内存状态
ResearchCheckpoint：研究恢复状态
ChatMessage：会话历史消息
```

浏览器断开连接后，已经发出的 SSE 不会自动重放；要恢复研究页面，前端需要读取完整检查点和会话消息。检查点中的 `state_json` 与 `ui_state_json` 解决的是恢复问题，不是 SSE 本身的可靠消息队列。

## 8. 取消时发生什么

前端停止按钮会先取消 `ReadableStream`，再调用：

```text
POST /research/cancel/{session_id}
```

后端把 Redis 取消标志写入 `research:cancel:{session_id}`。`_run_simplified()` 在 Agent 开始前和运行期间检查标志，发现取消后结束任务并发送 `research_cancelled`。这属于协作式取消；正在等待的外部 HTTP 请求不一定会立刻被强制杀死。

## 9. 本课练习

1. 如果一次 `reader.read()` 只拿到半行 JSON，前端为什么不能马上 `JSON.parse()`？
2. 为什么 `message_queue` 不能替代 `ResearchCheckpoint`？
3. 为什么 `researchDetailsRef` 修改后还要递增 `researchDataVersion`？
4. V2 服务已经 yield 事件后，浏览器断开连接，页面刷新时靠什么恢复？

## 10. 关键源码

- `backend/app/router/research_router.py:80-149`
- `backend/app/service/deep_research_v2/graph.py:349-447`
- `backend/app/service/deep_research_v2/agents/base.py:237-258`
- `frontend/src/api/session.ts` 的 `deepsearch()`
- `frontend/src/pages/chat/index.tsx:270-632`

