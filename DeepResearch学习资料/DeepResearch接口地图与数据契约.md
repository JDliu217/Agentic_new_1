# DeepResearch 接口地图与数据契约

## 1. 如何使用这份地图

排错时按三列追踪：

```text
前端调用 → 后端路由 → 业务服务/存储
```

如果请求根本没有发出，查前端；如果返回 401/403/422，查认证或 Schema；如果请求进入但结果错误，继续追踪 Service 和外部依赖。

认证标记：

- **必需**：`get_current_user_required`，没有有效 JWT 会拒绝。
- **可选**：`get_current_user`，可以匿名进入，若有 token 则附带用户。
- **当前未强制**：路由签名中没有认证依赖；是否允许访问由业务逻辑决定。

---

## 2. 认证接口

| 方法和路径 | 认证 | 主要作用 | 主要返回 |
|---|---|---|---|
| `POST /auth/register` | 否 | 注册用户 | access token、用户 |
| `POST /auth/login` | 否 | 登录 | access token、用户 |
| `POST /auth/token` | 否 | 兼容 token 登录 | token |
| `GET /auth/me` | 必需 | 获取当前用户 | 用户 |
| `POST /auth/change-password` | 必需 | 修改密码 | 操作结果 |
| `POST /auth/logout` | 必需 | 注销接口 | 操作结果 |

前端：`src/api/auth.ts`、`src/pages/auth/login.tsx`。请求插件在 `src/api/request/plugins/auth.ts` 读取本地 `auth` 并加上 `Authorization: Bearer ...`。

---

## 3. 新会话接口（PostgreSQL）

| 方法和路径 | 认证 | 主要作用 |
|---|---|---|
| `GET /sessions` | 必需 | 用户会话列表，可按类型筛选 |
| `POST /sessions` | 必需 | 创建 `chat` 或 `deepsearch` 会话 |
| `GET /sessions/{session_id}` | 必需 | 获取会话和消息 |
| `PUT /sessions/{session_id}` | 必需 | 修改标题 |
| `DELETE /sessions/{session_id}` | 必需 | 删除会话 |
| `GET /sessions/{session_id}/messages` | 必需 | 分页读取消息 |
| `POST /sessions/{session_id}/messages` | 必需 | 写入一条消息 |

模型：`ChatSession`、`ChatMessage`。新会话列表由 `src/store/session.ts` 管理。

### 重要边界

旧 `/chat/*` 路由还使用 Redis `SessionService`。因此 `/sessions` 的 PostgreSQL 会话和旧 Redis 会话不是自动共享的同一个存储对象。

---

## 4. 普通聊天和 DeepResearch

| 方法和路径 | 认证 | 主要作用 | 返回形式 |
|---|---|---|---|
| `POST /chat/session` | 当前未强制 | 旧版创建聊天会话 | JSON |
| `POST /chat/completion/v1` | 当前未强制 | 旧知识库 + Web 搜索聊天 | SSE |
| `POST /chat/completion` | 当前未强制 | 政策检索 + Web 搜索聊天 | SSE |
| `POST /chat/completion/v3` | 当前未强制 | 带附件聊天 | SSE |
| `POST /research/stream` | 当前未强制 | V1/V2 深度研究 | SSE |
| `GET /research/stream` | 当前未强制 | 兼容 GET 研究请求 | SSE |
| `POST /research/cancel/{session_id}` | 当前未强制 | 写入 Redis 取消标志 | JSON |
| `GET /research/checkpoint/{session_id}` | 当前未强制 | 获取检查点概要 | JSON |
| `GET /research/checkpoint/{session_id}/full` | 当前未强制 | 获取完整后端/UI 状态 | JSON |
| `GET /research/checkpoints` | 当前未强制 | 检查点列表 | JSON |
| `DELETE /research/checkpoint/{session_id}` | 当前未强制 | 删除检查点 | JSON |
| `POST /research/resume/{session_id}` | 当前未强制 | 从检查点恢复 | SSE/JSON |
| `GET /research/test-wizard` | 当前未强制 | 用模拟数据测试 CodeWizard | JSON |

DeepResearch 请求体的核心字段：

```json
{
  "query": "问题",
  "session_id": "可选会话 ID",
  "search_modes": ["web", "local"],
  "version": "v2"
}
```

`search_modes` 会被转成 `search_web` 和 `search_local`。前端调用位置：`src/api/session.ts::deepsearch()`。

---

## 5. 聊天附件接口

| 方法和路径 | 认证 | 主要作用 |
|---|---|---|
| `POST /attachments` | 可选 | 上传文件并创建 pending 记录 |
| `GET /attachments/{attachment_id}` | 可选 | 查询处理状态 |
| `GET /attachments/session/{session_id}` | 可选 | 查询会话附件 |
| `DELETE /attachments/{attachment_id}` | 可选 | 删除附件和数据库记录 |

允许的扩展名包括 PDF、Word、文本、表格、演示、图片和代码文件。

处理链：

```text
上传 → 文件保存 → ChatAttachment(pending)
     → BackgroundTasks
     → processing → completed/failed
```

当前 PDF、Word 和图片主要保存占位文本，完整解析能力只在知识库文档链路中实现得更完整。

---

## 6. 知识库接口

| 方法和路径 | 认证 | 主要作用 |
|---|---|---|
| `GET /knowledge-bases` | 必需 | 用户知识库列表 |
| `POST /knowledge-bases` | 必需 | 创建知识库 |
| `GET /knowledge-bases/{kb_id}` | 必需 | 知识库和文档列表 |
| `PUT /knowledge-bases/{kb_id}` | 必需 | 修改知识库 |
| `DELETE /knowledge-bases/{kb_id}` | 必需 | 删除知识库 |
| `POST /knowledge-bases/{kb_id}/documents` | 必需 | 上传并处理文档 |
| `GET /knowledge-bases/{kb_id}/documents` | 必需 | 文档列表 |
| `GET /knowledge-bases/{kb_id}/documents/{doc_id}/chunks` | 必需 | 查看文档切片 |
| `DELETE /knowledge-bases/{kb_id}/documents/{doc_id}` | 必需 | 删除文档 |

数据契约：

```text
PostgreSQL：KnowledgeBase、Document、处理状态、chunk_count
Milvus：文本切片向量和检索内容
```

前端：`src/api/knowledge.ts`、`src/store/knowledge.ts`、`src/pages/knowledge/index.tsx`。

---

## 7. 长期记忆接口

| 方法和路径 | 认证 | 主要作用 |
|---|---|---|
| `GET /memories` | 必需 | 用户记忆列表 |
| `GET /memories/{memory_id}` | 必需 | 记忆详情 |
| `POST /memories/search` | 必需 | Milvus 语义搜索 |
| `POST /memories/create` | 必需 | 从会话总结记忆 |
| `DELETE /memories/{memory_id}` | 必需 | 删除 PostgreSQL 和 Milvus 记录 |
| `GET /memories/context/{query}` | 必需 | 构造可放入 Prompt 的记忆上下文 |

创建记忆会经过：

```text
ChatMessage → LLM summary/key_insights/topics
           → LongTermMemory
           → Embedding
           → Milvus long_term_memories
```

当前注意：`ChatService` 支持 `user_id` 记忆注入，但普通聊天 Router 的调用没有显式传入 `user_id`，所以要通过实际运行确认记忆是否接通。

---

## 8. 数据库探索和 Text2SQL

| 方法和路径 | 认证 | 主要作用 |
|---|---|---|
| `GET /database/tables` | 必需 | 表列表、大小和行数 |
| `GET /database/tables/{table_name}/schema` | 必需 | 列、主键、索引 |
| `GET /database/tables/{table_name}/data` | 必需 | 分页读取表数据 |
| `POST /database/query` | 必需 | 只读 SELECT |
| `POST /database/text2sql` | 必需 | 自然语言生成并执行 SQL |

Text2SQL 返回：

```json
{
  "success": true,
  "sql": "SELECT ...",
  "data": [],
  "columns": [],
  "visualization_hint": "line",
  "confidence": 0.9,
  "row_count": 5
}
```

没有数据库连接时，源码可能走 `_get_mock_data()`。验证真实执行时要检查连接配置和数据库日志。

---

## 9. 新闻、招投标和行业配置

| 方法和路径 | 认证 | 主要作用 |
|---|---|---|
| `GET /news/list` | 当前未强制 | 新闻分页、分类和行业筛选 |
| `GET /news/bidding/list` | 当前未强制 | 招投标分页、类型、省份和行业筛选 |
| `GET /news/stats` | 当前未强制 | 新闻和招投标统计 |
| `POST /news/collect` | 当前未强制 | 手动触发采集 |
| `GET /news/scheduler/status` | 当前未强制 | 查看定时任务 |
| `GET /news/check` | 当前未强制 | 检查是否有数据 |
| `GET /news/industries` | 当前未强制 | 行业列表 |
| `GET /news/industries/{industry_id}` | 当前未强制 | 行业关键词配置 |

采集链路：

```text
行业配置 → 新闻/招投标关键词 → 外部 API → IndustryNews/BiddingInfo → PostgreSQL
```

---

## 10. 文档和搜索兼容接口

| 方法和路径 | 主要作用 |
|---|---|
| `POST /documents/upload` | 旧文档服务上传 |
| `GET /documents/list` | 旧文档列表 |
| `POST /documents/delete` | 旧文档删除 |
| `POST /documents/retrieve` | 旧文档检索 |
| `POST /search/web` | 直接 Web 搜索 |

这些接口与新知识库管理接口并存，阅读时要看它们调用的是 `DocumentService`、RAGFlow 兼容服务，还是本地 `KnowledgeBase/Document` 模型。

---

## 11. 一次排错的接口路径

### 页面没有数据显示

```text
浏览器 Network
  → 请求 URL/参数/状态码
  → 前端 API 类型
  → Router 是否进入
  → Service 查询条件
  → PostgreSQL/Milvus/外部 API
```

### 研究页面卡在加载中

```text
/research/stream 是否建立
  → 是否收到 research_start
  → 是否收到 research_step
  → 后端 Agent 是否完成
  → 是否收到 research_complete 或 error
  → parseData 是否处理对应 type
```

### 认证相关异常

```text
localStorage.auth
  → authPlugin
  → Authorization header
  → get_current_user_required
  → 用户 ID 和资源归属过滤
```

---

## 12. 本接口地图的掌握标准

你应该能从任意一个页面动作开始，反向说出：

1. 调用了哪个前端 API 函数。
2. 发送了什么参数。
3. 命中了哪个 FastAPI Router。
4. 是否需要 JWT。
5. Router 调用了哪个 Service。
6. 数据读写 PostgreSQL、Redis、Milvus 还是外部 API。
7. 返回 JSON、SSE 还是后台状态轮询。
8. 哪个 React 状态最终显示结果。

