# DeepResearch 学习手册：第 86 课

## 六个 Agent：责任边界、输入和输出

理解多 Agent 项目不能只背六个名字。要能回答：每个 Agent 在什么时候运行，读取哪些状态，写入哪些状态，失败或缺数据时会怎样。

## 1. 总体责任矩阵

| Agent | 主要问题 | 主要读取 | 主要写入 | 典型事件 |
|---|---|---|---|---|
| ChiefArchitect | 研究什么 | `query`、已有事实 | `outline`、问题、假设 | `research_step`、`outline` |
| DeepScout | 去哪里找证据 | `outline`、搜索开关 | `facts`、来源、数据点、知识图谱 | `search_results`、`knowledge_graph` |
| DataAnalyst | 从事实中提取什么数据 | `facts`、`query` | `data_points`、`insights`、ECharts 图表、知识图谱 | `charts`、`knowledge_graph` |
| CodeWizard | 如何用 Python 计算和绘图 | `data_points`、`outline` | `code_executions`、图片型 `charts` | `code`、`code_result`、`chart` |
| LeadWriter | 如何组织报告 | 大纲、事实、数据、图表、洞察 | `draft_sections`、`final_report`、引用 | `section_content`、`report_draft` |
| CriticMaster | 报告是否可信完整 | 报告、事实、数据、大纲 | `critic_feedback`、质量分、迭代和下一阶段 | `review`、`critic_feedback` |

## 2. ChiefArchitect：把问题变成计划

文件：`agents/architect.py`

它的输入是用户问题 `query`，主要输出：

```text
outline
research_questions
hypotheses
key_entities
mind_map
```

大纲章节还会带：

```text
id、title、description、section_type
requires_data、requires_chart、search_queries、status
```

后续 Agent 依赖这些字段来决定搜索关键词、是否抽取数据以及是否生成图表。

如果规划 LLM 返回格式不符合预期，Architect 会重试；仍失败时把错误写入 `state["errors"]`，但当前整体流程可能继续。这是一个重要的可靠性边界。

## 3. DeepScout：把计划变成证据

文件：`agents/scout.py`

它读取 `outline` 中状态为 `pending` 的章节，每次最多并行处理三个章节。根据状态开关选择：

```text
网络搜索
本地知识库搜索
股票行情识别（问题相关时）
```

搜索结果经过 LLM 分析后形成：

```text
facts
references
data_points
insights
knowledge_graph
```

DeepScout 不只是拿搜索摘要，还可能深读网页、追溯来源、交叉验证和生成补充查询。

## 4. DataAnalyst：把事实变成结构化分析

文件：`agents/data_analyst.py`

它先从最多一批事实中提取结构化数据：

```text
data_points
time_series
distributions
insights
```

然后构建知识图谱和 ECharts 配置。它通常不会执行任意 Python；它的主产物是结构化配置和分析结果。

因此：

```text
DataAnalyst 有 charts，不一定有 code_executions
```

## 5. CodeWizard：把数据交给 Python

CodeWizard 接着读取 `data_points`。它在数据点不足时可能跳过；数据足够时调用 LLM 生成 Python，执行后写入：

```text
code_executions
charts（图片 Base64）
```

它的图表事件类型是 `chart`；DataAnalyst 的批量图表事件通常是 `charts`。前端对这两种事件有不同分支。

## 6. LeadWriter：把产物组织成报告

文件：`agents/writer.py`

它逐章节读取大纲、相关事实和数据，写入 `draft_sections`，再整合成 `final_report`。同时补充 `references`，并发送章节内容和报告草稿事件。

写作阶段完成后，把 `phase` 改成 `reviewing`，交给 CriticMaster。

## 7. CriticMaster：决定完成、补搜还是修订

文件：`agents/critic.py`

它检查报告是否存在：

```text
缺少来源
逻辑错误
偏差
疑似幻觉
过时信息
内容不完整
```

它写入 `critic_feedback`、`quality_score` 和 `unresolved_issues`，再根据审核结果路由：

```text
pass                -> completed
需要补证据          -> re_researching
只需改写文字        -> revising
达到最大迭代次数    -> 强制 completed，并发 warning
```

## 8. 为什么字段异常可以定位到 Agent

几个典型判断：

### 有大纲，没有事实

优先查 DeepScout：搜索开关、API、Milvus、章节状态和 LLM 分析结果。

### 有事实，没有数据点

优先查 DataAnalyst 的数据提取提示词、JSON 解析结果和问题是否真的包含定量信息。

### 有数据点，没有图片

优先查 CodeWizard：数据点数量、危险模式检查、语法错误、执行异常和图表保存逻辑。

### 有报告，没有审核反馈

优先查 CriticMaster 是否进入 `reviewing`，以及审核 LLM 是否返回了可解析 JSON。

### 后端有 charts，页面没有图表

检查是 `charts` 还是 `chart` 事件，再检查前端详情 key 和对应分支。

## 9. 当前实现中的阶段条件

六个 Agent 虽然被设计成工作流节点，但实际简化流程直接按阶段调用。每个 Agent 自己仍会检查 `state["phase"]`，不满足条件时返回原状态。因此排错时要同时看：

```text
Graph 是否调用了 Agent
Agent 的 phase 条件是否允许它工作
Agent 是否因为输入不足主动跳过
```

## 10. 本课练习

请判断下面三个情况应该先查谁，并说明依据：

1. `outline` 有 6 个章节，但 `facts` 始终为空。
2. `facts` 有 30 条，`data_points` 有 0 条，问题是“近五年市场规模变化”。
3. 后端 `chart` 事件正常，浏览器分析步骤仍无图片。
