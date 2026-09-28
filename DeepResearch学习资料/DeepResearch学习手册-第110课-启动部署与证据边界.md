# DeepResearch 学习手册·第 110 课：启动部署与证据边界

## 1. 学习目标

启动一个项目不是执行一条命令，而是建立依赖顺序并用证据确认每一层：

```text
配置文件
→ 基础设施
→ 数据库和缓存
→ FastAPI 后端
→ Vite 前端
→ 外部 LLM、搜索、文档解析服务
→ 一次真实业务请求
```

“源码里写了地址”只能证明配置存在；“容器健康”只能证明基础设施存在；“页面能打开”只能证明前端启动。只有端到端请求成功，才证明研究链路真实可用。

## 2. 根目录 Compose 的服务关系

文件：`D:\课\s4-6\industry_information_assistant\docker-compose.yml`

定义的主要服务：

| 服务 | 默认端口 | 作用 |
|---|---:|---|
| PostgreSQL | 5432 | 用户、会话、文档、检查点和行业数据 |
| Redis | 6379 | 缓存、旧会话、研究取消标志 |
| etcd | 容器内部 2379 | Milvus 元数据 |
| MinIO | 9000/9001 | Milvus 对象存储和控制台 |
| Milvus | 19530/9091 | 向量检索和健康检查 |
| Elasticsearch | 宿主机 1200 映射到容器 9200 | 可选全文检索 |

Milvus 不是单独一个无依赖程序：它需要 etcd 和 MinIO。启动顺序应先确认它们健康，再验证 Milvus。

## 3. 后端启动发生了什么

文件：`backend/app/app_main.py`

### 3.1 导入阶段

```text
load_dotenv()
→ 导入路由
→ 导入全部 SQLAlchemy 模型
→ Base.metadata.create_all(bind=engine)
→ 创建 FastAPI app
→ 注册路由
```

因此后端一旦导入，就需要能连接 PostgreSQL。数据库不可达时，失败可能发生在 Uvicorn 真正监听端口之前。

### 3.2 生命周期阶段

`app_main.py:37-60` 的 `lifespan()` 在启动时调用 `init_scheduler_and_check_data()`，尝试启动定时采集任务；应用关闭时停止调度器。

所以“后端进程存在”与“调度器启动成功”是两个证据。调度器失败会被记录日志，代码仍可能继续提供 HTTP 服务。

### 3.3 CORS 事实

当前配置是：

```python
allow_origins=["*"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

源码注释已经说明这适合开发验证，不适合生产环境。面试时要能指出它的跨域配置风险和改进方向。

## 4. 前端启动与端口漂移

文件：`frontend/vite.config.ts:11-23` 和 `frontend/.env`

实际配置：

```text
Vite dev server：5183
VITE_API_BASE：http://localhost:8000/
VITE_API_PROXY：http://localhost:8000/
```

Vite 读取 `VITE_API_BASE` 作为代理键，将请求转到 `VITE_API_PROXY`。README 仍写前端默认访问 `5173`，这是文档与实现不一致，排错时应以 `vite.config.ts` 和终端实际输出为准。

## 5. 环境变量按功能分组

文件：`backend/.env.example`

### 必须重点确认

```text
DASHSCOPE_API_KEY       LLM 和 Embedding
BOCHA_API_KEY           网络搜索
POSTGRES_*              关系数据库
REDIS_HOST/PORT         缓存和取消控制
MILVUS_HOST/PORT        向量数据库
JWT_SECRET_KEY          登录 token 签名
```

DocMind、招投标和股票 API 属于可选外围能力，但某些业务链路会在配置缺失时降级、返回空结果或使用 mock。看见 HTTP 200 不等于外部数据真实采集成功，需要结合日志和返回字段确认。

## 6. 推荐的启动验收阶梯

### 第 0 层：静态检查

```powershell
cd D:\课\s4-6\industry_information_assistant\backend
python -m compileall -q app
```

它只能证明 Python 语法可编译，不能证明依赖、数据库或 API 可用。

### 第 1 层：基础设施

```powershell
docker compose up -d
docker compose ps
```

确认 PostgreSQL、Redis、Milvus 及其依赖为 healthy/running。必须同时查看日志，尤其是 Milvus 启动较慢的情况。

### 第 2 层：后端健康

```powershell
cd backend
python app/app_main.py
```

浏览器或 curl 访问：

```text
GET http://localhost:8000/hello
GET http://localhost:8000/docs
```

`/hello` 只证明 FastAPI 能响应；`/docs` 只证明路由已注册。

### 第 3 层：前端健康

```powershell
cd frontend
npm run dev
```

以终端打印的端口为准。当前源码配置通常是 `http://localhost:5183/`，不要只按 README 的 5173 判断。

### 第 4 层：认证闭环

```text
POST /auth/register 或 /auth/login
→ 取得 access_token
→ GET /auth/me 携带 Bearer token
→ GET /sessions 验证 user_id 过滤
```

### 第 5 层：研究链路

```text
POST /research/stream
→ 收到 research_start
→ 收到 phase/research_step
→ 收到搜索、图表和报告事件
→ 收到 research_complete 和 [DONE]
```

只有这一层通过，才可以说“DeepResearch 真正运行了”。

## 7. 按错误层级排查

| 现象 | 首先检查 |
|---|---|
| 命令找不到 `docker` | Docker Desktop/CLI 是否安装并进入 PATH |
| 后端启动即退出 | PostgreSQL 连接、Python 依赖、导入错误 |
| `/hello` 失败 | Uvicorn 进程、端口占用、入口路径 |
| 登录 500 | 数据库表、bcrypt、JWT 配置 |
| 研究 401/422 | token、请求体字段、请求版本 |
| 研究只到开始事件 | LLM 配置、Architect 异常、SSE 日志 |
| 知识库 completed 但无召回 | DocMind、Embedding、集合名、kb_id、Milvus |
| 页面空白但后端有报告 | SSE 分块、事件 type、React 状态更新 |

排错时一次只改变一层，否则无法判断哪个变化解决了问题。

## 8. 当前环境的真实验证边界

本次静态核对已确认：

- Python `compileall` 通过；
- 前端构建此前已通过，只有 bundle 体积警告；
- Compose、环境变量、后端入口和前端代理配置可以读取。

本次不能确认：

- Docker 容器是否真实启动；
- PostgreSQL、Redis、Milvus 是否健康；
- 外部 LLM、搜索和 DocMind 是否能调用；
- `/research/stream` 是否完成端到端报告生成。

当前执行环境没有可用的 `docker` 命令，因此不能把上述项目配置描述为真实运行结果。等 Docker 可用后，按第 6 节逐层验收。

## 9. 练习

1. 为什么 `python -m compileall -q app` 通过，仍然可能启动不了后端？
2. README 写 5173、Vite 配置写 5183 时，你以什么证据为准？
3. `/hello` 返回 200 能证明 Milvus 可用吗？为什么？
4. 研究请求返回 500 时，请按“基础设施、后端入口、认证、LLM、SSE、Agent”写出排查顺序。

