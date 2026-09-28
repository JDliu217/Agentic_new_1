# DeepResearch 学习手册·第 63 课

## `/research/stream` 返回 500：认证、配置和外部依赖排错

上一课的场景是：前端构建通过，但登录后研究请求返回 500。本课把它拆成三段：请求是否有资格进入、应用是否正确配置、研究过程中外部服务是否可用。

---

## 1. 先区分构建问题和运行问题

`npm run build` 通过只能说明：

- TypeScript/TSX 能被 Vite 打包。
- 依赖和导入在构建阶段基本可解析。
- 可以生成前端静态资源。

它不能证明：

- FastAPI 已启动。
- JWT 已正确签发和发送。
- PostgreSQL 可连接。
- Redis、Milvus、LLM、搜索 API 可用。
- `/research/stream` 能完成六个 Agent。

因此前端构建成功后出现 500，排查重点应转到后端响应体和后端日志。

---

## 2. 先看状态码，别把 401 当 500

需要先校对一个当前实现边界：`research_router.py` 中 `stream_research()` 的签名目前没有显式注入 `get_current_user_required`。前端虽然会通过 Axios 自动携带 Token，但不能仅凭这一点断言 `/research/stream` 当前一定强制 JWT。研究路由的 `session_id` 也不能自动证明会话属于当前用户。若实际观察到 401，应同时检查代理、中间件或部署层是否增加了认证；不能把 401 直接归因于这段 Router。

认证依赖在 `auth_router.py`：

```text
get_current_user_required()
  → 读取 Bearer Token
  → decode_token()
  → 按 token 的 user_id 查 PostgreSQL
  → 检查 user.is_active
```

前端 `authPlugin` 从 `localStorage.auth` 读取 token，并添加：

```http
Authorization: Bearer <token>
```

常见结果：

| 状态码 | 优先判断 |
|---:|---|
| 401 | Token 缺失、过期、签名不匹配或用户不存在 |
| 403 | 用户被禁用，或权限规则拒绝 |
| 422 | 请求体字段不符合 `ResearchRequest` |
| 500 | 已进入后端处理，但内部发生异常 |

如果实际是 401，不要把问题归因于 Agent 或 LLM。

---

## 3. 为什么登录成功仍可能研究失败

登录只证明：

1. 登录请求到达了 FastAPI。
2. 用户查询和密码校验成功。
3. 后端签发了 JWT。

研究请求还要额外经过：

- 研究请求字段校验。
- V2 Service 初始化。
- LLM 配置读取。
- 搜索服务初始化。
- PostgreSQL/检查点操作。
- Redis 取消检查。
- Agent 的外部调用。

所以“能登录”不是“DeepResearch 可用”的充分条件。

---

## 4. 后端启动阶段的数据库风险

`app_main.py` 在导入模型后执行：

```python
Base.metadata.create_all(bind=engine)
```

这发生在应用生命周期启动之前。如果 PostgreSQL 地址、账号或数据库不存在，应用可能在真正监听端口前就失败。

因此排查顺序是：

1. 看 Uvicorn 是否真正监听 `8000`。
2. 访问 `/hello`。
3. 查看导入阶段的数据库异常。
4. 确认 PostgreSQL 的 host、port、user、password、database。
5. 再检查登录和研究接口。

如果 `/hello` 也无法访问，优先查启动和数据库导入；如果 `/hello` 正常而研究返回 500，再进入研究依赖排查。

---

## 5. LLM 配置是研究主链的入口依赖

`LLMConfig` 默认读取：

```text
DASHSCOPE_API_KEY
LLM_BASE_URL
BOCHA_API_KEY
```

研究服务初始化时会读取 LLM API Key、Base URL、搜索 Key、默认模型和研究配置。

要检查：

- API Key 是否为空。
- Base URL 是否能访问。
- 模型名称是否被当前服务支持。
- 当前项目是否在不同模块使用了不同环境变量名。
- 失败是否发生在 LLM 请求前，还是 LLM 返回后 JSON 解析阶段。

不要把真实密钥打印到日志。可以只记录是否为空、Base URL 主机名和模型名。

---

## 6. 研究请求的分层排错表

```text
无法连接 8000
  → 启动日志、Python 依赖、数据库导入、端口

/hello 正常，/auth/login 失败
  → PostgreSQL、用户表、密码哈希、请求体

登录成功，/research/stream 返回 401/403
  → localStorage、Authorization、JWT 密钥、用户状态

登录成功，/research/stream 返回 422
  → query、session_id、version、search_modes 的请求 JSON

返回 500 且没有 SSE
  → Router、Service 初始化、配置、数据库/Redis

已经收到 SSE，随后 error
  → 当前阶段 Agent、LLM、搜索、Milvus 或 CodeWizard

收到结果但前端不显示
  → SSE 缓冲解析、事件映射、React 状态更新
```

这张表的关键是先判断故障发生在流开始之前还是流已经开始之后。

---

## 7. 不要只看后端的“500”

500 只是 HTTP 层的结果，不是根因。应该同时收集：

1. 浏览器 Network 的响应体。
2. FastAPI/Uvicorn 的异常堆栈。
3. 最后一个成功的 SSE 事件。
4. 当前 `ResearchState.phase`。
5. `errors`、`messages`、`code_executions` 等状态字段。
6. 外部服务的响应码和耗时。

例如：

- 没有任何事件：看请求入口或 Service 初始化。
- 有 `phase=researching`：说明规划阶段已经完成，重点转向 DeepScout。
- 有 `phase=analyzing` 后报错：重点看 DataAnalyst、CodeWizard 和数据格式。
- 有 `phase=writing` 但没有完成：重点看 LeadWriter 输入和 LLM 返回。

---

## 8. 标准回答

上一课练习的标准回答是：

> `npm run build` 通过只证明前端静态代码可以被 Vite 打包，不证明后端、数据库、JWT、LLM 或 Agent 链路可用。下一步先看浏览器 Network 的实际状态码和响应体，再看 FastAPI 启动日志、`/hello`、数据库连接、JWT 请求头和 `/research/stream` 的请求体。如果已经进入 SSE，则根据最后一个事件和当前阶段检查对应 Agent 及外部依赖；不能因为前端构建成功就断言 DeepResearch 可用。

---

## 练习

现在判断这个场景：

```text
/hello 返回 200
/auth/login 返回 200
/research/stream 返回 401
浏览器请求头中没有 Authorization
```

请回答：

1. 根因更可能在哪一层？
2. 应先查 `auth_router.py`、LLM 配置，还是前端 `authPlugin`？
3. 为什么此时不应该先查六个 Agent？

参考答案：问题更可能在前端认证请求插件或 localStorage Token 读取，先查 `frontend/src/api/request/plugins/auth.ts` 和 `localStorage.auth`；请求还没有通过后端认证依赖，尚未进入六个 Agent。

