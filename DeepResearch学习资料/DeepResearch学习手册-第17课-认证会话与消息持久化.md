# DeepResearch 学习手册·第 17 课

## 认证、会话与消息持久化

本课追踪用户从登录开始，到创建会话、发送消息、保存消息和恢复页面的完整链路。

源码根目录：D:\课\s4-6\industry_information_assistant

---

## 1. 先区分三个概念

项目里有三个容易混淆的对象：

| 对象 | 作用 | 主要存储 |
|---|---|---|
| 用户 | 证明谁在使用系统 | PostgreSQL users |
| 新会话 | 页面中的聊天或研究容器 | PostgreSQL chat_sessions |
| 旧聊天会话 | 兼容旧聊天 API 的历史消息容器 | Redis session:<id> |

用户、会话和消息不是一回事。JWT 证明身份；会话 ID 标识一段对话；消息属于会话。

---

## 2. 注册和登录

### 2.1 前端

登录页面：frontend/src/pages/auth/login.tsx

登录调用：

    api.auth.login(values)
    → POST /auth/login
    → 得到 access_token 和 user
    → authActions.login(token, user)
    → navigate('/chat')

注册流程类似。注册成功后，前端直接保存返回的 token 并跳转到聊天页。

前端把认证状态保存到浏览器 localStorage 的 auth 键中：

    {
      "token": "JWT...",
      "user": {"id": "...", "username": "..."},
      "isLoggedIn": true
    }

### 2.2 后端注册

auth_router.py 的 register()：

1. 检查用户名是否存在。
2. 检查邮箱是否存在。
3. 使用 bcrypt 对密码哈希。
4. 创建 User 记录。
5. 生成 JWT。
6. 返回用户信息和 token。

数据库中保存的是 hashed_password，不是明文密码。

### 2.3 后端登录

login() 支持用用户名或邮箱登录：

    用户名/邮箱
    → 查询 User
    → bcrypt 校验密码
    → create_access_token({sub: user.id, username: user.username})

JWT payload 中的 sub 是用户 ID，后端随后用它查询 PostgreSQL 用户。

---

## 3. JWT 如何被每个请求使用

后端安全代码：backend/app/core/security.py

### 3.1 生成和解码

create_access_token() 把用户数据和过期时间写入 JWT，并使用 JWT_SECRET_KEY 和 HS256 签名。

decode_token() 验证签名和过期时间，读取：

    sub      → user_id
    username → 用户名

### 3.2 两种认证依赖

auth_router.py 提供：

- get_current_user()：没有 token 时返回 None，可选认证。
- get_current_user_required()：没有 token、token 无效或用户被禁用时返回 401 或 403。

会话和知识库管理接口使用必需认证；部分旧聊天、研究和资讯接口当前没有在路由签名中强制认证，必须结合具体业务逻辑判断访问边界。

### 3.3 前端自动附加

frontend/src/api/request/plugins/auth.ts 每次请求前读取 localStorage.auth.token，加入：

    Authorization: Bearer <JWT>

这就是为什么页面代码通常不需要手写 Authorization 头。

### 3.4 前端守卫和后端权限不是一层

AuthGuard 只判断前端状态里的 isLoggedIn，负责页面跳转，不是安全边界。

真正的资源权限由后端查询条件保证，例如：

    ChatSession.id == session_uuid
    ChatSession.user_id == current_user.id

因此，用户修改前端状态也不能合法读取别人的会话，前提是相关 Router 使用了必需认证和用户归属过滤。

---

## 4. 新 PostgreSQL 会话系统

模型位于 backend/app/models/chat.py。

### 4.1 ChatSession

关键字段：

    id
    user_id
    title
    session_type
    created_at
    updated_at

session_type 约定为 chat 或 deepsearch，但它是业务标记，不会自动决定研究接口。

### 4.2 ChatMessage

关键字段：

    id
    session_id
    role
    content
    thinking
    references_data
    image_results
    created_at

references_data 和 image_results 使用 PostgreSQL JSONB，允许消息保存结构化引用和图片结果。

### 4.3 外键和级联

会话属于用户，消息属于会话。删除会话时，SQLAlchemy relationship 的 delete-orphan 会删除其消息和附件关联。

---

## 5. 新会话 API

session_router.py 的主要接口：

    GET    /sessions
    POST   /sessions
    GET    /sessions/{session_id}
    PUT    /sessions/{session_id}
    DELETE /sessions/{session_id}
    GET    /sessions/{session_id}/messages
    POST   /sessions/{session_id}/messages

查询列表时，后端先按当前用户过滤，再按 updated_at 倒序分页，并统计每个会话的消息数量。

创建会话时，如果不传标题，默认是“新对话”；如果不传类型，Schema 默认是 chat。

添加消息时，后端会：

1. 解析 UUID。
2. 检查会话存在且属于当前用户。
3. 创建 ChatMessage。
4. 更新会话的 updated_at。
5. 如果是第一条用户消息，用前 20 个字符生成标题。
6. 提交事务并返回消息。

“先查归属再写入”是防止跨用户写入的关键。

---

## 6. 新聊天页如何使用会话

frontend/src/pages/chat/newchat.tsx：

1. 用户输入问题或点击推荐问题。
2. 调用 createSession() 创建 PostgreSQL 会话。
3. 通过页面跳转参数把问题带到 /chat/{sessionId}。
4. 详情页读取问题并发起聊天或 DeepResearch。

上传附件时，页面可能先创建一个会话，再上传附件，确保附件有 session_id。

frontend/src/pages/chat/index.tsx 的 send() 顺序是：

    1. 先把用户消息和空的助手消息放入本地 chat.list
    2. POST /sessions/{id}/messages 保存用户消息
    3. 根据搜索模式调用普通聊天或 /research/stream
    4. 持续更新本地助手消息
    5. 流结束后 POST /sessions/{id}/messages 保存助手最终内容

流式输出期间，助手消息先存在于前端内存；后端 PostgreSQL 消息是在流完成后由前端再写入。

实际边界：如果浏览器在生成过程中崩溃或网络中断，助手最终消息可能没有写入新会话表，但研究检查点可能已经保存部分状态。

---

## 7. DeepResearch 会话标记和真实请求模式

前端根据 deviceState.searchModes 是否为空决定助手消息显示为普通聊天还是 DeepResearch：

    searchModes 非空 → ChatType.Deepsearch
    searchModes 为空 → ChatType.Normal

DeepResearch 请求包含：

    {
      "query": "问题",
      "session_id": "PostgreSQL 会话 ID",
      "search_modes": ["web", "local"]
    }

必须区分：

- 前端消息的 ChatType.Deepsearch：显示层标记。
- 后端请求的 version="v2"：研究流程版本。
- PostgreSQL 的 session_type：会话记录上的业务类型。

当前新聊天页创建会话时通常只传标题，Schema 把 session_type 默认成 chat；之后搜索模式仍可以让该会话实际发起 DeepResearch。这是数据库类型标记和本次请求模式可能不一致的地方。

---

## 8. 旧 Redis 会话系统

旧聊天路由 backend/app/router/chat_router.py 通过依赖创建：

    DocumentService
    WebSearchService
    SessionService（Redis）
    ChatService

SessionService 使用：

    session:<session_id>                 → Hash，会话元数据
    session:<session_id>:messages        → Sorted Set，消息 ID 和时间
    message:<session_id>:<message_id>    → Hash，消息内容

它还限制：

- 最多保存 20 条消息。
- 生成提示词时最多使用约 5000 token 的历史。

旧 /chat/session 创建的是 Redis 会话 ID；新 /sessions 创建的是 PostgreSQL UUID。两者不是同一个存储对象，不能混用 ID 或假设消息自动同步。

---

## 9. 登出和安全边界

后端 /auth/logout 只返回成功；代码注释说明真正动作是前端清除 Token。当前没有展示 JWT 黑名单或服务端撤销表。

security.py 提供了默认 JWT 密钥字符串，生产环境必须通过环境变量设置随机的 JWT_SECRET_KEY。

前端把 token 放在 localStorage，使用简单，但如果页面存在 XSS，token 可能被读取。生产系统通常会评估 HttpOnly Cookie、CSRF 防护、短期 access token 和 refresh token 等方案。

这些是工程边界，不代表当前项目已经实现了生产增强方案。

还要特别区分“会话标识”和“授权凭证”：`/research/stream` 当前路由没有显式注入 `get_current_user_required`，传入的 `session_id` 主要用于研究流程、检查点和 Redis 取消标志，并不会自动验证它属于当前登录用户。不能仅凭一个 UUID 就推断请求已经完成会话所有权校验。

---

## 10. 恢复页面时发生什么

进入 /chat/{id} 后，前端会：

1. 读取当前会话已有消息。
2. 把 PostgreSQL 消息转换成 chat.list。
3. 如果有研究检查点，再加载完整 UI 状态。
4. 重建研究步骤、搜索结果、图表、报告和引用。

助手消息是否显示为 DeepResearch，当前还有一个启发式判断：历史助手消息内容长度很大时会被标成 Deepsearch。它不是从每条消息读取一个明确的研究版本字段。

---

## 11. 一张完整时序图

    浏览器
      │ POST /auth/login
      ▼
    FastAPI → PostgreSQL users → JWT 返回
      │
      ▼
    localStorage.auth.token
      │ Authorization: Bearer JWT
      ▼
    POST /sessions → PostgreSQL chat_sessions
      │
      ▼
    POST /sessions/{id}/messages → PostgreSQL 用户消息
      │
      ├─ 普通聊天：POST /chat/completion → 旧 Redis SessionService
      └─ DeepResearch：POST /research/stream → V2 ResearchState/SSE
      │
      ▼
    流结束后 POST /sessions/{id}/messages → PostgreSQL 助手消息

---

## 12. 练习

1. JWT 的 sub 保存什么？后端如何用它找回用户？
2. AuthGuard 为什么不能替代后端权限检查？
3. 新 PostgreSQL 会话和旧 Redis 会话分别由哪些接口创建？
4. 一条 DeepResearch 消息什么时候写入 PostgreSQL？
5. 为什么浏览器中断可能导致检查点存在但助手最终消息不存在？
6. session_type="chat" 是否一定代表这次请求不会走 DeepResearch？为什么？
7. 当前 /auth/logout 为什么不能称为服务端撤销 JWT？

### 我的回答

<!-- 在这里填写答案；下一次教学会逐题批改 -->


### 我的会话时序图

<!-- 在这里画出登录、创建会话、发送消息、SSE、保存助手消息 -->

