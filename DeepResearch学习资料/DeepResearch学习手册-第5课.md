# DeepResearch 项目学习手册

## 第 5 课：V1 ReAct 链路、工具系统和 V1/V2 选择

本课讲项目中较早的深度研究实现。它仍然被 `/research/stream` 保留为 `version="v1"` 的兼容路径，也是理解“Agent 为什么需要工具、观察和反思”的最好入口。

## 1. V1 的总架构

V1 主链路是：

```text
ResearchService
  -> ReActController
  -> ToolExecutor
  -> 外部搜索 / 本地检索 / Text2SQL / 数据分析 / 图表 / 股票 / 招投标
  -> ReActContext
  -> 反思并补充搜索
  -> _generate_final_report
  -> SSE 字符串事件
```

与 V2 相比，V1 的中心不是一个固定的六阶段状态机，而是“LLM 选择下一步工具”。

## 2. ReAct 的基本概念

ReAct 是 Reasoning + Acting：

```text
Thought   思考下一步要做什么
Action    选择工具并填写参数
Observation 读取工具结果
```

项目中对应的数据类是：

```text
Thought
Action
Observation
ReActStep
ReActContext
```

一次简单循环可能是：

```text
Thought: 先找市场规模数据
Action:  web_search(query="...市场规模", count=5)
Observation: 返回若干网页摘要
Thought: 还缺主要企业数据
Action:  text2sql(question="主要企业营收", intent="comparison")
Observation: 返回结构化数据
```

## 3. `ReActContext` 保存什么

`ReActContext` 是 V1 的局部工作记忆，包含：

| 字段 | 用途 |
| --- | --- |
| `query` | 原始用户问题 |
| `steps` | 每次思考、动作和观察的记录 |
| `observations` | 所有工具观察结果 |
| `collected_data` | 搜索和工具收集的数据 |
| `insights` | 数据分析洞察 |
| `charts` | 图表结果 |
| `metadata` | 知识库名、搜索开关等上下文 |
| `plan` | LLM 生成的研究计划 |
| `executed_queries` | 已执行的查询 |
| `iteration` | 当前反思轮次 |

`add_observation()` 会根据工具类型自动把结果放入不同集合：搜索结果进入 `collected_data`，数据分析结果的 `insights` 进入洞察列表，图表结果进入 `charts`。

## 4. Plan 阶段：先拆子问题

`ReActController._generate_plan()` 调用 LLM，要求返回：

```json
{
  "understanding": "对问题的理解",
  "sub_queries": [
    {
      "query": "具体搜索关键词",
      "purpose": "查询目的",
      "tool": "web_search",
      "priority": 1
    }
  ],
  "strategy": "研究策略",
  "expected_aspects": ["规模", "竞争格局", "风险"]
}
```

如果 LLM 没返回有效子查询，代码会退回到原问题、原问题加“最新动态”、原问题加“分析报告”等默认查询。这种 fallback 是工程上很重要的容错方式。

## 5. Execute 阶段：并行执行

第一轮会选择优先级 1 和 2 的子查询，构造 `Action`，再通过 `asyncio.gather()` 并行执行。

```text
子查询 A -> web_search
子查询 B -> web_search
子查询 C -> knowledge_search
             并行等待
                 -> Observation 列表
```

并行执行的好处是减少多个独立网络请求的总等待时间。工具本身是否能安全并行，仍取决于外部 API 限流和数据库连接池。

## 6. Reflect 阶段：判断是否继续

反思 Prompt 会把下面信息交给 LLM：

```text
原始问题
计划中预期覆盖的方面
已收集数据摘要
已执行查询
```

LLM 返回：

```json
{
  "coverage_analysis": "覆盖度分析",
  "missing_aspects": ["缺少政策数据"],
  "is_sufficient": false,
  "additional_queries": [
    {"query": "行业政策", "purpose": "补充政策", "tool": "web_search"}
  ],
  "confidence": 0.8
}
```

如果 `is_sufficient` 为 false，补充查询进入下一轮；最多运行三轮。项目还会记录已执行查询，避免重复搜索。

## 7. V1 的工具表

`create_default_tools()` 注册八类工具：

| 工具 | 作用 | 实际处理器 |
| --- | --- | --- |
| `web_search` | 搜索互联网 | Bocha API，带进程内缓存 |
| `knowledge_search` | 搜索本地知识库 | Embedding + Milvus |
| `text2sql` | 自然语言查询数据库 | `Text2SQLService` |
| `data_analyzer` | 识别类型、趋势和异常 | `SmartDataAnalyzer` |
| `chart_generator` | 生成 ECharts 配置 | `ChartGenerator` |
| `stock_query` | 查询股票行情 | 聚合数据 API |
| `bidding_search` | 查询招投标 | 81API |
| `finish` | 表示工具研究结束 | 返回统计信息 |

控制器只保存工具定义和 handler 的引用，真正实现由 `ToolExecutor` 提供，再由 `bind_tools_to_controller()` 绑定。这种分离让决策层和执行层可以分别替换或测试。

## 8. `ToolExecutor` 的几个关键实现

### 8.1 Web 搜索

```text
查询参数为空
  -> 回退到原始问题
查询参数正常
  -> 计算 MD5 查询哈希
  -> 命中进程内缓存则直接返回
  -> 否则调用 Bocha
  -> 缓存结果 1 小时
```

这里的缓存是 Python 进程内字典，不是 Redis。服务重启后缓存消失，多进程部署也不会共享。

### 8.2 知识库搜索

工具把知识库检索结果转换成和 Web 结果相同的格式：`url`、`name`、`summary`、`snippet`、`siteName`、`source`。这样后续报告生成不用分别处理两种数据结构。

### 8.3 Text2SQL

工具把用户的自然语言问题交给 Text2SQL 服务。服务返回数据和列，工具本身不重新解释 SQL 安全规则；安全检查集中在 `Text2SQLService`。

### 8.4 数据分析和图表

分析工具默认读取 `context.collected_data`，也可以在参数中传入显式数据。图表工具读取数据、图表类型和标题，返回 ECharts 兼容配置。

### 8.5 股票和招投标

两个工具调用外部服务；成功后会把数据追加到 `context.collected_data`，使它们可以参与后续报告综合。

## 9. V1 的三种去重和缓存

`dr_g.py` 还实现了：

```text
查询哈希缓存
URL 去重
基于分词集合 Jaccard 相似度的摘要去重
```

摘要去重的计算是：

```text
交集词数 / 并集词数
```

默认阈值是 0.8。它是轻量规则，不是向量语义相似度；中文没有分词时，效果也可能有限。

## 10. V1 最终报告生成

`ResearchService._generate_final_report()` 会：

1. 给每条收集内容加 `reference_id`。
2. 发送 `reference_materials` 事件。
3. 将所有摘要、URL、标题拼进综合 Prompt。
4. 要求报告只基于收集信息，不添加外部知识。
5. 要求使用 `##引用编号$$` 标记引用。
6. 用流式 LLM 输出思考和答案事件。
7. 最后发送图表和 `complete`。

报告生成阶段使用另一套流式事件：

```text
thinking_start
thinking
thinking_end
answer_start
answer
answer_end
chart
complete
```

前端 `chat/index.tsx` 同时兼容这套 V1 事件和 V2 事件，因此代码中会看到很多 `json.type` 分支。

## 11. V1 和 V2 的本质差异

| 维度 | V1 ReAct | V2 多 Agent |
| --- | --- | --- |
| 控制方式 | LLM 动态选择工具 | 代码固定阶段顺序，审核后路由 |
| 工作记忆 | `ReActContext` | `ResearchState` |
| 角色划分 | 一个控制器 + 工具 | Architect、Scout、Analyst、Wizard、Writer、Critic |
| 搜索 | 子查询并行，反思补充 | DeepScout 按大纲研究 |
| 分析 | 工具按需调用 | DataAnalyst + CodeWizard 固定阶段 |
| 写作 | 最后一次综合 Prompt | LeadWriter 章节化写作 |
| 审核 | 主要是搜索信息是否足够 | CriticMaster 可决定补搜或修订 |
| 检查点 | V1 主要没有完整状态保存 | V2 保存后端和 UI 状态 |
| 事件 | V1 status/thought/action/observation | V2 phase/research_step/section_content 等 |

当前 POST `/research/stream` 默认 `version="v2"`。只有显式传入 `v1` 才进入旧 `ResearchService`。

## 12. 为什么项目同时保留 V1

保留 V1 有几个工程原因：

```text
兼容已有前端和调用方
保留 ReAct 工具系统作为通用工具层
便于比较固定工作流和动态工具决策
降低一次迁移全部功能的风险
```

但双轨也带来成本：事件协议不同、配置不同、错误处理不同、部分服务重复实现。维护时要先确认请求版本，再追对应代码。

## 13. 旧代码中的安全问题

阅读 `dr_g.py` 时可以发现 API 配置存在硬编码默认值。教材不复制这些值，但你需要把它当成高优先级工程问题：

```text
默认值不应包含真实密钥
密钥应从环境变量或密钥管理系统读取
已暴露的密钥应立即轮换
Git 历史和日志也要检查是否泄露
```

这不是 V1 算法本身的问题，而是部署和凭据管理问题。后续若要上线，必须先处理。

## 14. 本课练习：手工走一轮 V1

问题：

```text
请比较新能源汽车 2024 年市场规模和主要企业竞争格局。
```

请按顺序写出：

```text
1. Plan 生成哪几个子查询？
2. 哪些查询可以并行？
3. 哪些结果进入 collected_data？
4. 反思发现“缺企业利润数据”后生成什么补充查询？
5. 最终报告中的来源如何编号？
```

参考思路：先并行搜索市场规模、企业排名和政策；若需要准确营收/利润，可选择 Text2SQL；所有成功检索结果会进入上下文；补充查询进入下一轮；最终报告按收集数据顺序添加引用编号。

## 15. 面试检查题

### 初级

- ReAct 中 Thought、Action、Observation 分别是什么？
- `ToolExecutor` 为什么不直接由 LLM 调用？
- V1 的 `ReActContext` 保存哪些重要数据？

### 中级

- 为什么 V1 要并行执行子查询？
- 反思阶段如何决定是否继续搜索？
- V1 的摘要去重为什么不等于语义去重？

### 高级

- V1 动态工具选择和 V2 固定角色流程分别适合什么场景？
- 如何让 V1 和 V2 共用一套事件协议，减少前端分支？
- 如果工具调用成功但进程在报告生成前崩溃，V1 如何恢复？需要增加什么状态持久化？

## 16. 本课结论

V1 让你理解 Agent 的最小闭环：

```text
LLM 决策 -> 选择工具 -> 执行工具 -> 观察结果 -> 再决策 -> 综合
```

V2 则把这个闭环拆成更可控、更容易监控和恢复的角色化阶段。两者不是互相否定的实现，而是“动态工具代理”和“固定协作工作流”两种工程取舍。

