# DeepResearch 项目学习手册

## 第 6 课：运行、部署、测试和故障排查

本课根据项目当前文件和实际命令结果整理。目标是让你知道“代码读懂后怎样判断系统真的能运行”，以及故障发生时先查哪一层。

## 1. 运行时由四层组成

~~~text
浏览器前端 React/Vite
        |
        | HTTP / SSE
        v
FastAPI 后端
        |
        +-- PostgreSQL
        +-- Redis
        +-- Milvus
        |     +-- etcd
        |     +-- MinIO
        +-- Elasticsearch（可选）
        |
        +-- 外部 API：LLM、Embedding、Bocha、DocMind、股票、招投标
~~~

任何一层没准备好，系统都可能表现为“页面能打开但功能失败”。启动成功不等于业务链路可用。

## 2. Docker Compose 中每个服务的职责

根目录 docker-compose.yml 定义：

| 服务 | 端口 | 作用 |
| --- | --- | --- |
| postgres | 5432 | 关系型业务数据 |
| redis | 6379 | 缓存、短期状态、取消标志 |
| etcd | 容器内部 2379 | Milvus 元数据 |
| minio | 9000/9001 | Milvus 对象存储和控制台 |
| milvus | 19530/9091 | 向量数据库和健康检查 |
| elasticsearch | 宿主机 1200 | 可选全文检索 |

持久化卷包括 postgres_data、redis_data、etcd_data、minio_data、milvus_data 和 es_data。docker compose down 通常保留卷；docker compose down -v 会删除数据卷，只适合明确要清空开发数据时使用。

## 3. 正确启动顺序

### 3.1 启动基础服务

在项目根目录：

~~~bash
docker compose up -d
~~~

或使用：

~~~bash
./start-services.sh start
~~~

脚本会检查 Docker、启动 Compose、等待一段时间，再用 pg_isready、redis-cli ping、Milvus health endpoint 和 Elasticsearch health endpoint 做简单检查。

### 3.2 配置后端

~~~bash
cd backend
cp .env.example .env
~~~

至少要准备：

~~~text
DASHSCOPE_API_KEY
BOCHA_API_KEY
POSTGRES_*
REDIS_*
MILVUS_*
JWT_SECRET_KEY
~~~

DocMind、股票和招投标功能还需要各自的可选密钥。生产环境不能使用示例文件中的默认密码或 JWT 密钥。

### 3.3 启动后端

~~~bash
cd backend
python app/app_main.py
~~~

默认端口是 8000，启动后可以访问：

~~~text
http://localhost:8000/hello
http://localhost:8000/docs
~~~

### 3.4 启动前端

~~~bash
cd frontend
npm install --legacy-peer-deps
npm run dev
~~~

README 中写的是 `5173`，但当前源码 `frontend/vite.config.ts` 实际配置开发服务器端口为 `5183`，所以按当前代码应访问 `http://localhost:5183/login`。前端请求地址由 `VITE_API_BASE` 决定。

## 4. 当前环境的实际验证结果

我在当前项目目录执行了以下检查。

### 4.1 Python 语法

~~~text
python -m compileall -q backend/app
结果：通过
~~~

这只能证明 Python 文件可以编译，不能证明外部 API、数据库或模型调用可用。

### 4.2 前端依赖安装

第一次执行 npm ci --ignore-scripts 时失败，原因是 ahooks@3.8.4 的 peer dependency 只声明 React 16/17/18，而项目声明 React 19。

按项目 README 约定执行：

~~~bash
npm ci --legacy-peer-deps --ignore-scripts
~~~

结果：依赖安装成功，但 npm 报告存在依赖漏洞。--legacy-peer-deps 是绕过 peer dependency 解析冲突，不是证明这些依赖完全兼容。

### 4.3 前端构建

~~~text
npm run build
结果：通过
~~~

构建完成，但 Vite 报告主 JS chunk 超过 500 kB。后续可以使用动态导入和 Rollup 分包，当前不影响构建成功。

### 4.4 端到端研究测试

backend/app/scripts/test_deep_research_v2.py 需要真实的 DASHSCOPE_API_KEY 和 BOCHA_API_KEY，还需要后端依赖和外部网络服务。没有这些配置时，测试会在环境变量检查阶段停止；这不是代码逻辑通过的证据。

## 5. 测试脚本实际测试什么

测试脚本包含两部分。

### 5.1 Agent 单独测试

依次调用：

~~~text
ChiefArchitect -> 检查是否生成大纲
DeepScout      -> 检查事实或引用
CodeWizard     -> 检查洞察和数据点
~~~

这部分覆盖了部分 Agent，但没有单独验证 Writer、Critic、检查点和前端。

### 5.2 端到端测试

它消费 DeepResearchV2Service.research() 的 SSE 字符串，记录规划、搜索、分析、写作、审核和完成事件，并检查是否缺失关键阶段、是否有最终报告和错误事件。

需要注意：测试脚本中识别的事件名称和当前 V2 某些实现事件可能不完全一致，例如测试代码寻找 search_result、analysis_result、section_written、review_result，而前端主要处理 search_results、charts、section_content、review。运行测试时要把“测试脚本协议”和“实际事件协议”一起核对。

## 6. 四层故障排查法

### 6.1 第一层：前端请求有没有发出

检查浏览器 Network 面板、请求 URL 是否使用正确的 VITE_API_BASE、Authorization 是否存在、请求体字段是否匹配，以及 SSE response 是否持续收到 data:。

如果页面直接跳转登录，先查 authState 和 localStorage 的 auth。

### 6.2 第二层：FastAPI 路由有没有收到

检查：

~~~text
http://localhost:8000/hello
http://localhost:8000/docs
后端日志中的路由和异常堆栈
~~~

如果 /hello 都无法访问，先不要排查 Agent；问题在后端进程、端口或网络。

### 6.3 第三层：中间件是否可用

~~~bash
docker compose ps
docker compose logs postgres
docker compose logs redis
docker compose logs milvus
~~~

对应检查：

~~~text
PostgreSQL -> 连接字符串、数据库是否创建
Redis      -> 主机/端口、取消标志和缓存是否可读
Milvus     -> 集合是否存在、Embedding 维度是否一致
MinIO/etcd -> Milvus 的依赖是否健康
~~~

### 6.4 第四层：外部 API 和业务数据

~~~text
LLM key 是否有效
Bocha key 是否有效
DocMind 凭据是否完整
股票/招投标 API 是否有配额
数据库是否已经 seed 行业数据
知识库文档是否 completed
~~~

外部 API 失败时，项目很多服务会返回空列表或错误字典，所以“HTTP 200 但结果为空”不一定代表业务成功。

## 7. 运行不同功能需要哪些最小依赖

| 功能 | 最小依赖 |
| --- | --- |
| 登录和会话 | PostgreSQL、JWT 配置 |
| 普通 Redis 聊天兼容路径 | Redis、LLM |
| V2 DeepResearch | LLM、Bocha，按配置可选 Milvus/PostgreSQL |
| 知识库上传 | PostgreSQL、DocMind、Embedding、Milvus |
| 本地检索 | Embedding、Milvus |
| Text2SQL | LLM、PostgreSQL 或模拟数据模式 |
| 新闻采集 | PostgreSQL、Bocha |
| 招投标采集 | PostgreSQL、81API 配额 |
| 股票查询 | 聚合数据 API key |
| 长期记忆 | PostgreSQL、LLM、Embedding、Milvus |

## 8. 部署时必须区分的地址

后端在宿主机运行时通常使用：

~~~text
POSTGRES_HOST=localhost
REDIS_HOST=localhost
MILVUS_HOST=localhost
~~~

后端如果也放进 Docker Compose 网络中，通常应改为：

~~~text
POSTGRES_HOST=postgres
REDIS_HOST=redis
MILVUS_HOST=milvus
~~~

容器里的 localhost 指当前容器本身，不是宿主机，也不是另一个 Compose 服务。

## 9. 当前项目的工程风险清单

1. 前端 React 19 与 ahooks peer dependency 不匹配，需要 --legacy-peer-deps 安装。
2. npm 审计报告存在漏洞，不能只看构建成功就认为依赖安全。
3. 主前端 bundle 较大，需要后续分包。
4. 后端测试依赖真实外部 API，缺少隔离的 mock 测试。
5. E2E 测试的事件名称需要和当前 V2 事件协议重新对齐。
6. 代码中存在硬编码默认凭据风险，应移除并轮换已经暴露的密钥。
7. create_all() 不能替代完整迁移机制。
8. Shell 启动脚本面向 Unix；Windows 使用 Docker Compose 命令更直接。
9. 外部服务错误经常降级为空结果，监控中应区分“空数据”和“请求失败”。

## 10. 推荐的学习和实践顺序

~~~text
第 1 步 只启动 PostgreSQL 和 Redis，理解登录与会话
第 2 步 启动后端，访问 /hello 和 /docs
第 3 步 用测试账号走 /auth 和 /sessions
第 4 步 初始化 industry_data，使用 /database/text2sql
第 5 步 配置 Bocha，验证普通搜索
第 6 步 配置 LLM，运行单个 Agent
第 7 步 运行 V2 DeepResearch SSE
第 8 步 启动 Milvus，上传文档并验证向量检索
第 9 步 验证检查点、恢复和取消
第 10 步 最后再看新闻、招投标和长期记忆
~~~

每一步只增加一类依赖，出错时才容易定位。

## 11. 本课练习

### 练习一：解释为什么前端能构建但运行仍可能失败

构建只验证 TypeScript、JS、CSS 和打包依赖；运行还需要正确的 API 地址、后端进程、Token、数据库、Redis、模型和外部 API。

### 练习二：设计一次 DeepResearch 自检

至少检查：

~~~text
/hello 可访问
POST /auth/login 成功
POST /sessions 成功
POST /research/stream 返回 research_start
收到 planning、researching、writing 等事件
收到 research_complete 或明确 error
~~~

### 练习三：定位 Milvus 检索为空

先确认集合存在，再确认文档处理完成、Embedding 维度相同、查询使用了正确集合名，最后才检查排序和 top_k。

## 12. 面试检查题

### 初级

- Docker Compose 中 etcd 和 MinIO 为什么也属于 Milvus 的依赖？
- python -m compileall 能证明什么，不能证明什么？
- 为什么容器内不能随便把数据库主机写成 localhost？

### 中级

- 如何区分前端问题、FastAPI 问题、中间件问题和外部 API 问题？
- 为什么 E2E 测试不能只检查 HTTP 200？
- --legacy-peer-deps 解决了什么，留下了什么风险？

### 高级

- 怎样把依赖外部 API 的 Agent 测试改造成可重复的 mock 测试？
- 怎样设计 SSE 协议版本，避免 V1/V2 事件名称漂移？
- 如何将后端、PostgreSQL、Redis 和 Milvus 一起部署，同时安全管理密钥和持久化卷？

## 13. 本课结论

工程上的“能运行”要用证据判断：

~~~text
语法通过 != 依赖安装成功
构建成功 != 后端可达
HTTP 200 != 业务成功
页面有数据 != 数据来自真实服务
~~~

掌握分层启动和分层排查，你才能把项目从“看懂代码”推进到“能独立运行、验证和定位问题”。

