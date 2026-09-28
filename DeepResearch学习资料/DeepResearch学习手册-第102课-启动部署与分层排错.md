# DeepResearch 学习手册：第 102 课

## 启动部署与分层排错

真正推进项目时，第一步不是直接点击页面，而是确认每一层都已启动并且配置一致。

## 1. 项目的启动层次

项目大致分为四层：

```text
Docker 基础设施
→ FastAPI 后端
→ Vite/React 前端
→ LLM、搜索、DocMind、股票和招投标等外部服务
```

## 2. Docker 基础设施

根目录：

```text
docker-compose.yml
```

主要服务：

```text
PostgreSQL  localhost:5432
Redis       localhost:6379
Milvus      localhost:19530
MinIO       localhost:9000 / 9001
Elasticsearch localhost:1200
```

Milvus 还依赖：

```text
etcd
MinIO
```

这意味着 Milvus 不是一个完全独立的单容器业务依赖。

## 3. 后端启动

主要入口：

```text
backend/app/app_main.py
```

导入阶段会：

```text
加载环境变量
→ 导入模型
→ Base.metadata.create_all(bind=engine)
→ 创建 FastAPI app
→ 注册路由
```

应用生命周期启动时还会：

```text
初始化 APScheduler
→ 检查行业数据
→ 启动定时任务
```

后端默认监听：

```text
0.0.0.0:8000
```

## 4. 前端启动

主要配置：

```text
frontend/vite.config.ts
```

当前 Vite 端口是：

```text
5183
```

Vite 根据：

```text
VITE_API_BASE
VITE_API_PROXY
```

把前端请求代理到后端。README 中如果写了 5173，不能优先于实际配置文件。

## 5. 环境变量负责连接什么

常见配置关系：

| 变量 | 使用方 |
|---|---|
| `DASHSCOPE_API_KEY` | LLM、Embedding、长期记忆、CodeWizard |
| `DASHSCOPE_BASE_URL` | OpenAI 兼容客户端地址 |
| `BOCHA_API_KEY` | DeepScout 网络搜索、行业资讯 |
| `DOCMIND_ACCESS_KEY_ID/SECRET` | 文档解析 |
| `POSTGRES_*` | SQLAlchemy 数据库连接 |
| `REDIS_*` | Redis 客户端和取消标志 |
| `MILVUS_HOST/PORT` | 向量库连接 |
| `JWT_SECRET_KEY` | JWT 签名 |

配置排错时要查“变量名”和“读取代码”是否一致。比如项目同时存在直接读取环境变量和配置类读取的路径，不能只看 `.env.example`。

## 6. 分层排错顺序

### 第一层：容器

```text
docker compose ps
docker compose logs <service>
```

确认 PostgreSQL、Redis、Milvus、etcd、MinIO 是否健康。

### 第二层：后端

先访问：

```text
GET /hello
```

如果 `/hello` 都失败，先查后端启动、端口、数据库导入和依赖安装，不要先查 LLM。

### 第三层：认证

```text
注册 → 登录 → JWT → Authorization Bearer → AuthGuard/后端依赖
```

出现 `401` 时，先查 Token 是否存在、是否过期、请求头是否发送、后端 JWT 密钥是否一致。

### 第四层：数据库和向量库

出现会话、知识库或检查点错误时，查 PostgreSQL；出现召回为空时，再查 Embedding、Milvus 集合和过滤条件。

### 第五层：SSE

研究接口连接成功但页面不动时，依次查：

```text
Network 是否有响应
→ 原始 data 行
→ JSON 是否完整
→ 事件 type
→ React 分支
→ 详情状态
```

### 第六层：外部服务

只有内部层都确认后，才检查：

```text
LLM Key、Bocha、DocMind、股票 API、招投标 API
```

## 7. 用 HTTP 状态快速定位

| 现象 | 优先检查 |
|---|---|
| 页面打不开 | Vite、端口、浏览器控制台 |
| `ERR_CONNECTION_REFUSED` | 后端或前端进程是否监听 |
| `401` | JWT、Authorization、用户依赖 |
| `422` | 请求 JSON 字段和 Pydantic Schema |
| `500` 启动时出现 | 导入、数据库连接、环境变量、生命周期 |
| 研究接口立即返回 error SSE | LLM、Bocha、Agent 初始化和序列化 |
| SSE 有事件但页面空白 | 前端事件映射和状态触发 |
| 文档 completed 但召回为空 | 集合名、Embedding、Milvus |
| Text2SQL 有数据但不可信 | 是否进入 Mock fallback |

## 8. 当前项目的证据等级

```text
源码阅读：确认设计和分支存在
python -m compileall：确认 Python 可解析
npm run build：确认前端可打包
Docker 健康：确认基础设施可连接
真实 SSE：确认研究链路实际运行
真实外部 API：确认业务数据不是 fallback
```

不能用低等级证据替代高等级结论。例如：

```text
build 通过
≠ DeepResearch 真实运行成功
```

## 9. 本课练习

1. 后端启动时为什么数据库不可达可能导致应用无法启动？
2. 研究页面不动时，为什么应该先看 Network 的 SSE，而不是直接修改 React？
3. `401`、`422`、`500` 分别优先检查哪一层？
4. 为什么 `npm run build` 通过仍不能证明完整项目可运行？
