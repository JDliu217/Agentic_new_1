# DeepResearch 学习手册·第 117 课：启动证据、Mock 边界与分层排错

## 本课目标

工程上最容易犯的错，是把“某个页面能打开”“某条命令成功”误认为“整个项目已经运行”。本课练习按证据判断系统处在哪一层。

## 一、先画出运行组件

根目录 `docker-compose.yml` 负责基础服务：

```text
PostgreSQL
Redis
etcd + MinIO + Milvus
Elasticsearch
```

它没有启动 FastAPI，也没有启动 React/Vite。后端由 `backend/app/app_main.py` 运行在 8000 端口；前端由 Vite 开发服务器运行。当前 `frontend/vite.config.ts` 配置端口是 5183。

仓库还有 `backend/docker-compose-base.yml`，它是另一套只启动 Redis/Milvus 相关服务的 Compose 配置。先看清要启动哪套，不要把两套配置当作同一个部署文件。

## 二、启动顺序与证据强弱

从容易到困难，逐层验证：

| 层 | 验证动作 | 能说明什么 | 不能说明什么 |
|---|---|---|---|
| 1. 配置 | 检查 `.env` 和依赖是否齐全 | 应用知道要连接哪些服务 | 服务真实可用 |
| 2. 基础设施 | 检查 Compose 容器健康状态 | PostgreSQL/Redis/Milvus 等启动 | 后端配置正确、密钥有效 |
| 3. 后端进程 | 启动 `app_main.py` | Python 进程开始运行 | 每个 API 和外部服务都正常 |
| 4. 健康路由 | 请求 `/hello` | FastAPI 能处理简单请求 | LLM、搜索、RAG 和数据库业务正常 |
| 5. 页面构建 | `npm run build` | 前端代码可打包 | 浏览器能连后端、SSE 可解析 |
| 6. 业务请求 | 登录后发起真实研究/上传文档 | 被测链路在本次环境中工作 | 其它功能也自动成立 |

关键原则：每项验证只证明它实际覆盖的范围。

## 三、源码中的几个“看起来成功”陷阱

### 1. README 端口和代码配置不一致

根目录 `READMED.md` 写前端是 5173；`frontend/vite.config.ts` 写的是 5183。排错时以正在运行的配置和终端输出为准，不要仅照抄 README 地址。

### 2. `/hello` 是窄健康检查

`backend/app/app_main.py` 注册了 `/hello`。它适合先确认 FastAPI 能响应，但研究还依赖数据库、LLM、搜索服务等。`/hello` 返回成功不能推出这些依赖都已接通。

此外，`app_main.py` 在模块导入阶段执行 `Base.metadata.create_all(bind=engine)`。数据库连不上时，应用可能还没开始监听端口就启动失败；排查要看启动日志和数据库连接，而不只是浏览器。

### 3. Text2SQL 可能返回 Mock 数据

`backend/app/service/text2sql_service.py` 在数据库引擎不可用的分支会调用 `_get_mock_data(sql)`。因此页面出现表格不一定说明 SQL 真在 PostgreSQL 执行。

要确认数据来源，应检查后端连接状态、日志、实际 SQL 执行路径和数据库中的记录。演示结果不能自动算作生产数据。

### 4. `/research/test-wizard` 绕过真实搜索

`backend/app/router/research_router.py` 的 `/research/test-wizard` 用手写的 GDP mock state 测 CodeWizard，因此它跳过了 DeepScout 和真实搜索；但 CodeWizard 仍会请求 LLM 生成代码。

它可以用于隔离测试图表代码生成的一部分，不等同于完整研究请求，也不等于完全离线测试。

### 5. 前端 Mock 插件目前关闭

`frontend/vite.config.ts` 配置了 `viteMockServe`，但 `enable: false`。看到 `frontend/mock/` 目录不能推断开发时 API 一定由 Mock 提供。仍需检查实际网络请求和后端响应。

## 四、建议的新手排错顺序

遇到“页面能打开，但研究请求失败”时，按顺序收集证据：

1. 浏览器 Network：请求 URL、方法、状态码、请求体和响应头。
2. Vite 终端：实际监听端口和代理目标；对照 `vite.config.ts` 与 `.env` 里的 `VITE_API_BASE` / `VITE_API_PROXY`。
3. FastAPI 终端：请求是否抵达 Router，完整异常栈是什么。
4. 后端启动阶段：数据库是否在导入时连接成功，模型表是否创建成功。
5. 基础服务：PostgreSQL、Redis、Milvus 的健康状态与地址是否匹配 `.env`。
6. 外部依赖：LLM、Bocha、DocMind 等 API 的密钥、配额、网络和返回错误。
7. 数据流：SSE 是否有事件、前端是否按完整事件块解析、React 是否更新对应状态。

不要先改代码。先明确故障发生在哪一层，再针对该层收集一条可复现证据。

## 五、前端构建结果应该怎么说

当前执行 `npm run build` 可以完成 Vite 打包，但提示主 JS chunk 超过 500 kB。准确表述是：

```text
前端生产构建成功；有 bundle 体积警告。
```

不要把它说成“前端所有功能运行正常”。构建没有启动浏览器，也没有检验真实 API、登录、SSE、图表或文件上传。

## 六、本课的面试回答模板

别人问“你怎么证明这个功能真的通了”，按四句回答：

1. 我验证了哪条具体路径和环境。
2. 我看到的直接证据是什么，例如 HTTP 状态、日志、数据库记录或 SSE 事件。
3. 这个证据覆盖哪些模块。
4. 它还没有覆盖哪些外部服务或异常路径。

例如：

```text
npm run build 通过，证明当前前端代码可以由 Vite 打包。
它没有启动页面，也没有请求 FastAPI，所以不能证明登录和 SSE 研究链路可用。
```

## 七、练习

请判断下面说法是否严谨，并把证据层级说出来：

```text
A. GET /hello 返回 200，所以 DeepResearch 可以正常调用 LLM。
B. Text2SQL 页面显示了数据，所以这些数据一定来自 PostgreSQL。
C. /research/test-wizard 成功，所以一次完整研究的搜索、写作和审核都成功。
D. npm run build 成功，所以浏览器到后端的代理和 SSE 已经验证。
```

再选其中一项，写出你还需要采集的两条直接证据。

## 八、下一阶段

在主链路验收和部署证据练习完成后，进入综合故障演练：我给出一个故障现象，你先画出请求经过的模块，再决定查哪些日志、状态字段和外部依赖。项目掌握后，再进入大厂面试官模式。小红书面经分析继续等你后续提供 Prompt。
