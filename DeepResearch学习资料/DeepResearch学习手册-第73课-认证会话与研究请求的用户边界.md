# DeepResearch 学习手册：第 73 课

## 认证、会话与研究请求的用户边界

这一课解释三个经常被混淆的概念：

```text
用户认证：你是谁？
会话：这次聊天属于哪一段上下文？
研究检查点：这次 DeepResearch 执行到哪里？
```

## 1. 登录后发生了什么

前端调用：

```text
frontend/src/api/auth.ts::login()
  → POST /auth/login
```

后端 `auth_router.py` 会：

```text
查询用户
→ bcrypt 校验密码
→ 检查 is_active
→ create_access_token()
→ 返回 access_token 和 user
```

JWT 里至少包含：

```text
sub       用户 ID
username  用户名
exp       过期时间
```

密码不会以明文保存在数据库，只保存 bcrypt 哈希。

## 2. Token 如何进入后续请求

登录页面拿到响应后调用：

```text
authActions.login(data.access_token, data.user)
```

`frontend/src/store/auth.ts` 把认证状态保存到 `localStorage` 的 `auth` 项中。

之后 Axios 认证插件会在请求发送前读取这个值，并添加：

```http
Authorization: Bearer <token>
```

后端使用 `get_current_user_required()` 时会：

```text
读取 Bearer Token
→ 解码 JWT
→ 取得 sub 中的用户 ID
→ 查询 users 表
→ 检查用户是否启用
→ 把 User 注入路由函数
```

## 3. AuthGuard 和后端鉴权不是一回事

前端 `AuthGuard` 只做页面跳转：

```text
authState.isLoggedIn == false
→ Navigate to /login
```

它的作用是改善导航体验，不能保护后端接口。真正的数据安全依赖后端的 JWT 校验和资源归属检查。

应记住：

```text
AuthGuard：控制用户能否进入页面
get_current_user_required：控制请求能否通过后端认证
```

## 4. `session_id` 和 `user_id` 的区别

### `user_id`

表示“哪个用户”。它来自 JWT 的 `sub`，用于：

```text
过滤用户自己的会话
过滤知识库
过滤检查点
```

### `session_id`

表示“哪一次聊天或研究”。它用于：

```text
关联聊天消息
关联研究取消标志
关联 ResearchCheckpoint
恢复某一次研究
```

可以用这个关系记忆：

```text
一个 user_id 可以拥有多个 session_id
一个 session_id 应该属于一个 user_id
```

## 5. 研究请求的当前真实边界

研究 POST 路由的请求模型包含：

```text
query
session_id
search_modes
version
```

它会把 `session_id` 传给 V2 服务。V2 还支持把 `_user_id` 放入状态，以便保存检查点时关联用户。

但当前 `POST /research/stream` 的函数签名没有直接声明：

```python
current_user: User = Depends(get_current_user_required)
```

因此必须准确区分两件事：

```text
前端通常要求先登录才能进入研究页面
研究路由本身是否强制后端 JWT，需要单独检查
```

不能因为页面有 AuthGuard，就直接断言研究接口已经完成后端授权。

这是阅读代码时很重要的工程习惯：不要只看调用方，要看被调用的路由函数签名和依赖。

## 6. 检查点和会话的关系

`ResearchCheckpoint` 保存：

```text
session_id
user_id
query
phase
iteration
state_json
ui_state_json
final_report
status
```

其中：

```text
session_id：找到哪一次研究
user_id：确认属于哪个用户
state_json：后端 Agent 状态
ui_state_json：前端步骤、来源、图表和报告展示状态
```

检查点不是普通聊天消息的替代品。聊天消息保存对话记录，检查点保存研究流程的中间状态。

## 7. 登出不等于服务端撤销 JWT

当前前端登出会清理本地 `auth` 状态。后端 `/auth/logout` 主要返回登出结果，代码没有看到完整的 JWT 黑名单或撤销表。

因此在当前实现中：

```text
前端删除 Token：浏览器后续请求不再自动携带
旧 Token 在过期前：服务端通常仍能验证其签名
```

这是一个需要在生产环境进一步加强的安全边界。

## 8. 排错示例

### 页面跳转到登录页

先看：

```text
localStorage.auth 是否存在
authState.isLoggedIn 是否为 true
AuthGuard 是否重定向
```

### 接口返回 401

再看：

```text
请求是否有 Authorization 头
Token 是否过期
JWT_SECRET_KEY 是否一致
sub 对应用户是否存在或已禁用
```

### 能登录但看到了别人的会话

检查：

```text
后端是否用当前 user_id 过滤 session_id
路由是否只相信前端传入的 ID
查询是否经过 get_current_user_required()
```

### 研究能启动但检查点没有用户归属

检查：

```text
研究路由是否注入 current_user
Graph.run() 是否收到 user_id
save_checkpoint() 是否写入 user_id
```

## 9. 本课练习

请回答：

1. JWT 的 `sub` 在本项目中表示什么？
2. `user_id` 和 `session_id` 分别解决什么问题？
3. 为什么 AuthGuard 不能替代后端权限校验？
4. 如果页面显示已登录，但 `/research/stream` 返回 401，你先检查哪三层？
5. 为什么不能仅凭“研究页面必须登录”就断言研究 Router 已经完成后端授权？

## 10. 本课结论

认证、会话和研究状态是三条相关但不同的数据线：

```text
JWT / user_id
  → 确认用户身份和资源归属

session_id
  → 关联一次聊天或研究

ResearchCheckpoint
  → 保存这次研究的后端状态和前端恢复状态
```

