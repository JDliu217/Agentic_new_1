# DeepResearch 学习手册：第 7 课

## 实践实验与掌握检查

这节课把前 1 至 6 课的源码理解变成可以执行的实验。目标不是一次性把所有服务都启动，而是逐层证明：页面请求、后端路由、研究状态、Agent、数据存储和前端展示之间确实连得起来。

---

## 1. 实验前准备

项目目录：

```text
D:\课\s4-6\industry_information_assistant
```

建议打开两个 PowerShell 窗口：窗口 A 运行基础服务和后端，窗口 B 运行前端。密钥只放在本地环境变量或后端 `.env` 中，不要提交到公开仓库。

---

## 2. 静态验证

### 2.1 后端语法检查

```powershell
Set-Location D:\课\s4-6\industry_information_assistant\backend
python -m compileall -q app
```

成功时没有错误输出。它只能证明 Python 文件能被编译，不能证明数据库、外部 API 或研究流程已经成功运行。

### 2.2 前端生产构建

```powershell
Set-Location D:\课\s4-6\industry_information_assistant\frontend
npm run build
```

当前源码构建可以通过，但 Vite 会提示主 JavaScript bundle 较大。这个提示属于性能优化问题，不等同于构建失败。

---

## 3. 启动基础设施

项目 README 推荐 Docker Compose。先检查 Docker：

```powershell
docker version
docker compose version
```

在项目根目录启动：

```powershell
Set-Location D:\课\s4-6\industry_information_assistant
docker compose up -d
docker compose ps
docker compose logs --tail=100 postgres
docker compose logs --tail=100 redis
docker compose logs --tail=100 milvus
```

重点观察 PostgreSQL、Redis、Milvus 以及依赖服务是否为运行状态。若 Docker 不可用，仍可完成静态阅读、前端构建和不依赖基础服务的练习，但不能声称完成真实端到端验证。

---

## 4. 配置与启动

重点配置包括：

```text
DASHSCOPE_API_KEY     LLM 和 Embedding
BOCHA_API_KEY         网络搜索
POSTGRES_*            PostgreSQL
REDIS_*               Redis
MILVUS_*              Milvus
JWT_SECRET_KEY        登录令牌签名
```

阅读位置：`backend/app/config/llm_config.py`、`backend/app/service/config.py` 和 `READMED.md`。

要区分：Agent 模型、temperature、max_tokens、最大迭代次数是研究流程配置；数据库、缓存、搜索和模型密钥是基础设施连接配置。

启动后端：

```powershell
Set-Location D:\课\s4-6\industry_information_assistant\backend
python app\app_main.py
```

启动前端（另开窗口）：

```powershell
Set-Location D:\课\s4-6\industry_information_assistant\frontend
npm run dev
```

当前 `frontend/vite.config.ts` 将开发服务器端口配置为 `5183`，因此访问 `http://localhost:5183/login`；后端文档访问 `http://localhost:8000/docs`。README 中的 `5173` 与当前 Vite 配置不一致，以源码为准。

特别注意：`llm_config.py` 的 `ResearchConfig.max_iterations` 默认是 1，而 `create_initial_state()` 的默认值是 3。通过 `DeepResearchGraph.run()` 执行时，配置值会覆盖初始状态值。

---

## 5. 实验一：注册、登录和会话

按这条链路阅读：

```text
frontend/src/pages/auth/login.tsx
  → frontend/src/api/auth.ts
  → backend/app/router/auth_router.py
  → 用户模型和 JWT 逻辑
  → frontend/src/store/auth.ts
  → frontend/src/api/request/plugins/auth.ts
```

操作目标：

1. 注册一个测试用户。
2. 登录并观察浏览器本地存储中的 `auth`。
3. 创建一个普通聊天会话。
4. 刷新页面，确认会话列表来自后端。

必须能解释：token 保存在哪里；哪个插件添加 `Authorization: Bearer ...`；认证守卫如何阻止未登录访问；会话和消息分别由哪个接口管理。

---

## 6. 实验二：普通聊天和 SSE

阅读 `frontend/src/api/session.ts`、`backend/app/router/chat_router.py`、`backend/app/service/chat_service.py` 和 `frontend/src/pages/chat/index.tsx`。

在浏览器 Network 面板观察：请求 URL、请求体中的 `session_id` 和 `question`、响应类型 `text/event-stream`，以及以 `data:` 开头的事件。

前端拿到 `ReadableStream` 后不断调用 `reader.read()`，按换行取出 `data: `，解析 JSON，再追加到当前聊天项。这是普通聊天和 DeepResearch 共享的实时传输基础。

---

## 7. 实验三：知识库和向量检索

链路：

```text
pages/knowledge/index.tsx
  → store/knowledge.ts
  → api/knowledge.ts
  → knowledge_router.py
  → DocumentService / DocMindService
  → EmbeddingService
  → MilvusService
```

操作目标：创建知识库，上传公开 PDF 或 Word，观察文档从 `pending` / `processing` 变为 `completed`，查看切片，再开启本地知识库搜索。

必须分清：

```text
PostgreSQL：知识库、文档元数据、处理状态、文件信息
Milvus：切片向量和向量检索内容
```

元数据存在而检索为空，优先检查 Milvus、Embedding 和集合初始化；向量存在但页面不显示，优先检查 PostgreSQL 或 API 层。

---

## 8. 实验四：一次 DeepResearch 的状态追踪

预期事件链：

```text
POST /research/stream
  → research_start
  → planning
  → researching
  → analyzing
  → writing
  → reviewing
  → research_complete
```

真实流程中，`analyzing` 依次调用 `DataAnalyst` 和 `CodeWizard`。`DeepResearchGraph.run()` 中被注释掉的 LangGraph 分支不是当前默认执行分支；当前默认是 `_run_simplified()`。

阅读 `frontend/src/pages/chat/index.tsx` 的 `parseData()`，完成这张映射表：

| 后端事件 | 前端结果 |
|---|---|
| `research_start` | 初始化研究模式和详情容器 |
| `research_step` | 更新 `researchSteps` 和详情 Map |
| `search_results` | 写入搜索详情并更新数量 |
| `knowledge_graph` | 写入分析步骤的图谱 |
| 图表事件 | 写入详情中的 `charts` |
| 报告增量 | 更新写作步骤的 `streamingReport` |
| `research_complete` | 保存最终报告和引用 |
| `research_cancelled` | 结束加载并显示取消结果 |

阅读 `backend/app/service/deep_research_v2/graph.py`，逐阶段记录 `state["phase"]`、Agent 写入的字段和 `save_checkpoint_async()` 的调用位置。

---

## 9. 实验五：取消和恢复

停止按钮先取消浏览器端流读取，再请求 `/research/cancel/{session_id}`。后端把取消标志写入 Redis，并在 Agent 执行前和执行期间检查它。

检查点包含两套状态：

```text
state_json：后端完整 ResearchState
ui_state_json：前端步骤、搜索结果、图表、图谱和报告
```

页面恢复时重新组装研究步骤和详情面板。两套状态分开保存，是因为“研究怎么运行”和“页面怎么显示”是两个不同的恢复问题。

---

## 10. 实验六：Text2SQL、分析和图表

阅读 `text2sql_service.py`、`database_explorer.py`、`smart_analyzer.py`、`chart_generator.py`、`pages/database/index.tsx` 和 `components/chart/index.tsx`。

可以使用问题：`查询新能源汽车 2023 和 2024 年的销量，并按年份比较。`

追踪四个结果：

1. LLM 生成的 SQL。
2. 数据库真正执行的结果。
3. 结构化分析结论。
4. ECharts 配置如何被 React 组件渲染。

不要把“生成 SQL”和“执行 SQL”当成一步。前者需要校验，后者才会改变或读取外部数据。

---

## 11. CodeWizard 实验

阅读 `backend/app/service/deep_research_v2/agents/wizard.py`，记住顺序：

```text
LLM 生成 Python
  → 清理代码
  → compile() 语法检查
  → 危险模式检查
  → 受限 globals 中 exec()
  → 捕获输出和 matplotlib 图片
  → 写回 state['charts'] 和 code_executions
```

失败时会把错误交给 LLM，自修复并最多重试 3 次。`compile()` 只能检查语法；正则和受限 builtins 也不是强安全边界。生产环境应使用独立容器或专用代码执行服务，并限制时间、资源、网络和文件系统。

---

## 12. 分层排错顺序

```text
1. 浏览器：请求是否发出、状态码和响应体
2. 前端：SSE 是否读到、json.type 是否识别
3. 后端路由：是否进入正确 Router
4. 业务服务：Agent 或数据库调用是否异常
5. 基础设施：PostgreSQL、Redis、Milvus 是否健康
6. 外部服务：LLM、搜索、Embedding、DocMind 是否可用
7. 数据契约：字段是否符合前后端 Schema
```

常见信号：401/403 多为认证或权限；422 多为请求体不符合 Schema；500 是后端执行异常；流已建立但无事件，重点检查 Agent、消息队列和外部 API；事件已收到但页面不显示，重点检查前端事件映射和状态聚合。

---

## 13. 掌握检查

不看源码回答：

1. `ResearchState` 为什么是多 Agent 的交接协议？
2. PostgreSQL 和 Milvus 各保存什么？
3. 为什么 DeepResearch 用 SSE？
4. V1 ReAct 和 V2 多 Agent 的核心差异是什么？
5. 如果知识库上传成功但检索为空，按什么顺序排查？
6. 如果研究页面一直加载，检查哪些事件和状态？
7. 为什么检查点同时保存 `state_json` 和 `ui_state_json`？
8. 为什么当前 LangGraph 图不能直接代表真实运行路径？
9. 为什么 CodeWizard 不能视为生产级安全隔离？
10. DeepScout 只处理部分章节而 LeadWriter 遍历完整大纲，会带来什么风险？

完成标准：能从聊天页找到请求起点；能从 `/research/stream` 跟到 `DeepResearchGraph.run()`；能指出 `_run_simplified()` 的证据；能说出六个 Agent 的职责；能画出一条 SSE 到 React 的路径；能按分层顺序排错。

