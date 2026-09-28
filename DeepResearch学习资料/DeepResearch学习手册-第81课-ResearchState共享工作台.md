# DeepResearch 学习手册：第 81 课

## ResearchState：六个 Agent 共用的工作台

上一课的填空标准答案是：

```text
用户发送问题后，前端通过 deepsearch() 调用 POST /research/stream；
后端默认进入 V2，由 ResearchState 保存 Agent 之间的中间结果，
再按 ChiefArchitect、DeepScout、DataAnalyst、CodeWizard、LeadWriter、CriticMaster 的顺序处理，
最后通过 SSE 返回给前端。
```

这不是要求你死记函数名，而是要能说清楚数据如何向后流动。

## 1. 为什么需要共享状态

假设没有 `ResearchState`，每个 Agent 都只能把结果作为一大段字符串传给下一个 Agent。这样会出现：

- 下一个 Agent 不知道哪些内容是事实、哪些内容是原始网页、哪些内容是图表数据。
- 检查点很难保存，因为中间结果没有统一结构。
- 出问题时只能查看一长段提示词，无法判断是哪一个字段丢失。
- 前端想展示图表、来源和知识图谱时，没有稳定的字段可以读取。

`ResearchState` 用 `TypedDict` 定义了一个统一的状态契约。它不是数据库表，也不是 LLM 的记忆；它是本次研究运行期间的共享工作内存，必要时会被序列化到检查点。

## 2. 状态从开始到结束怎样变化

### 2.1 初始状态

`create_initial_state()` 创建：

```text
query = 用户问题
session_id = 当前会话
phase = init
outline = []
facts = []
data_points = []
charts = []
final_report = ""
critic_feedback = []
```

此时还没有研究结果，只有任务身份和空的产物容器。

### 2.2 ChiefArchitect 之后

规划 Agent 根据 `query` 调用 LLM，填充：

```text
outline
research_questions
hypotheses
key_entities
mind_map
knowledge_graph
```

它的核心产物不是答案，而是“接下来要研究什么”。

### 2.3 DeepScout 之后

搜索 Agent 读取 `outline` 和搜索开关，把搜索和阅读结果写入：

```text
raw_sources
facts
references
data_points
knowledge_graph
```

`facts` 是已经整理过的结构化事实；`raw_sources` 更接近原始网页或搜索材料。两者不要混为一谈。

### 2.4 DataAnalyst 和 CodeWizard 之后

分析阶段主要产生：

```text
data_points
insights
charts
code_executions
```

DataAnalyst 偏向从事实中抽取数据、生成洞察和 ECharts 配置。CodeWizard 偏向让 LLM 生成 Python 并执行，记录代码、输出、错误和图片。

### 2.5 LeadWriter 之后

写作 Agent 读取大纲、事实、数据和分析产物，写入：

```text
draft_sections
final_report
references
```

`draft_sections` 是按章节保存的草稿；`final_report` 是面向用户的整篇报告。

### 2.6 CriticMaster 之后

审核 Agent 读取报告和证据，写入：

```text
critic_feedback
unresolved_issues
quality_score
pending_search_queries
phase
iteration
```

如果缺少证据，状态可能进入 `re_researching`；如果只是文字或结构问题，可能进入 `revising`；没有需要处理的问题时进入完成路径。

## 3. Agent 不是通过返回值串联全部事件

每个 Agent 的 `process(state)` 返回更新后的状态，但实时事件还有另一条通道：

```text
Agent.add_message(state, event_type, content)
    -> state["_message_queue"].put_nowait(message)
    -> Graph 从 asyncio.Queue 读取
    -> Service 格式化为 SSE
    -> React 解析并更新界面
```

所以要区分：

| 通道 | 用途 |
|---|---|
| `ResearchState` 字段 | 保存研究产物，供后续 Agent 和检查点使用 |
| `_message_queue` | 把过程事件即时推给前端 |

事件发出不等于状态字段一定已经正确保存；状态字段有值也不等于前端一定收到了对应事件。排错时要分别检查这两条通道。

## 4. 看到字段为空时怎样判断

不要看到空数组就立即判定故障。先问三个问题：

1. 这个问题是否真的需要该产物？例如定性问题可能没有 `data_points`。
2. 上游 Agent 是否执行？看 `phase`、日志和 `research_step`。
3. 下游是否有跳过条件？例如 CodeWizard 在数据点不足时会跳过分析。

例子：

```text
facts 有值，data_points 为空，charts 为空
```

如果问题主要是政策解读，这可能正常；如果问题要求近五年市场规模趋势，则更像数据抽取或分析链异常。下一条证据应查看 DataAnalyst 的日志、LLM 返回结构和 CodeWizard 的数据点数量，而不是先修改前端。

## 5. 检查点保存什么

Graph 在阶段完成时调用检查点服务，至少涉及两种状态：

```text
state_json    后端 ResearchState
ui_state_json 前端研究步骤、搜索结果、图表、报告等恢复数据
```

这样做是因为后端状态适合继续处理，前端状态适合直接恢复页面。两者都保存成功，才更接近完整恢复；只恢复后端状态不一定能还原页面展示。

## 6. 本课练习

请回答下面三个小问题：

### 问题 A

为什么 `outline` 应该由规划 Agent 写入，而不是由前端直接生成？

### 问题 B

如果日志显示 Agent 已经把消息放入 `_message_queue`，但页面没有显示，应该检查 `ResearchState` 还是 SSE/前端解析链？为什么？

### 问题 C

`facts`、`data_points`、`charts` 三者分别代表什么？请各用一句话解释。

参考判断方向：A 看职责边界；B 优先查队列到 SSE 再到浏览器解析的事件通道；C 分别对应证据、可计算指标、可视化产物。
