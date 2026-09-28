# DeepResearch 源码覆盖审计

## 审计口径

本审计针对本地项目 `D:\课\s4-6\industry_information_assistant`。统计排除了 `frontend/node_modules`、`frontend/dist`、Python `__pycache__` 和 `.pyc` 文件，因为它们不是项目业务源码。

## 当前统计

统计分成两种口径：后端按 `backend/app` 下的 Python 文件统计；前端把 TypeScript/TSX 业务源码与样式、图片、SVG 静态资源分开统计。这样不会把“可执行代码文件”和“界面资源”混在一个数字里。

| 区域 | 文件数 | 代码/配置行数（约） | 已核对范围 |
|---|---:|---:|---|
| `backend/app` Python 源文件 | 75 | 20,717 | 入口、路由、模型、Schema、服务、V1/V2、脚本 |
| `frontend/src` TypeScript/TSX 源文件 | 81 | 11,310 | 路由、页面、组件、API、状态、请求插件 |
| `frontend/src` 样式和静态资源 | 78 | 未按代码行统计 | SCSS/CSS、PNG、SVG |
| 根目录配置与脚本 | 3 | 584 | Docker Compose、启动脚本、项目说明 |
| 可执行/类型代码合计 | 156 | 32,027 | 后端 Python + 前端 TypeScript/TSX |

## 全项目清点补充

排除 `frontend/node_modules`、`frontend/dist`、Python `__pycache__`、`.pyc` 和 `.DS_Store` 后，项目当前约有 291 个非生成文件。除业务代码外，还包括：

- `backend/requirements.txt` 与 `backend/app/requirements.txt` 两份依赖清单。
- 根 `docker-compose.yml`、`docker/init-db/01-init.sql`、`start-services.sh`。
- `backend/.env.example`、两个 README、前端 `.env`、Vite/TypeScript 配置和 `package-lock.json`。
- 根 `data/` 的 4 份 PDF 样例资产。
- `backend/test/` 的 PDF、Excel 和 PNG 测试输入/历史输出。
- `frontend/mock/` 的 Mock SSE 路由和聊天/研究样例数据。

这些文件已经在第 40、42、44 课和本审计中单独标注。它们不是全部“业务代码”，但会影响启动、测试、数据导入和新手学习结果。

## 后端覆盖

- `app_main.py`：FastAPI 入口、CORS、模型注册、路由注册、生命周期调度器。
- `router/`：认证、会话、聊天、研究、知识库、附件、记忆、数据库、文档、搜索、新闻和招投标接口。
- `models/`：用户、会话、消息、附件、长期记忆、知识库、文档、行业数据、新闻、招投标、研究检查点。
- `schemas/`：认证、会话、聊天、附件、文档、知识库和搜索的数据契约。
- `service/deep_research_v2/`：状态、图流程、服务入口和六个 Agent。
- `service/`：V1 ReAct、工具执行、搜索、文档、Embedding、Milvus、Text2SQL、数据分析、图表、股票、招投标、新闻、记忆和检查点。
- `config/`：LLM/Agent 配置、行业关键词、股票映射。
- `scripts/`：行业数据初始化、种子数据和 DeepResearch 测试脚本。

第 38 课继续核对了模型、Schema 和前端基础契约：`models/__init__.py` 集中导入数据库模型；`schemas/` 区分请求校验、响应转换和旧兼容接口；`api/type.d.ts`、`api/session.type.d.ts` 只提供前端编译期类型；Axios 插件统一处理认证、加载、重复请求和错误提示；`usePageTransport()` 是一次性内存传值，`proxyWithPersist()` 是带版本迁移的持久化工具；`select-file.tsx` 的文档引用对象与数据库 `Document`、浏览器 `File` 不是同一类型。

第 39 至 44 课继续核对了低业务复杂度但会影响工程判断的文件：路由 Context/hooks、聊天展示组件、图表类型、存储适配器、前端 Mock、两套 Compose、用户认证、旧文档/Serper 兼容接口、两份后端 requirements 以及 Vite/TypeScript/ESLint 的检查边界。验证结果为 Python 编译通过、Vite build 通过，TypeScript 严格检查和 ESLint 仍有项目既有错误，未修改用户项目源码。

## 前端覆盖

- `router/` 和 `components/auth-guard/`：页面路由和登录保护。
- `pages/auth`：登录和注册。
- `pages/chat`：普通聊天、附件、DeepResearch SSE、研究步骤、搜索结果、图谱、图表、报告和恢复。
- `pages/knowledge` 与 `components/chunks-drawer`：知识库、文档上传、删除和切片查看。
- `pages/memory`：记忆列表、搜索、创建和删除。
- `pages/database`、`news`、`bidding`：行业数据、新闻和招投标页面。
- `api/`：认证、会话、研究、附件、知识库、记忆、数据库和新闻请求。
- `store/`：认证、会话、知识库、设备、行业和持久化状态。
- `components/`：Markdown、RichContent、ECharts、上传、会话抽屉和布局组件。

## 已确认的真实运行边界

1. `POST /research/stream` 默认使用 V2；V2 的 `run()` 当前默认执行 `_run_simplified()`，不是被注释的 LangGraph 分支。
2. README 的前端端口 `5173` 与当前 `frontend/vite.config.ts` 的 `5183` 不一致，以源码为准。
3. Docker 当前环境不可用，因此 PostgreSQL、Redis、Milvus 和 Elasticsearch 尚未在本机完成真实启动验证。
4. 后端 `python -m compileall -q app` 通过；前端 `npm run build` 通过，只有 bundle 过大的警告。
5. `CodeWizard` 是进程内简化沙箱；源码明确建议生产环境使用更强的隔离方案。
6. `DeepScout.deep_read_url()` 当前是 requests/HTML 简化抓取，不是真正的 Headless Browser。
7. `PolicySearchService` 的部分检索方式存在向量搜索降级行为。
8. `ChartGenerator.merge_configs()` 当前保留空实现，不能按函数名假定它已经完成。
9. `tool_executor.py` 对未配置的 Text2SQL、股票和招投标能力有明确的 fallback/错误返回。
10. 项目目录没有 Git 元数据；不能从提交历史判断版本演进，也不能仅凭这个目录直接产生 GitHub 贡献记录。

## 阅读结论

项目的主干已经形成清晰闭环：

```text
React 页面
  → FastAPI Router
  → Service
  → Agent / 搜索 / 数据库 / 向量库 / 代码执行
  → ResearchState 或业务模型
  → SSE / JSON
  → React 状态和组件
```

后续教学应优先围绕这条闭环做实践，再扩展到新闻采集、股票、招投标和部署细节。源码覆盖审计不等同于端到端运行验证；需要 Docker、数据库和外部 API 的部分必须在对应环境可用后再验证。

## 最近追加的源码核对

第 30 至 32 课继续核对了以下边界：

- DataAnalyst 生成知识图谱和 ECharts 配置，charts 事件经 React 状态聚合后由研究详情页渲染；这条链与数据库页 Text2SQL 的 visualization_hint 分开。
- POST /research/stream 默认选择 V2，GET /research/stream 默认选择 V1；V1 还可能在 ReAct 和 classic fallback 之间切换。
- V1 的工具注册表不等于每次请求都会执行所有工具；必须从 Action、handler、日志和事件共同确认真实调用。
- app_main.py 导入阶段执行 Base.metadata.create_all()，随后 lifespan 启动调度器；Docker Compose 只启动基础设施，不启动前后端。
- PostgreSQL 的 ResearchCheckpoint.state_json 与 ui_state_json 分别承载后端研究状态和前端恢复状态。

第 33 课继续核对股票外围链路：`stock_mapping.py` 负责公司名称到 A 股代码的静态匹配，`StockService` 调用聚合数据 API，V2 `DeepScout` 写入 `data_points` 并发出 `stock_quote`，前端 `chat/index.tsx`、`result.tsx` 和 `StockCard` 完成状态保存与展示。该链路仍依赖 `JUHE_STOCK_API_KEY` 和外部行情服务，未完成带真实密钥的端到端验证。

第 34 课继续核对行业资讯闭环：`industry_config.py` 提供四个行业的关键词，`NewsCollectionService` 调用 Bocha 和 `BiddingService`，分别按 `source_url`、`bid_id` 去重并写入 `IndustryNews`、`BiddingInfo`；`SchedulerService` 每日 12:00 执行采集，启动时无数据还会立即初始化。Bocha、81API 和 PostgreSQL 尚未完成真实联通验证。

第 35 课核对检查点和恢复链路：`ResearchCheckpoint` 分开保存 `state_json`、`ui_state_json` 和 `final_report`；V2 在主要阶段结束时保存检查点，取消通过 Redis 标志协作式生效；前端使用完整检查点重建研究步骤、搜索结果、图表、图谱和报告。当前 `resume=True` 会加载旧状态，但 `_run_simplified()` 仍从规划入口开始，不能证明是精确的节点级断点续跑。

第 36 课核对工程外围文件：根 SQL 初始化用户、会话、知识库、记忆和 Text2SQL 示例表；两个行业脚本分别写入新能源汽车和智慧交通样例；V2 测试脚本依赖真实 DashScope/Bocha 服务；前端路由覆盖首页、聊天、知识库、记忆、数据库、资讯和招投标。发现 `/memory` 页面与 API 已实现，但导航栏点击仍提示“暂未开放”。

第 37 课核对剩余配置和前端基础文件：`llm_config.py`、`service/config.py`、数据库连接、JWT/bcrypt、Axios 类型扩展、聊天类型声明、Valtio 持久化和页面临时传输工具。发现 LLM Base URL 变量存在 `LLM_BASE_URL` 与 `DASHSCOPE_BASE_URL` 读取差异，旧兼容配置仍有硬编码默认值风险。

这些内容补充了主干调用链，但没有改变“静态源码阅读不等于外部服务端到端验证”的结论。
