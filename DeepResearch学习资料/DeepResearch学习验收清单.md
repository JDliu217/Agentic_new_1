# DeepResearch 学习验收清单

这份清单用于判断“读过材料”和“真正理解项目”的差别。每项都建议同时留下：

- 理论解释：不用看源码也能讲清。
- 源码证据：能指出文件和函数。
- 运行证据：能在本地启动后用日志、接口或页面验证。

## 1. 项目全景

- [ ] 能画出 React、FastAPI、PostgreSQL、Redis、Milvus、Embedding、外部搜索和 LLM 的关系。
- [ ] 能区分 V1 ReAct 链路与 V2 DeepResearch 链路。
- [ ] 能解释为什么 LangGraph 图是设计层，而当前 `run()` 主要走 `_run_simplified()`。
- [ ] 能说出前端实际 Vite 端口是 `5183`，并知道 README 与源码存在差异。

源码证据：`backend/app/service/deep_research_v2/`、`backend/app/router/research_router.py`、`frontend/vite.config.ts`。

## 2. 请求和流式输出

- [ ] 能从 React Chat 页面追踪到 `POST /research/stream`。
- [ ] 能解释 SSE 如何把 Agent 进度传回浏览器。
- [ ] 能区分研究请求的数据库记录、会话记录和前端研究详情页面。
- [ ] 能说明一次请求失败时应该先看哪一层日志。

源码证据：`backend/app/router/research_router.py`、V2 service、前端研究页面。

## 3. 多 Agent 协作

- [ ] 能说出 ChiefArchitect、DeepScout、DataAnalyst、CodeWizard、LeadWriter、CriticMaster 各自负责什么。
- [ ] 能解释 Agent 之间通过什么状态或结果传递信息。
- [ ] 能指出 DeepScout 每次最多处理的待研究章节数。
- [ ] 能发现 LeadWriter 遍历整个大纲而证据覆盖可能不均的风险。

## 4. RAG 和知识库

- [ ] 能解释切片、Embedding、Milvus、Top-K 和来源引用。
- [ ] 能画出“上传文档到可检索”的完整链路。
- [ ] 能区分新知识库管理链、旧外部文档服务链和政策文档链。
- [ ] 能指出 `kb_<知识库名>` 与 DeepScout 固定 `knowledge_base` 的命名风险。
- [ ] 能说明政策搜索的 keyword/hybrid 当前为什么只是向量搜索。

### 4.1 知识库页面到向量库验收

- [ ] 能从 `KnowledgePage.handleUpload()` 追踪到 `POST /knowledge-bases/{kb_id}/documents`。
- [ ] 能区分上传接口成功、`pending`、`processing`、`completed` 和 `failed` 的含义。
- [ ] 能说明为什么前端每 3 秒轮询文档状态，以及组件卸载时如何清理定时器。
- [ ] 能按顺序解释后台任务中的 DocMind 解析、文本切片、Embedding 和 Milvus 写入。
- [ ] 能解释 `chunk_size=500`、`overlap=50` 对检索的影响。
- [ ] 能说明 PostgreSQL 的 `Document` 记录与 Milvus 的切片向量为什么要同时存在。
- [ ] 能追踪查看切片接口的权限检查、集合命名和 Milvus 查询。
- [ ] 能指出 Milvus 查询异常当前可能被降级为空数组，页面不一定展示真实故障。
- [ ] 能指出 `kb_<知识库名>` 与 V2 固定集合名之间的集成风险。
- [ ] 能提出用稳定 `kb_id`、统一配置或显式 `kb_name` 状态字段修复集合命名贯通问题。

## 6.1 长期记忆、数据库和附件验收

- [ ] 能区分 `KnowledgeBase/Document`、`LongTermMemory` 和 `ChatAttachment` 三类对象。
- [ ] 能说明长期记忆为什么同时写 PostgreSQL 和 Milvus。
- [ ] 能解释记忆检索如何用 Embedding、COSINE 和 `user_id` 过滤。
- [ ] 能指出普通聊天自动注入长期记忆当前没有被源码完全证明。
- [ ] 能解释数据库页的表白名单和分页请求。
- [ ] 能从 `/database/text2sql` 追踪 LLM 生成 SQL、SQL 校验、执行和结果返回。
- [ ] 能指出 Text2SQL 数据库不可用时可能走 `_get_mock_data()`。
- [ ] 能说明字符串 SQL 校验不是完整的生产安全边界。
- [ ] 能区分普通附件的 `/attachments`、附件状态轮询和 `/chat/completion/v3`。
- [ ] 能指出普通 PDF、Word、图片附件当前主要是占位文本，不等同于知识库 DocMind 解析。

## 12.1 行业资讯和招投标验收

- [ ] 能解释 `industryState.currentIndustryId` 如何影响资讯和招投标请求。
- [ ] 能说出 `/news/list` 和 `/news/bidding/list` 的筛选、分页和统计字段。
- [ ] 能解释新闻按 `source_url` 去重、招投标按 `bid_id` 去重。
- [ ] 能追踪手动采集从页面按钮到 Bocha/81API 再到 PostgreSQL 入库。
- [ ] 能解释 `success=true` 为什么仍可能伴随 `errors`。
- [ ] 能区分 `publish_time`、`collected_at`、`started_at` 和 `completed_at`。
- [ ] 能说明每日 12:00 APScheduler、启动时初始化采集和手动 `/news/collect` 的关系。
- [ ] 能指出 Bocha API Key、BID_APP_CODE、配额耗尽和外部请求失败的影响。
- [ ] 能提出采集任务幂等、重试、并发和监控方案。

## 13.1 外围支撑和兼容链路验收

- [ ] 能说明 `app_main.py` 导入、表创建、路由注册和生命周期启动的顺序。
- [ ] 能解释后端导入阶段 PostgreSQL 不可达为什么可能阻止服务启动。
- [ ] 能从首页行业卡片追踪到 `localStorage.selected_industry_id` 和 `/chat`。
- [ ] 能区分 AuthGuard、Axios JWT 请求头和后端 JWT 权限校验。
- [ ] 能区分 PostgreSQL 新会话系统与 Redis 旧 SessionService。
- [ ] 能说明 `/chat/completion`、`/chat/completion/v1`、`/chat/completion/v3` 的数据源和用途。
- [ ] 能区分外部 `DocumentService` 文档链和本地 DocMind/Milvus 知识库链。
- [ ] 能解释 `/search/web` 的 Serper 结果格式和 V2 Agent 搜索事件不是同一契约。
- [ ] 能指出 Markdown `dangerouslySetInnerHTML`、CORS 通配符和 JWT 默认密钥的安全检查点。
- [ ] 能用调用方判断某个文件属于 V1、V2、当前主路径或兼容路径。

源码证据：`knowledge_router.py`、`docmind_service.py`、`embedding_service.py`、`milvus_service.py`、`retrieval_service.py`、`policy_search_service.py`、`deep_research_v2/agents/scout.py`。

## 5. 代码解释器

- [ ] 能解释 LLM 负责生成和修正代码，执行环境负责真正运行代码。
- [ ] 能说出 CodeWizard 当前的语法检查、危险模式拦截、白名单 globals、`exec()`、输出捕获和图表保存流程。
- [ ] 能解释为什么进程内 `exec()` 不是生产级安全沙箱。
- [ ] 能说明代码错误如何反馈给 LLM，以及最多重试次数。

源码证据：`backend/app/service/deep_research_v2/agents/wizard.py`。

## 6. 数据库、缓存和记忆

- [ ] 能区分 PostgreSQL 会话系统和旧 Redis 会话系统。
- [ ] 能解释长期记忆如何向量化并写入 Milvus。
- [ ] 能指出普通聊天当前没有在每次 `get_chat_completion()` 调用中明确传入 `user_id` 的边界。
- [ ] 能说明附件聊天的 PDF、Word、图片处理与知识库 DocMind 链不是同一条路径。

## 7. 数据分析和 Text2SQL

- [ ] 能说明 Text2SQL 在真实数据库不可用时可能进入 mock 数据路径。
- [ ] 能区分数据分析 Agent 生成分析意图、CodeWizard 执行代码和图表渲染。
- [ ] 能指出 `ChartGenerator.merge_configs()` 当前为空实现。

## 8. 工程运行和排错

- [ ] 能从配置文件找出 LLM、数据库、Redis、Milvus、搜索服务和 DocMind 的依赖。
- [ ] 能解释 Docker 缺失时为什么无法完成真实端到端验证。
- [ ] 能检查密钥是否来自环境变量，避免把真实密钥提交到仓库。
- [ ] 能用 `python -m compileall -q backend/app` 验证 Python 语法。
- [ ] 能用 `npm run build` 验证前端构建。

## 9. 面试表达验收

- [ ] 能用 90 秒讲清项目解决的问题、核心架构和 V2 主链路。
- [ ] 能用 3 分钟讲清一次研究请求的完整数据流。
- [ ] 能诚实区分“当前实现”“设计目标”和“尚未验证”。
- [ ] 能主动说出至少三个工程风险，并给出修复方案。

## 9.1 前端数据流验收

- [ ] 能从 `main.tsx` 说明 React 如何挂载，并解释 `App` 中 `ConfigProvider`、`AntdApp` 和 `Router` 的关系。
- [ ] 能画出 `routes.tsx` 中 `/login` 与 `AuthGuard → BaseLayout → 页面路由` 的层级。
- [ ] 能说明 Axios 的 `authPlugin`、`servicePlugin`、`loadingPlugin`、`repeatPlugin` 和 `errorToastPlugin` 各自处理什么问题。
- [ ] 能解释 `deviceState.searchModes` 如何影响 `/research/stream` 的 `search_modes` 请求字段。
- [ ] 能区分 `researchSteps`、`researchDetailsRef`、`selectedResearchDetail` 和 `researchDataVersion` 的职责。
- [ ] 能把 `research_step`、`search_results`、`knowledge_graph`、`charts`、`research_complete` 映射到最终研究详情组件。
- [ ] 能解释 `ReadableStream` 为什么需要缓冲区并按换行解析 SSE。
- [ ] 能区分 `/sessions/{id}` 的消息恢复和 `/research/checkpoint/{id}/full` 的研究 UI 状态恢复。
- [ ] 能指出 `AuthGuard` 只是前端导航控制，不能代替后端权限校验。
- [ ] 能指出历史消息通过内容长度判断 DeepResearch 存在误判风险。

## 10. 尚未完成的运行证据

- [ ] Docker Compose 在当前机器可用并启动成功。
- [ ] PostgreSQL、Redis、Milvus、Elasticsearch/外部搜索和 DocMind 完成真实连通性验证。
- [ ] 真实上传文档后能在目标 Milvus 集合中查到切片。
- [ ] 真实 `/research/stream` 请求能收到完整 SSE 事件并渲染到前端。

这些项目依赖外部服务和当前机器环境，不能用静态阅读替代。

## 10.1 最近追加的源码理解验收

- [ ] 能区分数据库页 visualization_hint 与 DeepResearch V2 的 charts SSE 图表链。
- [ ] 能从 DataAnalyst 追踪到 state["charts"]、charts 事件、React researchDataVersion 和 ECharts 渲染。
- [ ] 能说明 POST /research/stream 默认 V2、GET /research/stream 默认 V1。
- [ ] 能区分 V1 ReAct、V1 classic fallback 与 V2 _run_simplified()。
- [ ] 能解释工具注册不等于工具真实调用。
- [ ] 能画出 app_main.py 导入、create_all、lifespan、路由注册和监听端口的顺序。
- [ ] 能说明 Docker Compose 只提供基础设施，后端和前端需要单独启动。
- [ ] 能区分 ResearchCheckpoint.state_json 与 ui_state_json。

## 11. 我的学习记录

### 已掌握

<!-- 写下已经能独立解释的模块 -->


### 需要补课

<!-- 写下仍然混淆的概念或文件 -->


### 下一次要追踪的请求

<!-- 记录一个具体问题、入口接口和预期日志 -->

## 12. 业务数据域

- [ ] 能解释行业配置如何提供新闻、招投标和研究关键词。
- [ ] 能画出 Bocha/81API 到 IndustryNews、BiddingInfo 的入库链路。
- [ ] 能说明新闻按 source_url 去重、招投标按 bid_id 去重的区别。
- [ ] 能区分 publish_time、collected_at 和 NewsCollectionTask 的完成时间。
- [ ] 能解释每日 12:00 APScheduler 任务和手动 /news/collect 的关系。
- [ ] 能说明 success=true 为什么仍可能伴随 errors。

源码证据：`backend/app/config/industry_config.py`、`backend/app/service/news_collection_service.py`、`backend/app/service/scheduler_service.py`、`backend/app/router/news_router.py`、`backend/app/models/news.py`。

## 14. 行业资讯和招投标闭环验收

- [ ] 能解释 `IndustryConfig` 的四类字段和默认行业回退。
- [ ] 能从 `news_keywords` 追踪到 Bocha 搜索和 `IndustryNews` 入库。
- [ ] 能从 `bidding_keywords` 追踪到 81API 招标/中标查询和 `BiddingInfo` 入库。
- [ ] 能区分新闻按 `source_url` 去重、招投标按 `bid_id` 去重。
- [ ] 能解释 `NewsCollectionTask` 如何记录 running、completed、failed 和错误。
- [ ] 能说明 `success=True` 为什么仍可能带有 `errors`。
- [ ] 能列出 `/news/list`、`/news/bidding/list`、`/news/collect` 和调度状态接口。
- [ ] 能指出 `/news/collect` 当前直接等待 `collect_all()`，`BackgroundTasks` 声明没有实际入队。
- [ ] 能说明 APScheduler 每日 12:00 任务与启动时无数据初始化的区别。
- [ ] 能从新闻页或招投标页的行业筛选追踪到 `industry_id` 请求参数。
- [ ] 能指出 Bocha、81API、数据库、配额和 TLS 验证的运行限制。

源码证据：`backend/app/config/industry_config.py`、`backend/app/service/news_collection_service.py`、`backend/app/service/bidding_service.py`、`backend/app/service/scheduler_service.py`、`backend/app/router/news_router.py`、`backend/app/models/news.py`、`frontend/src/api/news.ts`、`frontend/src/pages/news/index.tsx`、`frontend/src/pages/bidding/index.tsx`。

## 15. 检查点、取消和恢复验收

- [ ] 能区分 `ResearchState`、`ui_state_json` 和会话消息的职责。
- [ ] 能说出 `ResearchCheckpoint` 中 `state_json`、`ui_state_json`、`final_report` 和 `status` 的作用。
- [ ] 能追踪 V2 在规划、搜索、分析和写作阶段保存检查点的时机。
- [ ] 能说明 `update_ui_state()` 如何把 facts、charts、knowledge_graph 和 references 转成前端结构。
- [ ] 能列出检查点概要、完整检查点、列表、删除和恢复接口。
- [ ] 能解释 Redis 取消 key 的格式和 300 秒 TTL。
- [ ] 能说明取消是协作式检查，不是强制终止当前外部请求。
- [ ] 能解释页面刷新为什么要同时加载会话消息和完整检查点。
- [ ] 能指出当前 `resume=True` 会载入状态，但 `_run_simplified()` 仍从规划入口执行。
- [ ] 能指出取消分支当前没有明确把检查点更新为 `paused` 的源码证据。
- [ ] 能区分“检查点保存成功”和“研究最终完成”。

源码证据：`backend/app/models/research.py`、`backend/app/service/checkpoint_service.py`、`backend/app/service/deep_research_v2/graph.py`、`backend/app/router/research_router.py`、`backend/app/core/redis_client.py`、`frontend/src/api/session.ts`、`frontend/src/pages/chat/index.tsx`。

## 16. 工程外围和页面地图验收

- [ ] 能区分根 `docker-compose.yml` 和 `backend/docker-compose-base.yml` 启动的服务集合。
- [ ] 能列出 `01-init.sql` 创建的核心业务表和 Text2SQL 示例表。
- [ ] 能区分 `init_industry_data.py` 与 `seed_industry_data.py` 的行业和数据用途。
- [ ] 能说明 V2 测试脚本需要哪些外部 Key，以及它为什么不是纯单元测试。
- [ ] 能画出 `/`、`/chat`、`/knowledge`、`/memory`、`/database`、`/news`、`/bidding` 的路由地图。
- [ ] 能解释行业状态如何从首页进入 Valtio、localStorage 和后端请求参数。
- [ ] 能说明知识库页面为什么需要文档状态轮询。
- [ ] 能识别 `/memory` 页面已实现但侧边栏入口仍显示“暂未开放”的代码与产品不一致。
- [ ] 能说明 SQL 示例表与实时行情 API、行业资讯入库之间的区别。

源码证据：`docker/init-db/01-init.sql`、`backend/app/scripts/`、`backend/docker-compose-base.yml`、`frontend/src/router/routes.tsx`、`frontend/src/layout/base/nav.tsx`、`frontend/src/store/industry.ts`、`frontend/src/pages/index/index.tsx`、`frontend/src/pages/knowledge/index.tsx`、`frontend/src/pages/memory/index.tsx`、`frontend/src/pages/database/index.tsx`。

## 17. 配置、安全和前端基础设施验收

- [ ] 能解释 `LLMConfig`、`ServiceConfig` 和直接读取环境变量的区别。
- [ ] 能指出 `LLM_BASE_URL` 与 `DASHSCOPE_BASE_URL` 的读取差异及配置漂移风险。
- [ ] 能追踪 LLM、搜索、数据库和 JWT 环境变量的读取与使用。
- [ ] 能说明 `pool_pre_ping` 不能替代数据库连通性。
- [ ] 能解释 bcrypt 密码哈希、JWT `sub` 和 `exp` 的作用。
- [ ] 能说明 AuthGuard 和后端 JWT 权限校验不是同一层安全机制。
- [ ] 能解释 Axios 类型扩展为什么必须结合 plugins 才有运行时效果。
- [ ] 能区分前端 TypeScript 类型、后端 JSON 和 SSE 运行时校验。
- [ ] 能说明 `proxyWithPersist()` 的版本迁移与 localStorage 行业状态不是同一实现。
- [ ] 能解释 `usePageTransport()` 为什么是一次性内存传输而不是持久化。
- [ ] 能指出旧兼容配置中的硬编码默认值风险，并提出环境变量化方案。

源码证据：`backend/app/config/llm_config.py`、`backend/app/service/config.py`、`backend/app/core/database.py`、`backend/app/core/security.py`、`frontend/src/api/request/axios-extend.d.ts`、`frontend/src/api/session.type.d.ts`、`frontend/src/store/valtio-persist.ts`、`frontend/src/utils/usePageTransport.ts`。

## 18. 模型、Schema 与前端基础契约验收

- [ ] 能区分 SQLAlchemy 模型、Pydantic Schema 和 TypeScript 类型分别在哪个边界生效。
- [ ] 能画出 `User`、`ChatSession`、`ChatMessage`、`ChatAttachment`、`KnowledgeBase`、`Document` 和 `ResearchCheckpoint` 的关系。
- [ ] 能解释 `Document`、`ChatAttachment` 和旧外部文档服务 `DocumentResponse` 的区别。
- [ ] 能说明 `ResearchCheckpoint.state_json`、`ui_state_json` 和 `final_report` 为什么要分开保存。
- [ ] 能从 `ChatRequest` 追踪到普通聊天接口，并说明 DeepResearch SSE 为什么不等同于 `ChatResponse`。
- [ ] 能解释 `Config.from_attributes = True` 的作用和局限。
- [ ] 能说明 `API.ChatItem`、`ResearchStep`、`ChartConfig` 是编译期类型，不是运行时校验器。
- [ ] 能解释 Axios 的认证、加载、重复请求和错误提示插件分别解决什么问题。
- [ ] 能说明 `unwrap: true` 为什么会造成调用方对 `res.data` 和 `res` 的兼容写法。
- [ ] 能解释 `NavItem` 有 `onClick` 时为什么会阻止路由跳转，并指出记忆页入口的不一致。
- [ ] 能画出 `setPageTransport()` 到 `usePageTransport()` 的一次性传值流程。
- [ ] 能区分前端 `API.Document`、浏览器 `File` 和后端 SQLAlchemy `Document`。
- [ ] 能说明 `proxyWithPersist()` 的 SingleFile/MultiFile、版本迁移和 `_persist.loaded` 各自做什么。
- [ ] 能解释 `ChatType.Deepsearch` 如何影响聊天布局、SSE 解析和研究详情恢复。

源码证据：`backend/app/models/`、`backend/app/schemas/`、`frontend/src/api/type.d.ts`、`frontend/src/api/session.type.d.ts`、`frontend/src/api/request/`、`frontend/src/layout/base/nav-item.tsx`、`frontend/src/layout/base/nav.tsx`、`frontend/src/pages/chat/shared.ts`、`frontend/src/pages/chat/component/select-file.tsx`、`frontend/src/store/valtio-persist.ts`、`frontend/src/utils/usePageTransport.ts`。

## 19. 前端基础展示与路由辅助验收

- [ ] 能解释 `RouterContext`、`useRoute()` 和 `useQuery()` 的职责边界。
- [ ] 能说明 `ChatMessage` 为什么只负责按角色分派展示，发送请求由父页面完成。
- [ ] 能追踪 `Source`、`Drawer` 和 `search_results` 的展示关系。
- [ ] 能区分静态演示新闻组件和真实行业资讯页面的数据来源。
- [ ] 能区分 `visualization_hint`、`ChartConfig` 和真正的 ECharts 渲染。
- [ ] 能解释 `ResponseError` 为什么要保留 Axios response。
- [ ] 能说明 Axios 插件的 `preinstall`、`install`、`postinstall` 顺序。
- [ ] 能从用户菜单追踪到前端 logout 和 `/login` 跳转，并说明服务端 JWT 失效边界。
- [ ] 能区分 `storage.ts` 的存储适配、`valtio-persist.ts` 的持久化策略和具体 store 的业务状态。
- [ ] 能说明 404 页面和加载动画分别属于什么层次。

源码证据：`frontend/src/router/context.ts`、`frontend/src/router/hook.ts`、`frontend/src/pages/chat/component/chat-message.tsx`、`frontend/src/pages/chat/component/drawer.tsx`、`frontend/src/pages/chat/component/source.tsx`、`frontend/src/pages/chat/component/news.tsx`、`frontend/src/components/chart/types.ts`、`frontend/src/api/request/error.ts`、`frontend/src/api/request/plugins/plugin.ts`、`frontend/src/layout/base/footer.tsx`、`frontend/src/store/storage.ts`、`frontend/src/pages/404.tsx`。

## 20. 工程配置、依赖与启动契约验收

- [ ] 能画出 Docker 中间件、FastAPI 和 Vite 的启动层次。
- [ ] 能列出根 `docker-compose.yml` 与 `backend/docker-compose-base.yml` 的服务差异。
- [ ] 能说明 `start-services.sh clean` 为什么可能造成不可逆数据删除。
- [ ] 能按 Web、数据库、LLM、向量库、文档解析和数据分析解释后端依赖。
- [ ] 能从三个环境变量找到对应的实际读取代码和调用场景。
- [ ] 能说明 `VITE_API_BASE`、`VITE_API_PROXY` 和 Vite `5183` 端口的关系。
- [ ] 能指出 README、Compose 和源码之间的配置差异，并说明源码或实际日志为何更可靠。
- [ ] 能按容器、数据库、后端、前端、外部服务的顺序分层排错。
- [ ] 能解释“容器健康”“后端启动”“完整研究成功”分别需要什么证据。

源码证据：根 `docker-compose.yml`、`backend/docker-compose-base.yml`、`start-services.sh`、`backend/requirements.txt`、`backend/.env.example`、`frontend/package.json`、`frontend/vite.config.ts`、`frontend/.env`、`READMED.md`。

## 21. 用户认证从注册到授权验收

- [ ] 能列出 `User` 表的公开字段、敏感字段和关联关系。
- [ ] 能区分 `UserCreate`、`UserLogin`、`UserResponse`、`UserInDB` 和 `TokenResponse`。
- [ ] 能画出注册和登录的完整请求时序。
- [ ] 能解释 bcrypt 哈希、JWT `sub`、`exp` 和数据库用户查询的关系。
- [ ] 能比较 `get_current_user()` 和 `get_current_user_required()`。
- [ ] 能说明 Axios 如何附加 `Authorization: Bearer` 请求头。
- [ ] 能解释 AuthGuard 的导航作用和后端鉴权的区别。
- [ ] 能说明登录后如何回到原始路径。
- [ ] 能指出当前登出接口没有实现服务端 JWT 撤销的源码证据。
- [ ] 能列出硬编码 JWT 密钥、localStorage Token 和可选认证误用等风险。

源码证据：`backend/app/models/user.py`、`backend/app/schemas/user.py`、`backend/app/router/auth_router.py`、`backend/app/core/security.py`、`frontend/src/api/auth.ts`、`frontend/src/store/auth.ts`、`frontend/src/api/request/plugins/auth.ts`、`frontend/src/components/auth-guard/index.tsx`、`frontend/src/pages/auth/login.tsx`。

## 22. 测试夹具、Mock 与样例资产验收

- [ ] 能说明 `frontend/mock/session.ts` 如何模拟 SSE，并知道当前 Mock 默认关闭。
- [ ] 能区分 Mock 的旧事件格式和当前 V2 事件格式。
- [ ] 能说明 `test_deep_research_v2.py` 为什么依赖真实 LLM、搜索 API 和外部网络。
- [ ] 能区分测试输入、历史生成 PNG 和真实运行产物。
- [ ] 能说明根目录 PDF 从存在到可检索需要哪些观测证据。
- [ ] 能区分前端 Mock 验证、脚本测试和真实端到端验证的证明范围。

源码证据：`frontend/mock/session.ts`、`frontend/mock/data/chat`、`frontend/mock/data/deepsearch`、`frontend/vite.config.ts`、`backend/app/scripts/test_deep_research_v2.py`、`backend/test/`、根目录 `data/`。

## 23. 旧文档服务与直接搜索兼容链验收

- [ ] 能列出 `/documents/*` 和 `/knowledge-bases/*/documents` 的接口差异。
- [ ] 能解释旧文档上传的临时文件、DocMind 处理和外部 dataset 配置。
- [ ] 能指出 `document None` 被降级为空列表可能掩盖外部服务异常。
- [ ] 能说明旧文档 Router 当前缺少强制用户认证的边界。
- [ ] 能解释 `/search/web` 的 Serper JSON 契约。
- [ ] 能区分 `/search/web` 和 V2 `DeepScout` 的 API、状态、事件和前端入口。
- [ ] 能指出 `/tmp/{filename}` 的并发覆盖、路径字符和跨平台风险。
- [ ] 能提出兼容链逐步收敛或统一配置的方案。

源码证据：`backend/app/router/document_router.py`、`backend/app/service/document_service.py`、`backend/app/service/docmind_service.py`、`backend/app/router/search_router.py`、`backend/app/service/web_search_service.py`、`backend/app/service/deep_research_v2/agents/scout.py`。

## 24. 配置漂移与构建检查验收

- [ ] 能指出两份后端 requirements 文件及其可能造成的环境差异。
- [ ] 能区分 Vite build、TypeScript `tsc` 和 ESLint 的证明范围。
- [ ] 能解释当前项目为什么可能出现“build 通过但 tsc/lint 失败”。
- [ ] 能举出一个前端类型契约不一致的实际证据。
- [ ] 能从 `VITE_API_BASE` 和 `DASHSCOPE_BASE_URL` 追踪到真实读取点。
- [ ] 能说明前端 `VITE_` 变量与后端密钥的暴露边界。
- [ ] 能按运行日志、源码、README 的证据等级处理配置冲突。

源码证据：`backend/requirements.txt`、`backend/app/requirements.txt`、`frontend/package.json`、`frontend/tsconfig.app.json`、`frontend/vite.config.ts`、`frontend/.env`、`backend/.env.example`、`backend/app/config/llm_config.py`、`backend/app/service/config.py`。

## 13. 股票行情链路验收

- [ ] 能从用户问题追踪到 `find_company_in_query()` 的静态公司映射。
- [ ] 能解释 `sh`、`sz` 股票代码标准化规则及其适用范围。
- [ ] 能说出 `JUHE_STOCK_API_KEY`、超时和结构化失败返回的作用。
- [ ] 能解释 V2 `DeepScout` 为什么最多查询两只股票。
- [ ] 能区分行情数据写入 `data_points` 与发送 `stock_quote` 的两个用途。
- [ ] 能从 `chat/index.tsx` 追踪 `stock_quote` 到 `target.stockQuote`。
- [ ] 能解释 `result.tsx` 和 `StockCard` 如何展示行情。
- [ ] 能区分 V2 Scout 自动行情查询和 V1 `ToolExecutor.execute_stock_query()`。
- [ ] 能指出静态映射、无缓存、无行情时间戳和第三方 API 依赖等限制。

源码证据：`backend/app/config/stock_mapping.py`、`backend/app/service/stock_service.py`、`backend/app/service/deep_research_v2/agents/scout.py`、`frontend/src/pages/chat/index.tsx`、`frontend/src/pages/chat/component/result.tsx`、`frontend/src/components/stock-card/index.tsx`。

