# DeepResearch 学习手册·第 27 课

## 启动部署与分层排错

学会项目不只是能读懂 Agent，还要能回答：服务为什么起不来？前端为什么请求不到后端？研究为什么卡住？本课建立一套从底层依赖到页面的排错顺序。

源码依据：

```text
D:\课\s4-6\industry_information_assistant\docker-compose.yml
D:\课\s4-6\industry_information_assistant\start-services.sh
D:\课\s4-6\industry_information_assistant\backend\app\app_main.py
D:\课\s4-6\industry_information_assistant\backend\app\core\database.py
D:\课\s4-6\industry_information_assistant\frontend\vite.config.ts
D:\课\s4-6\industry_information_assistant\READMED.md
```

---

## 1. 运行时由哪些层组成

```text
Docker 中间件
  PostgreSQL、Redis、Milvus、etcd、MinIO、Elasticsearch
        ↓
后端 FastAPI
  数据库连接、路由、Agent、外部 API、调度器
        ↓
前端 Vite/React
  页面、登录、请求、SSE、图表和研究详情
```

DeepResearch 还依赖外部服务：

```text
LLM / Embedding：DASHSCOPE_API_KEY
网页搜索：BOCHA_API_KEY 等
文档解析：DOCMIND_ACCESS_KEY_ID / SECRET
```

因此“前端能打开”只证明 Vite 层工作；“后端端口能访问”也不证明 PostgreSQL、Milvus 和 LLM 都可用。

---

## 2. Docker Compose 各服务的作用

项目的 `docker-compose.yml` 定义：

| 服务 | 用途 | 默认端口 |
|---|---|---:|
| `postgres` | 用户、会话、知识库、研究检查点、行业数据 | 5432 |
| `redis` | 旧会话、取消标志和部分缓存 | 6379 |
| `etcd` | Milvus 元数据依赖 | 容器内部 2379 |
| `minio` | Milvus 对象存储依赖，也提供控制台 | 9000、9001 |
| `milvus` | 文本块和向量检索 | 19530、健康检查 9091 |
| `elasticsearch` | 可选全文检索兼容链 | 宿主机 1200 映射到 9200 |

Milvus 不是单独启动就够了，它依赖 etcd 和 MinIO。Compose 中通过 `depends_on` 描述启动依赖，但实际健康状态仍应使用健康检查或日志确认。

---

## 3. 后端真正的启动顺序

`backend/app/app_main.py` 的重要顺序是：

```text
load_dotenv()
  ↓
导入路由、数据库和模型
  ↓
Base.metadata.create_all(bind=engine)
  ↓
创建 FastAPI app
  ↓
注册 CORS 和全部路由
  ↓
进入 lifespan
  ↓
启动 SchedulerService
```

### 3.1 为什么数据库故障会阻止后端启动

`Base.metadata.create_all(bind=engine)` 在模块导入阶段执行，不是在某个请求到来时才执行。因此如果 PostgreSQL 不可达，后端可能在 Uvicorn 真正开始监听 8000 之前就报错退出。

排错时看到“8000 端口没有监听”，不能只查 Uvicorn；先查 PostgreSQL 地址、端口、用户、密码和数据库名。

### 3.2 生命周期还会做什么

进入 `lifespan` 后，代码调用 `init_scheduler_and_check_data()`：

1. 启动 APScheduler。
2. 注册每天 12:00 的资讯采集任务。
3. 检查数据库是否有行业资讯。
4. 没有数据时立即执行一次采集。

所以即使核心聊天功能不需要行业采集，启动日志中也可能出现外部 API 失败、初始采集失败或调度器错误。要区分“启动错误”和“启动后可选任务错误”。

---

## 4. 最小验证阶梯

不要一上来就运行完整 DeepResearch。按下面顺序，每一步都比前一步多验证一层：

### 第 1 层：文件和依赖

```bash
python -m compileall -q app
npm run build
```

这只能证明 Python 语法和前端构建基本通过，不能证明外部服务可用。

### 第 2 层：中间件

```bash
docker compose ps
docker exec industry_postgres pg_isready -U postgres
docker exec industry_redis redis-cli ping
curl http://localhost:9091/healthz
curl http://localhost:1200/_cluster/health
```

如果系统找不到 `docker`，就没有进入真实容器验证阶段；此时不能声称 PostgreSQL、Redis 或 Milvus 已启动。

### 第 3 层：后端基础接口

后端启动后先请求：

```text
GET http://localhost:8000/hello
```

该接口只验证 FastAPI 进程和端口，不验证登录、数据库业务和 LLM。

### 第 4 层：认证和数据库

按顺序验证注册、登录、`/auth/me`、创建会话和读取会话。此时可以判断 JWT、PostgreSQL 表和用户权限是否贯通。

### 第 5 层：知识库

创建知识库、上传小文本、轮询文档状态，再查看切片。这里还需要验证 DocMind、Embedding 和 Milvus。

### 第 6 层：普通聊天

先验证不带附件的普通聊天，再验证 SSE 和历史消息。

### 第 7 层：DeepResearch

最后才运行 `/research/stream`，逐步确认规划、搜索、分析、代码、写作、审核和 `research_complete` 事件。

---

## 5. 常见故障如何定位

### 5.1 页面打不开

先查：

```text
Vite 是否启动
实际端口是否为 5183
浏览器访问路径是否为 /login
```

当前 `frontend/vite.config.ts` 明确配置 `port: 5183`，而 `READMED.md` 写的是 5173。以 Vite 配置和启动日志为准。

### 5.2 页面能打开，但请求 404 或连接失败

查三件事：

1. `VITE_API_BASE` 和 `VITE_API_PROXY` 是否加载到正确值。
2. 后端是否监听 8000。
3. 浏览器 Network 面板中的真实请求路径和代理目标。

### 5.3 后端导入即失败

优先检查：

```text
PostgreSQL 是否可达
DATABASE_URL 是否拼接正确
依赖是否安装
模型导入是否有异常
```

由于 `create_all()` 在导入阶段执行，数据库连接错误的表现可能看起来像“FastAPI 没启动”。

### 5.4 登录返回 401/422

```text
422 → 请求体字段、Content-Type 或 Pydantic Schema
401 → token 缺失、过期或签名不匹配
403 → 用户存在但没有资源权限
```

继续检查前端 Axios 插件是否把 `Authorization: Bearer <token>` 加上，以及后端使用的是哪个认证依赖。

### 5.5 知识库一直 processing

按顺序查：

```text
Document.status 是否从 pending 变成 processing
DocMind 凭证是否存在
DocMind 任务是否成功
DashScope Embedding 是否返回向量
Milvus 是否可连接
Milvus 插入是否报错
```

前端每 3 秒轮询一次，但轮询只反映 PostgreSQL 的状态；它不能修复后台处理失败。

### 5.6 DeepResearch 一直等待或只有空结果

分层查：

```text
research_start 是否发出
planning 是否完成
Scout 是否发出 search_results
search_web/search_local 是否正确
外部搜索 API 是否有密钥和配额
本地搜索集合名是否一致
LLM 是否返回可解析 JSON
```

不要看到 `research_complete` 就默认报告可信；还要检查事实数、引用数、质量分数和审核反馈。

---

## 6. 环境变量的实际含义

至少要分为四类：

```text
数据库：POSTGRES_*
缓存/取消：REDIS_*
向量库：MILVUS_HOST、MILVUS_PORT
智能能力：DASHSCOPE_*、BOCHA_*、DOCMIND_*
```

默认值可以帮助本地开发，但不应当被当作生产配置。尤其要检查：

- JWT 密钥是否是自定义强随机值。
- LLM、搜索和 DocMind 密钥是否只来自环境变量。
- Docker 内部服务名与宿主机访问地址是否混用。
- 容器内的 `localhost` 指的是容器自己，不是另一个容器。

源码中还有个必须主动修复的安全检查点：`dr_g.py` 出现 API 密钥硬编码回退值。真实密钥一旦提交到代码或日志，应立即撤销并更换，代码中只保留环境变量读取。

---

## 7. 当前验证结论

已经有证据的部分：

```text
后端 Python compileall 通过
前端 npm run build 通过
源码中的启动顺序、路由和配置已核对
```

尚未有真实运行证据的部分：

```text
Docker Compose 容器启动
PostgreSQL、Redis、Milvus、Elasticsearch 连接
DocMind、Embedding、搜索和 LLM 请求
真实 /research/stream 全流程
```

当前电脑执行 `docker info` 时系统找不到 `docker` 命令，因此本课不能把容器启动结果写成“已验证”。

---

## 8. 练习

1. 为什么 PostgreSQL 不可达时，后端可能连 8000 端口都没有？
2. 页面端口应该相信 README 的 5173 还是 Vite 配置的 5183？为什么？
3. 如果 `/hello` 正常但登录失败，你下一步查什么？
4. 知识库一直是 `processing` 时，为什么不能只盯着前端轮询？
5. 用“容器 → 后端 → 前端 → 外部 API → DeepResearch”顺序写出你的排错流程。

