# DeepResearch 学习手册：第 82 课

## SSE：从 Agent 消息队列到 React 页面

这一课解决一个常见现象：后端日志写着“事件已经生成”，但浏览器页面没有显示。要解决它，必须把事件经过的每一层都看成一个独立环节。

## 1. 后端事件的第一站：Agent.add_message

文件：`backend/app/service/deep_research_v2/agents/base.py`

Agent 调用：

```python
self.add_message(state, "research_step", {...})
```

`add_message()` 会构造统一消息：

```json
{
  "type": "research_step",
  "agent": "ChiefArchitect",
  "timestamp": "...",
  "content": {"step_type": "planning", "status": "running"}
}
```

然后同时做两件事：

1. 追加到 `state["messages"]`，供状态记录和调试使用。
2. 如果 `state["_message_queue"]` 存在，把同一消息放进 `asyncio.Queue`。

这里是第一个可能的故障点：如果 `_message_queue` 没有创建，日志会提示 `No queue available`，状态里可能仍有消息，但实时流不会收到它。

## 2. Graph 从队列取消息

文件：`backend/app/service/deep_research_v2/graph.py`

`_run_simplified()` 先创建队列：

```python
message_queue = asyncio.Queue()
state["_message_queue"] = message_queue
```

它启动 Agent 的 `process(state)`，同时循环执行：

```python
msg = await message_queue.get()
yield msg
```

这使得 Agent 还没有完全结束时，中间事件就能继续向上层流动。Agent 结束后，Graph 还会清空队列中剩余的消息。

## 3. Service 把事件包装成 SSE

文件：`backend/app/service/deep_research_v2/service.py`

Graph yield 出来的是 Python 字典，例如：

```python
{"type": "phase", "phase": "researching", "content": "开始深度搜索..."}
```

服务层调用 `_format_sse()`，变成：

```text
data: {"type": "phase", "phase": "researching", "content": "开始深度搜索..."}\n\n
```

`data: ` 是 SSE 数据行的前缀，末尾的空行表示一条事件结束。服务最后还会发送：

```text
data: [DONE]\n\n
```

## 4. FastAPI StreamingResponse 把它发到浏览器

文件：`backend/app/router/research_router.py`

路由返回：

```python
StreamingResponse(generate_sse_v2(), media_type="text/event-stream")
```

这里的响应不是等全部研究完成后一次性返回，而是生成器每 yield 一次，网络就有机会传输一次或一批数据。

## 5. 浏览器为什么需要缓冲区

文件：`frontend/src/pages/chat/index.tsx`

前端通过：

```ts
const reader = res.data.getReader()
const { value, done } = await reader.read()
```

但是一次 `reader.read()` 的结果不保证对应一条完整 SSE 事件。可能出现：

```text
第一次读取：data: {"type":"research_
第二次读取：step", "content": {...}}\n\n
```

也可能一次读取包含两条事件。因此代码把内容先放入 `temp`，找到换行后才取出完整的 `data: ` 行，再调用 `JSON.parse()`。

这就是网络分块和应用事件边界不同的原因。

## 6. React 如何按事件类型更新页面

`parseData()` 解析 JSON 后，根据 `json.type` 分支：

| 事件 | 页面动作 |
|---|---|
| `research_start` | 清空上一轮研究详情，创建研究上下文 |
| `research_step` | 新增或更新规划、搜索、分析等步骤 |
| `phase` | 更新阶段文字和步骤状态 |
| `search_results` | 写入搜索详情中的来源列表 |
| `knowledge_graph` | 写入知识图谱详情 |
| `charts` | 写入分析步骤的图表集合 |
| `chart` | 追加单个 CodeWizard 图表 |
| `research_complete` | 写入最终报告、质量分数、来源和统计 |

前端还用 `researchDetailsRef` 保存每个步骤的详情，用 `setResearchSteps()` 和 `setSelectedResearchDetail()` 触发 React 重新渲染。

## 7. 五层排错顺序

出现“后端有日志，页面没显示”时，按下面顺序排查：

### 第 1 层：Agent 是否真的入队

看后端日志是否出现：

```text
[SSE] Queued event: research_step
```

如果没有，检查 `add_message()` 的调用、事件类型和 `_message_queue`。

### 第 2 层：Graph 是否取出并 yield

看是否出现：

```text
[SSE YIELD] [AgentName] #n: research_step
```

没有的话，检查 Agent 任务是否提前结束、队列是否被错误清空、异常是否被吞掉。

### 第 3 层：Service 和 Router 是否包装并发送

检查响应是否为 `text/event-stream`，是否有 `data: ` 前缀和两个换行。还要确认路由走的是 POST V2，而不是 GET 默认 V1。

### 第 4 层：浏览器是否收到字节

在 Network 面板查看 `/research/stream` 响应是否持续产生内容。若后端 yield 了但浏览器没有字节，检查代理、反向代理缓冲和响应头。

### 第 5 层：React 是否识别并写入状态

查看前端控制台是否出现解析失败，确认 `json.type` 与分支名称一致，确认详情 key（例如 `analyzing`、`searching`）已经创建。

## 8. 三个容易混淆的结论

1. 后端 `state["messages"]` 有消息，不代表消息已经通过网络发送。
2. 网络收到 JSON，不代表 React 一定有对应的事件分支。
3. 页面没有显示，不一定是 Agent 没有工作，也可能是事件格式、缓冲、步骤 key 或 React 状态更新出了问题。

## 9. 练习

请按顺序写出下面四个词之间的关系：

```text
add_message、asyncio.Queue、StreamingResponse、ReadableStream
```

参考方向：Agent 先调用第一个；Graph 利用第二个转发；Router 使用第三个输出；浏览器用第四个读取。
