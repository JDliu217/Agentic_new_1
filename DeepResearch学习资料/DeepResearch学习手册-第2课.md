# DeepResearch 项目学习手册

## 第 2 课：从一个问题看懂状态、Agent、SSE 和前端

本课继续依据本地项目 `D:\课\s4-6\industry_information_assistant` 的源码整理。目标不是背文件名，而是建立一条可调试的因果链：用户输入什么、后端把它放进哪里、哪个 Agent 处理、产生什么事件、前端最后显示什么。

## 1. 先看一条完整的运行链

假设用户输入：

```text
请研究 2025 年中国工业机器人市场，并给出主要厂商、增长因素和风险。
```

当前 V2 流程可以抽象为：

```text
React 聊天页
  -> POST /research/stream
  -> research_router
  -> DeepResearchV2Service
  -> DeepResearchGraph.run
  -> _run_simplified
  -> 规划
  -> 搜索
  -> 数据分析
  -> 写作
  -> 审核 / 修订
  -> SSE 事件
  -> React 状态
  -> 研究步骤、搜索结果、图谱、图表、报告
```

这里有一个必须记住的实现事实：代码虽然定义了 LangGraph 图，但 `run()` 当前把 LangGraph 执行段注释掉，默认进入 `_run_simplified()`。因此学习时要区分“设计出来的图”和“当前真正运行的流程”。

## 2. `ResearchState` 是所有 Agent 共用的工作台

`backend/app/service/deep_research_v2/state.py` 用 `TypedDict` 定义全局状态。它不是某个 Agent 的局部变量，而是整个研究过程共享的数据容器。

### 2.1 输入和控制字段

| 字段 | 作用 | 初始来源 |
| --- | --- | --- |
| `query` | 用户原始问题 | 请求体 |
| `session_id` | 关联会话、取消和检查点 | 请求体 |
| `phase` | 当前阶段 | `init` |
| `iteration` | 已进行的审核轮次 | `0` |
| `max_iterations` | 最大审核轮次 | 配置覆盖初始状态 |
| `search_web` | 是否搜索互联网 | 请求体 |
| `search_local` | 是否搜索本地知识库 | 请求体 |

一个容易忽略的细节是：`create_initial_state()` 有自己的 `max_iterations` 默认值，但 `DeepResearchGraph.run()` 创建状态后又用配置中的 `self.max_iterations` 覆盖它。实际运行时应以配置为准。

### 2.2 规划产物

| 字段 | 谁写入 | 后续用途 |
| --- | --- | --- |
| `outline` | `ChiefArchitect` | 决定报告章节和搜索范围 |
| `research_questions` | `ChiefArchitect` | 拆分需要回答的子问题 |
| `key_entities` | `ChiefArchitect` | 形成实体、搜索词和图谱候选 |
| `hypotheses` | `ChiefArchitect` | 让搜索围绕待验证假设进行 |
| `mind_map` | `ChiefArchitect` | 保存规划阶段的结构化关系 |
| `knowledge_graph` | 规划或研究阶段逐步完善 | 前端图谱面板 |

对上面的研究问题，一个可能的 `outline` 会包含“市场规模与增速”“主要厂商”“下游需求”“政策与供应链风险”等章节。搜索 Agent 不应该凭空决定报告结构，它应该读取这个大纲。

### 2.3 检索和分析产物

| 字段 | 含义 |
| --- | --- |
| `raw_sources` | 抓到的原始网页或文档内容 |
| `facts` | 从来源中抽取并整理后的结构化事实 |
| `data_points` | 可用于计算或作图的数值数据 |
| `charts` | 图表配置、数据和生成结果 |
| `code_executions` | 代码解释器每次执行的记录 |
| `insights` | 从数据或事实中得到的分析结论 |

这几个字段代表不同层次：`raw_sources` 是原材料，`facts` 是整理后的证据，`data_points` 是可计算数据，`charts` 和 `insights` 是分析输出。调试时不能把“搜到一段网页”误认为“已经形成了可引用事实”。

### 2.4 写作和审核产物

| 字段 | 含义 |
| --- | --- |
| `draft_sections` | 按章节保存的草稿 |
| `final_report` | 当前最终报告文本 |
| `references` | 报告引用来源 |
| `critic_feedback` | 审核发现的问题和修改建议 |
| `unresolved_issues` | 尚未解决的问题数量 |
| `quality_score` | 审核质量分 |
| `pending_search_queries` | 审核后需要补充执行的查询 |

审核并不是只返回一段自然语言意见。它还会改变控制字段，使主流程决定继续补充搜索、只做文字修订，或者结束。

### 2.5 流式和故障处理字段

| 字段 | 用途 |
| --- | --- |
| `messages` | Agent 产生的事件，供实时 SSE 输出 |
| `logs` | 执行日志 |
| `errors` | 错误记录 |
| `_message_queue` | `_run_simplified()` 临时注入的异步队列 |
| `_user_id` | 检查点保存时关联用户 |

下划线字段是运行时辅助字段，不属于面向用户的研究结果。`_message_queue` 在流程结束的 `finally` 中会被清理。

## 3. 五个阶段中状态怎样变化

### 3.1 阶段一：ChiefArchitect 规划

流程先发送：

```json
{"type":"phase","phase":"planning","content":"开始规划研究..."}
```

然后调用 `ChiefArchitect.process(state)`。它主要读取 `query`，生成 `outline`、`research_questions`、`key_entities`、`hypotheses` 等字段，并通过 `BaseAgent.add_message()` 发出 `outline` 等事件。

阶段完成后，图保存一个检查点，步骤信息类似：

```json
{
  "type": "planning",
  "status": "completed",
  "stats": {"sections": 4}
}
```

这一步的关键问题是“研究什么”。它还没有回答市场规模，也没有生成最终报告。

### 3.2 阶段二：DeepScout 搜索

流程发送 `researching` 阶段事件，再调用 `DeepScout.process(state)`。它读取大纲和待研究问题，调用网络搜索或本地检索，提取事实，构建引用，并可能更新知识图谱。

典型状态变化如下：

```text
pending_search_queries
  -> 搜索查询
raw_sources
  -> 网页原文
facts
  -> 结构化事实
references
  -> 可引用来源
knowledge_graph
  -> 节点和关系
```

流程完成后，检查点会记录事实数和来源数。后端还会把 `facts` 转换为前端易用的搜索结果：标题、来源、URL、摘要和日期。

### 3.3 阶段三：DataAnalyst 和 CodeWizard 分析

当前手写流程中，分析阶段依次调用两个 Agent：

```text
DataAnalyst -> 整理数据点、发现分析需求
CodeWizard  -> 生成并执行 Python，返回图表和代码执行记录
```

这与 LangGraph 中 `_analyze_node()` 只调用 `CodeWizard` 的设计存在差异。学习源码时应以当前 `_run_simplified()` 的真实调用为准。

如果数据足够，状态可能从：

```json
{"data_points": [], "charts": [], "insights": []}
```

变成：

```json
{
  "data_points": [{"name":"市场规模","value":123,"unit":"亿元","year":2025}],
  "charts": [{"title":"市场规模趋势","chart_type":"line"}],
  "insights": ["市场规模保持增长，但增速受到下游投资周期影响"]
}
```

CodeWizard 不是一个天然安全的外部沙箱。当前实现是“LLM 生成 Python，再在受限 globals 中 `exec()`”，会做语法检查、模块白名单和危险操作过滤，并捕获标准输出和 matplotlib 图像。源码已经明确提示，生产环境应改用 Docker 或专用执行服务。

### 3.4 阶段四：LeadWriter 写作

LeadWriter 读取大纲、事实、数据、洞察、图表和引用，按章节生成 `draft_sections`，再形成 `final_report`。写作阶段会发送：

```text
phase
section_content
section_draft
report_draft
```

其中 `section_content` 允许前端一章一章更新“过程报告”，`report_draft` 表示完整草稿已经形成。

源码中还有一个边界：`DeepScout` 每次最多处理前几个待处理章节，但 LeadWriter 会遍历整个大纲。因此如果后续章节没有拿到足够事实，报告可能仍然生成，但证据覆盖度会不均匀。

### 3.5 阶段五：CriticMaster 审核和循环

审核开始时发送 `reviewing`。CriticMaster 读取报告、引用和事实，写入：

```text
critic_feedback
unresolved_issues
quality_score
phase
iteration
```

主流程依据 `state["phase"]` 做路由：

```text
COMPLETED       -> 结束
RE_RESEARCHING  -> DeepScout 补充搜索 -> LeadWriter 重写
REVISING        -> LeadWriter 只修订文字
```

循环条件是 `state["iteration"] < state["max_iterations"]`。配置中的最大轮数会直接影响审核和修订是否发生。

## 4. `BaseAgent.add_message()` 为什么能实时显示

每个 Agent 都继承基础 Agent。调用：

```python
self.add_message(state, "outline", content)
```

会完成两件事：

1. 把消息追加到 `state["messages"]`。
2. 如果状态里存在 `_message_queue`，立即 `put_nowait()`。

`_run_simplified()` 在 Agent 运行期间用 `asyncio.create_task()` 启动 Agent，同时循环读取这个队列。读到一条消息就 `yield` 一条事件，路由层再把它包装成 SSE 发给浏览器。

因此实时性的关键不是“模型一次生成全部结果”，而是：

```text
Agent 产生事件
  -> asyncio.Queue
  -> graph yield
  -> FastAPI StreamingResponse
  -> 浏览器逐条解析
```

## 5. 前端怎样把事件变成界面

前端主要处理文件是 `frontend/src/pages/chat/index.tsx`。它收到 SSE 后，先解析 JSON，再按 `json.type` 分支处理。

### 5.1 事件到 UI 的映射

| 后端事件 | 前端保存位置 | 用户看到的内容 |
| --- | --- | --- |
| `research_start` | `reactSteps`、研究状态 | 开始深度研究 |
| `research_step` | `researchSteps`、`researchDetailsRef` | 时间线步骤和统计 |
| `phase` | `reactSteps`、步骤状态 | 当前处于规划/搜索/分析/写作/审核 |
| `outline` | `reactSteps` | 研究大纲和核心问题 |
| `search_results` | 搜索阶段 detail | 搜索结果列表 |
| `knowledge_graph` | 分析或搜索 detail | 节点和关系图 |
| `charts` / `chart` | 分析 detail、消息图表 | 可视化图表 |
| `section_content` | 写作 detail 的 `sections` | 章节逐步出现 |
| `report_draft` | `streamingReport`、消息内容 | 草稿报告 |
| `review` | `reactSteps`、审核步骤 | 质量分和是否通过 |
| `revision_complete` | `reactSteps` | 修订次数或修改数 |
| `research_complete` | 最终消息、引用、所有步骤 | 研究完成和最终报告 |
| `checkpoint_saved` | 恢复所需状态 | 后台保存成功 |
| `research_cancelled` | 消息和步骤状态 | 研究已取消 |

### 5.2 为什么用 `stepType` 作为 key

前端用 `researchDetailsRef` 保存每个阶段的详细数据，例如：

```text
planning
searching
analyzing
writing
reviewing
```

步骤更新和详情更新都使用相同的阶段类型作为 key。这样收到 `charts` 时可以直接找到 `analyzing`，收到 `section_content` 时可以直接找到 `writing`。这是一种简单但重要的前后端约定。

### 5.3 右侧研究详情面板

`research-detail/index.tsx` 把详情分成四个 tab：

1. 搜索结果
2. 知识图谱
3. 可视化图表
4. 过程报告

`research-process/index.tsx` 负责时间线和完成状态。统计标签来自后端事件中的数量，前端把 snake_case 字段转换成 camelCase，例如 `results_count` 转成 `resultsCount`。

## 6. 检查点、恢复和取消

### 6.1 检查点保存了什么

每个主要阶段结束后，`save_checkpoint_async()` 先调用 `update_ui_state()`，把后端状态转换成 UI 状态，再调用检查点服务保存：

```text
后端 ResearchState
  + UI research_steps
  + UI search_results
  + UI charts
  + UI knowledge_graph
  + streaming_report
  -> PostgreSQL 检查点
```

保存成功后产生 `checkpoint_saved` 事件。用户刷新或恢复会话时，前端用检查点中的 UI 状态重建步骤、结果、图谱和报告。

### 6.2 恢复流程

调用 `run(..., resume=True)` 时，后端先按 `session_id` 加载检查点。如果找到，就发送：

```json
{"type":"research_resumed","phase":"writing","session_id":"..."}
```

然后继续执行后续流程。恢复的重点是“状态恢复”，不是重新从用户问题开始调用所有 Agent。

### 6.3 取消流程

每个阶段和 Agent 运行期间都会检查 `is_research_cancelled(session_id)`。如果发现取消标志：

1. 取消当前 Agent 任务。
2. 发送 `research_cancelled`。
3. 结束当前生成器。

前端收到后会停止 loading，并把研究步骤标为完成状态。这个“完成”表示流程停止，不代表报告质量已经通过审核。

## 7. 用一个最小例子练习状态变化

请手工回答下面的问题，不需要先运行项目：

> 用户要求研究“新能源汽车电池价格趋势”，搜索得到 10 条来源，其中 3 条有明确年度价格数据。

你应该能写出：

```text
query                 = 用户问题
outline               = 价格趋势、厂商、成本因素、风险
facts                 = 经过来源整理的事实
data_points           = 3 条年度价格数据
charts                = 至少一个趋势图配置
insights              = 对趋势和原因的解释
draft_sections        = 每个章节的草稿
final_report          = 合并后的报告
references            = 可追溯来源
```

然后回答：

1. 如果只有 `raw_sources`，没有 `facts`，写作 Agent 缺少什么？
2. 如果有 `data_points`，没有 `code_executions`，是否一定有图表？为什么？
3. 如果审核发现来源不足，应该进入 `REVISING` 还是 `RE_RESEARCHING`？
4. 前端要显示图表，至少需要哪个事件和哪个 detail key？

参考答案：

1. 缺少经过整理、可引用的结构化证据。
2. 不一定。数据还需要被代码解释器成功执行并产生图表结果。
3. 来源不足应进入 `RE_RESEARCHING`；只有文字表达问题才进入 `REVISING`。
4. 通常需要 `charts` 或 `chart` 事件，并把结果放到 `analyzing` detail。

## 8. 面试检查题

### 初级

- `ResearchState` 为什么要由所有 Agent 共享？
- `raw_sources`、`facts`、`references` 有什么区别？
- SSE 和一次性返回 JSON 的主要区别是什么？

### 中级

- 为什么当前 `run()` 使用 `_run_simplified()` 而不是已构建的 LangGraph？
- `asyncio.Queue` 在实时输出中解决了什么问题？
- 为什么前端收到事件后还要维护 `researchDetailsRef`？

### 高级

- 当前 CodeWizard 的 `exec()` 隔离为什么不能视为生产级安全沙箱？
- 如果 `DeepScout` 只处理部分章节，如何保证未处理章节不会被写作阶段伪造为有充分证据？
- 检查点同时保存后端状态和 UI 状态有什么好处？两者不一致时可能出现什么问题？

## 9. 本课结论

这个项目的核心不是“六个 Agent 轮流调用模型”，而是一个共享状态和事件流系统：

```text
ResearchState 保存事实和产物
Agent 读取并更新状态
BaseAgent 生成事件
asyncio.Queue 提供实时通道
SSE 把事件传到浏览器
React 把事件映射成可见的研究过程
检查点保存状态以支持恢复
```

掌握这条链以后，再去学习具体搜索服务、Milvus、PostgreSQL、Redis 和代码解释器，才不会把它们误认为互相独立的功能。

