# DeepResearch 学习手册·第 56 课

## 从注册到资源授权：用户身份如何贯穿系统

本课追踪一个用户身份从注册开始，如何进入 JWT、浏览器存储、Axios 请求头，最后影响知识库、会话和检查点能否访问。

---

## 1. 注册和登录不是“前端记住用户名”

后端认证入口是 backend/app/router/auth_router.py。

注册流程：

~~~~text
POST /auth/register
  ↓
Pydantic UserCreate 校验
  ↓
查询用户名和邮箱是否重复
  ↓
bcrypt 哈希密码
  ↓
写入 PostgreSQL users
  ↓
create_access_token
  ↓
返回 access_token + user
~~~~

登录流程类似，但不会新建用户：

~~~~text
POST /auth/login
  ↓
按用户名查找；找不到再按邮箱查找
  ↓
bcrypt.checkpw 校验密码
  ↓
检查 is_active
  ↓
生成 JWT
  ↓
返回 token 和用户信息
~~~~

密码不会以明文写入数据库。数据库中的 hashed_password 是 bcrypt 结果。

---

## 2. JWT 里面最关键的是什么

backend/app/core/security.py 的 create_access_token 会把传入数据和过期时间写入 JWT：

~~~~python
{
    "sub": "用户 UUID",
    "username": "用户名",
    "exp": "过期时间"
}
~~~~

后端 decode_token 读取：

- sub 作为 user_id。
- username 作为辅助信息。
- exp 由 JWT 库验证是否过期。

真正授权时，后端不会只相信 Token 里的用户名。get_current_user_required 会再根据 user_id 查询 PostgreSQL User，并检查用户是否存在和是否 active。

---

## 3. 可选认证和必须认证

auth_router.py 定义两个依赖。

### get_current_user

- 没有 Token 时返回 None。
- Token 无效时返回 None。
- 用户不存在时返回 None。
- 适合允许匿名访问、登录后增强功能的接口。

### get_current_user_required

- 没有 Token 时返回 401。
- Token 无效时返回 401。
- 用户不存在时返回 401。
- 用户被禁用时返回 403。
- 适合知识库、会话、记忆等必须隔离用户资源的接口。

这两个依赖的返回结果不同，所以查看 Router 签名是判断接口安全边界的第一步。

---

## 4. 前端如何保存登录状态

frontend/src/store/auth.ts 使用 Valtio 保存：

- token
- user
- isLoggedIn

状态初始化时从 localStorage 的 auth 键读取。状态变化后，subscribe 自动写回 localStorage。

因此刷新浏览器后，前端可以恢复登录界面状态。

但要注意：localStorage 中存在 token 不等于 token 永远有效。后端 JWT 过期、用户被删除或被禁用后，API 仍可能返回 401/403。

---

## 5. Axios 如何自动带上 Token

frontend/src/api/request/plugins/auth.ts 在请求拦截器中：

1. 从 localStorage 的 auth 读取 token。
2. 如果存在，设置：

~~~~text
Authorization: Bearer <token>
~~~~

所以具体业务 API 不需要每次手写 Authorization。

这也是排查认证失败时的固定顺序：

~~~~text
localStorage.auth 是否有 token
  ↓
authPlugin 是否读取到 token
  ↓
Network 请求是否带 Authorization
  ↓
JWT 是否能 decode
  ↓
数据库是否找到用户
  ↓
资源查询是否按 user_id 过滤
~~~~

---

## 6. AuthGuard 和后端鉴权不是一回事

frontend/src/components/auth-guard/index.tsx 只负责页面导航：

- isLoggedIn 为 false 时跳转 /login。
- 同时保存原始 location。
- 登录后可返回原路径。

它不能保护后端接口。用户可以绕过浏览器直接调用 API，所以后端必须继续使用 get_current_user_required。

正确的分工是：

~~~~text
AuthGuard：避免未登录用户进入页面
后端依赖：真正拒绝未授权请求
数据库过滤：保证用户只能看到自己的资源
~~~~

---

## 7. 知识库资源如何隔离

knowledge_router.py 查询知识库时同时使用：

~~~~python
KnowledgeBase.id == kb_uuid,
KnowledgeBase.user_id == current_user.id
~~~~

文档上传、文档列表、切片查看和删除也会先验证知识库属于当前用户。

这意味着即使攻击者知道另一个知识库的 UUID，只凭 UUID 也不能通过正常认证依赖读到它。

---

## 8. PostgreSQL 新会话如何隔离

sessions 路由的查询都带：

~~~~python
ChatSession.user_id == current_user.id
~~~~

创建会话时，把当前用户 ID 写入 ChatSession。读取详情、修改标题、删除会话、读取消息和新增消息时，都会先验证会话所有权。

因此会话 ID 不是授权凭据。它只是定位对象的标识，真正的授权条件是 Token 对应的 user_id 与会话的 user_id 一致。

---

## 9. 为什么有时“登录了却看不到历史”

项目同时存在两套会话体系：

### PostgreSQL 新会话

- Router：/sessions
- 模型：ChatSession、ChatMessage
- 需要当前用户认证
- 适合用户持久化历史

### Redis 旧会话

- Router：/chat/session
- 服务：SessionService
- 兼容旧聊天链
- 不等于 PostgreSQL 的 ChatSession

如果前端创建的是旧 /chat/session，会话记录可能不出现在 /sessions 列表中。接口路径、服务类和存储位置必须一起确认。

---

## 10. 登出为什么不等于服务端撤销 JWT

/auth/logout 的后端实现返回“登出成功”，注释明确说明前端清除 Token 即可。

前端 logout 会：

- token 设为 null。
- user 设为 null。
- isLoggedIn 设为 false。
- 删除 localStorage.auth。

但服务端没有维护 JWT 黑名单，也没有立即让已经签发的 Token 失效。只要 Token 未过期，直接持有它的客户端理论上仍可能调用接口。

这是当前实现的安全边界，生产系统通常需要短过期 Token、刷新 Token、服务端撤销机制或 Token 版本控制。

---

## 11. 修改密码后的边界

修改密码接口需要当前认证用户，验证旧密码后写入新的 bcrypt 哈希。

当前实现没有显式撤销该用户已经签发的其他 JWT。也就是说，旧 Token 的生命周期仍要看 exp。

---

## 12. 一次 401 排错例子

现象：知识库页面提示未授权。

按层排查：

1. localStorage 是否保存 auth。
2. auth 中 token 字段是否为空或 JSON 损坏。
3. Network 请求是否带 Bearer Token。
4. JWT 是否过期或签名不匹配。
5. JWT 的 sub 是否是合法用户 UUID。
6. PostgreSQL users 表是否有该用户。
7. 用户 is_active 是否为真。
8. 当前知识库是否属于该用户。

不要一看到 401 就修改知识库页面。401 可能发生在请求发送前、JWT 解码时或用户查询时。

---

## 13. 小练习

用户已登录，浏览器页面也能打开，但 GET /knowledge-bases 返回 401。最合理的排查顺序是什么？

A. 先改知识库列表 CSS

B. 检查 localStorage token、Authorization 请求头、JWT 解码和用户数据库记录

C. 直接把后端接口改成匿名访问

D. 只清空浏览器缓存

---

## 留白：身份链路笔记

注册写入：

JWT 的 user_id 来源：

Token 保存位置：

请求头：

后端必须认证依赖：

资源所有权过滤：

旧 Redis 会话与新 PostgreSQL 会话的区别：

登出后的服务端限制：

---

## 源码定位

- backend/app/router/auth_router.py：注册、登录、当前用户和登出
- backend/app/core/security.py：bcrypt 和 JWT
- backend/app/models/user.py：用户模型
- backend/app/router/session_router.py：PostgreSQL 会话授权
- backend/app/router/knowledge_router.py：知识库资源授权
- frontend/src/store/auth.ts：登录状态持久化
- frontend/src/api/auth.ts：认证请求
- frontend/src/api/request/plugins/auth.ts：Authorization 请求头
- frontend/src/components/auth-guard/index.tsx：前端页面守卫

