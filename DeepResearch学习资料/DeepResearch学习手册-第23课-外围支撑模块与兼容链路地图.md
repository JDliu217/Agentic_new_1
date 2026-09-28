# DeepResearch 学习手册·第 23 课

## 首页、认证、会话历史、兼容接口与运行支撑

> 前 22 课覆盖了主要业务能力。本课把剩余支撑模块串起来，重点区分当前推荐路径、旧兼容路径和纯展示组件，避免看到一个文件就误以为它是线上主链路。

---

## 1. 应用从入口到运行时

文件：`backend/app/app_main.py`

后端导入时执行：

```text
load_dotenv()
导入模型
Base.metadata.create_all(bind=engine)
创建 FastAPI 应用
注册 CORS
注册全部 Router
```

应用生命周期 `lifespan` 启动时会：

1. 启动 APScheduler。
2. 检查行业数据是否存在。
3. 必要时执行初始资讯采集。

关闭时停止调度器。

一个重要边界是：`create_all()` 在模块导入阶段就需要数据库连接。如果 PostgreSQL 不可达，后端可能在真正启动路由之前就失败。排错时应先验证数据库，而不是只看 HTTP 端口。

应用注册的主要路由前缀：

```text
/auth
/sessions
/knowledge-bases
/attachments
/memories
/database
/documents
/search
/chat
/research
/news
```

---

## 2. 首页、登录和行业选择

### 2.1 首页

文件：`frontend/src/pages/index/index.tsx`

首页从 `INDUSTRY_CONFIGS` 生成行业卡片。搜索框只过滤卡片，不调用后端搜索接口。

点击行业卡片时：

```text
setCurrentIndustry(industryId)
  → localStorage.selected_industry_id
  → navigate('/chat?title=...')
```

因此首页选择行业影响后续资讯、招投标和推荐问题，但它不是创建一个新的后端行业实体。

### 2.2 登录与注册

文件：`frontend/src/pages/auth/login.tsx`。

登录：

```text
表单
  → POST /auth/login
  → access_token + user
  → authActions.login()
  → localStorage.auth
  → 返回原来被拦截的路径或 /chat
```

注册流程类似，区别是先调用 `/auth/register`。

`AuthGuard` 只读取前端 `isLoggedIn` 决定导航；Axios `authPlugin` 负责把 token 放入请求头；后端 `get_current_user_required` 才是真正的接口权限校验。

### 2.3 JWT 的后端实现

文件：`backend/app/core/security.py`。

密码使用 bcrypt 哈希，JWT 使用：

```text
JWT_SECRET_KEY
JWT_ALGORITHM（默认 HS256）
JWT_ACCESS_TOKEN_EXPIRE_MINUTES
```

Token 中包含用户 ID 和用户名，并写入 `exp`。默认密钥是开发占位值，生产环境必须通过环境变量覆盖。

当前 `/auth/logout` 主要依赖前端清除 token，没有服务端 JWT 黑名单或撤销表，所以注销后的已签发 token 是否立即失效取决于过期和服务端校验策略。

---

## 3. 会话历史抽屉

文件：

```text
frontend/src/components/session-drawer/index.tsx
frontend/src/store/session.ts
frontend/src/api/session.ts
```

打开历史抽屉时调用：

```http
GET /sessions?limit=50
```

点击一个会话时：

```text
关闭抽屉
  → sessionActions.loadSession(id)
  → GET /sessions/{id}
  → 写入 sessionState.currentSession
  → navigate('/chat/{id}')
```

这样页面进入聊天页时可以优先使用预加载的消息，减少一次重复请求。

历史条目支持：

- 重命名：`PUT /sessions/{id}`。
- 删除：`DELETE /sessions/{id}`。
- 显示更新时间和消息数。

这条链是 PostgreSQL 新会话系统，不是 Redis 旧 `SessionService`。

---

## 4. Redis 和 PostgreSQL 的边界

文件：`backend/app/core/redis_client.py`。

Redis 工具提供：

```text
JSON get/set/delete/exists
session:{id} 读写
列表 lpush/ltrim/lrange
```

默认缓存过期时间是 1 小时，会话数据默认 24 小时。它适合缓存、短期状态和旧聊天会话，不等于 PostgreSQL 的永久消息记录。

项目并存两条会话体系：

```text
新系统：/sessions，SQLAlchemy 模型，前端会话历史和消息持久化
旧系统：/chat/session、SessionService、Redis，会被兼容聊天路由使用
```

读代码时必须先确认调用方，否则看到 `SessionService` 不能直接推断当前 `/chat/:id` 使用它。

---

## 5. 三个聊天接口的兼容关系

文件：`backend/app/router/chat_router.py`。

### 5.1 `/chat/completion/v1`

旧版普通聊天路径：

```text
知识库外部文档服务检索
  + Serper Web 搜索
  → 重排
  → ChatService 流式回答
```

### 5.2 `/chat/completion`

当前普通聊天前端主要使用的路径。它使用政策向量集合 `policy_documents` 加 Web 搜索，再调用 `ChatService` 流式回答。

### 5.3 `/chat/completion/v3`

附件聊天路径，在普通检索上下文之外读取已完成 `ChatAttachment.content_text`，把附件内容拼接到增强问题中，再调用同一个聊天生成服务。

前端发送逻辑是：

```text
Deepsearch → /research/stream
普通无附件 → /chat/completion
普通有附件 → /chat/completion/v3
```

因此接口版本不是简单的数字升级，而是不同数据源和业务行为的分支。

---

## 6. 外部文档服务和本地知识库

`DocumentService` 通过 HTTP 调用外部文档服务：

```text
upload_document
parse_documents
get_documents
delete_documents
retrieve_documents
```

它与新知识库链的区别：

```text
外部文档链：dataset_id → 外部服务 API → 外部切片/检索
本地知识库链：knowledge_base_id → 本地 Document → DocMind/Embedding/Milvus
```

旧 `/chat/completion/v1` 使用外部文档服务；新知识库页面使用 `/knowledge-bases`。不能只看到两个地方都叫“知识库”就认为它们共享同一集合和同一文档记录。

---

## 7. Web 搜索服务

文件：`backend/app/service/web_search_service.py` 与 `search_router.py`。

`WebSearchService` 使用 Serper API，默认主机为 `google.serper.dev`，请求参数包括：

```text
q
gl
hl
autocorrect
page
type
```

响应会被拆成：

```text
knowledgeGraph
organic
peopleAlsoAsk
relatedSearches
```

`POST /search/web` 是独立的搜索接口；DeepResearch 还可以通过自己的 Scout/工具路径使用搜索。独立接口和 V2 Agent 的搜索事件不是同一层的响应契约。

---

## 8. 数据库探索器的安全边界

文件：`backend/app/service/database_explorer.py`。

探索器提供：

```text
获取表列表和行数
获取列、主键、索引
分页读取表数据
执行只读 SQL
```

表名和排序列使用正则限制为字母、数字和下划线；查询要求以 `SELECT` 开头并禁止写操作关键词。没有 `LIMIT` 时会自动追加限制。

这比直接把字符串拼进 SQL 好，但仍不是完整数据库安全方案。应再配合：

- 只读数据库账号。
- 表/列白名单。
- 数据库级超时和行数限制。
- SQL AST 解析。
- 审计日志。

---

## 9. 前端内容渲染层

### 9.1 Markdown

`components/markdown` 使用 `marked` 转换 Markdown，并自定义图片渲染：只允许 `data:image/...` 和 `http(s)` 图片，其他图片 URL 被隐藏。

这解释了为什么报告里的无效图片占位符不会直接显示破图；真实图表由可视化组件重新插入。

项目使用 `dangerouslySetInnerHTML`，因此 Markdown 来源必须经过可信控制或 HTML 清理。当前代码应列为内容安全检查点。

### 9.2 普通结果和引用

`chat-message/result.tsx` 把助手消息拆成：

```text
ReAct 过程
传统思考过程
数据洞察
股票行情卡片
Markdown 思考内容
Markdown 最终回答
来源列表
图像结果
```

Markdown 扩展支持 `##1$$` 形式的引用标记，并把它转换为对应来源链接。

### 9.3 页面布局

`ComPageLayout` 将聊天页拆为：

```text
左侧主内容
  ├── 消息列表
  └── Sender 输入区
右侧可选面板
```

DeepResearch 时设置 `wideRight`，让研究详情面板获得更宽的显示空间；普通聊天则可以显示来源抽屉或不显示右栏。

---

## 10. Docker 运行支撑

`docker-compose.yml` 定义：

```text
PostgreSQL
Redis
etcd
MinIO
Milvus
Elasticsearch（可选全文检索）
```

`start-services.sh` 提供：

```text
start / stop / restart / status / logs / clean
```

脚本启动后会检查 PostgreSQL、Redis、Milvus 和 Elasticsearch 健康状态。

其中 `clean` 会执行 `docker-compose down -v` 并删除数据卷，属于破坏性操作。学习时要理解命令含义，不能把它当作普通重启。

---

## 11. 旧 ReAct 工具执行器

V1 相关文件：

```text
backend/app/service/dr_g.py
backend/app/service/react_controller.py
backend/app/service/tool_executor.py
```

V1 抽象是：

```text
LLM 思考
  → 选择工具
  → ToolExecutor 分发
  → 得到 observation
  → 再思考
```

工具可能包括：

```text
web_search
knowledge_search
text2sql
data_analysis
generate_chart
stock_query
bidding_search
finish
```

`bind_tools_to_controller()` 把执行器方法绑定给 ReAct 控制器。V1 通过 `context.collected_data`、`context.insights` 和 `context.charts` 保存产物；V2 则主要通过 `ResearchState` 和固定 Agent 阶段交接。

---

## 12. 当前兼容链路判断方法

阅读任何功能时先问三个问题：

1. 哪个前端页面现在调用它？
2. 哪个 Router 注册了它？
3. 是否被 V2 `research_router` 或当前聊天页实际使用？

可以用这张表快速判断：

| 文件/接口 | 当前角色 |
|---|---|
| `/research/stream` | V2 DeepResearch 当前主入口 |
| `/chat/completion` | 当前普通聊天主要入口 |
| `/chat/completion/v3` | 普通附件聊天入口 |
| `/chat/completion/v1` | 旧外部文档兼容路径 |
| `/search/web` | 独立 Serper 搜索接口 |
| `DocumentService` | 旧外部文档服务适配器 |
| `SessionService`/Redis | 旧会话兼容能力 |
| `ResearchService`/ReAct | V1 研究链 |
| `DeepResearchV2Service` | V2 研究链 |

---

## 13. 练习

1. 为什么后端导入阶段数据库不可达会阻止应用启动？
2. `/chat/completion`、`/chat/completion/v1` 和 `/chat/completion/v3` 的数据源差异是什么？
3. `AuthGuard`、Axios token 和后端 JWT 校验分别负责什么？
4. 为什么当前会话历史使用 PostgreSQL，而旧聊天仍可能使用 Redis？
5. `DocumentService` 与本地知识库页面为什么不能直接互换？
6. Markdown 的 `dangerouslySetInnerHTML` 会带来什么安全检查点？
7. V1 ReAct 和 V2 多 Agent 各自通过什么结构传递中间结果？
8. 如何判断一个文件是线上主路径还是兼容代码？

---

## 14. 留白与我的笔记

### 14.1 我画的入口和兼容路径

<!-- 画出 app_main 注册的 Router，并标记主路径、旧路径和独立工具接口。 -->



### 14.2 我需要验证的安全点

<!-- 记录 JWT 默认密钥、CORS、Markdown HTML、SQL 只读和文件路径等检查项。 -->



### 14.3 我还没能运行的依赖

<!-- 记录 Docker、PostgreSQL、Redis、Milvus、Elasticsearch 和外部 API 的真实验证情况。 -->



