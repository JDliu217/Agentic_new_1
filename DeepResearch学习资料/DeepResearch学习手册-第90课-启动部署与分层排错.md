# DeepResearch 学习手册：第 90 课

## 启动、依赖和分层排错

“项目能编译”与“项目能完整运行”是两件事。本课建立启动顺序，并说明每一层失败时应该看什么证据。

## 1. 项目需要哪些运行部分

### 基础设施

主 `docker-compose.yml` 提供：

```text
PostgreSQL：用户、会话、文档、研究检查点和行业数据
Redis：缓存、旧会话、取消标志
Milvus：知识库和长期记忆向量
etcd + MinIO：Milvus 的依赖
Elasticsearch：可选全文检索服务
```

### 后端

```text
Python 依赖
FastAPI + Uvicorn
环境变量
外部 LLM、搜索、DocMind、股票和招投标 API
```

### 前端

```text
Node 依赖
Vite
React
VITE_API_BASE
VITE_API_PROXY
```

## 2. 后端启动顺序

在 `backend/app/app_main.py` 中，导入阶段会：

1. `load_dotenv()` 加载环境变量。
2. 导入 Router 和模型。
3. 使用 `Base.metadata.create_all(bind=engine)` 创建表。

应用进入 lifespan 后：

```text
启动 Scheduler
→ 检查行业数据
→ 没有数据时立即采集
→ 应用开始提供 API
```

因此数据库连接在导入阶段就很重要；调度器还可能在启动时访问外部 API。

常见启动命令：

```text
cd backend
pip install -r requirements.txt
python app/app_main.py
```

或使用 Uvicorn 指向应用对象。

## 3. 前端启动和代理

文件：`frontend/vite.config.ts`

前端 Vite 默认端口是 `5183`，并将 `VITE_API_BASE` 对应的请求代理到 `VITE_API_PROXY`。

当前 `.env` 的核心配置类似：

```text
VITE_API_BASE=http://localhost:8000/
VITE_API_PROXY=http://localhost:8000/
```

启动：

```text
cd frontend
npm install
npm run dev
```

如果前端页面能打开但 API 全部失败，先检查代理目标和后端端口，而不是先检查 React 组件。

## 4. 环境变量按用途分类

### 必须优先确认

```text
DASHSCOPE_API_KEY
POSTGRES_HOST/PORT/USER/PASSWORD/DB
REDIS_HOST/PORT
MILVUS_HOST/PORT
JWT_SECRET_KEY
```

### 按功能确认

```text
BOCHA_API_KEY：网络搜索和行业资讯
DOCMIND_ACCESS_KEY_ID/SECRET：文档解析
JUHE_STOCK_API_KEY：股票行情
BID_APP_KEY/SECRET/CODE：招投标
```

缺少可选外部 API 时，部分页面仍然能启动，但对应功能会返回空结果或错误。

## 5. 最小验证阶梯

不要一上来就跑完整 DeepResearch，按下面顺序获得证据：

### 第 1 层：静态检查

```text
python -m compileall -q app
npm run build
```

证明代码可以编译、前端可以打包，但不证明依赖可连接。

### 第 2 层：基础设施健康

```text
docker compose ps
```

确认 PostgreSQL、Redis、Milvus、etcd 和 MinIO 健康。

### 第 3 层：应用存活

```text
GET /hello
```

确认 FastAPI 已启动并能响应。

### 第 4 层：认证和会话

```text
注册或登录
→ 创建 session
→ 获取 session 详情
```

确认 JWT、数据库和用户归属都正常。

### 第 5 层：单功能验证

按风险从低到高验证：

```text
Text2SQL / 数据库查询
知识库上传和状态查询
普通聊天 SSE
DeepResearch SSE
```

### 第 6 层：完整外部链路

最后才验证真实 LLM、网络搜索、DocMind、Milvus 召回、CodeWizard 图表和前端完整渲染。

## 6. 按错误类型定位

| 现象 | 第一检查层 |
|---|---|
| 页面打不开 | Vite、端口、Node 依赖 |
| 页面打开但 404 | API base、代理、路由前缀 |
| 401 | JWT、localStorage、请求头、用户状态 |
| 422 | Pydantic 请求字段和类型 |
| 500 且应用启动失败 | PostgreSQL、导入阶段、环境变量 |
| SSE 连接建立但无内容 | Graph、队列、外部 LLM、SSE 格式 |
| 研究有报告但无来源 | DeepScout、facts、references、前端映射 |
| 知识库 completed 但搜不到 | Milvus 集合名、Embedding、查询链 |
| 图表为空 | DataAnalyst/CodeWizard 数据点、执行结果、事件分支 |

## 7. 当前验证证据的边界

已经完成的静态证据：

```text
后端 Python compileall 通过
前端 npm run build 通过
```

尚不能由此证明的运行事实：

```text
Docker 中间件真的健康
真实数据库可连接
LLM key 有效
外部搜索和 DocMind 可用
Milvus 能正确写入和召回
完整 DeepResearch 能从浏览器展示结束
```

如果当前机器没有 Docker 或有效外部密钥，这些部分必须明确标为“未完成运行验证”，不能用构建结果替代。

## 8. 本课练习

请按证据强弱回答：

1. `npm run build` 通过，能证明哪些事情，不能证明哪些事情？
2. 前端页面能打开但 `/research/stream` 返回 404，优先查哪三项？
3. 研究接口返回 500，如何区分是认证、配置、LLM 还是 Agent 阶段的问题？
