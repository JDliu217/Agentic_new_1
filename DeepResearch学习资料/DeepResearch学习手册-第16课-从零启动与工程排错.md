# DeepResearch 学习手册·第 16 课

## 从零启动与工程排错

本课解决两个问题：

1. 项目从电脑启动到浏览器页面，中间到底需要哪些依赖？
2. 启动失败时，如何知道是哪一层出了问题？

源码根目录：`D:\课\s4-6\industry_information_assistant`

---

## 1. 先理解“项目启动”不是一个命令

这个项目至少包含四层：

```text
基础设施：PostgreSQL、Redis、Milvus、etcd、MinIO、Elasticsearch
        ↓
后端进程：Python + FastAPI + Uvicorn
        ↓
前端进程：Node.js + Vite + React
        ↓
外部能力：LLM、Embedding、Bocha 搜索、DocMind 等 API
```

它们的验证顺序应该是从底到顶：

```text
端口/容器 → 数据库连接 → 后端健康接口 → 前端代理 → 外部 API → 完整研究请求
```

前端页面能打开，只能证明前端进程能服务静态资源；不能证明后端、数据库或模型可用。

---

## 2. Docker Compose 管什么

根目录 `docker-compose.yml` 定义了：

| 服务 | 默认端口 | 作用 |
|---|---:|---|
| `postgres` | 5432 | 关系型业务数据库 |
| `redis` | 6379 | 缓存、短期状态和取消标志 |
| `etcd` | 容器内部 2379 | Milvus 元数据依赖 |
| `minio` | 9000 / 9001 | Milvus 对象存储和控制台 |
| `milvus` | 19530 / 9091 | 向量数据库和健康检查 |
| `elasticsearch` | 宿主机 1200 → 容器 9200 | 可选全文检索服务 |

Milvus 不是独立只需要一个端口的程序，它依赖 etcd 和 MinIO。PostgreSQL、Redis、Milvus 和 Elasticsearch 都配置了持久化卷。

### 2.1 `start-services.sh` 做什么

启动脚本依次：

1. 检查 `docker info`。
2. 执行 `docker-compose up -d`。
3. 等待约 10 秒。
4. 用 `pg_isready`、`redis-cli ping`、Milvus 和 Elasticsearch 健康接口检查服务。

“容器处于 running”不等于“服务已经 ready”，所以脚本还做了健康检查。但固定等待 10 秒仍不是严格的就绪编排，第一次启动时可能需要再次检查。

---

## 3. 后端进程启动顺序

入口：`backend/app/app_main.py`

它的顶层顺序是：

```text
load_dotenv()
→ 导入 Router、数据库和模型
→ Base.metadata.create_all(bind=engine)
→ 创建 FastAPI app
→ 注册 CORS
→ 注册所有路由
→ 由 lifespan 启动调度器
→ Uvicorn 监听 0.0.0.0:8000
```

### 3.1 一个重要的启动边界

`Base.metadata.create_all(bind=engine)` 在模块加载阶段执行，不是在第一次请求时执行。因此：

- PostgreSQL 没启动，后端可能在启动早期就失败。
- 数据库地址或密码错误，不一定等到访问业务接口才暴露。
- 能看到 Uvicorn 日志，不代表所有外部依赖都已可用；需要观察表创建和调度器日志。

### 3.2 FastAPI lifespan

`lifespan()` 的启动部分调用 `init_scheduler_and_check_data()`，用于初始化定时任务调度器和检查行业数据；关闭时停止调度器。

这说明调度器不是一个独立的常驻命令，而是后端进程生命周期的一部分。

---

## 4. 后端配置的两种来源

### 4.1 环境变量配置

`backend/app/core/database.py` 直接从环境变量读取：

```text
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
```

`backend/app/core/redis_client.py` 读取：

```text
REDIS_HOST
REDIS_PORT
REDIS_PASSWORD
```

### 4.2 LLM 和研究配置

`backend/app/config/llm_config.py` 集中定义：

```text
DASHSCOPE_API_KEY
LLM_BASE_URL
BOCHA_API_KEY
各 Agent 的模型、temperature、max_tokens
研究最大迭代次数、图表上限、质量阈值
```

当前默认 Agent 模型并不全部相同：Scout 使用较快的 `qwen-plus`，其他关键 Agent 多使用 `deepseek-v3.2`。模型配置是按 Agent 角色设置的，不是整个系统永远只用一个模型。

### 4.3 `.env` 的安全边界

`.env.example` 只提供变量名和说明；真实 `.env` 不应提交到 GitHub。尤其注意：

- LLM API Key
- 搜索 API Key
- DocMind 密钥
- JWT 密钥
- 招投标和股票 API 密钥

日志中可以打印“是否配置”或脱敏前缀，但不要打印完整密钥。

---

## 5. 前端启动和代理

`frontend/vite.config.ts` 当前配置：

```text
host = 0.0.0.0
port = 5183
proxy = { [VITE_API_BASE]: VITE_API_PROXY }
```

前端 Axios 的 `baseURL` 使用 `import.meta.env.VITE_API_BASE`。因此必须同时检查：

1. `VITE_API_BASE` 是否存在。
2. `VITE_API_PROXY` 是否指向后端地址。
3. Vite 代理键是否和 Axios 的 baseURL 一致。

README 中写的前端端口是 5173，但当前 Vite 配置是 5183。排查时以 `vite.config.ts` 和终端实际输出为准。

---

## 6. 最小验证阶梯

不要一开始就提交完整研究请求。按下面阶梯逐层验证：

### 阶梯 1：静态语法

```powershell
cd D:\课\s4-6\industry_information_assistant\backend
python -m compileall -q app
```

通过只说明 Python 能编译。

### 阶梯 2：前端构建

```powershell
cd D:\课\s4-6\industry_information_assistant\frontend
npm run build
```

通过只说明 TypeScript/React 可以被 Vite 打包，不代表运行时 API 一定通。

### 阶梯 3：基础服务健康

```powershell
cd D:\课\s4-6\industry_information_assistant
docker compose ps
```

检查 PostgreSQL、Redis、Milvus 及其依赖是否 ready。

### 阶梯 4：后端最小接口

启动后访问：

```text
GET http://localhost:8000/hello
GET http://localhost:8000/docs
```

`/hello` 是网络连通性验证；`/docs` 是 FastAPI 接口文档入口。

### 阶梯 5：前端页面

访问：

```text
http://localhost:5183/login
```

页面能打开后，再检查浏览器 Network 中 API 请求是否走到了正确代理。

### 阶梯 6：认证和会话

先完成注册、登录、创建会话，再测试聊天。不要跳过身份层直接判断 DeepResearch 失败。

### 阶梯 7：研究请求

最后再验证：

```text
POST /research/stream
→ research_start
→ phase/research_step
→ research_complete 或 error
```

---

## 7. 常见故障的定位方法

### 7.1 后端一启动就退出

优先检查：

1. Python 依赖是否安装。
2. PostgreSQL 是否可达。
3. `POSTGRES_*` 是否正确。
4. 模型导入是否有语法或依赖错误。

### 7.2 页面能打开但接口 404

检查：

```text
浏览器请求 URL
→ VITE_API_BASE
→ Vite proxy 键
→ FastAPI 路由前缀
```

例如前端请求 `/research/stream`，后端必须注册带 `/research` 前缀的 Router；代理不能把路径改成不存在的地址。

### 7.3 页面返回 401

检查：

```text
localStorage 中 auth
→ auth 请求插件
→ Authorization: Bearer <token>
→ FastAPI 当前用户依赖
```

不要先去查 Milvus；请求还没有通过认证层。

### 7.4 研究请求建立但很快 error

按事件顺序判断：

- 没有 `research_start`：路由或服务初始化失败。
- 有 `research_start`，没有规划事件：Architect 或 LLM 配置失败。
- 有搜索阶段，没有事实：搜索 API、网络或来源解析失败。
- 有报告，没有 `research_complete`：审核循环、异常或事件生成失败。
- Network 有 `research_complete`，页面无报告：前端 `parseData()` 或状态映射问题。

### 7.5 知识库显示完成但检索为空

检查顺序：

```text
PostgreSQL Document.status
→ DocMind 文本是否为空
→ 切片数量
→ Embedding 是否成功
→ Milvus 集合名和实体数
→ 查询使用的集合名
```

还要记住第 13、15 课中的集合命名和 `kb_name` 参数未贯通问题。

---

## 8. 当前环境的验证边界

当前工作环境已验证：

- Python 后端 `compileall` 通过。
- 前端 `npm run build` 通过。

当前没有完成真实端到端验证的原因是 Docker 命令不可用；因此不能把静态通过写成“数据库、Milvus、LLM 和 DocMind 已经运行成功”。

工程学习中，必须区分三种证据：

```text
代码证据：源码中存在这条路径
构建证据：语法和打包通过
运行证据：真实服务响应和日志证明它确实跑通
```

---

## 9. 练习

1. 为什么 `GET /hello` 成功仍不能证明 `/research/stream` 能用？
2. `Base.metadata.create_all()` 在启动阶段执行会带来什么排错信息？
3. Milvus 为什么需要 etcd 和 MinIO？
4. README 写 5173、Vite 配置写 5183 时，应该以什么为准？
5. 页面能打开但 API 404，按什么顺序检查？
6. 为什么 `compileall` 通过不等于外部 LLM 可用？

### 我的排错顺序

<!-- 选择一个故障，写出你的分层定位步骤 -->


### 我需要补充的基础概念

<!-- 记录 Docker、端口、环境变量、进程或数据库方面的问题 -->

