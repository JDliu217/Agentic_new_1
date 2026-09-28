# DeepResearch 学习手册·第 55 课

## 从源码到可运行服务：启动顺序和证据等级

本课目标不是让你复制一组命令，而是让你理解每一步启动的前置条件、验证证据和失败边界。

---

## 1. 项目有四层运行对象

~~~~text
Docker 基础设施
  ├── PostgreSQL
  ├── Redis
  ├── Milvus
  │    ├── etcd
  │    └── MinIO
  └── Elasticsearch（可选兼容能力）

FastAPI 后端
  └── app/app_main.py :8000

Vite 前端
  └── frontend/vite.config.ts :5183

外部服务
  ├── DashScope LLM / Embedding
  ├── Bocha 搜索
  ├── DocMind 文档解析
  ├── 股票 API
  └── 招投标 API
~~~~

启动前端或后端，不代表所有能力已经可用。完整研究还依赖对应的外部服务和密钥。

---

## 2. 先选择正确的 Compose 文件

根目录 docker-compose.yml 提供：

- PostgreSQL
- Redis
- etcd
- MinIO
- Milvus
- Elasticsearch

backend/docker-compose-base.yml 提供：

- Redis
- etcd
- MinIO
- Milvus

因此：

- 需要本项目 PostgreSQL 时，用根 Compose。
- 已经有本地 PostgreSQL，或只想启动 Redis/Milvus 时，可用 backend Compose。
- 两套 Compose 的容器名称、网络名称和数据卷也不同，不能混合地记忆服务名。

当前源码的数据库默认配置是：

~~~~text
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123
POSTGRES_DB=industry_assistant
~~~~

---

## 3. 推荐启动顺序

### 第一步：确认 Docker

~~~~text
docker info
~~~~

如果 Docker 不可用，不能证明 PostgreSQL、Redis、Milvus 已启动。

### 第二步：启动基础设施

在项目根目录：

~~~~text
docker compose up -d
~~~~

启动后检查：

~~~~text
docker compose ps
~~~~

再按服务逐一看健康证据：

- PostgreSQL：pg_isready
- Redis：redis-cli ping
- Milvus：9091/healthz
- Elasticsearch：9200/_cluster/health

容器处于 running 不等于应用服务已经 ready。健康检查和实际连接日志更可靠。

### 第三步：准备后端环境变量

backend/.env.example 是模板。至少要根据实际启用的能力配置：

- DASHSCOPE_API_KEY
- BOCHA_API_KEY
- POSTGRES_*
- REDIS_*
- MILVUS_*
- JWT_SECRET_KEY

文档解析、股票、招投标等功能还需要各自的外部密钥。

不要把真实密钥提交到 Git。

### 第四步：安装并启动后端

~~~~text
cd backend
pip install -r requirements.txt
python app/app_main.py
~~~~

源码中的 app_main.py 会：

1. load_dotenv。
2. 导入所有 SQLAlchemy 模型。
3. 执行 Base.metadata.create_all。
4. 注册各类 Router。
5. 启动生命周期中的调度器。
6. 监听 0.0.0.0:8000。

健康检查：

~~~~text
http://localhost:8000/hello
~~~~

这个接口只证明 FastAPI 进程可访问，不证明数据库、Milvus、LLM 或搜索服务都正常。

### 第五步：安装并启动前端

~~~~text
cd frontend
npm install
npm run dev
~~~~

当前 frontend/vite.config.ts 明确配置端口 5183：

~~~~text
http://localhost:5183
~~~~

frontend/.env 中的 API 地址是：

~~~~text
VITE_API_BASE=http://localhost:8000/
VITE_API_PROXY=http://localhost:8000/
~~~~

README 中写的 5173 与当前 Vite 源码不一致，实际运行时应以 Vite 输出和配置为准。

---

## 4. 前端请求如何找到后端

frontend/src/api/request/index.ts 使用：

~~~~text
baseURL = import.meta.env.VITE_API_BASE
~~~~

因此登录、知识库、聊天和研究请求默认都发往 8000 端口。

Vite 的 server.port 是前端开发服务器端口；VITE_API_BASE 是后端 API 目标，两者不是同一个端口。

---

## 5. 后端启动成功的证据等级

### 低等级证据

- 终端没有立即报错。
- 进程仍然存在。
- 浏览器打开了前端页面。

### 中等级证据

- GET /hello 返回成功。
- Swagger 页面可访问。
- 后端日志显示路由和生命周期启动。

### 高等级证据

- PostgreSQL 查询成功。
- Redis ping 成功。
- Milvus collection 可创建和搜索。
- 登录、创建会话、发送聊天请求成功。
- 研究请求收到 research_start、research_step 和 research_complete。

排错时不要用低等级证据证明高等级结论。

---

## 6. 为什么 app_main 导入阶段可能就失败

app_main.py 在创建 FastAPI 应用前就导入数据库和模型，并执行：

~~~~python
Base.metadata.create_all(bind=engine)
~~~~

因此如果 PostgreSQL 不可连接，后端可能在启动导入阶段就失败，甚至还没有机会返回 /hello。

这是启动顺序的重要原因：先准备 PostgreSQL，再启动后端。

---

## 7. 外部 API 密钥的分层影响

| 缺少配置 | 可能影响 |
|---|---|
| DASHSCOPE_API_KEY | 规划、写作、Embedding、分析等 LLM 能力 |
| BOCHA_API_KEY | DeepScout 网络搜索 |
| DOCMIND 凭据 | 知识库文档解析 |
| JUHE_STOCK_API_KEY | 股票行情 |
| BID_APP_* | 招投标采集 |
| SERPER_API_KEY | 旧 Web 搜索链 |

后端可能仍然启动，但某一条业务链会在真正调用时失败或返回空结果。

“后端启动成功”和“业务功能完整可用”必须分开验收。

---

## 8. 最小验收路线

建议按以下最小闭环验证：

~~~~text
1. /hello
2. 注册或登录
3. GET /auth/me
4. 创建 PostgreSQL 会话
5. 普通聊天 SSE
6. POST /research/stream
7. 观察 research_start
8. 观察 research_step
9. 观察 research_complete
10. 检查前端报告和来源
~~~~

知识库、DocMind、Milvus 和图表再单独增加验证，不要第一次启动就把所有故障混在一起。

---

## 9. 常见启动误判

### 误判一：Docker 容器 running 就说明 Milvus 能用

还要验证 19530 连接、collection 创建和 search。

### 误判二：/hello 能访问就说明研究能跑

/hello 不访问 LLM、搜索、Milvus 或检查点。

### 误判三：前端页面能打开就说明 API 地址正确

还要看浏览器 Network 中请求是否发到 8000，以及是否出现 CORS、401 或连接失败。

### 误判四：README 的端口永远正确

当前源码 Vite 端口是 5183，README 仍写 5173，配置和运行日志优先。

### 误判五：安装依赖成功就说明类型检查成功

当前项目已验证 Vite build 通过，但 TypeScript 严格检查和 ESLint 仍存在原有问题。不同检查命令证明范围不同。

---

## 10. 小练习

后端启动时报数据库连接错误，前端页面也打不开 API。最合理的第一步是什么？

A. 先修改 React 组件

B. 先检查 PostgreSQL 容器是否 ready、POSTGRES_* 是否与连接串一致，再看后端启动日志

C. 先重新生成 ECharts 图表

D. 把前端端口改回 5173

---

## 留白：我的启动验收记录

Docker 证据：

PostgreSQL 证据：

Redis 证据：

Milvus 证据：

后端 /hello 证据：

前端实际端口：

外部 API 密钥：

第一次失败发生在哪一层：

---

## 源码定位

- D:/课/s4-6/industry_information_assistant/docker-compose.yml：完整基础设施
- D:/课/s4-6/industry_information_assistant/backend/docker-compose-base.yml：精简基础设施
- D:/课/s4-6/industry_information_assistant/start-services.sh：服务管理脚本
- D:/课/s4-6/industry_information_assistant/backend/app/app_main.py：后端入口
- D:/课/s4-6/industry_information_assistant/backend/.env.example：环境变量模板
- D:/课/s4-6/industry_information_assistant/frontend/vite.config.ts：开发端口和代理
- D:/课/s4-6/industry_information_assistant/frontend/src/api/request/index.ts：API baseURL
- D:/课/s4-6/industry_information_assistant/READMED.md：启动说明及其配置漂移

