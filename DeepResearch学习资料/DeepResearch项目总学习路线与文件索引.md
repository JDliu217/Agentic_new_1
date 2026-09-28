# DeepResearch 项目总学习路线与文件索引

## 0. 这份材料回答什么问题

这份材料是对本地项目 `D:\课\s4-6\industry_information_assistant` 的源码阅读总结。目标不是只告诉你“项目用了哪些技术”，而是帮助你回答：

1. 用户在页面输入一个问题后，代码从哪里开始执行？
2. 一个 Agent 如何把结果交给下一个 Agent？
3. 前端为什么能实时看到研究过程？
4. PostgreSQL、Redis、Milvus、DocMind、LLM 各自负责什么？
5. 项目中哪些功能已经真实接通，哪些只是设计层或兼容代码？
6. 学习时应该按什么顺序阅读和动手验证？

本地源码已经按后端、前端、基础设施和配置进行核对。飞书页面正文受页面导出限制，不能保证逐字读取，因此下面涉及实现细节时以本地源码和实际构建检查结果为准。

## 0.1 已完成的学习材料

| 材料 | 作用 |
|---|---|
| `DeepResearch学习手册-第1课.md` 至 `第12课...md` | 项目基础、架构、Agent、代码解释器、附件、行业数据和分析 |
| `DeepResearch学习手册-第13课-RAG知识库与三套检索链.md` | 新知识库、旧外部文档服务、政策 Milvus 链和集合命名风险 |
| `DeepResearch学习手册-第14课-一次研究请求的完整追踪.md` | 从前端请求到 V2 Agent、SSE、检查点和前端恢复 |
| `DeepResearch学习手册-第15课-ResearchState状态演化与Agent交接.md` | 逐阶段追踪共享状态字段和 Agent 交接，识别参数未贯通风险 |
| `DeepResearch学习手册-第16课-从零启动与工程排错.md` | Docker、后端生命周期、前端代理、最小验证阶梯和分层排错 |
| `DeepResearch学习手册-第17课-认证会话与消息持久化.md` | JWT、前端守卫、PostgreSQL 新会话、Redis 旧会话和消息保存 |
| `DeepResearch学习手册-第18课-行业资讯招投标与定时采集.md` | 行业关键词、Bocha/81API、PostgreSQL 入库、统计和定时采集 |
| `DeepResearch学习手册-第19课-React路由请求层与研究结果渲染.md` | React 启动、路由认证、Axios 插件、SSE、状态管理、检查点恢复和研究详情渲染 |
| `DeepResearch学习手册-第20课-知识库上传解析与向量检索前端链路.md` | 知识库 CRUD、文档上传、后台解析、切片、Embedding、Milvus、轮询和集合命名风险 |
| `DeepResearch学习手册-第21课-长期记忆数据库分析与普通附件链路.md` | 长期记忆、Text2SQL、数据库页、普通附件处理与知识库链路边界 |
| `DeepResearch学习手册-第22课-行业资讯招投标前端筛选与采集闭环.md` | 行业选择、资讯/招投标筛选分页、Bocha/81API 采集、去重、统计与定时任务 |
| `DeepResearch学习手册-第23课-外围支撑模块与兼容链路地图.md` | 应用入口、登录、会话历史、Redis、旧聊天/文档服务、Web 搜索、渲染组件和 V1/V2 边界 |
| `DeepResearch学习手册-第24课-一次请求的状态演化与前端实时渲染.md` | 把 ResearchState、六个 Agent、SSE 事件、检查点和 React 研究详情串成一条真实请求链路 |
| `DeepResearch学习手册-第25课-CodeWizard源码逐步追踪与执行边界.md` | 逐步追踪 LLM 代码生成、语法检查、正则拦截、线程执行、图表事件和源码级安全边界 |
| `DeepResearch学习手册-第26课-RAG知识库上传到召回的完整链路.md` | 追踪知识库上传、DocMind 解析、切片、Embedding、Milvus 写入、前端轮询和 DeepScout 本地召回，并标出集合名风险 |
| `DeepResearch学习手册-第27课-启动部署与分层排错.md` | 梳理 Docker、FastAPI 导入和生命周期、Vite 端口、环境变量、最小验证阶梯及分层排错方法 |
| `DeepResearch学习手册-第28课-认证会话与研究恢复时序.md` | 追踪 JWT、前端守卫、PostgreSQL 新会话、Redis 旧会话、SSE 消息落库和检查点恢复边界 |
| `DeepResearch学习手册-第30课-DeepResearch图表与研究详情渲染链.md` | 追踪 DataAnalyst 提取数据、知识图谱、图表 SSE、React 状态聚合、ECharts 渲染、报告插图和检查点恢复 |
| `DeepResearch学习手册-第31课-V1与V2研究链路边界.md` | 区分 GET/POST 版本选择、V1 ReAct/classic、V2 多 Agent、工具注册与真实调用及事件契约 |
| `DeepResearch学习手册-第32课-应用启动数据模型与基础设施边界.md` | 追踪 FastAPI 导入与生命周期、PostgreSQL 模型、Redis、检查点双状态和 Docker 基础设施边界 |
| `DeepResearch学习手册-第33课-股票行情自动识别与前端卡片链路.md` | 公司名映射、行情 API、`stock_quote` 事件和前端股票卡片 |
| `DeepResearch学习手册-第34课-行业资讯招投标采集闭环.md` | 行业关键词、外部采集 API、去重入库、前端筛选和定时任务 |
| `DeepResearch学习手册-第35课-检查点取消与研究恢复时序.md` | 检查点、取消标志、前端恢复和 resume 边界 |
| `DeepResearch学习手册-第36课-初始化脚本测试夹具与前端页面地图.md` | 初始化 SQL、样例数据、测试脚本、路由地图和页面入口不一致 |
| `DeepResearch学习手册-第37课-配置安全与前端基础设施.md` | 配置、安全、Axios 类型、Valtio 持久化和页面传值 |
| `DeepResearch学习手册-第38课-模型Schema与前端基础契约.md` | SQLAlchemy 模型、Pydantic Schema、TypeScript 全局类型、请求插件、导航、附件选择、页面传值和持久化 |
| `DeepResearch学习手册-第39课-前端基础展示与路由辅助模块.md` | 路由 Context 与 hooks、聊天消息展示、来源面板、图表类型、错误类型、登出、存储适配器和静态演示数据边界 |
| `DeepResearch学习手册-第40课-工程配置依赖与启动契约.md` | 两套 Compose、启动脚本、Python/Node 依赖、环境变量、Vite 代理和分层排错 |
| `DeepResearch学习手册-第41课-用户认证从注册到请求授权.md` | 用户模型、注册登录、bcrypt、JWT、AuthGuard、请求授权和认证边界 |
| `DeepResearch学习手册-第42课-测试夹具Mock与样例资产.md` | 前端 Mock SSE、V2 外部依赖测试脚本、测试 PDF/Excel/PNG、样例知识资产和证据边界 |
| `DeepResearch学习手册-第43课-旧文档服务与直接搜索兼容链.md` | 旧文档 Router、DocMind/外部数据集、Serper 直搜、V2 Scout 搜索差异和兼容链风险 |
| `DeepResearch学习手册-第44课-配置漂移与构建检查边界.md` | 两份后端依赖、Vite/TypeScript/ESLint 检查差异、环境变量来源和证据等级 |
| `DeepResearch零基础学习执行计划.md` | 把课程组织成“解释 → 追踪 → 练习 → 验收”的学习闭环，并给出第一轮作业和进入面试阶段的标准 |
| `DeepResearch第1课答题证据索引.md` | 第一轮七道题对应的源码文件、函数和行号，供答题后逐题验收 |
| `DeepResearch学习手册-第45课-SSE事件从Agent到React.md` | 版本选择、Agent 消息队列、SSE 格式、前端缓冲解析、React 状态、持久化和取消边界 |
| `DeepResearch学习手册-第46课-ResearchState共享工作台.md` | 状态字段分类、六个 Agent 交接、阶段状态机、消息队列与检查点边界 |
| `DeepResearch学习手册-第58课-长期记忆与语义召回.md` | 会话摘要、PostgreSQL 记忆元数据、Milvus 向量、用户过滤、语义召回和聊天上下文边界 |
| `DeepResearch学习手册-第59课-Text2SQL从自然语言到只读查询.md` | Text2SQL 请求、LLM 生成 SQL、只读校验、SQLAlchemy 执行、mock 回退和 Agent 工具边界 |
| `DeepResearch学习手册-第60课-一次研究请求的工程排错方法.md` | 从浏览器、SSE、Router、V2 Agent、检查点到外部依赖的分层排错方法 |
| `DeepResearch学习手册-第61课-综合数据流验收与面试前置.md` | 从 React 输入、Router、V2、ResearchState、六个 Agent、SSE 到检查点和故障判断的完整复述 |
| `DeepResearch学习手册-第62课-启动验收与证据等级.md` | 从静态检查、基础设施健康到业务端到端运行的启动顺序和证据边界 |
| `DeepResearch学习手册-第63课-研究请求500的认证配置排错.md` | 区分构建、认证、应用启动、LLM 配置、SSE 和 Agent 阶段的 500/401/422 排错方法 |
| `DeepResearch学习手册-第64课-研究接口契约与版本边界.md` | ResearchRequest 字段、search_modes 优先级、POST/GET 版本差异、SSE 包装和字段追踪 |
| `DeepResearch学习手册-第65课-六个Agent责任矩阵与跳过条件.md` | 六个 Agent 的阶段条件、输入输出字段、图表双路径、审核路由和故障定位 |
| `DeepResearch学习手册-第66课-Agent失败传播与检查点可靠性.md` | Agent 异常继续执行、CodeWizard 自愈、检查点保存失败和可靠性修复验收 |
| `DeepResearch学习手册-第67课-知识库文档到Milvus的完整链路.md` | 上传、文档状态、DocMind、切片、Embedding、Milvus、轮询、集合命名和普通附件边界 |
| `DeepResearch学习手册-第68课-三条RAG检索链的差异.md` | 普通聊天 v1/v2、DeepResearch 本地搜索、政策集合、重排、异常降级和集合不一致风险 |
| `DeepResearch学习手册-第69课-行业资讯招投标股票与调度闭环.md` | 行业关键词、Bocha/81API、去重入库、前端筛选、APScheduler、手动采集和股票行情边界 |
| `DeepResearch学习手册-第70课-前端Mock SSE与无Docker验证.md` | 前端 Mock SSE、ReadableStream 分块解析、事件聚合和无 Docker 时的证据边界 |
| `DeepResearch学习手册-第71课-从一个问题追踪完整请求.md` | 用一个具体研究问题追踪请求体、ResearchState、六个 Agent、SSE 和 React 展示 |
| `DeepResearch学习手册-第72课-ResearchState状态演化与故障定位.md` | 用状态字段演化判断规划、检索、分析、代码执行、写作和前端事件链故障 |
| `DeepResearch学习手册-第73课-认证会话与研究请求的用户边界.md` | JWT、localStorage、AuthGuard、user_id、session_id、检查点和研究接口授权边界 |
| `DeepResearch学习手册-第74课-RAG从上传文档到Agent召回.md` | 文档上传、DocMind、切片、Embedding、Milvus、相似度检索和集合名排错 |
| `DeepResearch学习手册-第75课-CodeWizard从LLM到执行结果.md` | CodeWizard 的代码生成、语法检查、危险模式过滤、exec、图表和自修复边界 |
| `DeepResearch学习手册-第76课-检查点取消与恢复的真实边界.md` | 检查点双状态、Redis 协作式取消、页面恢复和当前 resume 的节点级续跑限制 |
| `DeepResearch学习手册-第77课-普通聊天长期记忆与Text2SQL.md` | 普通聊天 RAG、长期记忆摘要与向量召回、Text2SQL 只读校验和 Mock 边界 |
| `DeepResearch学习手册-第78课-行业资讯招投标股票与调度闭环.md` | 行业关键词、Bocha/81API、去重入库、股票行情事件和 APScheduler 调度边界 |
| `DeepResearch学习手册-第79课-综合验收第一轮.md` | 从主链路、状态、SSE、RAG、代码执行、检查点到外围业务的综合验收题 |
| `DeepResearch学习手册-第80课-主链路逐层阅读.md` | 从 React 发送问题开始，逐层追踪 POST、V2 服务、Graph、ResearchState、六个 Agent、SSE 和前端展示 |
| `DeepResearch学习手册-第81课-ResearchState共享工作台.md` | 解释 ResearchState 如何承载 Agent 产物、消息队列、检查点和前端恢复，并练习区分事实、数据点和图表 |
| `DeepResearch学习手册-第82课-SSE从队列到React.md` | 逐层解释 Agent 消息、asyncio.Queue、StreamingResponse、ReadableStream 和 React 事件分支及排错顺序 |
| `DeepResearch学习手册-第83课-RAG从上传到DeepScout召回.md` | 追踪知识库上传、Document 状态、DocMind、切片、Embedding、Milvus 和 DeepScout 本地召回，并解释集合名风险 |
| `DeepResearch学习手册-第84课-CodeWizard代码执行链.md` | 追踪 CodeWizard 的 LLM 代码生成、compile、正则检查、exec、图表捕获、自修复和生产安全边界 |
| `DeepResearch学习手册-第85课-检查点取消与恢复.md` | 解释检查点双状态、Redis 协作式取消、浏览器 reader.cancel 和当前 resume 的真实边界 |
| `DeepResearch学习手册-第86课-六个Agent责任矩阵.md` | 对齐六个 Agent 的阶段条件、输入输出、事件和字段故障定位方法 |
| `DeepResearch学习手册-第87课-认证会话与研究请求边界.md` | 解释 JWT、AuthGuard、ChatSession、session_id、ResearchState、检查点和用户资源边界 |
| `DeepResearch学习手册-第88课-普通聊天长期记忆与Text2SQL.md` | 区分普通聊天、短期历史、长期记忆、Text2SQL 和 CodeWizard 的输入、存储、执行与安全边界 |
| `DeepResearch学习手册-第89课-行业资讯招投标股票与调度.md` | 追踪 Bocha 新闻、81API 招投标、股票行情、PostgreSQL 入库、前端页面和 APScheduler 定时任务 |
| `DeepResearch学习手册-第90课-启动部署与分层排错.md` | 梳理 Docker、FastAPI 生命周期、前端代理、环境变量、最小验证阶梯和按错误分层排错 |
| `DeepResearch学习手册-第91课-综合验收与评分标准.md` | 统一验收主链路、状态、Agent、SSE、RAG、代码执行、控制面和工程排错，并定义进入模拟面试的门槛 |
| `DeepResearch学习手册-第92课-用一个问题追踪状态变化.md` | 用一个假设研究问题演示 ResearchState 从规划、搜索、分析、写作到审核的字段变化和故障定位 |
| `DeepResearch学习手册-第93课-报告有值但页面不显示的排错.md` | 用 final_report 已有值的场景，追踪 report_draft、research_complete、SSE 和 React 报告渲染契约 |
| `DeepResearch学习手册-第94课-V1与V2研究链路边界.md` | 区分 POST/GET 默认版本、V1 ReAct 工具循环、V2 多 Agent 状态流程及事件命名差异 |
  | `DeepResearch学习手册-第95课-工程风险可靠性与面试深挖.md` | 从源码证据、实际影响和修复方向理解用户授权、CORS、密钥、恢复、降级、任务和代码执行风险 |
  | `DeepResearch学习手册-第96课-数据分析与代码解释器图表链.md` | 区分 DataAnalyst 的结构化 ECharts 图表和 CodeWizard 的 Python 执行、PNG 捕获、自愈与安全边界 |
  | `DeepResearch学习手册-第97课-写作审核与研究闭环.md` | 解释 LeadWriter 的章节草稿与全文整合、CriticMaster 的审核路由、补充搜索、修订和完成边界 |
  | `DeepResearch学习手册-第98课-前端SSE与研究详情渲染.md` | 追踪 ReadableStream 缓冲、SSE 事件映射、researchDetailsRef、researchDataVersion 和研究详情渲染排错 |
  | `DeepResearch学习手册-第99课-检查点取消与恢复控制面.md` | 解释 state_json、ui_state_json、Redis 取消标志、页面恢复与节点级执行恢复的区别及工程风险 |
  | `DeepResearch学习手册-第100课-RAG从上传到召回.md` | 追踪知识库上传、PostgreSQL、DocMind、切片、Embedding、Milvus、DeepScout 召回和集合命名风险 |
  | `DeepResearch学习手册-第101课-长期记忆与Text2SQL边界.md` | 区分长期记忆的摘要与语义召回、Text2SQL 的生成校验执行和 Mock fallback，并比较两者与 CodeWizard 的边界 |
  | `DeepResearch学习手册-第102课-启动部署与分层排错.md` | 解释 Docker、FastAPI、Vite、环境变量、认证、SSE 和外部服务的启动顺序、证据等级与分层排错 |
  | `DeepResearch学习手册-第103课-行业资讯招投标股票与调度.md` | 追踪行业关键词、Bocha/81API、PostgreSQL 去重入库、股票行情事件、前端卡片和 APScheduler 调度 |
  | `DeepResearch学习手册-第104课-项目总图与第一阶段验收.md` | 把前 103 课压缩成项目分层总图、核心用户动作、状态容器、证据等级和第一阶段验收题 |
  | `DeepResearch学习手册-第105课-第一阶段标准答案与零基础心智模型.md` | 给出第一阶段四题的标准答案、零基础类比、HTTP/API/数据库/向量/SSE 基础和概念-源码-运行答题法 |
  | `DeepResearch学习手册-第106课-认证会话与用户数据边界.md` | 追踪 bcrypt、JWT、Axios Bearer、AuthGuard、ChatSession/user_id 过滤和研究接口当前授权边界 |
| `DeepResearch学习手册-第107课-认证会话与研究边界练习.md` | 用概念—源码—运行练习巩固认证、会话、ResearchState、Milvus、SSE 与研究检查点授权边界 |
| `DeepResearch学习手册-第108课-ResearchState-Milvus-SSE三大核心.md` | 从零解释共享状态、向量检索和实时事件流，串起知识库召回、Agent 交接和 React 展示 |
| `DeepResearch学习手册-第109课-一次研究请求完整追踪.md` | 逐层追踪前端请求、V2 Router、ResearchState、六个 Agent、检查点、SSE 和 React 结果渲染 |
| `DeepResearch学习手册-第110课-启动部署与证据边界.md` | 解释 Compose、FastAPI 生命周期、Vite 代理、环境变量、验收阶梯和当前 Docker 验证限制 |
| `DeepResearch学习手册-第111课-RAG从上传到召回的完整链路.md` | 追踪知识库权限、后台任务、DocMind、切片、Embedding、Milvus 和 DeepScout 本地召回，并训练集合命名排错 |
| `DeepResearch学习手册-第112课-普通聊天附件长期记忆与Text2SQL边界.md` | 对照普通聊天、附件上下文、长期记忆和 Text2SQL 的输入、存储、检索、生成、降级和权限边界 |
| `DeepResearch学习手册-第113课-第一阶段综合验收试卷.md` | 验收主链路、状态、Agent、SSE、RAG、控制面、部署、模块边界和工程风险，作为进入源码深挖的门槛 |
| `DeepResearch学习手册-第114课-第一轮验收答题单.md` | 将综合验收拆成四道带源码提示的题，先验证研究主链路、ResearchState、SSE、RAG 和实现边界 |
| `DeepResearch学习手册-第115课-无外部服务的数据流实验.md` | 用可运行的本地模拟器观察共享状态、阶段事件、SSE 分块和浏览器缓冲，并映射回真实源码 |
| `DeepResearch项目一页总图与背诵版.md` | 把项目主链路、Agent、存储、RAG、代码执行、控制面和业务数据域压缩到一页 |
| `DeepResearch阶段性学习验收报告.md` | 汇总源码覆盖、课程进度、运行证据、当前限制和进入面试阶段的验收标准 |
| `DeepResearch学习手册-第47课-数据分析到图表的双路径.md` | DataAnalyst 的结构化/ECharts 路径、CodeWizard 的 Python/图片路径和前端图表来源 |
| `DeepResearch学习手册-第48课-CodeWizard执行边界与失败自修复.md` | LLM 与执行环境分工、compile/exec 限制、正则拦截、自修复和生产沙箱边界 |
| `DeepResearch学习验收清单.md` | 理论、源码证据、运行证据和面试表达的验收项目 |
| `DeepResearch源码覆盖审计.md` | 已阅读范围、统计口径和运行边界 |
| `DeepResearch接口地图与数据契约.md` | API、请求字段、响应字段和事件契约 |

---

## 1. 项目一句话理解

这是一个带有聊天、行业资讯、知识库、数据库分析和 DeepResearch 多 Agent 研究流程的行业信息助手。

可以把它分成四层：

```text
用户界面层：React 页面、聊天输入、研究过程、图表、知识图谱
        ↓ HTTP / SSE
接口与业务层：FastAPI 路由、会话、认证、知识库、研究服务
        ↓
智能能力层：LLM、Web 搜索、向量检索、Text2SQL、数据分析、代码执行
        ↓
数据与基础设施层：PostgreSQL、Redis、Milvus、MinIO、Elasticsearch、Docker
```

这里最重要的认识是：DeepResearch 不是一个单独的模型调用，而是一条由状态、工具和多个 Agent 共同完成的工作流。

---

## 2. 从用户点击到研究完成

### 2.1 实际请求链路

```text
React 聊天页
  → frontend/src/api/session.ts::deepsearch
  → POST /research/stream
  → backend/app/router/research_router.py
  → DeepResearchV2Service
  → DeepResearchGraph.run()
  → _run_simplified()
  → ChiefArchitect
  → DeepScout
  → DataAnalyst
  → CodeWizard
  → LeadWriter
  → CriticMaster
  → text/event-stream
  → React 解析 SSE 并更新研究面板
```

### 2.2 一个请求的输入

前端在 DeepSearch 模式下发送的核心数据类似：

```json
{
  "query": "新能源汽车行业未来三年的竞争格局",
  "session_id": "当前会话 ID",
  "search_modes": ["web", "local"]
}
```

后端将 `web`、`local` 转成是否搜索互联网和是否检索本地知识库的开关。

### 2.3 为什么返回 SSE

研究需要经历规划、搜索、分析、写作和审核。如果等所有 Agent 结束后才返回一个 JSON，用户只能看到长时间等待。项目使用 `text/event-stream`，让后端在阶段变化、搜索结果、图表、报告片段和完成时分别推送事件。

前端在 `frontend/src/pages/chat/index.tsx` 中读取 `ReadableStream`，按换行拆出 `data: {...}`，再根据 `json.type` 更新研究步骤和详情面板。

---

## 3. 后端目录地图

### 3.1 应用入口与路由

| 位置 | 作用 |
|---|---|
| `backend/app/app_main.py` | 创建 FastAPI 应用、注册路由、中间件和启动逻辑 |
| `backend/app/router/auth_router.py` | 注册、登录和身份认证 |
| `backend/app/router/session_router.py` | 会话和消息管理 |
| `backend/app/router/research_router.py` | DeepResearch 流式研究、取消、检查点 |
| `backend/app/router/chat_router.py` | 普通聊天和带附件聊天 |
| `backend/app/router/knowledge_router.py` | 知识库、文档和切片接口 |
| `backend/app/router/memory_router.py` | 长期记忆的查询、搜索、创建和删除 |
| `backend/app/router/database_router.py` | 数据库浏览和 Text2SQL 相关接口 |
| `backend/app/router/news_router.py` | 行业新闻和采集任务 |
| `backend/app/router/search_router.py` | 搜索能力接口 |
| `backend/app/router/attachment_router.py` | 会话附件上传、状态查询和删除 |
| `backend/app/router/document_router.py` | 文档解析和文档处理接口 |

阅读顺序建议：先看 `app_main.py`，再看 `research_router.py`，最后按页面需要展开其他 Router。

### 3.2 DeepResearch V2 核心文件

| 文件 | 学习重点 |
|---|---|
| `backend/app/service/deep_research_v2/state.py` | `ResearchState` 字段、阶段枚举、初始状态 |
| `backend/app/service/deep_research_v2/graph.py` | 工作流、SSE 事件、检查点和取消 |
| `backend/app/service/deep_research_v2/service.py` | 研究服务入口和依赖组装 |
| `.../agents/base.py` | Agent 公共 LLM 调用、日志和消息推送 |
| `.../agents/architect.py` | 规划大纲、研究问题、实体和假设 |
| `.../agents/scout.py` | 网络搜索、本地检索、深读 URL 和证据整理 |
| `.../agents/data_analyst.py` | 数据整理、洞察和知识图谱 |
| `.../agents/wizard.py` | Python 代码生成、检查、执行、图表和自修复 |
| `.../agents/writer.py` | 根据证据生成章节和最终报告 |
| `.../agents/critic.py` | 质量审核、补充搜索和修订路线 |

### 3.3 通用业务服务

| 服务 | 作用 |
|---|---|
| `chat_service.py` / `chat_service_v2.py` | 普通聊天、来源拼接和政策文档检索 |
| `session_service.py` | 会话和消息持久化 |
| `web_search_service.py` | 网络搜索 API 封装 |
| `retrieval_service.py` | 本地文档检索 |
| `embedding_service.py` | 文本向量化 |
| `milvus_service.py` | 向量集合、写入和相似度查询 |
| `document_service.py` | 文档元数据和处理状态 |
| `docmind_service.py` | 文档解析和切片来源 |
| `memory_service.py` | 长期记忆生成、搜索和上下文 |
| `text2sql_service.py` | 自然语言到 SQL，再执行和格式化结果 |
| `smart_analyzer.py` | 数据分析和结构化洞察 |
| `chart_generator.py` | 图表配置生成 |
| `stock_service.py` | 股票数据查询 |
| `bidding_service.py` | 招投标数据查询 |
| `news_collection_service.py` | 新闻采集和入库 |
| `checkpoint_service.py` | 研究状态保存、恢复和状态更新 |
| `react_controller.py` / `dr_g.py` | V1 ReAct 研究流程 |
| `tool_executor.py` | V1 工具分发和执行 |

---

## 4. V2 的共享状态：Agent 的交接协议

`ResearchState` 位于 `backend/app/service/deep_research_v2/state.py`。它是整个 V2 的共享工作台。

### 4.1 状态字段按用途分组

| 分组 | 典型字段 | 用途 |
|---|---|---|
| 请求上下文 | `query`、`session_id`、用户信息 | 说明当前研究是谁发起的 |
| 流程控制 | `phase`、`iteration`、`status` | 控制当前阶段和是否结束 |
| 规划结果 | `outline`、`research_questions`、`key_entities`、`hypotheses` | 告诉后续 Agent 研究什么 |
| 证据 | `facts`、`data_points`、`references`、`knowledge_graph` | 保存搜索与分析结果 |
| 分析结果 | `insights`、`charts`、`code_executions` | 保存可解释的数据分析产物 |
| 写作结果 | `draft_sections`、`final_report` | 保存章节和完整报告 |
| 审核结果 | `critic_feedback`、`unresolved_issues`、`quality_score` | 决定是否补搜或修订 |
| 运行记录 | `logs`、`errors`、`messages` | 方便 SSE、排错和恢复 |

### 4.2 六个 Agent 的分工

```text
ChiefArchitect：把问题拆成研究计划
DeepScout：为计划寻找来源和事实
DataAnalyst：把事实整理成结构化数据、洞察和关系
CodeWizard：执行需要代码验证的计算并生成图表
LeadWriter：把证据写成章节和报告
CriticMaster：检查完整性和可信度，决定补搜或完成
```

它们不应该被理解为六个互相随意聊天的模型。更准确的说法是：每个 Agent 读取状态中的一部分字段，完成自己的职责，再把结构化结果写回状态。

---

## 5. 设计图和当前真实执行路径

项目定义了 LangGraph 工作流，设计意图类似：

```text
plan → research → analyze → write → review
                                  ├→ revise → review
                                  └→ complete
```

但当前 `DeepResearchGraph.run()` 为了实时 SSE，默认调用的是 `_run_simplified()`。实际顺序是：

```text
planning
  → researching
  → analyzing（DataAnalyst，然后 CodeWizard）
  → writing
  → reviewing
  → re_researching 或 revising
  → completed
```

这是阅读项目时必须记住的边界：

- LangGraph 图是设计层和可扩展结构。
- `_run_simplified()` 是当前默认流式执行路径。
- 不能只看图上的节点，就断言线上一定按 LangGraph 执行。

---

## 6. CodeWizard：项目中的代码解释器

文件：`backend/app/service/deep_research_v2/agents/wizard.py`

当前实现的过程：

```text
LLM 生成 Python
  → 清理 Markdown 代码围栏和转义字符
  → compile() 做语法检查
  → 正则规则拦截明显危险代码
  → 在白名单 globals 中 exec()
  → 捕获 stdout/stderr
  → 捕获 matplotlib PNG
  → Base64 写入 state['charts']
  → 通过 chart/code_result 事件发送前端
```

失败时会把错误反馈给 LLM，自动修复并重试，当前最多 3 次。这个能力适合教学和受控演示，但不能作为生产级隔离：Python 进程内的正则拦截和受限 builtins 不是强安全边界。生产方案应使用 Docker、独立沙箱或专用代码执行服务，并配合资源、时间、网络和文件系统限制。

---

## 7. 搜索、知识库和数据存储

### 7.1 本地知识库链路

```text
上传文件
  → 文档解析（DocMind）
  → 文本切片
  → Embedding 模型生成向量
  → Milvus 保存向量和切片内容
  → 查询文本向量化
  → COSINE 相似度检索
  → 返回相关切片给聊天或研究 Agent
```

### 7.2 四个基础设施分别保存什么

| 组件 | 保存或提供的内容 |
|---|---|
| PostgreSQL | 用户、会话、消息、知识库元数据、文档状态、研究检查点、行业业务数据 |
| Redis | 缓存、短期状态、取消标志等快速访问数据 |
| Milvus | 文档切片的向量和向量检索所需内容 |
| MinIO | Docker 环境中的对象存储能力，具体使用取决于配置和服务调用 |

不能把 PostgreSQL 和 Milvus 都称为“向量数据库”。PostgreSQL 管业务关系和元数据，Milvus 管相似度检索。

### 7.3 当前实现边界

- `deep_read_url()` 目前使用 requests 和 HTML 提取，尚未接入真正的 Headless Browser。
- 事实去重主要靠关键词和数字指纹，不是向量语义去重。
- `PolicySearchService` 的 keyword/hybrid 路径当前存在降级为向量搜索的行为。
- 普通聊天附件中的 PDF、Word、图片处理主要是占位流程；知识库上传才走完整文档解析链路。

---

## 8. 前端目录地图

### 8.1 路由和认证

| 文件 | 作用 |
|---|---|
| `frontend/src/router/routes.tsx` | 登录、聊天、知识库、记忆、数据库、新闻、招投标页面路由 |
| `frontend/src/components/auth-guard/index.tsx` | 未登录用户跳转登录页 |
| `frontend/src/pages/auth/login.tsx` | 登录和注册表单 |
| `frontend/src/store/auth.ts` | 保存 token 和用户信息 |
| `frontend/src/api/request/plugins/auth.ts` | 自动把 token 放入 `Authorization` 请求头 |

### 8.2 研究页面

| 文件 | 作用 |
|---|---|
| `frontend/src/pages/chat/index.tsx` | 发起聊天和 DeepResearch、读取 SSE、处理取消和恢复 |
| `.../research-detail/index.tsx` | 研究详情右侧面板和标签页 |
| `.../research-detail/search-results.tsx` | 搜索结果展示 |
| `.../research-detail/knowledge-graph.tsx` | 知识图谱展示 |
| `.../research-detail/visualization.tsx` | 图表展示 |
| `.../research-detail/process-report.tsx` | 报告、章节和图表混合渲染 |
| `frontend/src/components/chart/index.tsx` | ECharts 图表渲染 |
| `frontend/src/components/rich-content/index.tsx` | 富内容和结构化内容渲染 |

### 8.3 业务页面和状态

| 主题 | 页面 | 状态/API |
|---|---|---|
| 会话 | `pages/chat`、`newchat` | `store/session.ts`、`api/session.ts` |
| 知识库 | `pages/knowledge` | `store/knowledge.ts`、`api/knowledge.ts` |
| 记忆 | `pages/memory` | `api/memory.ts` |
| 数据库 | `pages/database` | `api/database.ts` |
| 新闻 | `pages/news` | `api/news.ts` |
| 招投标 | `pages/bidding` | 对应页面请求逻辑 |
| 设备和搜索偏好 | 页面与全局状态 | `store/device.ts`、`store/industry.ts` |

### 8.4 前端研究事件的核心映射

前端会把后端事件转成研究步骤和详情：

| 后端事件 | 前端结果 |
|---|---|
| `research_start` | 初始化研究模式和步骤容器 |
| `research_step` | 创建或更新 planning、researching、analyzing、writing、reviewing 步骤 |
| `search_results` | 放入搜索详情并更新结果数量 |
| `knowledge_graph` | 放入分析步骤的图谱数据 |
| `chart` / 图表事件 | 放入图表数组，交给 ECharts 渲染 |
| 报告增量事件 | 更新写作步骤的流式报告 |
| `research_complete` | 保存最终报告、引用和完成状态 |
| `research_cancelled` | 关闭加载状态并显示取消结果 |

---

## 9. V1 与 V2 的关系

### V1：ReAct

```text
ResearchService
  → ReActController
  → Thought / Action / Observation
  → ToolExecutor
  → 搜索、知识库、Text2SQL、分析、图表等工具
  → 反思和补充搜索
  → 报告
```

V1 的特点是一个控制器根据当前观察选择工具，灵活但流程边界较弱。

### V2：多 Agent 工作流

```text
规划 Agent → 搜索 Agent → 分析 Agent → 代码 Agent → 写作 Agent → 审核 Agent
```

V2 把职责拆开，用共享状态和固定阶段管理复杂流程，更适合展示过程、插入检查点和扩展专门能力。

面试时可以这样回答差异：V1 的核心抽象是“控制器选择工具”，V2 的核心抽象是“多个有明确职责的 Agent 共享状态并按阶段协作”。

---

## 10. 推荐学习路线

### 第 0 阶段：先跑通外围认知

学习：HTTP、JSON、FastAPI 路由、React 组件、异步函数、Docker、数据库基本概念。

结果：能看懂一个请求怎样从页面进入后端。

### 第 1 阶段：登录和会话

阅读：`auth_router.py`、`pages/auth/login.tsx`、`store/auth.ts`、`session_router.py`、`session_service.py`。

练习：注册用户、登录、查看 token、创建一个普通会话、发送一条普通消息。

### 第 2 阶段：完整 DeepResearch 主链路

阅读：`research_router.py` → `service.py` → `graph.py` → `state.py`。

练习：画出请求链路；写出每个阶段读哪些字段、写哪些字段；解释为什么使用 SSE。

### 第 3 阶段：六个 Agent

阅读：`agents/base.py` 和六个 Agent 文件。

练习：为每个 Agent 写一张卡片：输入、输出、调用的工具、可能失败的地方。

### 第 4 阶段：搜索与知识库

阅读：`web_search_service.py`、`retrieval_service.py`、`embedding_service.py`、`milvus_service.py`、`docmind_service.py`。

练习：上传文档、查看文档状态和切片、用一个问题检索本地内容。

### 第 5 阶段：数据分析与代码解释器

阅读：`text2sql_service.py`、`smart_analyzer.py`、`chart_generator.py`、`agents/wizard.py`。

练习：执行一次结构化查询，观察数据如何变成图表；说明为什么 `compile()` 不是安全隔离。

### 第 6 阶段：检查点、取消和恢复

阅读：`checkpoint_service.py`、`models/research.py`、`research_router.py` 的检查点接口，以及聊天页恢复逻辑。

练习：启动研究后取消；查询检查点；刷新页面后观察 UI 状态恢复。

### 第 7 阶段：前端实时渲染

阅读：`pages/chat/index.tsx`、`research-detail` 目录、`components/chart`、`components/rich-content`。

练习：把一个 SSE 事件从后端 JSON 跟到 React state，再跟到最终 DOM 展示。

第 19 课进一步补全了这条前端链路：`main.tsx` → `App` → Router/AuthGuard → API 请求插件 → `ReadableStream` → `researchDetailsRef`/`researchDataVersion` → `ResearchDetail`。

第 20 课补全知识库页面到 RAG 的链路：`Upload` → `multipart/form-data` → `Document(pending)` → `BackgroundTasks` → DocMind/Embedding/Milvus → 状态轮询 → 切片查看或检索。

第 21 课补全三条业务链：会话摘要到长期记忆、自然语言到只读 SQL、普通附件到当前聊天，并标出 mock 数据和 PDF/Word/图片占位处理。

第 22 课把行业配置、前端列表、手动采集、外部 API、PostgreSQL 和每日调度任务连成完整闭环。

第 23 课完成外围支撑和兼容代码地图，明确当前主入口、旧路径、独立工具接口以及安全和运行边界。

第 33 课补全股票行情链路：公司名静态映射、A 股代码标准化、聚合数据 API、DeepScout 的 `stock_quote` 事件、React 状态保存和 `StockCard` 渲染，并区分 V2 自动查询和 V1 股票工具注册。

第 34 课补全行业业务数据闭环：行业配置关键词、Bocha 新闻采集、81API 招投标采集、PostgreSQL 去重入库、`/news` 路由、前端筛选、每日调度和启动时初始化，并指出手动采集接口当前是直接等待而非真正后台任务。

第 35 课补全检查点、取消和恢复时序：区分 `ResearchState`、`ui_state_json` 与会话消息，追踪 Redis 取消标志、阶段检查点、前端恢复映射和 `/research/resume`，并指出当前 resume 会载入旧状态但仍从手写流程的规划入口重新执行。

第 36 课补全工程外围：Docker 两套 Compose、数据库初始化 SQL、两套行业样例脚本、V2 人工端到端测试脚本、前端路由页面地图、行业状态持久化、知识库轮询、数据库示例表，以及“记忆页面已实现但导航仍提示未开放”的入口不一致。

第 37 课补全配置和前端基础设施：LLMConfig/ServiceConfig、环境变量命名漂移、PostgreSQL Session、bcrypt/JWT、Axios 扩展、前端类型、Valtio 持久化、页面间一次性传值和配置排错方法。

第 49 课继续追踪知识库异步处理：上传接口立即返回、Document 的 pending/processing/completed/failed 状态、FastAPI BackgroundTasks、前端 3 秒轮询、定时器清理，以及 PostgreSQL 状态和 Milvus 实际写入之间的排错边界。

第 50 课把这条链路变成工程排错方法：按 PostgreSQL、后台任务、DocMind、Embedding、Milvus、检索过滤和 React 展示的顺序收集证据，并指出状态完成、集合命名、kb_id 过滤和元数据删除之间的边界。

第 51 课追踪普通聊天的三条入口：旧版 v1、新版 `/chat/completion` 和带附件 v3，讲清 Embedding 召回、Milvus search、DashScope 重排、token 截断、Prompt 组装、SSE 来源事件和前端 ReadableStream 缓冲之间的关系。

第 52 课追踪一次 DeepResearch V2 请求的真实默认主链：`POST /research/stream` → `DeepResearchV2Service` → `ResearchState` → `_run_simplified()` → 六个 Agent → `asyncio.Queue` → SSE → React，并区分实际手写执行路径和代码中暂未默认使用的 LangGraph 路径。

第 53 课建立六个 Agent 的输入、输出和事件责任矩阵，解释 BaseAgent 的统一 LLM/JSON/Queue 契约，并用“facts 有但 charts 为空”的故障示例训练按责任边界排错。

第 54 课拆解取消、检查点和恢复：前端 `reader.cancel()`、Redis 协作式取消、Graph 的检查时机、`state_json` 与 `ui_state_json`，以及当前简化执行器恢复状态但不等于精确节点级续跑的限制。

第 55 课把源码理解连接到实际启动：区分两套 Compose、PostgreSQL/Redis/Milvus/MinIO/Elasticsearch、FastAPI 8000、Vite 5183、环境变量、外部 API 密钥和分层运行验收，并指出 README 的 5173 端口漂移。

第 56 课追踪认证与资源授权：注册/登录、bcrypt、JWT `sub` 和 `exp`、localStorage、Axios Bearer 请求头、AuthGuard、知识库和 PostgreSQL 会话的 `user_id` 过滤，以及旧 Redis 会话与新 PostgreSQL 会话的差异。

第 57 课区分普通聊天附件和知识库文档：ChatAttachment 的临时 `content_text` 与 Document 的 DocMind/Embedding/Milvus 长期入库，前端 2 秒附件轮询、v3 上下文拼接、长度截断，以及 PDF/Word/图片当前只写占位文本的边界。

### 第 8 阶段：部署和排错

阅读：`docker-compose.yml`、`start-services.sh`、`READMED.md`、环境变量和依赖文件。

练习：按“容器 → 数据库 → 后端 → 前端 → 外部 API”的顺序定位一个故障。

### 第 9 阶段：从源码跟读到掌握

第 116 课沿着“前端发起研究 → Router 选择版本 → V2 Service → ResearchState → `_run_simplified()` → 六个 Agent → SSE → React 展示”逐文件跟读一次真实请求，并设置四题验收。完成验收后再进入 CodeWizard、RAG、检查点的综合故障排查和面试准备。

第 117 课训练工程证据判断：区分 Compose 基础服务和应用进程，核对 README 与 Vite 端口差异，解释 `/hello`、Text2SQL Mock、`/research/test-wizard` 与前端 Mock 插件各能证明什么，并给出从浏览器 Network 到外部 API 的分层排错顺序。

第 118 课追踪图表不显示：区分 DataAnalyst 的 charts 事件和 CodeWizard 的 chart 事件，核对状态、队列、SSE 和 React 详情对象，并训练按证据定位故障。

《DeepResearch阶段验收答题表.md》把第116至118课的题目、源码提示、回答栏和卡点栏集中起来，作为进入下一阶段前的掌握证据入口。

---

## 11. 当前项目的真实限制清单

这些内容适合在学习和面试中主动说明：

1. V2 `run()` 当前默认走 `_run_simplified()`，LangGraph 设计图不是默认执行器。
2. `max_iterations` 的配置默认值与初始状态默认值存在差异，运行时应以实际配置覆盖为准。
3. DeepScout 每次最多处理部分待研究章节，LeadWriter 仍会遍历整个大纲，可能导致证据覆盖不均。
4. `graph.py` 的分析节点设计与手写流程的 DataAnalyst + CodeWizard 顺序并不完全一致。
5. CodeWizard 是简化沙箱，不能承担生产安全隔离。
6. URL 深读还不是浏览器级渲染，遇到需要 JavaScript 的网页会受限。
7. 某些检索模式名称和实际实现存在降级关系，不能只按函数名推断算法。
8. `ChartGenerator.merge_configs()` 尚未实现完整合并逻辑。
9. 项目中存在硬编码默认配置风险，真实密钥不能提交到仓库。
10. 当前项目目录没有可用 Git 历史，不能用提交记录判断功能演进。

---

## 12. 我建议你用什么方式学习

不要一次性背完整个项目。每次只追踪一条真实链路：

```text
一个页面动作
  → 一个 HTTP 请求
  → 一个 Router
  → 一个 Service
  → 一个数据结构
  → 一个外部依赖
  → 一个前端展示结果
```

例如“发起深度研究”这条链路已经足够学习很多内容：React 状态、Fetch 流、SSE、FastAPI 异步生成器、Agent 编排、LLM 结构化输出、向量检索、代码执行、检查点和报告渲染。

后续教学可以按上面的第 1 至第 8 阶段逐课推进。每课都应包含：源码位置、运行时数据、一个最小练习、一个容易误解的边界，以及面试官可能追问的问题。


第 119 课用研究公司类比解释前端、后端、HTTP、Agent、ResearchState 和 SSE，并把每个概念映射到项目文件，最后设置一句话填空，适合零基础学习者建立第一次请求的心智模型。

《DeepResearch全项目学习教材总册.md》是统一学习入口，按零基础理论、目录地图、启动、认证、普通聊天、RAG、DeepResearch V1/V2、ResearchState、CodeWizard、前端渲染、行业业务、排错、风险和面试阶段重新组织全部项目内容。

《DeepResearch文件级阅读清单.md》按路径列出已核对的后端入口、模型、Schema、Router、V2 Agent、通用 Service、脚本、前端 API、页面、组件、配置、Mock 和测试资产。
