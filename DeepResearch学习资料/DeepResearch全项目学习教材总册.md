# DeepResearch 全项目学习教材总册

> 目标：先把项目完整阅读和教学材料准备齐，再统一学习。本文是总导航和完整心智模型；各专题课提供源码级细节。

## 0. 阅读口径和证据边界

项目根目录：D:\课\s4-6\industry_information_assistant。

本轮已核对的范围：后端 app 目录、前端 src 目录、根目录与 backend 配置、Docker Compose、数据库初始化 SQL、测试夹具、样例 PDF/Excel/PNG、前端 Mock 数据和依赖配置。

当前源码规模约为：backend/app 75 个 Python 文件；frontend/src 约 81 个 TypeScript/TSX 业务文件，另有类型声明、样式和静态资源；项目中还包含 Docker、配置、测试和样例资产。

已验证：backend 执行 python -m compileall -q app 通过；frontend 执行 npm run build 通过，仅有 bundle 体积警告；无外部服务的数据流演示脚本运行成功。

尚未能用当前环境证明：PostgreSQL、Redis、Milvus、DocMind、真实 LLM、Bocha、股票和招投标 API 的完整端到端链路。当前机器没有可用 Docker CLI。

飞书页面正文受到复制和导出限制，不能保证逐字读取。实现细节以本地源码为权威；课程会明确区分源码证据、静态检查和真实运行证据。

## 1. 先建立零基础理论

### 1.1 HTTP、接口和 JSON

浏览器和后端通过 HTTP 传递请求和响应。请求通常包含方法、路径、请求头和请求体；响应包含状态码、响应头和响应体。

本项目的研究请求是 POST /research/stream。请求体是 JSON，例如 query、session_id、search_modes。后端不是直接把 Python 函数暴露给浏览器，而是通过 HTTP 路由把网络数据转换成 Python 对象。

### 1.2 前端、后端和数据库

前端负责用户交互和展示，后端负责业务规则、模型调用、数据处理和权限，数据库负责长期保存结构化数据。React 页面本身不负责生成研究报告；它只负责把后端事件转换成界面状态。

### 1.3 异步和流式响应

async/await 允许程序等待网络或模型调用时不阻塞整个服务。异步生成器可以不断 yield 中间结果，FastAPI StreamingResponse 可以把这些结果持续写给浏览器。

### 1.4 SSE

Server-Sent Events 是服务器到浏览器的单向事件流。每条事件通常是 data: JSON 加两个换行。SSE 不是 WebSocket，也不负责生成内容；它只负责把后端已经产生的事件持续传输给前端。

### 1.5 LLM、Agent 和工具

LLM 根据提示词生成文本或结构化 JSON。Agent 是围绕 LLM 加上角色、输入、输出、工具和状态更新规则的业务组件。搜索 API、向量检索、代码执行、SQL 查询都是工具或外部能力。

### 1.6 关系数据库、向量数据库和 RAG

PostgreSQL 适合用户、会话、文档元数据和检查点等关系数据。Milvus 适合保存向量并按相似度召回文本片段。Embedding 把文本变成向量；RAG 先召回相关片段，再把片段放入 LLM 上下文。

### 1.7 JWT 和权限

JWT 是登录后发给客户端的凭证。前端把 token 放到请求头，后端验证签名和过期时间，再根据用户 ID过滤资源。前端 AuthGuard 只负责导航体验，不能替代后端权限校验。

## 2. 项目全景

项目可以分成五层：

```text
用户界面层：React、路由、状态、研究详情和业务页面
API 层：FastAPI Router、请求 Schema、SSE 和 JSON 响应
业务编排层：普通聊天、DeepResearch V1/V2、知识库、记忆、Text2SQL
能力服务层：LLM、搜索、DocMind、Embedding、Milvus、代码执行、行业 API
基础设施层：PostgreSQL、Redis、Milvus 依赖的 etcd/MinIO、Elasticsearch、Docker
```

最重要的用户动作是：登录、普通聊天、发起 DeepResearch、上传知识库文档、检索文档、查看长期记忆、执行 Text2SQL、查看行业资讯/招投标/股票。

## 3. 仓库目录和代码职责

### 3.1 根目录

| 路径 | 职责 |
|---|---|
| READMED.md | 启动说明、环境变量、常见问题和 API 文档入口 |
| docker-compose.yml | PostgreSQL、Redis、Milvus、Elasticsearch 等基础服务 |
| start-services.sh | 基础服务启停和日志命令 |
| data/ | 研究样例 PDF |
| docker/init-db/01-init.sql | 初始化数据库和示例表 |

根 Compose 不启动 FastAPI 和 Vite。README 写的前端端口与当前 vite.config.ts 有差异，实际运行时以代码和终端输出为准。

### 3.2 后端入口、配置和核心

| 路径 | 职责 |
|---|---|
| backend/app/app_main.py | FastAPI 应用、模型建表、路由注册、生命周期和调度器 |
| backend/app/config/llm_config.py | LLM、Agent 和研究配置 |
| backend/app/config/industry_config.py | 行业关键词和行业配置 |
| backend/app/config/stock_mapping.py | 公司名称到股票代码映射 |
| backend/app/core/database.py | PostgreSQL engine、SessionLocal 和 get_db |
| backend/app/core/redis_client.py | Redis 客户端和缓存调用 |
| backend/app/core/security.py | 密码哈希、JWT 和认证依赖 |

### 3.3 数据模型和 Schema

models 目录包含用户、会话、消息、附件、知识库、文档、长期记忆、行业数据、新闻、招投标和研究检查点模型。

schemas 目录定义认证、会话、聊天、附件、文档、知识库和搜索的请求与响应契约。Schema 是网络数据契约，ResearchState 是研究过程状态，两者不能混为一谈。

### 3.4 Router

| Router | 主要接口 |
|---|---|
| auth_router.py | 注册、登录、当前用户、改密、退出 |
| session_router.py | 会话和消息 CRUD |
| chat_router.py | 普通聊天 v1/v2/v3 和附件上下文 |
| research_router.py | DeepResearch、取消、检查点、恢复、CodeWizard 测试 |
| knowledge_router.py | 知识库和文档上传、切片、删除 |
| attachment_router.py | 普通聊天附件上传和状态 |
| document_router.py | 旧文档服务兼容接口 |
| memory_router.py | 长期记忆列表、搜索、创建和删除 |
| database_router.py | 表、Schema、数据、Text2SQL |
| search_router.py | Web 搜索 |
| news_router.py | 新闻、招投标、行业和采集 |

### 3.5 通用 Service

chat_service.py 和 chat_service_v2.py 处理普通聊天；session_service.py 处理会话和消息；web_search_service.py 封装网络搜索；retrieval_service.py、embedding_service.py 和 milvus_service.py 组成向量检索；docmind_service.py 处理文档解析；document_service.py 管文档状态；memory_service.py 管长期记忆；text2sql_service.py 管自然语言查询；checkpoint_service.py 管研究检查点；news_collection_service.py、bidding_service.py 和 stock_service.py 管行业业务能力。

react_controller.py、dr_g.py 和 tool_executor.py 属于 V1 ReAct/工具兼容链；不能因为工具已注册就认为每次请求都会调用全部工具。

## 4. 应用启动链

```text
load_dotenv()
→ 导入数据库和模型
→ Base.metadata.create_all(bind=engine)
→ 创建 FastAPI 应用
→ 注册路由
→ lifespan 启动行业数据初始化和调度器
→ uvicorn 监听 8000
```

导入阶段就会触发数据库建表，因此 PostgreSQL 不可连接时，后端可能在开始监听前就失败。启动排错必须看后端启动日志，不能只看浏览器页面。

前端由 Vite 启动，当前 vite.config.ts 端口为 5183，并根据 VITE_API_BASE 和 VITE_API_PROXY 配置代理。Vite Mock 插件存在但当前 enable 为 false。

## 5. 认证和会话完整链路

```text
登录表单
→ POST /auth/login
→ 后端查询用户并用 bcrypt 校验密码
→ 生成 JWT，sub 保存用户 ID，exp 保存过期时间
→ 前端保存 localStorage['auth']
→ Axios auth 插件附加 Authorization: Bearer token
→ 后端认证依赖解析当前用户
```

普通会话和知识库接口已经按 user_id 做主要过滤。研究、检查点和取消接口仍需重点检查当前用户归属校验，不能把“已经登录”说成“所有研究资源都已完成隔离”。退出主要清理前端 token，服务端没有统一 JWT 撤销表。

## 6. 普通聊天、附件、长期记忆和 Text2SQL

### 6.1 普通聊天

普通聊天请求进入 chat_router，再由 chat_service 或 chat_service_v2 处理历史、向量召回、重排、Prompt 拼接和 LLM 流式输出。前端通过 ReadableStream 解析答案和来源事件。

### 6.2 普通聊天附件

普通附件属于当前聊天上下文。附件记录和解析状态保存在 ChatAttachment，处理完成后把 content_text 拼入当前消息；它不等价于知识库长期文档，也不必然进入 Milvus。

### 6.3 长期记忆

长期记忆把会话中的稳定信息摘要成记忆，元数据和用户归属保存在 PostgreSQL，向量保存在 Milvus。下次聊天时用查询向量召回相关记忆，再放入上下文。它与当前会话历史和知识库文档是不同数据域。

### 6.4 Text2SQL

```text
自然语言问题
→ 读取允许的表和字段
→ LLM 生成 SQL
→ 只读/危险语句校验
→ SQLAlchemy 执行
→ 返回列、行和可视化提示
→ 前端数据库页展示
```

数据库引擎不可用时，源码可能走 _get_mock_data(sql)。页面有表格不能单独证明查询来自 PostgreSQL。

## 7. RAG 知识库全链路

```text
知识库页面选择文件
→ POST /knowledge/{kb_id}/documents
→ PostgreSQL Document=pending
→ BackgroundTasks 异步处理
→ DocMind 或解析器提取文本
→ 文本切片
→ Embedding
→ Milvus 写入向量和元数据
→ Document=completed
→ 前端轮询状态
→ DeepScout 或普通聊天向量召回
```

Document=completed 只说明数据库状态流程完成，不自动证明 Milvus 写入成功、查询集合正确、kb_id 过滤正确或前端展示成功。

当前需要特别记忆的排错点：上传链路使用的集合名和 DeepScout 某路径固定查询的集合名可能不同；集合名、连接地址、Embedding 维度、插入数量、查询过滤和结果映射必须逐项检查。

项目存在三条相关检索链：新知识库上传后的文档检索、旧 document_router/外部文档兼容链、政策/行业向量检索链。不能只看到“RAG”三个字就假设它们共享同一集合和同一过滤逻辑。

## 8. DeepResearch V1 和 V2

### 8.1 V1

V1 的核心是 ReAct：控制器根据当前思考选择 Action，调用 ToolExecutor，再根据 Observation 继续循环，最后生成答案或报告。它强调工具循环和动态决策。

### 8.2 V2

V2 的核心是固定职责的多 Agent 工作流：规划、搜索、分析、代码、写作、审核。它强调共享状态、阶段事件、检查点和可解释过程。

POST /research/stream 的 ResearchRequest.version 默认是 v2；GET /research/stream 的 version 默认是 v1。实际参数可以改变版本，不能只根据路径名称判断。

## 9. V2 一次研究请求逐层追踪

```text
React 聊天页
→ api.session.deepsearch()
→ POST /research/stream
→ research_router.stream_research()
→ get_research_service_v2()
→ DeepResearchV2Service.research()
→ DeepResearchGraph.run()
→ create_initial_state() 或加载检查点
→ _run_simplified()
→ 六个 Agent
→ asyncio.Queue
→ SSE
→ ReadableStream
→ React 状态和研究详情
→ research_complete
→ 最终报告
```

### 9.1 请求阶段

frontend/src/api/session.ts 的 deepsearch 设置 Accept=text/event-stream、responseType=stream 和 fetch adapter，POST 到 /research/stream。

### 9.2 Router 阶段

research_router.py 验证 query、session_id、search_modes 等字段，根据 version 选择服务，并返回 media_type=text/event-stream 的 StreamingResponse。

### 9.3 Service 阶段

DeepResearchV2Service.research() 补充 session_id，调用 graph.run()，把每个事件交给 _format_sse()，包装为 data: JSON 空行，并在最后发送 data: [DONE]。

### 9.4 Graph 阶段

graph.py 的 run() 可以尝试加载 checkpoint；没有状态时用 create_initial_state() 创建 ResearchState，然后当前默认始终进入 _run_simplified()。LangGraph astream 分支存在，但不是当前默认执行路径。

### 9.5 Agent 阶段

| 阶段 | Agent | 主要读写 |
|---|---|---|
| planning | ChiefArchitect | query → outline、research_questions、entities、hypotheses |
| researching | DeepScout | outline → raw_sources、facts、data_points、references |
| analyzing | DataAnalyst | facts/data_points → insights、knowledge_graph、ECharts charts |
| analyzing | CodeWizard | data_points/outline → code_executions、PNG charts |
| writing | LeadWriter | outline/evidence/insights → draft_sections、final_report |
| reviewing | CriticMaster | report/evidence → feedback、quality_score、unresolved_issues |

CriticMaster 如果认为证据不足，可以把流程导向补充搜索和重新写作；所以六个 Agent 不一定每次只调用一次。

## 10. ResearchState 全字段心智模型

| 字段 | 含义 |
|---|---|
| query/session_id | 当前问题和研究会话 |
| phase/iteration/max_iterations | 流程阶段和审核轮次 |
| search_web/search_local | 搜索开关 |
| outline | 章节结构和章节要求 |
| research_questions/key_entities/hypotheses | 规划产生的研究问题和假设 |
| facts/raw_sources/references | 事实、原始来源和引用 |
| data_points | 可用于计算和图表的数据点 |
| insights | 数据分析洞察 |
| knowledge_graph | 节点和关系 |
| charts/code_executions | 图表和代码执行记录 |
| draft_sections/final_report | 章节草稿和最终报告 |
| critic_feedback/quality_score/unresolved_issues | 审核结果和是否需要补救 |
| pending_search_queries | 审核后待补充查询 |
| logs/errors/messages | 运行记录、错误和流式消息 |

ResearchState 是一次执行期间的共享工作台，不是 PostgreSQL。检查点服务会把它序列化保存，但内存状态和持久化状态仍是两个层次。

## 11. CodeWizard 代码解释器

```text
data_points
→ Prompt
→ LLM 返回 JSON 和 Python
→ _clean_code
→ compile(..., exec)
→ _is_code_safe 正则拦截
→ asyncio.to_thread
→ 当前进程内 exec
→ stdout/stderr 和 Matplotlib PNG
→ code_executions/charts
→ code_result/chart SSE
```

允许的常用模块包括 pandas、numpy、matplotlib、seaborn、datetime、math、statistics、json、collections 和 re；部分 builtins 被限制，open 被置空。

失败时 _execute_with_self_correction() 把错误和输出交给 LLM 修复，最多重试 3 次。语法检查、危险模式检查和线程执行分别解决不同问题：compile 只检查语法，正则只拦截已知模式，线程只改变调度方式，exec 才是真正执行。

当前实现不是生产级沙箱：没有可靠的进程隔离、资源限制、网络隔离和强制终止；正则过滤也不是安全证明。生产环境应使用容器或专门代码执行服务。

## 12. 图表双路径和前端显示

DataAnalyst 生成结构化 ECharts 配置并发送 charts 事件；CodeWizard 执行 Python 产生 PNG Base64 并发送 chart 事件。两者都可能写入 state.charts。

前端 index.tsx 处理这两种事件并把结果放入分析详情。visualization.tsx 优先显示 image_base64；没有图片但有 echarts_option 时使用 ReactECharts；两者都没有时显示占位。

图表排错必须分开看：state.charts 是否增加、add_message 是否进队列、Graph 是否 yield、浏览器是否收到事件、React 是否找到 analyzing 详情、字段名称是否符合组件契约。

## 13. 写作、审核、检查点、取消和恢复

### 13.1 写作审核循环

LeadWriter 遍历大纲生成章节，保存 draft_sections，并整合为 final_report。CriticMaster 检查证据覆盖、引用和质量分，可能将 phase 设为 revising 或 re_researching。Graph 根据 phase 决定重新写作、补充搜索或完成。

### 13.2 检查点

ResearchCheckpoint 主要保存三类内容：state_json 保存后端 ResearchState；ui_state_json 保存前端步骤、搜索结果、图表、图谱和流式报告；final_report 保存报告文本。

### 13.3 取消

前端可以取消 reader，并调用取消接口；后端通过 Redis 标志协作式检查。Graph 在 Agent 前、Agent 中和阶段切换处检查取消。正在执行的外部模型调用不一定能被立即强制终止。

### 13.4 恢复边界

resume=True 会尝试载入旧状态，但当前 _run_simplified() 仍从手写流程入口执行。它不是已经证明的精确节点级断点续跑；恢复 UI 状态也不等于恢复后台执行位置。

## 14. 前端实时渲染

聊天页拿到 response.body.getReader() 后，用 TextDecoder 解码，并通过临时 buffer 按行拆分 data: 事件。单次 reader.read() 可能只有半个 JSON，必须等完整事件后再 JSON.parse。

研究步骤事件创建 planning、researching、analyzing、writing 和 reviewing 详情；搜索结果、知识图谱、图表和报告事件分别更新对应对象；research_complete 事件把 final_report 写入消息和研究详情，触发 React 重渲染。

前端 data 状态、researchDetailsRef、researchDataVersion 和组件 props 可能存在时序差异。页面空白时，要查事件是否收到、详情 key 是否存在、状态是否触发更新和组件字段是否正确。

## 15. 行业资讯、招投标、股票和调度

industry_config.py 提供行业关键词；NewsCollectionService 调用 Bocha 并按 source_url 去重写入 IndustryNews；BiddingService 调用 81API 或对应配置并按 bid_id 去重写入 BiddingInfo；news_router.py 提供列表、统计和采集接口。

StockService 根据 stock_mapping.py 把公司名称映射为 A 股代码，再调用聚合数据 API。DeepScout 可能发出 stock_quote 事件，前端 chat/index.tsx 和 StockCard 展示行情。

SchedulerService 在应用生命周期中启动，每日执行行业资讯和招投标采集；启动时可能检查并初始化缺失数据。真实采集仍依赖外部密钥、配额、网络和 PostgreSQL。

## 16. 启动和分层排错

推荐顺序：

```text
配置文件和依赖
→ Docker 基础服务健康
→ PostgreSQL/Redis/Milvus 连接
→ FastAPI 启动日志
→ /hello
→ 登录和 JWT
→ 普通 API
→ SSE 研究请求
→ LLM/搜索/DocMind 外部服务
→ 前端状态和组件
```

python -m compileall -q app 只能证明 Python 语法和导入编译阶段基本通过；npm run build 只能证明前端能打包；GET /hello 只能证明简单 FastAPI 路由可响应。三者都不能证明完整研究链路可用。

遇到研究 500，按浏览器 Network、Vite 代理、FastAPI 日志、数据库导入、Redis/Milvus、LLM 配置、搜索 API、Agent 状态和 SSE 解析逐层收集直接证据。

## 17. 必须掌握的真实风险

1. V2 默认是 _run_simplified，不是 LangGraph astream。
2. resume 当前不是严格节点级续跑。
3. CodeWizard 进程内 exec 不是生产沙箱。
4. Document completed 不等于 Milvus 一定可召回。
5. 知识库集合名可能在写入和查询路径不一致。
6. 研究、检查点和取消接口需要继续审查 user_id 归属隔离。
7. Text2SQL 可能 mock fallback，页面结果不能直接当真实数据库证据。
8. 普通附件和知识库文档的持久化和检索能力不同。
9. URL 深读不是浏览器级 JS 渲染。
10. README、Vite 端口和环境变量存在配置漂移。
11. 真实外部 API 的可用性没有被当前静态构建证明。
12. 当前项目目录没有可用 Git 元数据，不能用提交历史解释演进。

## 18. 统一学习顺序

第一轮只读总册和项目一页总图，建立名词和层次。

第二轮按一条主链路读源码：session.ts → research_router.py → service.py → graph.py → state.py → agents → chat/index.tsx。

第三轮读四条外围链：认证/会话、知识库/RAG、普通聊天/附件/记忆、Text2SQL。

第四轮读工程控制面：启动、配置、Docker、检查点、取消、恢复、调度和外部 API。

第五轮做故障排查：报告有值但页面不显示、文档 completed 但搜不到、图表生成但不显示、研究 500、取消不生效。

第六轮做完整项目复述和源码定位。只有完成统一学习和项目复述后，才进入大厂面试官阶段。

## 19. 已准备的专题材料

现有 outputs 目录包含第 1 课至第 119 课、源码覆盖审计、项目一页总图、接口地图、零基础执行计划、阶段验收报告和可运行的最小数据流演示。

重要入口：

- DeepResearch项目总学习路线与文件索引.md
- DeepResearch源码覆盖审计.md
- DeepResearch项目一页总图与背诵版.md
- DeepResearch学习手册-第116课-从源码跟读一次研究请求.md
- DeepResearch学习手册-第117课-启动证据Mock边界与分层排错.md
- DeepResearch学习手册-第118课-图表不显示的完整排错链.md
- DeepResearch学习手册-第119课-零基础理解一次请求.md
- DeepResearch最小数据流演示.py

## 20. 后续面试阶段

项目教学和统一学习完成后，我会作为面试官围绕主链路、Agent 设计、状态契约、RAG、CodeWizard 安全、SSE、检查点、权限和工程风险进行追问，并要求给出源码位置和故障定位证据。

小红书最新面经分析暂时保留，等前两个阶段完成并收到你的相关 Prompt 后再执行。当前不把网络面经内容混入项目教材，避免把外部经验和本项目真实实现混在一起。

## 21. 统一学习完成标准

学习者最终需要能够：

1. 不看材料画出一次 DeepResearch 请求的完整数据流。
2. 解释六个 Agent 的输入、输出、跳过条件和失败传播。
3. 区分 ResearchState、数据库检查点、SSE 事件和 React 状态。
4. 解释 RAG 从上传到召回的每一步，并能定位 completed 但 0 结果。
5. 解释 CodeWizard 的 LLM、compile、过滤、exec、自修复和安全边界。
6. 解释 V1/V2、普通聊天、附件、记忆、Text2SQL 和行业业务链路的边界。
7. 按证据分层排查启动、500、SSE、图表、恢复和权限问题。
8. 能指出当前实现与生产级设计之间的差距。

达到这些标准后，才进入项目面试模拟；在此之前不把材料阅读本身当作已经掌握。

文件级阅读清单见《DeepResearch文件级阅读清单.md》，可按路径定位后端、前端、Agent、基础设施、配置和测试资产。
