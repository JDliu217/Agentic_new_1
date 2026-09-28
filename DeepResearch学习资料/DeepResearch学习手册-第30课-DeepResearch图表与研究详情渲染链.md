# DeepResearch 学习手册·第 30 课

## DeepResearch 图表与研究详情渲染链

上一课讲的是数据库页面的 Text2SQL。那条路径返回 visualization_hint，但数据库页面当前只展示结果表格。本课讲另一条真正会渲染图表的路径：DeepResearch V2 的 DataAnalyst、SSE、React 状态、检查点和 ECharts。

源码依据：

    D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\agents\data_analyst.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\graph.py
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\chat\index.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\chat\component\research-detail\index.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\chat\component\research-detail\visualization.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\chat\component\research-detail\process-report.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\components\chart\index.tsx

---

## 1. 两条“图表”概念不能混用

项目中有两个容易被叫成“图表”的结果：

    数据库页 Text2SQL：
      LLM 返回 visualization_hint
      页面当前显示 SQL、解释和表格

    DeepResearch V2：
      DataAnalyst 生成完整 echarts_option
      通过 charts SSE 事件传给聊天页
      研究详情页用 ECharts 真正渲染

所以看到 visualization_hint="line"，不能推断数据库页已经显示折线图；而在 DeepResearch 研究详情中，charts 事件包含完整配置时，才有真正绘图所需的数据。

---

## 2. DataAnalyst 的输入

DataAnalyst.process(state) 只在 state["phase"] == "analyzing" 时执行。它会先发送一个 research_step 开始事件：

    {
      "type": "research_step",
      "content": {
        "step_type": "analyzing",
        "title": "数据分析",
        "subtitle": "生成可视化",
        "status": "running"
      }
    }

随后它从 state["facts"] 中取最多 20 条事实，拼成数据提取 Prompt。LLM 被要求识别市场规模、增长率、市场份额、排名和时间序列，并返回 data_points、time_series、distributions、insights。提取出的 data_points 会追加回 state["data_points"]，洞察会追加回 state["insights"]。

---

## 3. 同一个 Agent 还构建知识图谱

DataAnalyst 接着从最多 15 条事实提取文本，调用知识图谱 Prompt，返回 nodes 和 edges。代码会根据 importance 计算节点 size，再写入 state["knowledge_graph"]，同时发送 knowledge_graph 事件。

因此“数据分析阶段”不只生成图表，也负责知识图谱。二者由同一个 Agent 产出，但在前端是两个独立的数据字段和两个展示区域。

---

## 4. 图表配置如何生成

DataAnalyst 把 data_points、time_series、distributions 和已有 state.data_points 的前 10 条数据放进图表 Prompt。LLM 被要求返回 charts 数组，每个图表包含 id、title、subtitle、type 和 echarts_option。

如果 LLM 没有提供 id，代码会补一个随机 ID。图表生成逻辑本身没有调用通用的 ChartGenerator 类；V2 DataAnalyst 是通过自己的 Prompt 直接让 LLM 生成 ECharts 配置。

这解释了为什么项目同时存在 service/chart_generator.py 和 DataAnalyst 的图表生成 Prompt。前者是通用工具，后者是当前 V2 主流程中的 Agent 实现，不能把两者混为同一个调用点。

---

## 5. 后端状态和 SSE 事件

DataAnalyst 生成图表后执行：

    state["charts"].extend(charts)
    self.add_message(state, "charts", {"charts": charts})

随后发送 research_step 完成事件，其中包含 results_count、charts_count 和 entities_count。

graph.py 的 _run_simplified() 使用 asyncio.Queue：

    Agent.add_message()
      → 放入 state["_message_queue"]
      → graph.run_agent_with_streaming() 读取
      → yield 给 research_router
      → StreamingResponse 输出 SSE

因此浏览器收到的 charts 不是前端自己计算出来的，而是后端 Agent 产生并通过队列转发的。

---

## 6. 前端收到 charts 后发生什么

聊天页 index.tsx 对每条 SSE JSON 做类型分发。当 json.type === "charts" 时，代码执行：

    content.charts
      → 找到 researchDetailsRef.current.get("analyzing")
      → detail.charts = charts
      → 更新 analyzing 步骤的 chartsCount
      → setSelectedResearchDetail({...detail})
      → researchDataVersion + 1

同时，当前聊天消息的 target.charts 也会追加这些图表，供报告和恢复使用。

researchDataVersion 的作用是触发依赖它的 useMemo 重新计算。因为部分研究详情数据存放在 useRef(Map) 中，单纯修改 Map 不会自动触发 React 渲染，所以代码显式维护版本号。

---

## 7. 多个步骤如何汇总到右侧面板

聊天页会遍历 researchDetailsRef.current 中的每个步骤，聚合出 allSearchResults、knowledgeGraph、allCharts、streamingReport 和 allSections，最后生成 aggregatedResearchData，交给 ResearchDetail。

ResearchDetail 提供四个标签：

    搜索结果
    知识图谱
    可视化图表
    过程报告

点击“可视化图表”时，组件把 data.charts 传给 Visualization。

---

## 8. ECharts 真正渲染位置

visualization.tsx 对每个图表做三路判断：

    有 image_base64
      → 使用 data:image/png;base64 图片

    没有图片但有 echarts_option
      → 使用 ReactECharts option={chart.echarts_option}

    两者都没有
      → 显示图表数据加载中占位

完整的渲染证据是：

    后端 charts 事件
      → detail.charts
      → aggregatedResearchData.charts
      → Visualization
      → ReactECharts

另一个 components/chart/index.tsx 是通用图表组件，使用动态加载的 echarts 和 setOption()；它支持 line、bar、pie、scatter、table。研究详情当前使用的是 echarts-for-react 的专用组件和自己的 Visualization，不是简单地从数据库页复用同一个组件。

---

## 9. 图表如何插入最终报告

ProcessReport 不只在独立的“可视化图表”标签中展示图表。它还会解析最终 Markdown 报告：

    1. 查找 Markdown 图片占位符
    2. 根据 alt 文本与图表标题做相似度匹配
    3. 将匹配的图表插入对应位置
    4. 对仍未使用的图表按章节标题分配
    5. 找不到章节时放在参考文献之前或末尾

这是前端排版策略。报告文本中的图片占位符不一定是真实图片 URL，前端会尝试用后端传来的图表配置替换它。因此报告中出现图表还依赖图表有有效标题、报告中有可匹配的占位符或章节标题，并且配置包含 echarts_option 或 image_base64。

---

## 10. 检查点如何保存和恢复图表

graph.py 每个阶段会调用 save_checkpoint_async()。保存前先执行 update_ui_state()，把 state.charts、state.knowledge_graph、state.final_report 和 state.facts 同步到 ui_state。检查点中的图表位置是 checkpoint.ui_state_json.charts。

页面重新打开时调用 GET /research/checkpoint/{session_id}/full，然后把 ui_state_json.charts 恢复到 analyzing 详情，并把图表附加到聊天消息。这样即使 SSE 已经结束，页面仍可以从检查点重新显示图表。

---

## 11. 这条链路的几个风险

### 11.1 SSE 事件和步骤必须按时到达

charts 事件到达时，前端查找的是 analyzing 详情。如果前端还没有初始化该步骤，代码找不到目标详情，图表就可能不会进入对应步骤。当前代码有日志帮助发现这个问题，但没有通用事件重放队列。

### 11.2 LLM 输出的 ECharts 配置需要校验

后端主要依赖 JSON 解析，没有看到针对每个 ECharts 字段的严格 Schema 校验。模型返回错误的 series、坐标轴或类型时，前端可能只显示空白图表或渲染错误。

### 11.3 图表 ID 可能重复

只有缺少 ID 时才补随机 ID。如果模型自己生成重复 ID，React 的 key 和报告匹配可能受影响。

### 11.4 图表来源是模型提取结果

DataAnalyst 从搜索事实中提取数字，再让模型生成图表。图表看起来正常不等于数据已经经过独立统计校验，报告中仍然需要结合来源和证据检查。

---

## 12. 一句话面试回答

DeepResearch V2 的图表不是数据库页面 Text2SQL 的 visualization_hint 直接渲染出来的。DataAnalyst 从 DeepScout 收集的 facts 中提取结构化数据和图表配置，写入 ResearchState，并通过 asyncio 队列转成 charts SSE 事件。聊天页收到事件后保存到 analyzing 详情和当前消息，再聚合到 ResearchDetail；Visualization 使用 ECharts 渲染，ProcessReport 还会按报告占位符和章节标题把图表插入最终报告。检查点保存 ui_state_json.charts，页面重开时可以恢复。当前风险是模型图表配置缺少严格 Schema 校验，且事件到达早于步骤初始化时可能丢失。

---

## 13. 练习

1. 数据库页面的 visualization_hint 和 DeepResearch 的 charts 事件有什么区别？
2. DataAnalyst 从 ResearchState 的哪些字段取数据？
3. state["charts"] 和 charts SSE 事件分别解决什么问题？
4. 为什么前端需要 researchDataVersion？
5. 右侧研究详情的图表最终由哪个组件调用 ECharts？
6. 页面重新打开时，图表从哪个检查点字段恢复？
7. 如果收到 charts 事件但页面没有图表，你会按什么顺序排查？

---

## 14. 留给你的笔记区

### 14.1 我画的图表数据流



### 14.2 我认为最需要补强的地方



