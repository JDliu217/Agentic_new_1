# DeepResearch 学习手册·第 107 课：认证、会话与研究边界练习

## 本课目标

学完后，你应该能用自己的话回答：

1. 用户登录后，密码、JWT、浏览器状态和后端用户对象分别在哪里？
2. 普通会话为什么能做到“只能看自己的数据”？
3. `ResearchCheckpoint` 虽然有 `user_id`，为什么当前研究接口仍不能直接证明已经完成隔离？

## 一、先建立运行模型

```text
登录表单
  -> POST /auth/login
  -> 后端查 User
  -> bcrypt 校验密码
  -> 签发 JWT(sub=user.id, exp=过期时间)
  -> 前端保存到 localStorage['auth']
  -> Axios 每次请求添加 Authorization: Bearer <token>
  -> FastAPI 依赖 decode_token()
  -> 根据 sub 查询当前 User
```

密码不会放进 JWT，也不会以明文保存。JWT 只是“这是谁”的可验证凭证；真正的资源过滤仍然要在每个资源接口中使用当前用户 ID。

## 二、源码证据

### 1. 后端密码和 JWT

- `backend/app/core/security.py:30-42`：bcrypt 校验和生成密码哈希。
- `backend/app/core/security.py:45-54`：创建 JWT，并加入 `exp`。
- `backend/app/core/security.py:57-67`：验证签名、读取 `sub` 和 `username`。
- `backend/app/router/auth_router.py:150-177`：登录时查询用户、校验密码、签发 token。

登录成功后，`sub` 是用户 UUID。后续接口不应相信前端自己传来的 `user_id`，而应相信后端从 token 解出的用户。

### 2. 前端 token 的去向

- `frontend/src/store/auth.ts`：把 `token`、用户信息和登录状态保存到 `localStorage['auth']`。
- `frontend/src/api/request/plugins/auth.ts:14-33`：读取 token，并添加 `Authorization: Bearer ...`。
- `frontend/src/components/auth-guard/index.tsx`：没有登录状态时跳转 `/login`。

`AuthGuard` 只是页面访问控制，不是后端安全边界。用户可以绕过页面直接发送 HTTP 请求，所以后端仍必须验证 token。

### 3. 普通会话的资源隔离

`backend/app/models/chat.py:37-50` 中，`ChatSession` 保存 `user_id`；会话路由查询时使用当前用户过滤。因此用户 A 的 token 不能正常读取用户 B 的聊天会话。

知识库路由也使用 `KnowledgeBase.user_id == current_user.id`。这就是“身份认证”之后的“资源授权”：认证回答“你是谁”，授权回答“你能访问哪条数据”。

### 4. 研究检查点的边界

`backend/app/models/research.py:18-26` 中，`ResearchCheckpoint` 有 `session_id`、`user_id`、`state_json`、`ui_state_json` 和 `final_report`。

但当前 `backend/app/router/research_router.py` 的研究、检查点、恢复和取消接口没有统一声明 `current_user: User = Depends(get_current_user_required)`，也没有在读取 `session_id` 时统一追加 `ResearchCheckpoint.user_id == current_user.id`。

因此要区分两句话：

- “模型设计支持保存用户 ID”：源码可以证明。
- “所有研究接口已经完成用户隔离”：当前源码不能证明。

这是学习项目时必须能主动发现的工程差异，也属于面试中的可靠性和安全追问点。

## 三、用一个请求追踪数据

假设用户 ID 为 `u1`，会话 ID 为 `s1`：

```text
浏览器 localStorage['auth'].token
  -> 请求头 Authorization: Bearer eyJ...
  -> decode_token(token).user_id == u1
  -> /sessions 查询 ChatSession.user_id == u1
  -> 返回 s1 的消息
```

对于当前研究接口，如果只传 `session_id=s1` 而没有后端当前用户依赖，就不能仅凭这个流程断言 `s1` 属于 `u1`。这就是“有字段”与“有强制校验”的区别。

## 四、最小练习

请不要复制材料原句，按下面格式回答：

### 练习 1：概念—源码—运行

分别解释 `ResearchState`、Milvus、SSE：

```text
概念：它是什么，解决什么问题？
源码：项目中哪个文件/函数使用它？至少写一个字段或调用。
运行：用户发起一次研究后，它什么时候产生数据，谁读取这些数据？
```

### 练习 2：认证判断题

判断并说明理由：

1. `AuthGuard` 存在，所以直接调用后端接口也安全。
2. JWT 的 `sub` 可以帮助后端找到当前用户。
3. `ResearchCheckpoint.user_id` 存在，就等于检查点接口已经完成用户隔离。
4. `ChatSession.user_id` 过滤属于授权，不属于密码认证。

### 练习 3：故障定位

页面显示“已登录”，但 `GET /sessions` 返回 401。请按顺序列出你会检查的三层证据：浏览器、请求、后端。

## 五、面试追问预告

- 为什么 JWT 登出接口当前不能真正撤销已经签发的 token？
- `localStorage` 保存 JWT 有什么工程风险？
- 如何给 `/research/checkpoint/{session_id}` 补上用户隔离？
- 研究流使用 SSE 时，如何在认证失败后停止继续发送结果？

本课的验收标准不是背出名词，而是能指出“身份从哪里来、资源如何过滤、哪条路径目前没有过滤”。
