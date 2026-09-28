# DeepResearch 学习手册·第 31 课

## V1 ReAct 与 V2 多 Agent 研究链路边界

项目中同时保留了 V1 和 V2。阅读时如果只看类名，很容易把两条链路拼成一条不存在的流程。本课只根据当前调用方说明：请求从哪里进入、哪个版本被选择、V1 内部如何运行、V2 内部如何运行，以及哪些旧代码不能当成当前主路径。

源码依据：

    D:\课\s4-6\industry_information_assistant\backend\app\router\research_router.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\dr_g.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\react_controller.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\tool_executor.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\service.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\graph.py

---

## 1. 先看入口：同一个路径有两个 HTTP 方法

研究路由同时定义了：

    POST /research/stream
    GET  /research/stream

它们的默认版本不一样：

    POST 请求体 ResearchRequest.version 默认是 "v2"
    GET 查询参数 version 默认是 "v1"

这是当前源码中最容易漏掉的事实。前端 DeepResearch API 使用 POST，因此前端正常发起的研究请求默认进入 V2；如果有人直接用浏览器地址或旧脚本访问 GET，默认可能进入 V1。

请求选择逻辑可以简化为：

    POST /research/stream + version=v2
      → DeepResearchV2Service.research()

    POST /research/stream + version=v1
      → ResearchService.research_stream()

    GET /research/stream（不写 version）
      → ResearchService.research_stream()

    GET /research/stream?version=v2
      → DeepResearchV2Service.research()

因此排查问题时，第一件事不是先看 Agent，而是记录 HTTP 方法、version 字段或查询参数、search_modes 和 session_id。

---

## 2. V2 主路径：六个 Agent 共享 ResearchState

POST 默认 V2 后，路由创建 DeepResearchV2Service。服务再创建 DeepResearchGraph，并将请求交给 graph.run()。

当前 run() 将 LangGraph 分支注释掉，始终调用 _run_simplified(state)。

实际阶段顺序是：

    ChiefArchitect
      → DeepScout
      → DataAnalyst
      → CodeWizard
      → LeadWriter
      → CriticMaster

每个 Agent 读取和修改同一个 ResearchState。阶段结果包括 outline、research_questions、facts、references、data_points、knowledge_graph、charts、insights、draft_sections、final_report、critic_feedback、unresolved_issues 和 quality_score。

实时消息通过 state["_message_queue"] 传出，再由 graph 转成 SSE。V2 的核心是“固定角色 Agent + 共享状态 + 阶段事件”。

---

## 3. V1 入口：ResearchService

V1 的 ResearchService 位于 service/dr_g.py。初始化时默认 use_react=True。

如果 ReAct 组件初始化成功，V1 的 research_stream() 会进入 _research_with_react()。如果初始化失败，代码把 use_react 改为 False，之后进入 _research_classic()。

所以 V1 也不是只有一种实现：

    V1 + ReAct
    V1 + classic fallback

这与 V2 的六个 Agent 流程不同。V1 主要围绕一个 ReActController、一个 ReActContext 和一组工具运行。

---

## 4. V1 ReAct 的数据结构

V1 通过 ReActContext 保存运行上下文：

    query
    steps
    observations
    collected_data
    insights
    charts
    metadata
    plan
    executed_queries
    iteration

LLM 在规划和反思阶段返回结构化 JSON。工具执行则通过：

    Action
      → ReActController._execute_action()
      → Tool.handler
      → Observation
      → context.add_observation()

ToolExecutor 为工具绑定真正的 handler。可注册的工具包括 web_search、knowledge_search、text2sql、data_analyzer、chart_generator、stock_query、bidding_search 和 finish。

工具注册表示“控制器知道这些能力”，不代表每次请求都会依次执行所有工具。

---

## 5. V1 优化版 ReAct 的真实主循环

ReActController.run() 的优化版主循环是：

    Plan
      → Execute parallel search
      → Reflect
      → 需要时补充搜索
      → Complete

第一步 _generate_plan() 要求 LLM 生成多个 SubQuery，每个子查询带有 query、purpose、tool 和 priority。

第一轮只执行 priority <= 2 的子查询，并通过 asyncio.gather() 并行执行。反思阶段评估信息覆盖度，最多进行三轮循环。

当前这段优化版循环的关键事实是：它根据计划执行子查询，主要调用 web_search 或 knowledge_search。虽然 ToolType 中存在 Text2SQL、DATA_ANALYZER 和 CHART_GENERATOR，且 ToolExecutor 也有对应 handler，但不能据此声称每个 V1 ReAct 研究请求会自动执行数据库分析和图表生成。

如果要证明某次 V1 请求确实调用了 Text2SQL 或图表工具，必须同时看到：

    LLM 产生了对应 tool 名称的 Action
    _execute_action() 被调用
    ToolExecutor 对应 handler 有日志或结果
    前端收到对应事件

只看 create_default_tools() 不足以证明闭环。

---

## 6. V1 ReAct 的报告生成

ResearchService._research_with_react() 收集 ReAct 事件和 collected_data，随后调用 _generate_final_report(query, memory, charts, insights)。

报告阶段：

    发送 reference_materials
    组装搜索结果和洞察 Prompt
    调用 deepseek-r1 流式生成报告
    发送 thinking、answer、complete
    如果有 charts，再逐个发送图表事件

这条链路的事件契约与 V2 不同。V2 使用 research_start、research_step、search_results、knowledge_graph、charts、phase 和 research_complete。

V1 常见的是 react_start、status、thought、plan、action、search_result_item、observation、reflection、reference_materials、thinking、answer 和 complete。

前端如果只按 V2 事件解析，就不能把 V1 的每个事件正确映射到同一套研究详情。

---

## 7. V1 classic fallback 的执行方式

classic 模式不使用 ReActController，而是在 dr_g.py 中直接实现：

    第一次调用 LLM 规划 5-8 个子问题
    并行搜索这些子问题
    按 URL 去重
    按内容相似度去重
    再调用 LLM 反思
    不足时生成新的子问题
    最后调用 _generate_final_report()

它同样支持网络和本地搜索，但它的状态主要是局部变量 memory、processed_urls、current_subqueries 和 all_subqueries_history。

这与 V2 把过程统一写进 ResearchState、检查点和 UI state 的方式不同。classic 分支更像旧版兼容实现，不应该和 V2 的恢复机制混为一谈。

---

## 8. V1、V2、普通聊天的对照

    普通聊天：
      /chat/completion
      /chat/completion/v1
      /chat/completion/v3
      ChatService、旧 SessionService、检索和附件

    V1 深度研究：
      /research/stream + version=v1
      ResearchService
      ReActController 或 classic
      ToolExecutor、搜索、旧版报告事件

    V2 深度研究：
      /research/stream + version=v2
      DeepResearchV2Service
      DeepResearchGraph._run_simplified()
      六个 Agent、ResearchState、检查点、V2 SSE

普通聊天、V1 研究和 V2 研究都可能出现“搜索”和“报告”，但它们的服务入口、状态对象和事件契约不同。

---

## 9. 为什么代码会显得重复

项目经历过演进，因此同时保留旧聊天接口、旧 Redis SessionService、V1 ReAct、V1 classic、V2 多 Agent、通用 ToolExecutor、新 PostgreSQL 会话和检查点。

重复代码不一定意味着它们会在一次请求中全部运行。判断实际路径要从路由调用方反向追踪：

    当前 URL
      → Router 分支
      → Service 实例
      → 主入口函数
      → 事件类型
      → 前端处理分支

这是阅读老项目时比“按目录顺序通读”更可靠的方法。

---

## 10. 配置和版本选择的风险

### 10.1 GET/POST 默认不一致

旧脚本用 GET，新前端用 POST，会导致默认版本不同。日志里必须打印 HTTP 方法和 version。

### 10.2 V1 与 V2 的模型配置不同

V2 从 llm_config.py 读取各 Agent 的模型。V1 ReAct 初始化时使用 qwen-max，报告生成又固定使用 deepseek-r1。不能用一个模型名解释整个项目。

### 10.3 兼容代码可能掩盖配置失败

V1 ReAct 初始化失败会降级 classic；Text2SQL、股票和招投标工具也有错误或 fallback 返回。看到“接口还能返回”不等于所有能力都已配置成功。

### 10.4 敏感配置必须审计

源码中出现过环境变量默认值和连接配置。实际部署时必须确认密钥来自安全的环境变量或密钥管理系统，不应把真实 API Key 写入仓库或日志。本课不复述任何密钥内容。

---

## 11. 排查同一个问题为什么结果不同

按以下顺序记录一次请求：

    1. 是 GET 还是 POST？
    2. version 是 v1 还是 v2？
    3. Router 选择了哪个 Service？
    4. V1 是 ReAct 还是 classic？
    5. V2 是否进入 _run_simplified()？
    6. 使用了哪些搜索开关？
    7. 收到的是 V1 事件还是 V2 事件？
    8. 前端是否按对应契约解析？

典型现象：

    页面能看到旧式 thought/answer
      → 可能是 V1

    页面有 analyzing、charts、knowledge_graph 标签
      → 更像 V2

    V1 返回搜索结果但没有图表
      → 不足以证明图表工具故障，可能是本次流程没有调用 chart_generator

---

## 12. 面试回答模板

如果面试官问“项目为什么有两套 DeepResearch”，可以这样回答：

项目保留了 V1 和 V2 两套研究实现。POST /research/stream 的请求模型默认 version=v2，前端主路径进入 DeepResearchV2Service，再由 DeepResearchGraph 的 _run_simplified() 按 ChiefArchitect、DeepScout、DataAnalyst、CodeWizard、LeadWriter、CriticMaster 顺序执行，并通过 ResearchState、检查点和 V2 SSE 输出。GET /research/stream 的默认 version 仍是 v1，V1 由 ResearchService 处理，内部默认使用 ReActController，初始化失败时降级 classic。V1 的工具注册表包含 Text2SQL、数据分析和图表生成，但优化版 ReAct 主循环主要按计划并行执行搜索子查询，不能仅凭工具注册断言每次请求都经过这些工具。排查时要先看 HTTP 方法和 version，再看事件契约和前端解析分支。

---

## 13. 练习

1. 为什么同一个 /research/stream，GET 和 POST 可能进入不同版本？
2. V2 的 run() 当前为什么不是 LangGraph 实际执行？
3. V1 的 ReActContext 和 V2 的 ResearchState 有什么区别？
4. create_default_tools() 中存在 chart_generator，为什么还不能证明 V1 每次都会生成图表？
5. V1 ReAct 初始化失败后会发生什么？
6. V1 和 V2 的 SSE 事件各举出三种，并说明前端为什么不能完全混用？
7. 如果用户说“我用浏览器打开接口和页面请求结果不同”，你会先检查哪些字段？

---

## 14. 留给你的笔记区

### 14.1 我画的版本选择图



### 14.2 我认为应该保留还是删除的兼容代码



### 14.3 一次请求的实际事件序列



