# DeepResearch 学习手册：第 41 课

## 用户认证：从注册到请求授权

这条链路是所有业务页面的前置条件。理解它可以回答：用户如何创建、密码存什么、Token 如何生成、前端如何保持登录，以及为什么前端守卫不能代替后端鉴权。

## 1. 后端的用户表

`backend/app/models/user.py` 的 `User` 表包含：

```text
id
username（唯一）
email（唯一）
hashed_password
is_active
is_superuser
created_at / updated_at
```

数据库不保存明文密码。`hashed_password` 是 bcrypt 结果；用户、会话、知识库、文档、长期记忆和检查点通过关系字段关联。

## 2. 请求和响应 Schema

`schemas/user.py` 把认证接口分成几种形状：

| Schema | 用途 |
|---|---|
| `UserCreate` | 注册，包含 username、email、password |
| `UserLogin` | JSON 登录，username 可以是用户名或邮箱 |
| `UserResponse` | 返回用户公开信息，不包含密码 |
| `TokenResponse` | 返回 access_token、token_type 和 user |
| `PasswordChange` | 修改密码，要求旧密码和新密码 |

`UserInDB` 适合内部对象，包含哈希密码和管理员字段；它不应该直接作为公开接口响应。

## 3. 注册时序

```text
前端 LoginPage.onRegister
  → api.auth.register()
  → POST /auth/register
  → 校验 username/email 是否重复
  → bcrypt 哈希 password
  → INSERT users
  → create_access_token(sub=user.id, username=user.username)
  → TokenResponse
  → authActions.login()
  → 跳回原路径
```

注册完成后直接返回 Token，所以用户不需要再次登录。用户名和邮箱重复时，Router 先返回 400；密码长度在 Schema 和前端表单两边都有约束，但后端校验才是可信边界。

## 4. 登录时序

```text
登录表单
  → POST /auth/login
  → 先按 username 查询
  → 找不到再按 email 查询
  → bcrypt.checkpw()
  → 检查 is_active
  → 签发 JWT
```

项目还保留 `/auth/token`，使用 OAuth2 表单格式。它和 `/auth/login` 都调用 `authenticate_user()`，区别主要是请求格式和兼容对象。

## 5. JWT 结构和验证

`core/security.py` 创建令牌时把：

```json
{
  "sub": "用户 UUID",
  "username": "用户名",
  "exp": "过期时间"
}
```

用 `JWT_SECRET_KEY` 和 `JWT_ALGORITHM` 签名。`decode_token()` 验签并把 `sub` 转成 `TokenData.user_id`。Router 的 `get_current_user_required()` 再根据这个 id 查询数据库，并检查用户是否仍然 active。

所以“Token 签名有效”不等于“用户一定能访问”：数据库中不存在用户或用户被禁用时，仍会失败。

## 6. 可选认证和必须认证

项目有两个依赖：

- `get_current_user()`：没有 Token 时返回 `None`，适合兼容匿名或可选登录的接口。
- `get_current_user_required()`：没有 Token、Token 无效、用户不存在或被禁用时抛出 401/403。

阅读任意 Router 时，先看它使用哪个依赖，就能判断接口是否强制登录。不能只因为前端页面在 `AuthGuard` 下面，就断言后端接口一定有权限保护。

## 7. 前端保存和发送 Token

`store/auth.ts` 用 Valtio 保存：

```text
token
user
isLoggedIn
```

它从 `localStorage['auth']` 恢复初始状态，并通过 `subscribe(authState, ...)` 自动写回。`authActions.logout()` 清空状态和 localStorage。

`api/request/plugins/auth.ts` 在请求拦截器中把 Token 放入：

```http
Authorization: Bearer <token>
```

前端登录状态的作用是改善导航体验；真正的授权判断仍由后端 `get_current_user_required()` 完成。

## 8. AuthGuard 和登录后回跳

`AuthGuard` 读取 `authState.isLoggedIn`：

```text
未登录 → Navigate('/login', state={ from: location })
已登录 → 渲染子页面
```

`LoginPage` 从 `location.state.from.pathname` 读取原路径，登录或注册成功后 `navigate(from, { replace: true })`。这是一条纯前端导航恢复链，不是服务端重定向。

## 9. 修改密码和登出边界

修改密码会校验旧密码，再重新生成 bcrypt 哈希并提交数据库。登出接口目前只返回成功消息，源码注释明确表示前端清除 Token 即可；服务器没有记录一个撤销列表。因此用户点击退出后，旧 JWT 在过期前是否仍能被接受，要结合当前系统是否实现额外失效机制判断，不能把前端 localStorage 清理等同于 Token 吊销。

## 10. 本链路的风险点

1. `core/security.py` 存在硬编码 JWT 默认密钥，生产环境必须通过环境变量覆盖并避免提交真实密钥。
2. Token 存在 localStorage，若前端存在 XSS，令牌可能被读取；项目当前需要结合部署安全和内容渲染策略评估风险。
3. 可选认证依赖若被误用于敏感接口，可能出现接口级权限缺失。
4. 前端 `isLoggedIn` 可以被 localStorage 篡改，不能作为后端授权依据。

## 11. 本课练习

### 练习 A：画注册链

从 `LoginPage.onRegister` 画到 `User` 插入、bcrypt、JWT、`authState` 和页面跳转。

### 练习 B：比较两种依赖

用一个表比较 `get_current_user()` 和 `get_current_user_required()` 在缺少 Token、Token 无效和用户被禁用时的行为。

### 练习 C：证明后端授权

说明如何用浏览器开发者工具或 curl 验证 `Authorization` 头确实被发送，以及如何验证服务端拒绝无效 Token。

## 12. 面试追问

1. 为什么数据库保存 bcrypt 哈希而不是密码？
2. JWT 的 `sub`、`exp` 分别做什么？
3. 为什么 AuthGuard 不能替代后端依赖校验？
4. `/auth/login` 和 `/auth/token` 为什么可以同时存在？
5. 用户退出后，如何设计真正的 Token 吊销？

