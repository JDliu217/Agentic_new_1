# DeepResearch 学习手册：第 87 课

## 认证、会话与研究请求的用户边界

前面我们追踪了研究内容本身。这一课回答另一个工程问题：系统怎样知道“这是哪个用户的哪一次研究”，以及为什么 `session_id` 不能简单理解成用户 ID。

## 1. 登录得到什么

文件：`backend/app/router/auth_router.py`

登录流程是：

```text
用户名或邮箱 + 密码
→ PostgreSQL 查询 User
→ bcrypt 校验密码
→ 创建 JWT access_token
→ 返回 token 和用户信息
```

前端把登录结果放入 `authState`，并持久化到浏览器 `localStorage`。请求插件从 `localStorage` 读取 token，自动添加：

```http
Authorization: Bearer <token>
```

## 2. 前端路由守卫和后端依赖是两道门

前端 `AuthGuard` 只控制页面能否进入。它检查 `authState.isLoggedIn`，没有登录就跳转 `/login`。

后端路由通过 `get_current_user_required` 解码 JWT、查询用户并检查用户是否 active。前端守卫不能代替后端授权，因为用户可以绕过浏览器直接调用 API。

## 3. 会话是什么

文件：`backend/app/router/session_router.py`

登录用户创建会话时，后端创建 `ChatSession`：

```text
id
user_id
title
session_type = chat 或 deepsearch
created_at
updated_at
```

后续获取会话、读取消息、重命名、删除和新增消息时，查询条件都会同时包含：

```text
session.id == session_id
session.user_id == current_user.id
```

这才保证用户只能访问自己的会话。

## 4. session_id 的作用

DeepResearch 前端把当前会话 ID 放到研究请求中：

```json
{
  "query": "用户问题",
  "session_id": "当前会话 UUID",
  "search_modes": ["web", "local"]
}
```

研究服务使用它关联：

```text
检查点
取消标志
研究恢复
前端当前研究上下文
```

它标识的是一次会话上下文，不是身份凭证。身份仍然来自 JWT。

## 5. 当前代码中的重要边界

会话 Router 明确要求登录并验证用户所有权；但 POST `/research/stream` 的 `stream_research()` 当前函数签名没有直接声明 `current_user: User = Depends(get_current_user_required)`。

这意味着阅读项目时要区分：

```text
前端只有登录用户才能进入页面
会话接口有用户归属校验
研究流接口本身是否强制 JWT，需要单独核对应用中间件和部署配置
```

不能因为页面被 AuthGuard 保护，就自动断言每一条后端流式接口都完成了资源授权。

## 6. 普通聊天消息和 ResearchState 不是同一个东西

普通聊天完成后，用户消息和助手消息可以写入 `ChatMessage`，用于会话历史和下次加载。

DeepResearch 运行过程中的 `ResearchState` 是任务工作内存，包含大纲、事实、图表和审核状态；阶段检查点把它保存到 `ResearchCheckpoint`。

可以这样区分：

| 对象 | 主要用途 |
|---|---|
| `ChatSession` | 用户的会话容器 |
| `ChatMessage` | 页面聊天消息历史 |
| `ResearchState` | 一次研究任务的中间工作状态 |
| `ResearchCheckpoint` | 研究状态的持久化快照 |
| JWT | 证明调用者是谁 |

## 7. 一次研究请求的身份和数据流

```text
登录
→ JWT 保存到 localStorage
→ 创建或打开 ChatSession
→ React 取 session_id
→ 请求插件附带 JWT
→ deepsearch 发送 session_id
→ ResearchGraph 用 session_id 保存检查点/处理取消
→ 页面通过当前会话展示研究结果
```

如果其中任何一层使用了错误的 ID，可能出现：

```text
研究结果保存到错误会话
取消了另一项研究
恢复不到检查点
页面和后端的结果对应不上
```

## 8. 排错顺序

看到 `401`：查 localStorage token、请求头、JWT 解码和用户状态。

看到 `404 session`：查 UUID 格式、会话是否存在和 user_id 是否匹配。

研究能启动但恢复失败：查 checkpoint 的 session_id、数据库记录和 `resume=True`。

停止按钮无效：查当前 session_id 是否和后端 Redis 取消 key 使用的是同一个值。

## 9. 本课练习

请回答：

1. JWT、`session_id`、`ResearchState` 分别代表什么？
2. 为什么前端 `AuthGuard` 不能替代后端用户归属校验？
3. 普通 `ChatMessage` 和 `ResearchCheckpoint.state_json` 的用途有什么不同？
