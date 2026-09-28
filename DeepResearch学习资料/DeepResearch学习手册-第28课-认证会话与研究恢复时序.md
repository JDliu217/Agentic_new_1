# DeepResearch 学习手册·第 28 课

## 认证、会话与研究恢复时序

本课解决三个容易混淆的问题：

1. 登录成功后，JWT 到底如何参与后续请求？
2. 为什么项目同时有 PostgreSQL 会话和 Redis 会话？
3. DeepResearch 流式输出时，哪些内容已经持久化，哪些还只在内存？

源码依据：

```text
D:\课\s4-6\industry_information_assistant\backend\app\router\auth_router.py
D:\课\s4-6\industry_information_assistant\backend\app\core\security.py
D:\课\s4-6\industry_information_assistant\backend\app\router\session_router.py
D:\课\s4-6\industry_information_assistant\backend\app\service\session_service.py
D:\课\s4-6\industry_information_assistant\frontend\src\store\auth.ts
D:\课\s4-6\industry_information_assistant\frontend\src\components\auth-guard\index.tsx
```

---

## 1. 登录时序：密码不会直接进入 JWT

```text
登录页
  → POST /auth/login
  → 根据用户名或邮箱查询 User
  → bcrypt 校验 hashed_password
  → create_access_token({sub: user.id, username: user.username})
  → 返回 access_token 和用户信息
```

数据库保存的是密码哈希，不是明文密码。JWT 的 `sub` 是用户 ID，后端以后通过这个 ID 查询用户，而不是把完整用户对象放进 Token。

`/auth/token` 是 OAuth2 表单格式的兼容入口；`/auth/login` 是前端使用的 JSON 登录入口。两者最后都生成同一类 JWT。

---

## 2. 前端保存和发送 Token

`frontend/src/store/auth.ts` 使用 Valtio 管理：

```text
token
user
isLoggedIn
```

状态会保存到浏览器 `localStorage.auth`。请求插件每次从这个键读取 Token，并加上：

```http
Authorization: Bearer <JWT>
```

`AuthGuard` 只根据 `isLoggedIn` 决定是否跳转到 `/login`。它负责用户体验，不是后端的安全边界。

真正的权限检查在后端：

```python
get_current_user_required()
```

它会验证 Token 签名和过期时间，再根据 `sub` 查用户，最后检查 `is_active`。

---

## 3. 新 PostgreSQL 会话系统

新页面使用的接口是：

```text
GET    /sessions
POST   /sessions
GET    /sessions/{session_id}
PUT    /sessions/{session_id}
DELETE /sessions/{session_id}
GET    /sessions/{session_id}/messages
POST   /sessions/{session_id}/messages
```

核心模型是：

```text
ChatSession
  id、user_id、title、session_type、created_at、updated_at

ChatMessage
  id、session_id、role、content、thinking、references_data、image_results
```

每次读取或写入会话时，`session_router.py` 都会使用：

```python
ChatSession.id == session_uuid,
ChatSession.user_id == current_user.id
```

这一步同时完成“会话存在”和“会话属于当前用户”的检查，避免只凭一个 UUID 读取别人的会话。

第一条用户消息写入时，如果标题还是“新对话”，后端会取前 20 个字符自动生成标题，并更新 `updated_at`。

---

## 4. 旧 Redis 会话系统

旧 `/chat/*` 路由在依赖中创建 `SessionService`，它不使用 `ChatSession` 表，而是使用 Redis：

```text
session:<id>              Hash，会话元数据
session:<id>:messages     Sorted Set，消息时间顺序
message:<id>:<message_id> Hash，消息内容
```

它还有两种限制：

```text
最多保留 20 条消息
生成提示词时最多使用约 5000 token 历史
```

因此：

```text
/sessions          → PostgreSQL 新会话
/chat/session      → Redis 旧会话
```

二者的 ID、消息和生命周期不是自动同步的。读代码时不能因为都叫“session”就把它们当成同一张表。

---

## 5. 一条新 DeepResearch 消息的实际时序

前端发送研究问题时，典型顺序是：

```text
1. 页面先把用户消息放入本地 chat.list
2. POST /sessions/{id}/messages 保存用户消息
3. POST /research/stream 发起研究
4. SSE 不断更新前端助手消息和研究详情
5. 收到 research_complete 后
6. POST /sessions/{id}/messages 保存助手最终报告
```

这里有两个并行的“状态”：

```text
ResearchState / 检查点
  保存研究阶段、事实、图表、报告和 UI 恢复信息

ChatMessage
  保存最终展示用的用户消息和助手消息
```

流式执行期间，助手的增量内容主要在前端内存和后端研究状态中；助手最终消息通常要等流结束后，由前端再次调用消息接口写入 PostgreSQL。

因此浏览器在生成中途崩溃时，可能出现：

```text
研究检查点已经存在
但 ChatMessage 中没有完整的助手最终报告
```

这不是数据矛盾，而是两个持久化时机不同。

---

## 6. 研究恢复时的两套数据

打开 `/chat/{sessionId}` 时，前端通常读取：

```text
会话详情/消息
  → 恢复聊天列表

研究检查点完整状态
  → 恢复步骤、搜索结果、图表、知识图谱、报告和引用
```

所以历史消息和研究面板不是完全同一份数据源：

```text
消息气泡主要来自 ChatMessage
研究过程面板主要来自 checkpoint.ui_state_json 和后端 state
```

如果只保存了最终消息而没有保存研究 UI 状态，页面可以显示报告，但不能重建搜索和图表过程；反过来，如果只有检查点而没有助手消息，聊天历史可能缺少最终回答。

---

## 7. `session_type` 不决定真实执行器

数据库中的 `session_type` 是会话记录上的业务标记，例如 `chat` 或 `deepsearch`。但实际一次请求是否走 DeepResearch，前端还会根据搜索模式调用 `/research/stream`。

因此可能出现：

```text
session_type = "chat"
但本次请求使用 search_modes = ["web", "local"]
实际走 V2 DeepResearch
```

不能只根据数据库字段判断真实执行路径。要同时看：

```text
前端调用的 URL
request.version
search_modes
research_router 的分支
```

---

## 8. 当前认证边界

这些接口明确使用 `get_current_user_required`：

```text
/sessions
/knowledge-bases
/memory
/database
/auth/me
/auth/change-password
```

但 `/research/stream` 的路由签名当前没有显式注入必需用户依赖。它接收 `session_id`，但这个 ID 主要用于研究运行、检查点和取消标志，不能仅凭此推断已经验证了会话所有权。

同样，`/auth/logout` 当前只是返回成功，前端清除 localStorage Token；服务端没有 JWT 黑名单或撤销表。因此准确说法是：

> 当前注销主要是客户端注销，已经签发的 JWT 在过期前未必会被服务端立即失效。

---

## 9. 面试时的完整回答模板

面试官问“项目如何处理认证、会话和研究恢复”，可以按以下顺序回答：

1. 登录时使用 bcrypt 校验密码，后端签发包含用户 ID 的 JWT。
2. 前端把 Token 保存到 `localStorage.auth`，请求插件自动加 Bearer 头。
3. 新页面使用 PostgreSQL 的 `ChatSession`/`ChatMessage`，每次按 `user_id` 做资源归属过滤。
4. 旧 `/chat/*` 兼容链使用 Redis `SessionService`，有独立的消息和 token 限制。
5. DeepResearch 通过 SSE 产生过程，阶段性状态写入检查点，最终助手消息再写入 PostgreSQL。
6. 恢复页面时，聊天消息和研究面板分别从消息表与检查点 UI 状态恢复。
7. 当前还需要补强研究接口的会话所有权校验和服务端 Token 撤销机制。

---

## 10. 练习

1. JWT 的 `sub` 保存什么？后端如何用它找回用户？
2. 为什么 AuthGuard 不能替代后端权限检查？
3. 新 PostgreSQL 会话和旧 Redis 会话分别由哪些接口创建？
4. 一条 DeepResearch 消息什么时候写入 PostgreSQL？
5. 为什么浏览器中断可能导致检查点存在，但助手最终消息不存在？
6. `session_type="chat"` 是否一定代表这次请求不会走 DeepResearch？为什么？
7. 当前 `/auth/logout` 为什么不能称为服务端撤销 JWT？

