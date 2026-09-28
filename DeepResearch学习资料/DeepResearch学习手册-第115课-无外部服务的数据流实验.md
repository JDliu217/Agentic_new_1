# DeepResearch 学习手册·第 115 课：无外部服务的数据流实验

## 1. 实验目的

前面课程讲的是项目真实源码。这次先用一个很小的模拟器观察同样的数据形状：

```text
共享状态逐步增长
→ 每个阶段发出事件
→ 事件被格式化成 SSE
→ 网络把一条消息拆成多个片段
→ 浏览器缓冲后再解析
```

它不替代真实项目，只用于理解主链路中最容易抽象的部分。

## 2. 运行实验

在 PowerShell 中执行：

```powershell
python "C:\Users\11853\Documents\Codex\2026-09-27\e-desk-desktop-git-agentic-new\outputs\DeepResearch最小数据流演示.py"
```

预期输出形状：

```text
事件顺序: research_start -> research_step -> search_results -> charts -> report_draft -> research_complete
最终阶段: reviewing
事实数量: 2
图表数量: 1
报告: 示例研究报告：市场增长，竞争集中。
```

## 3. 代码和真实项目的对应关系

| 实验代码 | 真实项目 |
|---|---|
| `initial_state()` | `deep_research_v2/state.py::create_initial_state()` |
| `state` 字典 | `ResearchState` |
| `run_agents()` | `graph.py::_run_simplified()` 调用六个 Agent |
| `format_sse()` | `service.py::_format_sse()` |
| `parse_sse_chunks()` | `frontend/src/pages/chat/index.tsx` 的 `ReadableStream` 读取和缓冲 |
| `facts/charts/final_report` | Agent 写回共享状态的真实字段 |

## 4. 你应该观察什么

### 观察一：状态和事件不是一回事

`state["final_report"]` 是后端状态里的值；`research_complete` 是把结果告诉前端的事件。只有状态写入、事件发送、前端解析和 React 更新都成功，页面才会显示报告。

### 观察二：网络分块不等于业务事件

脚本把完整 SSE 文本每 13 个字符切开。一个网络片段可能只有半个 JSON，因此解析器必须先把片段拼回完整的 `data: ...\n\n` 块。

### 观察三：阶段顺序来自执行器

示例顺序是规划、搜索、分析、写作、审核。真实项目的 `_run_simplified()` 在分析阶段依次调用 `DataAnalyst` 和 `CodeWizard`，审核还可能重新搜索或重新写作。

## 5. 实验后的四个问题

请运行脚本后回答：

1. 如果删除 `parse_sse_chunks()` 中的 `buffer += chunk`，会出现什么问题？
2. 如果只给 `state["final_report"]` 赋值，不发送 `research_complete`，前端为什么可能没有报告？
3. 真实项目中哪个对象承担了实验脚本中 `state` 的角色？
4. 实验输出能证明真实 LLM、Milvus 和 PostgreSQL 已经可用吗？为什么？

## 6. 学习边界

这个实验只证明本地 Python 解释器能运行教学代码，并不证明原项目的外部依赖已经启动。真实项目仍需 Docker、数据库、Milvus、外部 LLM 和搜索 API 才能做端到端验收。

