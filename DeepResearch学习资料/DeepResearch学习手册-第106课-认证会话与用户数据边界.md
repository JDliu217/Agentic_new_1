# DeepResearch 学习手册：第 106 课

## 从登录到研究请求：认证、会话与用户数据边界

这一课回答一个工程问题：系统怎样知道“这个请求属于哪个用户”，以及为什么前端显示登录不等于后端已经完成授权。

## 1. 注册和登录

源码：

```text
backend/app/router/auth_router.py
backend/app/core/security.py
```

注册流程：

```text
用户名、邮箱、密码
→ 检查是否重复
→ bcrypt 哈希密码
→ User 写入 PostgreSQL
→ create_access_token()
→ 返回 access_token 和 user
```

登录流程：

```text
用户名或邮箱 + 密码
→ 查询 User
→ bcrypt 校验
→ JWT payload 写入 sub=user.id、username、exp
→ 返回 TokenResponse
```

数据库不保存明文密码，只保存 `hashed_password`。

## 2. JWT 做什么

JWT 是后端签发给客户端的身份凭证。项目中 payload 主要包含：

```text
sub = 用户 ID
username = 用户名
exp = 过期时间
```

后端用 `JWT_SECRET_KEY` 和算法验证签名和过期时间，然后根据 `sub` 查数据库用户。

## 3. 前端怎样携带 Token

源码：

```text
frontend/src/store/auth.ts
frontend/src/api/request/plugins/auth.ts
```

前端把 Token 和用户信息保存到 `localStorage` 的 `auth` 键中。Axios 请求插件自动添加：

```http
Authorization: Bearer <token>
```

`AuthGuard` 负责未登录时跳转登录页，但它只是前端导航控制。

```text
AuthGuard 不能代替后端权限校验
```

## 4. `get_current_user` 和 `get_current_user_required`

```text
get_current_user：没有 Token 时返回 None
get_current_user_required：没有 Token 或 Token 无效时返回 401
```

知识库、会话、记忆和数据库等用户私有资源通常使用 required 版本。

## 5. 会话和用户的关系

`ChatSession` 保存：

```text
session.id
session.user_id
title
session_type
```

读取会话时，代码同时查询：

```text
ChatSession.id == session_id
ChatSession.user_id == current_user.id
```

这一步防止用户只凭猜到的 `session_id` 读取别人的消息。

## 6. 一次普通请求的身份时序

```text
浏览器从 localStorage 取 Token
→ Axios 添加 Authorization
→ FastAPI OAuth2PasswordBearer 取 Token
→ decode_token 验证 JWT
→ sub 找到 User
→ Router 得到 current_user
→ 查询资源时附加 user_id 过滤
```

身份验证和资源授权是两步：

```text
验证你是谁
≠ 证明你能访问这条数据
```

## 7. 研究接口的当前边界

`POST /research/stream` 当前函数签名主要接收请求和服务依赖，没有像知识库和会话接口一样直接声明 `current_user: User = Depends(...)`。

因此学习时要诚实区分：

```text
会话和知识库的用户归属校验较明确
研究流和检查点部分接口需要继续加强 session/user_id 授权边界
```

不能因为前端页面有登录守卫，就断言所有后端研究资源都已经完成授权隔离。

## 8. 登出边界

当前登出接口的语义是：

```text
前端清除 Token
```

服务端没有实现 JWT 黑名单或撤销表。因此 Token 在自然过期前，服务端通常仍能验证它。

生产系统可以使用短期 access token 加 refresh token，或者引入服务端撤销机制。

## 9. 本课练习

1. 为什么密码要 bcrypt 哈希而不是直接保存？
2. AuthGuard 为什么不能代替后端权限校验？
3. JWT 身份验证和 `session_id + user_id` 资源授权有什么区别？
4. 当前研究接口的用户边界有什么风险？
