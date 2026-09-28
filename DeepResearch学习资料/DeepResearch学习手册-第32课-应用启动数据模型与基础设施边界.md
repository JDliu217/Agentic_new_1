# DeepResearch 学习手册·第 32 课

## 应用启动、数据模型与基础设施边界

本课把“代码能不能跑起来”拆成三个问题：

1. FastAPI 应用导入和生命周期按照什么顺序执行？
2. PostgreSQL 模型分别保存什么，实体之间如何关联？
3. Docker Compose 启动的是什么，哪些服务仍然需要手动启动？

源码依据：

    D:\课\s4-6\industry_information_assistant\backend\app\app_main.py
    D:\课\s4-6\industry_information_assistant\backend\app\core\database.py
    D:\课\s4-6\industry_information_assistant\backend\app\core\redis_client.py
    D:\课\s4-6\industry_information_assistant\backend\app\core\security.py
    D:\课\s4-6\industry_information_assistant\backend\app\models\
    D:\课\s4-6\industry_information_assistant\docker-compose.yml
    D:\课\s4-6\industry_information_assistant\start-services.sh
    D:\课\s4-6\industry_information_assistant\backend\app\service\checkpoint_service.py

---

## 1. 启动不是从 lifespan 第一行开始

运行：

    python app/app_main.py

Python 会先导入 app_main.py 的顶层代码。当前顺序大致是：

    load_dotenv()
      → 导入路由和模型
      → 导入 core.database.engine 和 Base
      → Base.metadata.create_all(bind=engine)
      → 定义 lifespan()
      → 创建 FastAPI app
      → 添加 CORS
      → 注册路由
      → uvicorn.run(...)

关键点是 Base.metadata.create_all(bind=engine) 发生在应用真正开始监听端口之前。因为 engine 使用 PostgreSQL 连接，如果数据库不可达，后端可能在监听 8000 之前就失败。

这也是为什么“后端端口没有打开”不一定是路由代码的问题，可能是导入阶段数据库连接失败。

---

## 2. FastAPI 生命周期做什么

应用进入 lifespan 后：

    启动
      → init_scheduler_and_check_data()
      → 定时任务调度器启动
      → yield
      → 应用持续运行

应用关闭时：

    get_scheduler_service()
      → scheduler.stop()

启动时的定时服务会检查行业数据并注册采集任务。代码对调度器启动异常做了捕获并记录日志，因此某些情况下应用可能仍然监听端口，但定时采集没有正常工作。

要区分：

    Web 服务启动成功
    定时任务启动成功

它们不是同一个健康信号。

---

## 3. 路由注册后的接口地图

app_main.py 注册了认证、会话、知识库、附件、记忆、数据库、文档、搜索、聊天、研究、新闻和招投标相关路由。

启动成功只证明 FastAPI 应用已经装载这些路由，不代表每个路由依赖的 Redis、Milvus、外部 LLM、搜索 API 和 DocMind 都已经可用。

健康检查应分层进行：

    GET /hello
      → 只验证 FastAPI 是否在监听

    登录和会话接口
      → 验证 PostgreSQL 和 JWT

    旧聊天或取消研究
      → 验证 Redis

    知识库上传和召回
      → 验证 DocMind、Embedding、Milvus

    DeepResearch
      → 还要验证 LLM、搜索和完整 SSE

---

## 4. PostgreSQL 连接和会话

core/database.py 从环境变量读取 POSTGRES_HOST、POSTGRES_PORT、POSTGRES_USER、POSTGRES_PASSWORD 和 POSTGRES_DB，然后构造 SQLAlchemy URL，创建 engine、SessionLocal 和 Base。

路由中的 get_db() 每次请求创建一个 Session，并在 finally 中关闭。检查点服务没有使用请求依赖，而是直接调用 SessionLocal 创建独立会话。

因此要区分：

    路由请求 DB Session
    检查点后台保存使用的 DB Session

它们都连接同一个 PostgreSQL，但生命周期和创建位置不同。

---

## 5. 用户、会话和消息模型

核心关系可以画成：

    User
      ├── ChatSession
      │     ├── ChatMessage
      │     ├── ChatAttachment
      │     └── LongTermMemory
      ├── KnowledgeBase
      │     └── Document
      ├── LongTermMemory
      └── ResearchCheckpoint

User 保存用户名、邮箱、密码哈希、活跃状态和管理员标记。密码字段是 hashed_password，不会保存明文密码。

ChatSession 保存 id、user_id、title、session_type、created_at 和 updated_at。

ChatMessage 保存 session_id、role、content、thinking、references_data 和 image_results。

session_type 是业务标记，不能单独用来判断真实请求是否走 DeepResearch；真实执行器还要看前端调用的 URL 和请求字段。

---

## 6. 附件和长期记忆模型

ChatAttachment 属于普通聊天附件，保存 session_id、message_id、filename、file_type、file_path、content_text、status 和 error_message。状态通常是 pending、processing、completed 或 failed。

LongTermMemory 保存 user_id、session_id、summary、key_insights、milvus_ids 和 token_count。

这说明长期记忆在 PostgreSQL 中有摘要和元数据，同时可以在 Milvus 中保存向量。数据库记录和向量记录需要共同维护，删除或检索时不能只操作其中一边。

---

## 7. 知识库和文档模型

KnowledgeBase 保存用户拥有的知识库，包括 user_id、name、description 和 document_count。

Document 保存知识库中的文件元数据，包括 knowledge_base_id、user_id、filename、file_type、file_path、status、chunk_count 和 error_message。

文档正文切片和向量不直接存储在这个 SQL 模型里。它们由 DocMind、Embedding 和 Milvus 链路处理。PostgreSQL 负责管理对象、状态和权限，Milvus 负责相似度检索。

---

## 8. 研究检查点的双状态设计

ResearchCheckpoint 的重点字段是 session_id、user_id、query、phase、iteration、state_json、ui_state_json、final_report、status 和 error_message。

其中：

    state_json
      → 后端 ResearchState，供研究恢复

    ui_state_json
      → research_steps、search_results、charts、knowledge_graph、streaming_report

    final_report
      → 单独保存的最终报告文本

保存检查点时，CheckpointService 会清理不可序列化字段，再更新同一个 session_id 的记录。页面恢复时调用 full checkpoint 接口，同时读取后端状态和 UI 状态。

这就是为什么“研究状态能恢复”和“聊天消息表有最终回答”是两个不同问题。

---

## 9. Redis 在项目中承担的角色

core/redis_client.py 创建 Redis 连接池，并提供 get、set、delete、exists、set_session、get_session、add_to_list 和 get_list。

当前 Redis 被旧会话服务、取消研究标志和短期缓存使用。取消研究的键形如 research:cancel:<session_id>。

研究图每轮会检查这个键，结束或新研究开始时清除它。

Redis 连接池可以在应用导入时创建，但真正的读写通常在请求或研究执行过程中发生。因此 Redis 不可用不一定阻止所有模块导入，却会影响旧聊天、取消和缓存行为。

---

## 10. Docker Compose 启动的服务

根目录 docker-compose.yml 定义：

    postgres
    redis
    etcd
    minio
    milvus
    elasticsearch

它们的职责是：

    PostgreSQL
      → 用户、会话、消息、知识库、行业数据、检查点

    Redis
      → 旧会话、缓存、取消标志

    etcd + MinIO
      → Milvus 的依赖

    Milvus
      → 文本和长期记忆的向量检索

    Elasticsearch
      → 可选全文检索链

Compose 没有定义 backend 和 frontend 服务。启动中间件后，还需要单独执行：

    backend:  python app/app_main.py
    frontend: npm run dev

因此 docker compose up -d 成功不等于访问 localhost:8000 或前端页面已经成功。

---

## 11. 数据卷和危险操作

Compose 为 PostgreSQL、Redis、etcd、MinIO、Milvus 和 Elasticsearch 配置了 named volume。容器删除后，数据通常仍在 volume 中。

但是：

    docker compose down
      → 停止并删除容器，通常保留 volume

    docker compose down -v
      → 同时删除 volume，数据库、缓存和向量数据都会丢失

项目启动脚本的 clean 命令会执行带 -v 的清理。学习时不要把它当成普通重启命令。

---

## 12. README 与源码的差异

当前已确认：

    README 写前端默认端口 5173
    frontend/vite.config.ts 当前配置是 5183

README 描述的是推荐启动顺序，实际后端是否能启动还取决于 PostgreSQL 是否可达、环境变量是否已加载、Python 依赖是否安装，以及导入阶段 create_all 是否成功。

遇到文档和行为不一致时，以当前源码、配置和实际日志为准，并把差异记录下来。

---

## 13. 分层启动验证

建议按以下顺序验证：

    1. docker compose ps
    2. PostgreSQL healthcheck
    3. Redis ping
    4. Milvus /healthz
    5. python -m compileall -q backend/app
    6. 启动后端
    7. GET http://localhost:8000/hello
    8. 登录并访问 /sessions
    9. 启动前端并检查实际 Vite 端口
    10. 运行一个不依赖完整研究的页面请求
    11. 最后验证 DeepResearch SSE

每一步只证明对应的一层，不能把前一步的成功扩大解释成整个系统成功。

---

## 14. 面试回答模板

如果面试官问“项目如何启动，数据怎么存”，可以这样回答：

应用导入时先加载环境变量、注册模型并执行 SQLAlchemy 的 create_all，数据库不可达可能在监听端口前就阻止启动。FastAPI lifespan 再启动行业数据调度器。PostgreSQL 保存用户、会话、消息、知识库元数据、行业数据和研究检查点；Redis 服务旧会话、缓存和研究取消标志；Milvus 保存向量检索数据，MinIO 和 etcd 是 Milvus 依赖。Docker Compose 只启动这些基础设施，后端和前端仍需单独启动。研究恢复使用 ResearchCheckpoint 的 state_json 和 ui_state_json 两套状态，分别服务后端恢复和前端研究面板恢复。

---

## 15. 练习

1. 为什么 PostgreSQL 不可达可能导致后端在 8000 端口监听前失败？
2. lifespan 启动成功是否能证明定时采集一定正常？
3. ChatMessage、ChatAttachment 和 Document 分别属于什么业务链？
4. state_json 和 ui_state_json 为什么要分开？
5. Docker Compose 启动后为什么还需要单独启动 backend 和 frontend？
6. docker compose down 与 down -v 的数据影响有什么区别？
7. 你会用什么顺序判断问题是 PostgreSQL、Redis、Milvus 还是 FastAPI 本身？

---

## 16. 留给你的笔记区

### 16.1 我画的启动顺序



### 16.2 我画的数据库实体关系



### 16.3 我遇到过的启动错误和对应层级



