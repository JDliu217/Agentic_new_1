# DeepResearch 学习手册：第 71 课

## 从一个问题追踪完整请求

这一课只追踪一个动作：用户在 DeepResearch 页面输入问题并点击发送。

示例问题：

```text
请研究新能源汽车电池价格趋势，并说明主要影响因素。
```

目标不是一次看懂所有代码，而是建立四个问题：

1. 请求从哪里进入？
2. 数据被放到哪里？
3. 哪个 Agent 负责下一步？
4. 结果怎样回到浏览器？

## 1. 浏览器先发送什么

聊天页在 DeepSearch 模式下调用：

```text
frontend/src/api/session.ts::deepsearch()
```

请求方法是 `POST`，路径是：

```text
/research/stream
```

核心请求体可以理解为：

```json
{
  "query": "请研究新能源汽车电池价格趋势，并说明主要影响因素。",
  "session_id": "当前会话ID",
  "search_modes": ["web", "local"]
}
```

`Accept: text/event-stream` 表示浏览器希望后端持续发送事件，而不是只返回一个最终对象。

## 2. Router 做什么

请求进入：

```text
backend/app/router/research_router.py::stream_research()
```

FastAPI 先用 `ResearchRequest` 检查请求字段。这个模型包含：

```text
query          用户问题
session_id     会话和检查点关联
search_modes   web/local 搜索开关
version        v1 或 v2
```

当前 POST 请求的默认版本是 `v2`。当 `search_modes` 为 `["web", "local"]` 时，Router 会转换为：

```text
search_web   = True
search_local = True
```

随后 Router 创建 `DeepResearchV2Service`，调用它的异步研究方法，并把事件包装成 `StreamingResponse`。

这里要区分两层：

```text
Router：接收和分发请求
Service/Graph：真正执行研究
```

Router 本身不负责规划问题，也不负责写报告。

## 3. Graph 怎样创建共享状态

入口文件：

```text
backend/app/service/deep_research_v2/graph.py
```

`DeepResearchGraph.run()` 如果没有可恢复的检查点，会调用 `create_initial_state()` 创建初始状态。

针对本例，初始状态可以抽象成：

```text
query          = 新能源汽车电池价格趋势...
session_id     = 当前会话ID
phase          = init
iteration      = 0
search_web     = True
search_local   = True
outline        = []
facts          = []
data_points    = []
charts         = []
draft_sections = {}
final_report   = ""
```

这说明：刚创建状态时，项目还没有事实、数据、图表和报告。后续 Agent 会逐步填充这些字段。

## 4. 六个 Agent 怎样接力

当前默认执行器是：

```text
_run_simplified()
```

代码中调用 LangGraph 的部分被注释，原因是当前手写流程更方便实时发送 SSE。

### 4.1 ChiefArchitect：把问题拆开

它读取：

```text
state["query"]
```

它写入：

```text
outline
research_questions
key_entities
hypotheses
mind_map
```

本例可能被拆成：

```text
电池价格历史变化
价格变化的材料和制造原因
主要电池厂商和技术路线
供需、政策和原材料风险
未来价格趋势
```

此时 Agent 还没有完成报告，它只是决定“要研究哪些问题”。

### 4.2 DeepScout：寻找证据

它读取：

```text
outline
research_questions
search_web
search_local
```

它写入：

```text
raw_sources
facts
data_points
references
knowledge_graph
```

例如搜索到某年份的电池包价格后，原始网页可能进入 `raw_sources`，整理后的“某年平均价格为某值”进入 `facts`，可以用于趋势计算的年度数值进入 `data_points`。

所以：

```text
raw_sources = 原材料
facts       = 经过整理的证据
data_points = 可计算的数据
```

### 4.3 DataAnalyst：分析结构和关系

它读取事实和数据点，产生：

```text
insights
knowledge_graph
charts 中的结构化图表配置
```

它更像数据分析师，负责判断“这些数据说明什么、适合怎样展示”。

### 4.4 CodeWizard：执行代码验证

如果需要计算增长率、拟合趋势或生成图片，CodeWizard 会：

```text
LLM 生成 Python
→ compile() 语法检查
→ 危险模式检查
→ 受限环境 exec()
→ 捕获输出和图片
→ 写入 code_executions 和 charts
```

它更像一个受控的代码执行工具，不是第二个写作 Agent。

### 4.5 LeadWriter：生成章节和报告

它读取：

```text
outline
facts
data_points
insights
charts
references
```

然后写入：

```text
draft_sections
final_report
```

写作 Agent 应该根据已有证据组织报告，不能把没有证据的内容当成已验证事实。

### 4.6 CriticMaster：判断是否需要补充

它读取报告和证据，写入：

```text
critic_feedback
quality_score
unresolved_issues
pending_search_queries
```

如果发现资料不足，流程可能回到补充搜索；如果只是表达问题，可能进入修订；如果通过审核，则结束。

## 5. 事件怎样回到页面

Agent 运行时把消息放入：

```text
asyncio.Queue
```

`_run_simplified()` 持续从队列取出消息，并通过异步生成器交给 Router。Router 再把它变成类似这样的 SSE 行：

```text
data: {"type":"research_step","content":{...}}

```

浏览器端 `frontend/src/pages/chat/index.tsx` 调用：

```text
response.body.getReader()
```

注意：一次 `reader.read()` 得到的是网络分块，不保证刚好是一条事件。因此前端先放入字符串缓冲区，再按换行拆分，最后对 `data: ` 后的内容执行 `JSON.parse()`。

## 6. 一个事件的完整去向

以搜索来源为例：

```text
DeepScout 找到来源
  → 发送 search_result_item
  → asyncio.Queue
  → Graph 异步生成器
  → FastAPI StreamingResponse
  → 浏览器 ReadableStream
  → JSON.parse
  → researchDetailsRef
  → search_results 数组
  → Source / ResearchDetail 组件
```

如果页面没有显示来源，应沿这条链逐层查证，而不是先猜 LLM 出错：

```text
后端是否产生事件
→ SSE 是否真的发送
→ 浏览器是否读到
→ JSON 是否解析成功
→ detail key 是否匹配
→ React 是否触发更新
```

## 7. 初学者最容易混淆的三件事

### 7.1 有搜索结果不等于有报告

搜索结果只是证据输入。还要经过事实整理、分析、写作和审核，才会形成 `final_report`。

### 7.2 有数据点不等于有图片

`data_points` 可以存在，但 CodeWizard 可能执行失败，或者 DataAnalyst 只生成 ECharts 配置而没有生成 Base64 图片。因此排错时要分别看 `charts` 和 `code_executions`。

### 7.3 页面显示完成不等于所有外部服务真实可用

前端 Mock 或历史检查点也可能让页面显示部分内容。要证明真实业务成功，还需要后端日志、数据库、Milvus、LLM 和外部 API 的运行证据。

## 8. 本课练习

请用自己的话回答：

1. 用户问题进入 Router 后，为什么还要创建 `ResearchState`？
2. `outline`、`facts`、`data_points`、`final_report` 分别处于研究链的什么位置？
3. 如果后端日志显示已经生成 `search_result_item`，但页面没有来源列表，你会按哪几层排查？
4. 为什么 `DataAnalyst` 和 `CodeWizard` 不能简单看成同一个“画图 Agent”？
5. 当前代码中哪一处证据说明默认执行的是 `_run_simplified()`？

建议回答格式：

```text
1. 我的理解：
   源码位置：
   不确定点：
```

## 9. 下一步学习目标

完成本课后，下一课会专门拆解 `ResearchState` 的字段和状态演化，用一个“只有搜索结果、没有可计算数据”的故障案例，训练你判断问题发生在哪个 Agent。

