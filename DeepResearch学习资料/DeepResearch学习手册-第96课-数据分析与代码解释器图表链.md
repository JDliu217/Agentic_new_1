# DeepResearch 学习手册：第 96 课

## DataAnalyst 与 CodeWizard：两条图表生成链

搜索阶段结束后，`ResearchState` 通常已经有 `facts`、`references`，有时还会有搜索阶段直接得到的 `data_points`。接下来项目有两个不同的数据分析角色。

## 1. DataAnalyst 先把文本变成结构化数据

源码：

```text
backend/app/service/deep_research_v2/agents/data_analyst.py
```

当 `state["phase"] == "analyzing"` 时，DataAnalyst 依次做三件事：

```text
facts
→ 提取 data_points、time_series、distributions、insights
→ 构建 knowledge_graph
→ 生成 ECharts 配置
```

### 1.1 提取数据

它从最多 20 条事实中拼接文本，调用 LLM 输出结构化 JSON。结果中的数据点会追加到：

```text
state["data_points"]
```

洞察会追加到：

```text
state["insights"]
```

### 1.2 构建知识图谱

它从最多 15 条事实中提取实体和关系，生成：

```json
{
  "nodes": [],
  "edges": []
}
```

节点会根据 `importance` 计算展示大小，然后写入：

```text
state["knowledge_graph"]
```

并发送 `knowledge_graph` 事件。

### 1.3 生成 ECharts 图表

DataAnalyst 生成的是结构化图表配置，例如：

```json
{
  "id": "chart_001",
  "title": "新能源汽车销量趋势",
  "type": "line",
  "echarts_option": {}
}
```

这些配置写入：

```text
state["charts"]
```

并通过 `charts` 事件发送给前端，前端再交给 ECharts 渲染。

## 2. CodeWizard 让 LLM 生成并执行 Python

源码：

```text
backend/app/service/deep_research_v2/agents/wizard.py
```

它主要读取：

```text
state["data_points"]
state["outline"]
state["query"]
```

基本流程是：

```text
数据点
→ LLM 生成 Python
→ 清理代码
→ compile() 语法检查
→ 危险模式检查
→ exec() 执行
→ 捕获 stdout、stderr 和 PNG
→ 写入 code_executions/charts
```

## 3. `compile()` 和 `exec()` 的区别

```python
compile(code, "<string>", "exec")
```

只是在执行前检查代码能不能被 Python 解析。它不会运行代码，也不会判断代码是否安全。

```python
exec(code, exec_globals)
```

才是真正执行 LLM 生成的代码。

项目在两者之间增加了危险模式检查，并用受限的 globals 执行。这可以减少明显错误，但不能替代独立沙箱。

## 4. CodeWizard 的自愈流程

如果代码执行失败，CodeWizard 会把错误反馈给 LLM，让 LLM 重新生成修复代码。

```text
第一次执行失败
→ 读取错误信息
→ LLM 修复
→ 再次执行
→ 最多重试 3 次
```

每次最终结果会记录到：

```text
state["code_executions"]
```

里面包含代码、输出、错误、图表和重试次数。

## 5. 两种图表的根本区别

| 维度 | DataAnalyst | CodeWizard |
|---|---|---|
| 输入 | 搜索事实文本 | 结构化数据点 |
| LLM 输出 | ECharts JSON 配置 | Python 源代码 |
| 是否执行代码 | 否 | 是 |
| 图表形式 | 浏览器端 ECharts | Python 生成 PNG/Base64 |
| 主要状态 | `charts`、`knowledge_graph`、`insights` | `code_executions`、`charts` |
| 主要风险 | JSON 结构错误、数据抽取错误 | 代码安全、资源耗尽、执行失败 |
| 前端事件 | `charts`、`knowledge_graph` | `code`、`code_result`、`chart` |

两者都可能写入 `state["charts"]`，所以最终页面需要根据图表字段判断是 ECharts 配置还是图片型图表。

## 6. 一条具体数据流

```text
DeepScout 写入 facts
→ DataAnalyst 从 facts 提取 data_points
→ DataAnalyst 生成 ECharts 配置
→ CodeWizard 读取 data_points
→ LLM 生成 Python
→ Python 计算和绘图
→ CodeWizard 把 PNG 转 Base64
→ state["charts"]
→ asyncio.Queue
→ chart/charts SSE
→ React 研究详情页
```

## 7. 真实工程边界

### 数据点不足

CodeWizard 会检查数据点数量。如果不足，可能跳过代码分析；因此“分析阶段执行了”不等于“必然有图表”。

### 结构化配置和图片不能混为一谈

ECharts 图表需要前端解释 `echarts_option`。PNG 图表只需要把 Base64 图片展示出来。排错时先确认图表类型和字段，再检查 React 分支。

### 执行成功不等于分析可信

Python 能运行，只说明代码没有抛出错误。数据来源、单位、年份、异常值和统计方法仍需由事实来源和审核 Agent 检查。

### 进程内执行不是生产隔离

正则检查、受限 globals 和 `exec()` 不能真正隔离文件系统、网络、系统调用、CPU、内存和运行时间。生产环境应使用独立进程、容器或专用代码执行服务。

## 8. 本课练习

1. DataAnalyst 和 CodeWizard 的输入分别是什么？
2. 为什么 `compile()` 不能证明代码安全？
3. 如果前端没有显示 CodeWizard 生成的图片，你会检查哪三个地方？
4. 如果 `state["facts"]` 有很多内容但 `state["data_points"]` 为空，应该优先检查哪个 Agent？为什么？
