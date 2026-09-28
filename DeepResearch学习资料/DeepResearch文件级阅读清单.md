# DeepResearch 文件级阅读清单

项目：D:\课\s4-6\industry_information_assistant

状态说明：已核对表示已纳入第一轮源码阅读和教学材料；外部服务运行状态另见总册的证据边界。

## 一、后端入口、配置和核心

- backend/app/app_main.py：FastAPI 入口、CORS、建表、路由和生命周期。
- backend/app/config/__init__.py
- backend/app/config/llm_config.py：模型、Agent、搜索和研究配置。
- backend/app/config/industry_config.py：行业关键词。
- backend/app/config/stock_mapping.py：股票名称映射。
- backend/app/core/__init__.py
- backend/app/core/database.py：SQLAlchemy engine 和 Session。
- backend/app/core/redis_client.py：Redis 连接和缓存。
- backend/app/core/security.py：bcrypt、JWT 和认证依赖。

## 二、后端模型和 Schema

- backend/app/models/__init__.py
- backend/app/models/user.py
- backend/app/models/chat.py
- backend/app/models/knowledge.py
- backend/app/models/research.py
- backend/app/models/industry_data.py
- backend/app/models/news.py
- backend/app/schemas/__init__.py
- backend/app/schemas/user.py
- backend/app/schemas/chat.py
- backend/app/schemas/document.py
- backend/app/schemas/knowledge.py
- backend/app/schemas/search.py

## 三、后端 Router

- backend/app/router/__init__.py
- backend/app/router/auth_router.py
- backend/app/router/session_router.py
- backend/app/router/chat_router.py
- backend/app/router/research_router.py
- backend/app/router/knowledge_router.py
- backend/app/router/attachment_router.py
- backend/app/router/document_router.py
- backend/app/router/memory_router.py
- backend/app/router/database_router.py
- backend/app/router/search_router.py
- backend/app/router/news_router.py

## 四、DeepResearch V2

- backend/app/service/deep_research_v2/__init__.py
- backend/app/service/deep_research_v2/state.py：ResearchState、阶段枚举和初始状态。
- backend/app/service/deep_research_v2/graph.py：Graph、简化执行器、队列、检查点、取消和审核循环。
- backend/app/service/deep_research_v2/service.py：V2 服务入口和 SSE 格式化。
- backend/app/service/deep_research_v2/agents/__init__.py
- backend/app/service/deep_research_v2/agents/base.py：LLM 调用、JSON 解析、消息队列和通用日志。
- backend/app/service/deep_research_v2/agents/architect.py：规划。
- backend/app/service/deep_research_v2/agents/scout.py：网络搜索、本地检索、网页深读和事实整理。
- backend/app/service/deep_research_v2/agents/data_analyst.py：结构化数据、知识图谱、ECharts。
- backend/app/service/deep_research_v2/agents/wizard.py：Python 代码生成、执行、自修复和 PNG 图表。
- backend/app/service/deep_research_v2/agents/writer.py：章节和完整报告。
- backend/app/service/deep_research_v2/agents/critic.py：审核、补搜和修订。

## 五、通用后端 Service

- backend/app/service/__init__.py
- backend/app/service/config.py：旧服务配置。
- backend/app/service/chat_service.py：普通聊天旧链。
- backend/app/service/chat_service_v2.py：普通聊天新链。
- backend/app/service/session_service.py：会话和消息。
- backend/app/service/react_controller.py：V1 ReAct 控制器。
- backend/app/service/dr_g.py：旧研究兼容和事件序列化。
- backend/app/service/tool_executor.py：V1 工具分发。
- backend/app/service/web_search_service.py：网络搜索。
- backend/app/service/retrieval_service.py：文档检索。
- backend/app/service/embedding_service.py：Embedding。
- backend/app/service/milvus_service.py：向量集合、写入和查询。
- backend/app/service/document_service.py：文档状态和元数据。
- backend/app/service/docmind_service.py：DocMind 解析和切片。
- backend/app/service/memory_service.py：长期记忆。
- backend/app/service/text2sql_service.py：自然语言到 SQL、只读检查和执行。
- backend/app/service/database_explorer.py：数据库表和 Schema 浏览。
- backend/app/service/smart_analyzer.py：结构化分析。
- backend/app/service/chart_generator.py：图表配置。
- backend/app/service/checkpoint_service.py：研究检查点。
- backend/app/service/news_collection_service.py：行业新闻采集。
- backend/app/service/bidding_service.py：招投标查询和采集。
- backend/app/service/stock_service.py：股票行情。
- backend/app/service/policy_search_service.py：政策检索。
- backend/app/service/scheduler_service.py：定时调度。

## 六、脚本、依赖和后端测试资产

- backend/app/scripts/init_industry_data.py：行业数据初始化。
- backend/app/scripts/seed_industry_data.py：样例行业数据。
- backend/app/scripts/test_deep_research_v2.py：依赖真实外部服务的测试脚本。
- backend/requirements.txt、backend/app/requirements.txt：两份依赖清单。
- backend/.env.example：环境变量模板。
- backend/Dockerfile、backend/docker-compose-base.yml：后端镜像和基础服务配置。
- backend/test/test_doc.pdf：文档测试输入。
- backend/test/数据.xlsx：表格测试输入。
- backend/test/*.png：历史图表输出。

## 七、前端应用入口、请求和状态

- frontend/src/main.tsx：React 挂载入口。
- frontend/src/App.tsx：应用壳。
- frontend/src/router/context.ts、hook.ts、index.tsx、routes.tsx：路由系统。
- frontend/src/api/index.ts：API 汇总。
- frontend/src/api/auth.ts、session.ts、knowledge.ts、memory.ts、database.ts、news.ts：请求函数。
- frontend/src/api/type.d.ts、session.type.d.ts、request/axios-extend.d.ts：前端类型契约。
- frontend/src/api/request/request.ts、index.ts：Axios/fetch 请求创建。
- frontend/src/api/request/plugins/plugin.ts：请求插件协议。
- frontend/src/api/request/plugins/auth.ts：Bearer token。
- frontend/src/api/request/plugins/loading.ts：加载状态。
- frontend/src/api/request/plugins/error-toast.ts：错误提示。
- frontend/src/api/request/plugins/repeat.ts：重复请求控制。
- frontend/src/api/request/plugins/service.ts：请求服务封装。
- frontend/src/store/auth.ts、session.ts、knowledge.ts、industry.ts、device.ts：全局状态。
- frontend/src/store/storage.ts、valtio-persist.ts：持久化。
- frontend/src/utils/index.ts、usePageTransport.ts：工具和页面传值。

## 八、前端页面

- frontend/src/pages/auth/login.tsx：登录和注册。
- frontend/src/pages/index/index.tsx：首页。
- frontend/src/pages/chat/index.tsx：普通聊天、DeepResearch、SSE、取消和恢复。
- frontend/src/pages/chat/newchat.tsx：新会话。
- frontend/src/pages/chat/shared.ts：聊天共享类型和工具。
- frontend/src/pages/knowledge/index.tsx：知识库和文档上传。
- frontend/src/pages/memory/index.tsx：长期记忆。
- frontend/src/pages/database/index.tsx：数据库浏览和 Text2SQL。
- frontend/src/pages/news/index.tsx：行业资讯。
- frontend/src/pages/bidding/index.tsx：招投标。
- frontend/src/pages/404.tsx：兜底页面。

## 九、前端研究组件和通用组件

- frontend/src/pages/chat/component/research-detail/index.tsx：研究详情容器。
- frontend/src/pages/chat/component/research-detail/search-results.tsx：搜索结果。
- frontend/src/pages/chat/component/research-detail/knowledge-graph.tsx：知识图谱。
- frontend/src/pages/chat/component/research-detail/visualization.tsx：ECharts 和 PNG。
- frontend/src/pages/chat/component/research-detail/process-report.tsx：过程报告。
- frontend/src/pages/chat/component/research-process/index.tsx：研究步骤。
- frontend/src/pages/chat/component/step-detail-panel/index.tsx：步骤详情。
- frontend/src/pages/chat/component/result.tsx：聊天结果。
- frontend/src/pages/chat/component/chat-message.tsx：消息展示。
- frontend/src/pages/chat/component/select-file.tsx：附件选择。
- frontend/src/pages/chat/component/source.tsx：来源展示。
- frontend/src/components/auth-guard/index.tsx：前端登录守卫。
- frontend/src/components/chart/index.tsx、types.ts：通用图表。
- frontend/src/components/markdown/index.tsx：Markdown。
- frontend/src/components/rich-content/index.tsx：富内容。
- frontend/src/components/sender/index.tsx：发送输入框。
- frontend/src/components/session-drawer/index.tsx：会话抽屉。
- frontend/src/components/upload-modal/index.tsx：上传弹窗。
- frontend/src/components/chunks-drawer/index.tsx：文档切片。
- frontend/src/components/stock-card/index.tsx：股票卡片。
- frontend/src/components/page-layout/index.tsx：页面布局。
- frontend/src/components/spin/spinner.tsx：加载动画。

## 十、前端静态资源和配置

- frontend/src/assets/chat：聊天图标、头像、来源、搜索、文件等。
- frontend/src/assets/layout：导航图标。
- frontend/src/assets/index、component：首页和通用资源。
- frontend/src/layout/base：导航、页脚和基础布局。
- frontend/src/configs/index.ts、enum.ts、data/host.ts、data/news.ts：前端配置。
- frontend/src/index.css、antd.scss、各页面和组件的 scss：样式。
- frontend/vite.config.ts：端口 5183、代理和 Mock 插件。
- frontend/package.json、package-lock.json：Node 依赖和脚本。
- frontend/tsconfig*.json、eslint.config.js、.prettierrc：构建、类型和格式配置。
- frontend/mock/session.ts、mock/data/chat、mock/data/deepsearch：Mock 资产，当前 Vite Mock 插件配置为关闭。

## 十一、阅读完成后的主线索引

登录主线：login.tsx → auth.ts → auth_router.py → security.py → store/auth.ts → auth plugin。

研究主线：chat/index.tsx → session.ts → research_router.py → deep_research_v2/service.py → graph.py → state.py → six agents → SSE → research-detail。

RAG 主线：knowledge/index.tsx → knowledge.ts → knowledge_router.py → document_service.py/docmind_service.py → embedding_service.py → milvus_service.py → scout.py。

普通聊天主线：chat/index.tsx → chat API → chat_router.py → chat_service_v2.py → retrieval/embedding/Milvus → LLM → ReadableStream。

Text2SQL 主线：database/index.tsx → database.ts → database_router.py → text2sql_service.py/database_explorer.py → PostgreSQL 或 mock fallback。

行业主线：news/bidding 页面 → news.ts/news_router.py → collection/bidding service → 外部 API → PostgreSQL → 列表和统计。

## 十二、未验证不等于未阅读

源码阅读可以确认调用关系、字段、分支和实现边界；它不能替代真实外部服务运行。Docker、数据库、Milvus、DocMind、搜索 API 和 LLM 的端到端验证需在依赖可用后追加。
