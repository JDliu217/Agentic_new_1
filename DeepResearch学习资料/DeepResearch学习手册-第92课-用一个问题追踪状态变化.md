# DeepResearch 学习手册：第 92 课

## 用一个问题追踪 ResearchState 的变化

本课用一个假设问题演示状态如何变化：

```text
请分析新能源汽车行业未来三年的竞争格局，并提供市场规模数据和主要企业对比。
```

下面的章节标题、事实和数值是演示用的假设，不能当成项目真实 API 返回的数据；阶段顺序和字段变化依据当前源码。

## 1. 请求进入时

前端发送：

```json
{
  "query": "请分析新能源汽车行业未来三年的竞争格局，并提供市场规模数据和主要企业对比。",
  "session_id": "session-123",
  "search_modes": ["web", "local"]
}
```

路由转换为：

```text
search_web = true
search_local = true
version = v2（POST 默认）
```

初始状态大致是：

```text
phase = init
outline = []
facts = []
data_points = []
charts = []
final_report = ""
```

## 2. ChiefArchitect 之后

假设 LLM 返回五个章节，Architect 写入：

```text
phase = planning
outline = [市场规模、竞争企业、技术趋势、政策环境、未来展望]
research_questions = [...]
hypotheses = [...]
```

此时仍然没有可靠事实。规划完成只代表“知道要查什么”，不代表已经回答了问题。

前端可能收到：

```text
research_step(step_type=planning, status=running)
outline(...)
research_step(step_type=planning, status=completed)
```

## 3. DeepScout 之后

DeepScout 读取待研究章节，可能同时执行网络和本地检索。假设得到：

```text
facts = [
  {content: "市场规模事实", source_url: "...", related_sections: ["sec_1"]},
  {content: "企业销量事实", source_url: "...", related_sections: ["sec_2"]}
]
data_points = [
  {name: "2024市场规模", value: 3200, unit: "亿元", year: 2024}
]
references = [...]
knowledge_graph = {nodes: [...], edges: [...]}
```

搜索完成后，状态进入后续分析所需的基础形态。前端可能收到 `search_results` 和 `knowledge_graph` 事件。

## 4. DataAnalyst 之后

DataAnalyst 从 `facts` 中提取更多数据并生成结构化图表配置：

```text
data_points = [...更多可比较数据...]
insights = ["市场规模持续增长", "企业竞争集中度较高"]
charts = [{echarts_option: {...}}]
knowledge_graph = {...更新后的图谱...}
```

这里的 `charts` 可能包含 ECharts 配置，不一定是 PNG 图片。

## 5. CodeWizard 之后

CodeWizard 读取 `data_points`，让 LLM 生成 Python，执行后可能追加：

```text
code_executions = [{code: "...", success: true, output: "...", charts: [...]}]
charts = [
  {...ECharts 配置},
  {...image_base64: "..."}
]
```

因此同一个状态的 `charts` 可能同时包含结构化配置和图片型图表。前端要根据事件内容判断如何渲染。

## 6. LeadWriter 之后

Writer 读取：

```text
outline、facts、data_points、insights、charts、references
```

写入：

```text
draft_sections = {"sec_1": "...", "sec_2": "..."}
final_report = "完整研究报告..."
references = [...]
phase = reviewing
```

报告存在不代表质量已经通过审核。

## 7. CriticMaster 之后

假设 Critic 发现缺少 2025 年企业数据：

```text
critic_feedback = [{issue_type: "incomplete", severity: "major", ...}]
quality_score = 0.72
unresolved_issues = 1
pending_search_queries = ["2025 新能源汽车企业销量"]
phase = re_researching
iteration = 1
```

Graph 随后再次调用 DeepScout，补充事实，再调用 Writer 重新生成报告。

如果 Critic 判定只需修改表述，`phase` 可能是 `revising`；如果通过或达到最大迭代次数，则进入 `completed`。

## 8. 用状态快照定位问题

| 最后有值的字段 | 最可能的阶段边界 |
|---|---|
| `outline` | Architect 已完成，Scout 之前或 Scout 失败 |
| `facts` | Scout 已有结果，分析提取可能未完成 |
| `data_points` | DataAnalyst 已提取，CodeWizard 可能跳过或失败 |
| `charts` | 分析产物存在，前端事件或渲染可能有问题 |
| `final_report` | Writer 已完成，审核或展示可能有问题 |
| `critic_feedback` | 审核已执行，需检查路由和迭代 |

这是一种“看状态变化定位阶段”的方法，比只看最终错误字符串更有效。

## 9. 代码确定和演示假设的区别

### 代码确定

- POST 研究接口默认 V2。
- V2 `run()` 当前调用 `_run_simplified()`。
- 简化流程按规划、搜索、分析、写作、审核执行。
- Agent 通过状态字段交接，事件通过队列和 SSE 发送。

### 演示假设

- LLM 是否返回五个章节。
- 搜索是否得到某个具体事实。
- 某个公司或年份的具体数值。
- Critic 是否发现某个具体问题。

实际运行时，演示假设必须由日志、SSE 事件和数据库状态验证。

## 10. 本课练习

请用下面格式描述一个故障：

```text
现象：
最后确认有值的字段：
下一步查哪个 Agent 或事件：
需要的证据：
```

题目：`final_report` 有值，但页面没有显示报告。请完成这四行。
