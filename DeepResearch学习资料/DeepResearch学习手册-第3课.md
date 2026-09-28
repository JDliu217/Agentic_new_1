# DeepResearch 项目学习手册

## 第 3 课：从登录、会话到知识库和基础设施

本课对应本地项目 `D:\课\s4-6\industry_information_assistant` 的外围工程。前两课解释了 Agent 主链路；本课解释请求如何进入后端、数据存在哪里、文档如何变成可检索知识，以及 Docker 服务各自承担什么职责。

## 1. 先建立一个重要判断：项目存在两条工程轨道

当前代码不是从零一次性设计完成的，而是持续迭代形成的。可以看到两套相关能力：

| 能力 | 较早路径 | 较新路径 |
| --- | --- | --- |
| 会话 | `service/session_service.py` 使用 Redis | `/sessions` 路由使用 PostgreSQL ORM |
| 普通聊天 | `/chat/completion`、`/chat/completion/v1` | 仍由聊天服务兼容旧接口 |
| 深度研究 | V1 ReAct：`ResearchService -> ReActController` | V2 多 Agent：`DeepResearchGraph` |
| 文档检索 | 外部文档服务/旧索引 | 本地知识库上传后写入 Milvus |
| 附件 | 聊天附件表 + 本地临时文件 | 知识库文档表 + DocMind + Milvus |

所以“看到两个会话模型”不一定是代码读错，而是项目中确实保留了兼容路径。学习和排查问题时，第一步应先确认当前前端调用的是哪条路径。

## 2. 应用从哪里启动

入口是 `backend/app/app_main.py`：

```text
load_dotenv()
  -> 创建 SQLAlchemy engine
  -> 导入全部模型
  -> Base.metadata.create_all()
  -> 创建 FastAPI
  -> 注册 CORS
  -> 注册各个 router
  -> 启动生命周期任务
```

注册的主要路由包括：

```text
/auth              用户认证
/sessions          新会话和消息 API
/knowledge-bases   知识库与文档
/attachments       聊天附件
/memory            长期记忆
/database          数据库探索
/documents         外部文档服务兼容接口
/search            搜索
/chat              普通聊天
/research          深度研究和检查点
/news              行业新闻
```

应用启动时还会尝试初始化调度器，负责检查或更新行业数据。数据库表由 SQLAlchemy 的 `Base.metadata.create_all()` 创建，但已有表结构的增量修改仍需要手动 SQL 或迁移方案；README 中就记录了检查点字段的补充语句。

## 3. 登录链路：密码、JWT 和当前用户

### 3.1 注册和登录

`auth_router.py` 提供：

```text
POST /auth/register
POST /auth/login
POST /auth/token       OAuth2 兼容
GET  /auth/me
POST /auth/change-password
POST /auth/logout
```

注册过程：

```text
用户名/邮箱查重
  -> bcrypt 哈希密码
  -> 写入 users 表
  -> 生成 JWT
  -> 返回 access_token 和用户信息
```

登录过程允许使用用户名或邮箱。后端不会保存明文密码，只保存 `hashed_password`。

### 3.2 JWT 中有什么

`create_access_token()` 把用户 ID放在 `sub`，同时放入用户名和过期时间 `exp`。前端后续请求通过 Bearer Token 发送，`get_current_user_required()` 解码 Token、查询用户、检查用户是否启用。

代码里有默认 JWT 密钥字符串，生产部署必须通过环境变量覆盖并轮换真实密钥。API Key 和密钥不应写进教学资料或提交到 Git。

### 3.3 为什么有可选认证

部分附件接口使用 `get_current_user()`，允许没有 Token 的请求继续处理；会话管理和核心数据接口使用 `get_current_user_required()`。这表示项目对不同接口采用了不同的认证强度。安全审查时，应重点确认“允许匿名访问”的接口是否真的符合产品要求。

## 4. 新会话路径：PostgreSQL 保存业务数据

`models/chat.py` 定义了四个关键模型：

```text
User
  └── ChatSession
        ├── ChatMessage
        ├── ChatAttachment
        └── LongTermMemory
```

`/sessions` 路由的典型请求链：

```text
前端 createSession()
  -> POST /sessions
  -> get_current_user_required()
  -> SQLAlchemy 创建 ChatSession
  -> commit / refresh
  -> 返回 SessionResponse
```

获取会话详情时，后端先验证会话属于当前用户，再按时间升序返回消息。这个“按用户过滤”是数据隔离的关键，不应只依赖前端传入的 session ID。

消息内容包含：

| 字段 | 作用 |
| --- | --- |
| `role` | user、assistant 或 system |
| `content` | 正文 |
| `thinking` | 思考或过程文本 |
| `references_data` | 引用数据 JSONB |
| `image_results` | 图片结果 JSONB |

## 5. 旧会话路径：Redis 保存短期聊天上下文

`service/session_service.py` 是另一套会话服务。它把会话写入：

```text
session:{session_id}
message:{session_id}:{message_id}
session:{session_id}:messages   (sorted set)
```

添加消息时，消息正文写入 Hash，消息 ID 以时间戳写入 Sorted Set。超过 `max_messages = 20` 后删除最早消息。生成提示词时再从最近消息倒序取出，并用 `tiktoken` 控制总 token 不超过 `5000`。

这条路径适合短期上下文缓存，但它和 PostgreSQL 的业务会话不是同一套记录。调试时如果“数据库里没有聊天记录”，可能是请求实际走了旧 Redis 接口。

## 6. 普通聊天的数据流

以 `/chat/completion` 为例：

```text
请求问题
  -> 可选知识库检索
  -> 可选 Web 搜索
  -> 合并文档
  -> DashScope Rerank 重排
  -> token 限制截断
  -> 加入会话历史
  -> LLM 流式生成
  -> StreamingResponse
```

`/chat/completion/v2` 将本地检索改为 `retrieve_content(indexNames="policy_documents")`，`/chat/completion/v3` 还会读取已处理完成的聊天附件，把附件文本拼进增强问题。

普通聊天和 DeepResearch 的区别是：普通聊天通常是“一次检索 + 一次生成”，DeepResearch 是“规划、搜索、分析、写作、审核”的多阶段状态机。

## 7. 聊天附件链路

### 7.1 上传

前端 `uploadAttachment()` 使用 `multipart/form-data` 调用：

```text
POST /attachments
  file
  session_id
```

后端会：

1. 校验 session ID 格式。
2. 验证会话存在。
3. 校验扩展名白名单。
4. 把文件写入 `/tmp/chat_attachments`。
5. 在 `chat_attachments` 表创建 `pending` 记录。
6. 添加后台任务 `process_attachment()`。

### 7.2 后台处理

后台处理把状态改成 `processing`，再按扩展名读取：

```text
txt/md/py/js/json/yaml/xml/csv/html -> 直接读取文本
pdf/docx/图片                       -> 当前只写入占位文本
```

文本最长限制为 50000 个字符，完成后写入 `content_text` 并改为 `completed`。因此当前附件能力不能等同于“所有 PDF 和 Word 都已解析”；聊天附件和知识库文档的处理能力不同。

### 7.3 带附件提问

`/chat/completion/v3` 查询附件 ID，只有 `status == completed` 且有 `content_text` 的附件才会加入上下文。每个附件最多截取 10000 个字符，再与用户问题拼接后交给聊天服务。

## 8. 知识库文档链路

知识库上传与聊天附件是两套不同流程。知识库路由使用 `KnowledgeBase` 和 `Document` 模型。

### 8.1 上传和记录

```text
POST /knowledge-bases/{kb_id}/documents
  -> 校验知识库属于当前用户
  -> 校验扩展名
  -> 写入 /tmp/knowledge_uploads
  -> Document(status="pending")
  -> document_count + 1
  -> 后台 process_document()
```

文档状态依次可能是：

```text
pending -> processing -> completed
                    -> failed
```

### 8.2 DocMind、切片和向量

`process_document_with_docmind()` 的数据流是：

```text
本地文件
  -> DocMind 提交解析任务
  -> 轮询任务状态
  -> 分页收集 layouts
  -> 合并 Markdown/文本
  -> chunk_text(chunk_size=500, overlap=50)
  -> text-embedding-v4
  -> Milvus collection
```

切片会尽量在句号、问号或换行处断开，并保留 50 个字符重叠。每个切片包含文件名、文档 ID、知识库 ID、正文、顺序和向量。

### 8.3 查询

`retrieve_content()` 的核心步骤：

```text
问题
  -> 生成问题向量
  -> Milvus 向量搜索 top_k
  -> 取回 content / filename / doc_id / score
  -> 转成聊天或研究 Agent 能使用的格式
```

Embedding 默认使用 `text-embedding-v4` 和 1024 维向量。Milvus 的集合名称通常由知识库名称转换得到，例如 `kb_行业报告`；查询和写入时必须使用一致的命名规则。

## 9. 三类存储各自保存什么

| 系统 | 主要保存内容 | 典型访问方式 |
| --- | --- | --- |
| PostgreSQL | 用户、正式会话、消息、知识库、文档元数据、检查点、行业业务表 | SQLAlchemy ORM |
| Redis | 短期会话、消息列表、缓存、研究取消标志 | `RedisCache` 或旧 `SessionService` |
| Milvus | 文档切片向量、长期记忆向量 | `MilvusService.search/insert_documents` |

可以用一句话记忆：

```text
PostgreSQL 记业务事实
Redis       记短期状态
Milvus      记可相似检索的向量
```

## 10. Docker 基础设施

根目录 `docker-compose.yml` 提供：

```text
PostgreSQL       业务关系数据
Redis            缓存和短期状态
Milvus           向量检索
etcd             Milvus 元数据
MinIO            Milvus 对象存储
Elasticsearch    可选全文检索
```

端口映射和环境变量必须区分“容器内部地址”和“宿主机地址”。例如后端在宿主机运行时通常连接 `localhost:5432`，后端如果也在 Docker 网络内运行，则应使用服务名 `postgres`、`redis`、`milvus` 等。README 的本地启动方式和 Compose 启动方式不能混用连接地址。

## 11. 从用户登录到一次 DeepResearch 的完整线路

```text
1. 登录
   /auth/login -> bcrypt 校验 -> JWT

2. 创建会话
   /sessions -> PostgreSQL ChatSession

3. 前端发起研究
   /research/stream -> ResearchRequest

4. 后端执行
   DeepResearchV2Service -> DeepResearchGraph

5. 检索
   WebSearchService / Milvus / 本地知识库

6. 形成状态
   facts -> data_points -> charts -> draft_sections -> final_report

7. 实时展示
   Agent message -> asyncio.Queue -> SSE -> React

8. 持久化
   ResearchCheckpoint 保存后端 state 和 UI state

9. 页面恢复
   /research/checkpoint/{session_id}/full -> 前端重建研究步骤和详情
```

## 12. 当前实现边界和学习时必须记住的风险

1. 普通聊天存在 Redis 旧路径和 PostgreSQL 新路径，不能假定所有会话都在一个地方。
2. 聊天附件的 PDF、Word、图片当前主要是占位文本；知识库文档才走 DocMind 解析。
3. `Base.metadata.create_all()` 不是完整数据库迁移机制，字段变更仍需迁移脚本或手动 SQL。
4. CORS 当前允许所有源，JWT 有默认密钥，数据库连接也有默认密码，这些都不适合直接用于生产。
5. `DocumentService` 依赖外部文档服务，`DocMindService` 依赖阿里云服务，向量检索还依赖 Milvus；缺少任何一项都可能让链路降级或返回空结果。
6. 研究取消标志放在 Redis 中，研究执行过程通过 `session_id` 查询它；如果 Redis 不可用，取消机制就不能按预期工作。

## 13. 本课练习

### 练习一：判断数据落点

把下面数据分别归类到 PostgreSQL、Redis 或 Milvus：

```text
用户密码哈希
最近 20 条聊天消息
一段文档切片的 1024 维向量
研究检查点
取消研究标志
知识库文档的文件名和处理状态
```

参考：

```text
PostgreSQL：用户密码哈希、研究检查点、文档元数据
Redis：最近聊天消息、取消研究标志
Milvus：文档切片向量
```

### 练习二：排查附件为什么没有内容

如果 `/chat/completion/v3` 没有使用上传的 PDF 内容，按以下顺序检查：

```text
session_id 是否正确
附件是否存在
附件 status 是否已经 completed
content_text 是否只是 [PDF 文件: ...] 占位文本
前端是否把 attachment_ids 传给 v3
```

### 练习三：排查知识库检索为空

```text
1. Document 是否 completed
2. DocMind 是否解析成功
3. 是否切出了 chunks
4. Embedding 是否返回 1024 维向量
5. Milvus 集合名是否一致
6. Milvus 是否已 load
7. 查询时是否使用同一个 collection_name
```

## 14. 面试检查题

### 初级

- PostgreSQL、Redis、Milvus 为什么不能互相替代？
- 聊天附件和知识库文档的处理路径有什么区别？
- JWT 的 `sub` 字段在本项目中表示什么？

### 中级

- 为什么上传知识库文档要用后台任务？
- `chunk_size=500` 和 `overlap=50` 分别解决什么问题？
- 如果后端在 Docker 容器内运行，为什么不能照搬 `localhost:19530` 连接 Milvus？

### 高级

- 如何统一 Redis 旧会话和 PostgreSQL 新会话，避免同一用户看到两套历史？
- 如何把当前聊天附件的 PDF 占位解析替换为可靠的异步文档解析？
- 如何设计数据库迁移，替代启动时直接 `create_all()` 的方式？

## 15. 本课结论

DeepResearch 不是孤立的 Agent 代码。它依赖认证确定用户，依赖会话确定上下文，依赖知识库和向量检索提供证据，依赖 Redis 和 PostgreSQL 保存状态，依赖 SSE 把结果送到前端，依赖 Docker 提供运行时基础设施。

真正掌握这个项目，至少要能沿着下面三条线定位任何问题：

```text
请求线：浏览器 -> FastAPI 路由 -> Service -> 外部服务
数据线：输入 -> 数据库/缓存/向量库 -> Agent 状态 -> 报告
事件线：Agent -> Queue -> SSE -> React 状态 -> 页面
```

