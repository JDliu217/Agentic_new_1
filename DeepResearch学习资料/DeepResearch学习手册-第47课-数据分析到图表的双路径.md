# DeepResearch 学习手册：第 47 课

## DataAnalyst 到 CodeWizard：图表的双路径

项目中“生成图表”不是一个动作，而是两条互补路径：DataAnalyst 生成结构化分析和 ECharts 配置，CodeWizard 执行 Python 并生成需要计算或图片输出的图表。

## 1. DataAnalyst 先处理语义结构

DataAnalyst 接收搜索阶段得到的 `facts` 和已有 `data_points`，通过 LLM 结构化提取：

```text
事实文本
  → data_points
  → time_series / distributions
  → insights
  → knowledge_graph
  → ECharts option
```

它会把结果写入：

```text
state["data_points"]
state["insights"]
state["knowledge_graph"]
state["charts"]
```

同时发送 `knowledge_graph` 和 `charts` 事件，让前端能较早展示结构化分析结果。

## 2. CodeWizard 再执行代码

CodeWizard 的重点不是理解所有文本，而是处理需要真实计算的任务：

```text
数据点和分析任务
  → LLM 生成 Python
  → compile() 语法检查
  → 危险模式检查
  → exec() 执行
  → 捕获 stdout/stderr
  → 捕获 matplotlib 图片
  → state["code_executions"] / state["charts"]
```

它发送的事件通常包括 `code`、`code_result` 和 `chart`。如果代码失败，会把错误交回 LLM，尝试自动修复。

## 3. 两者为什么不能合并成一个 Agent

DataAnalyst 主要解决：

- 从非结构化事实中提取数据。
- 识别实体、关系和趋势。
- 生成前端可理解的 ECharts 配置。

CodeWizard 主要解决：

- 运行 Python 计算。
- 计算 CAGR、同比、预测等指标。
- 生成 matplotlib 图片。
- 记录执行代码和错误。

前者偏“语义分析和结构化”，后者偏“可执行计算和运行时产物”。拆开后，写作 Agent 可以同时读取配置图表和代码执行结果。

## 4. 当前简化流程中的真实顺序

`graph.py` 的分析阶段是：

```text
state["phase"] = "analyzing"
  → self.data_analyst.process(state)
  → self.wizard.process(state)
  → save_checkpoint_async()
```

所以如果 `facts` 已经有内容但 `charts` 为空，先检查 DataAnalyst 是否成功完成；如果 DataAnalyst 已产生 ECharts 配置，但需要计算的图片缺失，再检查 CodeWizard。

## 5. 前端的两种图表来源

前端研究详情可能收到：

```text
DataAnalyst 的 charts 事件
  → echarts_option
  → ECharts 组件渲染

CodeWizard 的 chart 事件
  → image_base64 或执行结果
  → 图表/报告组件展示
```

因此“图表数量增加”不能直接说明 Python 代码执行成功；要检查事件类型、图表字段和 `code_executions`。

## 6. 本课练习

1. DataAnalyst 产生 ECharts 配置后，为什么仍可能需要 CodeWizard？
2. 如果 DataAnalyst 没有提取出 `data_points`，CodeWizard 可能遇到什么问题？
3. 如何从 `state["code_executions"]` 判断代码是成功还是失败？
4. 为什么前端不能只根据 `charts_count` 判断图表是配置图还是 PNG 图片？

## 7. 关键源码

- `backend/app/service/deep_research_v2/graph.py:610-629`
- `backend/app/service/deep_research_v2/agents/data_analyst.py:256-445`
- `backend/app/service/deep_research_v2/agents/wizard.py:350-706`
- `frontend/src/components/chart/index.tsx`
- `frontend/src/pages/chat/component/research-detail/visualization.tsx`

