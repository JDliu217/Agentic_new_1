# DeepResearch 学习手册·第 53 课

## Agent 的输入、输出和事件契约

本课不把 Agent 当成六个神秘角色，而是把它们看成六个有明确输入输出的处理函数。排错时，先问“哪个字段应该被谁写入”，再问模型回答得好不好。

---

## 1. 所有 Agent 共享同一个基类

源码：backend/app/service/deep_research_v2/agents/base.py。

BaseAgent 提供：

- name：Agent 名称
- role：职责描述
- model：使用的模型
- client：OpenAI 兼容客户端
- process(state)：每个具体 Agent 必须实现
- call_llm(...)：统一调用大模型
- parse_json_response(...)：解析和修复模型 JSON
- add_message(...)：把事件写入状态和消息队列
- add_log(...)：记录执行日志

具体 Agent 只需要实现自己的 process，通用的 LLM 调用、日志和事件出口由基类处理。

---

## 2. LLM 调用为什么放到线程中

BaseAgent.call_llm 使用 asyncio.to_thread 执行同步的 OpenAI 客户端调用：

~~~~python
response = await asyncio.to_thread(
    self.client.chat.completions.create,
    **kwargs
)
~~~~

原因是：

- OpenAI 客户端调用在这里是同步函数。
- Agent process 是异步函数。
- 直接执行同步网络调用可能阻塞事件循环。
- 放到线程中可以让事件循环继续处理其他异步工作。

这里的线程不是多 Agent 并行编排。当前 Graph 仍然按阶段依次执行 Agent；线程主要是避免同步 LLM 调用卡住异步循环。

---

## 3. 为什么多数 Agent 要求 JSON 输出

call_llm 默认 json_mode=True，并设置：

~~~~python
response_format = {"type": "json_object"}
~~~~

因为后续代码需要读取结构化字段，例如：

- outline
- research_questions
- facts
- data_points
- charts
- critic_feedback
- fixed_code

如果模型只返回自然语言，程序很难稳定地把结果写入 ResearchState。

BaseAgent.parse_json_response 还处理多种常见异常：

1. 直接 json.loads。
2. 从 Markdown JSON 代码块中提取。
3. 从最外层大括号中提取。
4. 修复尾随逗号、注释和部分非法转义。
5. 最后尝试 ast.literal_eval。

这属于容错层，不是保证模型永远输出正确 JSON。解析失败时返回空字典，具体 Agent 需要根据空结果决定记录错误、重试或跳过。

---

## 4. add_message 是实时 UI 的共同出口

BaseAgent.add_message 生成统一消息：

~~~~text
{
  type: 事件类型,
  agent: Agent名称,
  timestamp: 时间,
  content: 事件内容
}
~~~~

然后做两件事：

1. 追加到 state.messages。
2. 如果 state 中存在 _message_queue，立即 put_nowait。

所以同一条消息有两个用途：

- state.messages：后端当前状态和检查点可以使用。
- asyncio.Queue：Graph 可以立即 yield 给 SSE。

它们不是两份互相独立的业务结果，而是同一事件的状态记录和实时传输出口。

---

## 5. ChiefArchitect 的契约

源码：agents/architect.py。

### 输入

- state.query
- state.phase
- 原始研究问题

### 主要工作

- 理解用户问题。
- 生成 5 到 8 个左右的研究章节。
- 为章节生成 description、section_type、requires_data、requires_chart。
- 为每个章节生成 search_queries。
- 生成 research_questions、hypotheses、key_entities。

### 写入字段

- outline
- research_questions
- hypotheses
- key_entities
- mind_map
- knowledge_graph 的初始空结构

### 事件

- research_step：规划开始和完成
- thought：当前正在分析问题
- outline：研究大纲和核心问题

### 失败时

它有有限重试。解析失败或大纲太短，会用更简单的 Prompt 重试；多次失败后会向 state.errors 写入错误。

如果最终 outline 为空，后续 DeepScout 没有可靠的章节和查询，搜索阶段的结果质量就会受到影响。

---

## 6. DeepScout 的契约

源码：agents/scout.py。

### 输入

- outline
- research_questions
- search_web
- search_local
- pending_search_queries
- query

### 主要工作

- 按章节和查询词搜索网络。
- 可选地搜索本地知识库。
- 提取来源、事实和数据点。
- 发现实体和关系。
- 必要时处理股票行情等相关数据。

### 写入字段

- raw_sources
- facts
- references
- data_points
- knowledge_graph
- pending_search_queries 的处理结果

### 事件

- research_step
- search_progress
- search_results
- fact 或进度类消息
- knowledge_graph 相关更新

DeepScout 是证据生产者。它没有证据时，DataAnalyst 没有可靠数据可分析，LeadWriter 也只能写出缺少来源的报告。

---

## 7. DataAnalyst 的契约

源码：agents/data_analyst.py。

### 输入

- facts
- query
- 已有 data_points

### 主要工作

1. 从事实中提取结构化数据。
2. 构建知识图谱。
3. 根据时间序列、分布和数据点生成 ECharts 配置。

### 写入字段

- data_points
- insights
- knowledge_graph
- charts

### 事件

- research_step
- knowledge_graph
- charts
- research_step completed

如果 facts 有内容但 charts 为空，先检查 DataAnalyst 的结构化数据提取和图表生成条件，不要先去改前端图表组件。

它在没有足够数据时会主动跳过图表生成，这是“没有可画的数据”和“图表组件坏了”两种不同情况。

---

## 8. CodeWizard 的契约

源码：agents/wizard.py。

### 输入

- data_points
- outline
- query
- phase

### 主要工作

- 让 LLM 根据数据生成 Python 分析代码。
- 清理代码并用 compile 检查语法。
- 在受限执行环境中执行。
- 失败后把错误反馈给 LLM，尝试修复。
- 记录输出和图像结果。

### 写入字段

- code_executions
- charts
- insights 或执行相关结果

### 事件

- thought
- code
- code_result
- chart
- error

这里的 compile 只是语法编译检查，不是安全沙箱。当前实现使用进程内执行和限制 globals，生产环境仍需要独立进程、容器或更强隔离。

如果 data_points 少于设定条件，CodeWizard 可能跳过分析。此时 charts 为空可能是输入不足，不一定是代码执行失败。

---

## 9. LeadWriter 的契约

源码：agents/writer.py。

### 输入

- outline
- facts
- data_points
- charts
- insights
- references
- query
- critic_feedback（修订时）

### 主要工作

- 按大纲生成章节草稿。
- 把证据、数据和图表说明组织成报告。
- 汇总章节为 final_report。
- 根据审核反馈重写或修订。

### 写入字段

- draft_sections
- final_report
- references
- 章节状态

### 事件

- research_step
- section 或报告进度事件
- report 相关消息

LeadWriter 不是搜索器。报告看起来完整，不代表所有章节都有足够证据；要结合 facts、references 和每个章节的来源检查覆盖率。

---

## 10. CriticMaster 的契约

源码：agents/critic.py。

### 输入

- final_report 或 draft_sections
- facts
- references
- outline
- data_points

### 主要工作

- 检查缺失来源。
- 检查逻辑错误和数据矛盾。
- 检查偏见、幻觉、过时内容和不完整章节。
- 给出严重程度和修复建议。

### 写入字段

- critic_feedback
- unresolved_issues
- quality_score
- pending_search_queries
- phase

### 结果分流

- 需要补证据：phase 变为 re_researching。
- 只需文字修改：phase 变为 revising。
- 没有严重问题：phase 变为 completed。

CriticMaster 的价值是把“生成了一篇文章”转成“这篇文章是否有证据和逻辑保障”的检查结果。

---

## 11. 一张责任矩阵

| 结果字段 | 主要责任 Agent | 失败时第一检查点 |
|---|---|---|
| outline | ChiefArchitect | LLM JSON 和重试日志 |
| facts | DeepScout | 搜索 API、查询词和解析 |
| references | DeepScout/Graph | 来源是否写入和转换 |
| data_points | DeepScout/DataAnalyst | 事实格式和结构化提取 |
| knowledge_graph | DeepScout/DataAnalyst | 图谱 Prompt 和节点关系 |
| charts | DataAnalyst/CodeWizard | 数据量、ECharts 配置、代码执行 |
| code_executions | CodeWizard | compile、执行错误和修复次数 |
| draft_sections | LeadWriter | 大纲和证据映射 |
| final_report | LeadWriter | 章节草稿、模型响应和备用报告 |
| critic_feedback | CriticMaster | 审核输入和 JSON 解析 |
| quality_score | CriticMaster | 审核输出字段 |
| SSE 事件 | BaseAgent/Graph | add_message、Queue 和前端 parseData |

---

## 12. 一个实用的定位例子

现象：前端研究步骤显示“数据分析完成”，但没有图表。

按责任矩阵排查：

1. DeepScout 是否产生 facts？
2. DataAnalyst 是否产生 data_points？
3. DataAnalyst 是否因数据不足主动返回空 charts？
4. CodeWizard 是否因 data_points 少于条件而跳过？
5. 是否发出了 charts 或 chart 事件？
6. Graph 是否从 Queue yield 出事件？
7. React 是否把事件放入 analyzing detail？
8. 最后才检查图表组件渲染。

这样可以把“没有图表”拆成输入不足、Agent 跳过、事件丢失和 UI 渲染四类问题。

---

## 13. 小练习

现象：facts 有 20 条，研究页面能显示搜索结果，但 charts 数组为空。第一责任对象是谁？

A. DataAnalyst，先检查结构化数据提取和图表生成条件

B. 只检查 React CSS

C. 只检查 CriticMaster

D. 只检查 PostgreSQL 用户表

请回答选项并说明：为什么 DeepScout 已经有 facts，仍然不代表一定会有 charts。

---

## 留白：Agent 契约笔记

ChiefArchitect 写入：

DeepScout 写入：

DataAnalyst 写入：

CodeWizard 写入：

LeadWriter 写入：

CriticMaster 写入：

我最容易混淆的两个 Agent：

---

## 源码定位

- backend/app/service/deep_research_v2/agents/base.py：基类、LLM、JSON、事件和日志
- backend/app/service/deep_research_v2/agents/architect.py：规划
- backend/app/service/deep_research_v2/agents/scout.py：搜索和证据
- backend/app/service/deep_research_v2/agents/data_analyst.py：结构化数据、图谱和 ECharts
- backend/app/service/deep_research_v2/agents/wizard.py：代码执行和自修复
- backend/app/service/deep_research_v2/agents/writer.py：写作和修订
- backend/app/service/deep_research_v2/agents/critic.py：审核和分流
- backend/app/service/deep_research_v2/state.py：共享状态字段

