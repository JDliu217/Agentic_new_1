# DeepResearch 第118课：图表不显示的完整排错链

## 目标

把图表为空拆成可验证的层次：

data_points → DataAnalyst 或 CodeWizard → ResearchState charts → add_message → asyncio.Queue → Graph yield → Service SSE → ReadableStream → researchDetailsRef → Visualization

## 后端两条图表路径

DataAnalyst 位于 backend/app/service/deep_research_v2/agents/data_analyst.py。它执行数据提取、知识图谱和图表生成，把结果写入共享状态的 charts，并发送 charts 事件，图表通常包含 echarts_option。

CodeWizard 位于 backend/app/service/deep_research_v2/agents/wizard.py。数据点少于 3 个时会跳过。数据足够时，它让 LLM 生成 Python，经过清理、compile、危险模式检查和线程执行，再把 Matplotlib 图片转成 image_base64，写入 charts，并发送 chart 事件。

## 排错顺序

1. 查 graph.py 是否进入 analyzing 阶段，是否启动 DataAnalyst 和 CodeWizard。
2. 查共享状态 charts 是否增加；没有增加就查事实、数据点、LLM 返回和代码执行结果。
3. 查 BaseAgent.add_message 是否把事件写入 messages 和 message_queue。
4. 查 Graph 是否从队列取到事件，Service 是否格式化成 SSE。
5. 查浏览器 Network 是否收到 charts 或 chart 事件，且响应头是 text/event-stream。
6. 查 frontend/src/pages/chat/index.tsx 是否找到 analyzing 详情并写入 charts。
7. 查 visualization.tsx：有 image_base64 就显示 PNG，有 echarts_option 才渲染 ECharts，否则显示占位。

## 四种现象

A. data_points=2：优先查 CodeWizard 的跳过条件和状态数据。
B. charts 有值但 Network 无事件：查 add_message、队列和 Graph yield。
C. Network 有 charts 但 analyzing 为空：查前端研究步骤是否先创建 analyzing 详情。
D. 详情有图但显示占位：查字段是否真的是 image_base64 或 echarts_option。

## 必须区分

共享状态 charts、SSE 事件和 React detail.charts 是三个不同层次。后端生成图表不等于事件送达，事件送达也不等于组件收到正确字段。CodeWizard 的进程内 exec 仍不是生产级安全沙箱。

## 练习

请给 A、B、C、D 各写第一检查点和一条直接证据。完成后进入 RAG 文档 completed 但召回为 0 的故障演练。
