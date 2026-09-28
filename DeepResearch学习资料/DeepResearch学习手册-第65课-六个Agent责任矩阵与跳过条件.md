# DeepResearch 学习手册·第 65 课

## 六个 Agent：责任矩阵、状态字段和跳过条件

看 Agent 代码时，最重要的不是背类名，而是回答三件事：

1. 它在什么 `phase` 执行？
2. 它读取和写入哪些状态字段？
3. 什么条件会让它跳过、失败或改变下一阶段？

---

## 1. ChiefArchitect：规划和大纲

文件：`agents/architect.py`。

主要输入：

- `state["query"]`
- 当前已有 `outline`
- 已有 `facts`、`data_points`

主要输出：

- `outline`
- `research_questions`
- `key_entities`
- `hypotheses`
- 初始化 `knowledge_graph`

LLM 返回结果为空或大纲不足时会重试；仍然失败则向 `state["errors"]` 写入错误并返回。

成功后发送 `outline` 和 `research_step` 事件，并把阶段设置为 `planning`。

排错重点：

```text
没有 outline
→ 看 LLM 原始响应、JSON 解析和重试

outline 太短
→ 看结果校验和 fallback Prompt

outline 有章节但没有搜索词
→ 看 search_queries 的默认补全
```

---

## 2. DeepScout：搜索和事实收集

文件：`agents/scout.py`。

主要输入：

- `outline`
- `search_web`
- `search_local`
- `pending_search_queries`
- `query`

主要输出：

- `facts`
- `raw_sources`
- `data_points`
- 部分 `knowledge_graph`
- 搜索结果事件

它只取 `pending_sections[:3]`，因此一次研究轮次最多处理三个待研究章节；大纲比三个章节长时，剩余章节可能继续保持 pending。

如果网络和本地搜索开关都为 false，代码会警告并退回网络搜索：

```text
search_web=False
search_local=False
  → search_web=True
```

这会造成“用户没有选择搜索模式，但实际仍然访问网络”的行为，排错时要看最终写入 `ResearchState` 的开关。

---

## 3. DataAnalyst：结构化分析、图谱和 ECharts

文件：`agents/data_analyst.py`。

只有当 `state["phase"] == "analyzing"` 时才处理。

主要步骤：

```text
facts
  → 提取结构化数据
  → 构建 knowledge_graph
  → 生成 ECharts 配置
  → 写入 state["charts"]
```

它产生的图表通常带有 `echarts_option`，前端可以直接交给 ECharts 渲染。

它还会发送：

- `research_step`
- `knowledge_graph`
- `charts`

排错重点：

- facts 为空时，结构化数据不足。
- LLM JSON 解析失败时，图表可能为空。
- 后端 `state["charts"]` 有数据但无 `charts` 事件时，看 `add_message()` 和消息队列。

---

## 4. CodeWizard：代码生成和执行图表

文件：`agents/wizard.py`。

它在分析阶段执行，主要读取：

- `data_points`
- `query`
- `outline`

主要输出：

- `code_executions`
- 代码事件 `code`
- 执行结果事件 `code_result`
- 图片图表事件 `chart`
- 可能追加 `state["charts"]`

它的代码链路是：

```text
LLM 生成 Python
  → 清理代码
  → compile() 语法检查
  → 危险模式和格式检查
  → 执行
  → 失败时把错误反馈给 LLM 修复
  → 最多重试 3 次
  → 记录 code_executions
```

CodeWizard 产生的图表通常是 `image_base64`，与 DataAnalyst 的 ECharts 配置来源不同。

注意：`compile()` 和进程内执行不是生产级沙箱。它能提供项目演示能力，但不能隔离恶意代码、资源耗尽或系统调用风险。

---

## 5. LeadWriter：报告生成

文件：`agents/writer.py`。

它在 `writing` 或 `revising` 阶段执行。

主要读取：

- `outline`
- `facts`
- `data_points`
- `charts`
- `insights`
- `references`
- `critic_feedback`（修订时）

主要输出：

- `draft_sections`
- `final_report`
- `references`

写作完成后把阶段设置为 `reviewing`。如果 CodeWizard 前面失败，LeadWriter 仍可能拿到事实和部分图表，但报告输入是不完整的；这不应只通过修改前端报告组件解决。

---

## 6. CriticMaster：审核和路由

文件：`agents/critic.py`。

只有 `phase == "reviewing"` 时处理。

主要输入：

- `final_report`
- `outline`
- `facts`
- `data_points`

主要输出：

- `critic_feedback`
- `quality_score`
- `unresolved_issues`
- `pending_search_queries`
- 下一阶段 `phase`

它根据审核结果做三种决定：

```text
verdict=pass
  → completed

需要补事实
  → re_researching

只需修改文字
  → revising
```

达到 `max_iterations` 时会强制完成，并发出 warning，即使仍有未解决问题。

---

## 7. 两个图表来源必须分开

V2 的分析阶段实际顺序是：

```text
DataAnalyst
  → charts 事件
  → ECharts option

CodeWizard
  → chart 事件
  → image_base64
```

两者都可能更新 `state["charts"]`，但事件类型、数据格式和前端渲染方式不同。

所以：

- `facts` 有、`charts` 为空：优先查 DataAnalyst/CodeWizard。
- `charts` 有、ECharts 空白：优先看图表格式和前端组件。
- `chart` 事件有、`charts` 事件没有：不一定是错误，可能只执行了 CodeWizard 路径。

---

## 8. 综合故障判断

场景：

```text
research_step 已出现
search_results 已出现
CodeWizard 执行失败
research_complete 没有出现
```

能证明：

- 规划阶段已经产生了可用的研究结构，或至少前端收到了研究步骤。
- DeepScout 至少产生过搜索结果。
- 请求已经进入分析阶段。

下一步检查：

1. `state["data_points"]` 是否足够。
2. `state["code_executions"]` 的 `error`、`retries`、`output`。
3. 是否出现 `code_result` 且 `success=false`。
4. `state["charts"]` 是否有 DataAnalyst 图表。
5. CodeWizard 的 LLM 响应、清理、语法检查和执行日志。
6. LeadWriter 是否被调用，以及 `final_report` 是否为空。

不能只改前端报告组件，因为后端可能根本没有完成写作阶段，也没有产生可展示的最终报告。

---

## 练习

请用一句话分别说明：

1. DataAnalyst 和 CodeWizard 的图表输出有什么不同？
2. DeepScout 为什么可能只研究前三个章节？
3. CriticMaster 为什么可能让流程回到搜索阶段？

参考答案：DataAnalyst 主要产生 ECharts 配置，CodeWizard 主要执行 Python 并产生图片；DeepScout 使用 `pending_sections[:3]`；审核发现事实缺失时会设置 `re_researching` 和 `pending_search_queries`。

