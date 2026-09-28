# DeepResearch 学习手册：第 40 课

## 工程配置、依赖与启动契约

这一课把“源码之外但决定项目能不能跑”的文件统一起来。阅读代码时，不能只看 `backend/app` 和 `frontend/src`，还要看依赖清单、环境变量、Compose、脚本和 README；这些文件共同定义了工程启动契约。

## 1. 项目启动需要哪些层

```text
Docker 中间件
  ├─ PostgreSQL
  ├─ Redis
  ├─ Milvus + etcd + MinIO
  └─ Elasticsearch（根 Compose 可选）
        ↓
后端 Python 依赖 + backend/.env
        ↓
FastAPI / Uvicorn :8000
        ↓ HTTP / SSE
前端 Node 依赖 + frontend/.env
        ↓
Vite :5183（当前源码）
```

Compose 不会自动替你启动 FastAPI 和 Vite。根 `docker-compose.yml` 主要提供中间件，后端和前端仍要单独运行。

## 2. 两套 Compose 的边界

### 2.1 根目录 `docker-compose.yml`

包含 PostgreSQL、Redis、etcd、MinIO、Milvus 和 Elasticsearch，并通过固定端口映射到本机。PostgreSQL 还挂载 `docker/init-db/01-init.sql`，首次初始化卷时执行 SQL。

### 2.2 `backend/docker-compose-base.yml`

只提供 Redis、Milvus 的 etcd、MinIO 和 Milvus，本身没有 PostgreSQL 和 Elasticsearch。它适合已经有本地 PostgreSQL、或只想启动文档向量链的场景。

两套文件的服务名、容器名、网络名和环境变量写法不同。排错时先确认使用的是哪一套 Compose，再检查后端 `.env` 是否与该套服务一致，不能把两套容器状态混在一起解释。

## 3. `start-services.sh` 做了什么

脚本提供 `start`、`stop`、`restart`、`status`、`logs` 和 `clean`：

```text
check_docker
  → docker-compose up -d
  → 等待 10 秒
  → docker exec / curl 做健康检查
```

`clean` 会执行 `docker-compose down -v`，删除卷中的数据库、缓存和向量数据，是不可逆的数据清理操作。脚本只检查容器健康，不证明 LLM、搜索 API、DocMind 或完整 SSE 已经可用。

## 4. 后端依赖按能力分组

`backend/requirements.txt` 可以按用途读：

| 能力 | 主要依赖 |
|---|---|
| Web | FastAPI、Uvicorn、python-multipart |
| 数据库 | SQLAlchemy、psycopg2、Alembic |
| 缓存和认证 | redis、python-jose、passlib、Pydantic |
| LLM/Agent | openai、tiktoken、llama-index、langgraph |
| 向量检索 | pymilvus |
| 抓取和解析 | httpx、aiohttp、requests、BeautifulSoup、trafilatura、lxml |
| 文档 | PyPDF2、python-docx、openpyxl、DocMind SDK |
| 分析和图表 | numpy、pandas、matplotlib、seaborn、wordcloud |

依赖存在不等于对应功能已经在当前环境真实接通。例如安装了 `langgraph` 不等于默认请求一定走 LangGraph；还要看 `graph.py` 的实际入口。

## 5. 环境变量的职责

`backend/.env.example` 把变量分成：

- LLM 和 Embedding：`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`OPENAI_MODEL`。
- 搜索：`BOCHA_API_KEY`、`SERPER_API_KEY`。
- 文档解析：`DOCMIND_ACCESS_KEY_ID`、`DOCMIND_ACCESS_KEY_SECRET`。
- 行业数据：股票 Key、招投标 Key。
- 基础设施：PostgreSQL、Redis、Milvus。
- 安全：`JWT_SECRET_KEY`、算法和过期时间。

敏感变量只能通过环境变量或安全配置注入，不能把真实 Key 写入源码、教学材料或 Git 提交。项目当前还存在 `LLM_BASE_URL` 与 `DASHSCOPE_BASE_URL` 的读取差异，应以实际调用方核对为准。

## 6. 前端构建和代理契约

`frontend/package.json` 的关键脚本是：

- `npm run dev`：启动 Vite 开发服务器。
- `npm run build`：执行生产构建检查。
- `npm run lint`：执行 ESLint。

`vite.config.ts` 当前将端口设为 `5183`，并把 `VITE_API_BASE` 指向的请求代理到 `VITE_API_PROXY`。前端 `.env` 当前配置为：

```env
VITE_API_BASE=http://localhost:8000/
VITE_API_PROXY=http://localhost:8000/
```

README 中仍写有 `/login` 使用 `5173` 的说明，学习和排错时应以 `vite.config.ts` 和实际启动日志为准。

## 7. README 与源码的阅读方法

README 是启动意图和示例，不是运行时证据。当前项目至少有这些需要核对的差异：

1. 文档写的前端端口与 Vite 源码端口不同。
2. Compose 选择不同会导致 PostgreSQL/Elasticsearch 是否存在不同。
3. 示例中的接口可能是旧兼容接口，不能直接推断当前主链路。
4. “必填 Key”只说明预期依赖，不证明外部配额、证书和网络都正常。

## 8. 分层启动排错

推荐顺序：

```text
1. docker compose ps
2. pg_isready / redis-cli ping / Milvus healthz
3. 检查 backend/.env 和 Python 依赖
4. 启动 FastAPI，访问 /docs 或健康接口
5. 检查 VITE_API_BASE / VITE_API_PROXY
6. 启动 Vite，确认浏览器端口
7. 最后验证 LLM、搜索、DocMind、股票和招投标外部服务
```

每一层只证明自己的边界。例如 PostgreSQL 健康只能证明数据库进程可用，不能证明 `/research/stream` 能完成一次研究。

## 9. 本课练习

### 练习 A：比较两套 Compose

列出根 Compose 和 backend Compose 各自启动的服务，并说明使用 backend Compose 时为什么还需要单独准备 PostgreSQL。

### 练习 B：从 Key 追到调用方

从 `DASHSCOPE_API_KEY`、`BOCHA_API_KEY` 和 `MILVUS_HOST` 出发，各找到一个真正读取它们的源码文件和调用场景。

### 练习 C：排错分层

假设前端页面打开但研究请求失败，按“浏览器请求 → Vite 代理 → FastAPI → LLM/搜索 → 数据库”的顺序列出检查证据。

## 10. 面试追问

1. 为什么 `docker compose up` 成功不代表应用可用？
2. 根 Compose 和 backend Compose 为什么不能随意混用？
3. `requirements.txt` 中有 LangGraph，为什么仍要确认 `run()` 实际执行分支？
4. Vite 的 `VITE_API_BASE` 和 `VITE_API_PROXY` 分别解决什么问题？
5. 如何安全地处理 JWT 和第三方 API Key？

