# DeepResearch 第119课：零基础理解一次请求

## 先把项目想成一家研究公司

前端是接待窗口：接收问题、展示进度和报告。
后端是研究部门：安排研究步骤、调用模型和工具、保存结果。
HTTP 接口是前台和研究部门之间的传单：前端用固定地址提交请求，后端返回结果。
Agent 是不同岗位的研究员：规划、搜索、分析、写作和审核。
ResearchState 是这次研究的共享工作台：每个研究员都从这里读资料，也把自己的结果写回这里。
SSE 是研究部门向接待窗口持续发送的进度广播：研究没有完成时，窗口也能不断显示新事件。

## 映射到当前项目

1. 用户在聊天页输入问题。
2. frontend/src/api/session.ts 的 deepsearch() 把问题 POST 到 /research/stream。
3. backend/app/router/research_router.py 接收请求。ResearchRequest 的 version 默认是 v2，因此通常选择 V2 服务。
4. backend/app/service/deep_research_v2/service.py 的 research() 调用 graph.run()。
5. graph.py 创建或加载 ResearchState，然后进入 _run_simplified()。
6. _run_simplified() 依次启动 ChiefArchitect、DeepScout、DataAnalyst、CodeWizard、LeadWriter 和 CriticMaster。
7. 每个 Agent 修改共享状态，并通过 BaseAgent.add_message() 发出事件。
8. asyncio.Queue 暂存事件，Graph 取出事件后交给 Service。
9. Service 把事件包装成 data: JSON 的 SSE 格式。
10. frontend/src/pages/chat/index.tsx 读取、解析事件，更新 React 状态。
11. research_complete 事件到达后，最终报告被写入聊天消息和研究详情。

## 为什么不直接返回一个 JSON

如果后端等六个 Agent 全部完成再返回，用户只能看到长时间等待。SSE 允许后端边研究边发送规划、搜索、分析、写作和审核事件，所以页面可以显示过程。

SSE 只负责传输事件，不负责决定研究内容。研究内容由 Agent、LLM、搜索服务和共享状态共同产生。

## 一次状态变化的例子

刚开始：query 有问题，outline、facts、charts 和 final_report 基本为空。
规划后：outline 有章节和研究问题。
搜索后：facts、raw_sources 和 data_points 增加。
分析后：insights、charts 和 code_executions 可能增加。
写作后：draft_sections 和 final_report 有内容。
审核后：critic_feedback、quality_score 和 unresolved_issues 被更新。

## 现在只做一个最小复述

请补全下面一句话，不需要写文件名：

用户的问题先由 ______ 发到后端的 ______，后端用 ______ 保存多个 Agent 的中间结果，再用 ______ 把过程事件持续传回浏览器，最后由 ______ 显示报告。

参考词：前端、ResearchState、POST /research/stream、SSE、React 页面。

等你填完这一个句子，我再解释 Router、Service 和 Agent 为什么要分成三层。
