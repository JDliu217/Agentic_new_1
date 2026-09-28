# DeepResearch 学习手册·第 50 课

## 用一条故障链学会工程排错

本课目标：当知识库上传后没有检索结果时，能够判断问题发生在数据库、后台任务、解析服务、Embedding、Milvus、检索参数，还是前端显示层。

---

## 1. 先画出事实链

~~~~text
浏览器上传请求成功
    ↓
PostgreSQL 有 documents 记录
    ↓
Document.status 从 pending 变为 processing
    ↓
DocMind 返回解析文本
    ↓
文本被切片
    ↓
Embedding 返回与切片数量相同的向量
    ↓
Milvus collection 存在并插入切片
    ↓
聊天请求使用相同 collection 和正确查询向量
    ↓
Milvus search 返回结果
    ↓
RAG 把结果交给模型
    ↓
前端渲染答案和来源
~~~~

排错规则：从最靠前的事实开始验证。前面的事实没有成立，就不要跳到后面的猜测。

---

## 2. 第一层：确认 PostgreSQL 记录

源码位置：backend/app/router/knowledge_router.py。

上传接口创建 Document，并将 status 设置为 pending，然后提交事务。因此第一步要问：

- 文档记录是否存在？
- knowledge_base_id 是否属于当前用户？
- status 是什么？
- chunk_count 是否为 0？
- error_message 是否有内容？

| 观察结果 | 更可能的范围 |
|---|---|
| 没有记录 | 上传请求、数据库连接、事务或权限 |
| 一直是 pending | 后台任务没有开始，或 Web 进程没有继续执行 |
| processing 后变 failed | DocMind、Embedding、Milvus 或代码异常 |
| completed 且 chunk_count 大于 0 | 进入向量存储验证 |
| completed 但 chunk_count 为 0 | 处理结果契约或成功判断有问题 |

---

## 3. 第二层：确认后台任务真的运行

上传接口调用 BackgroundTasks.add_task，把 process_document、文档 ID、临时路径、知识库名称和 SessionLocal 传进去。

process_document 会使用新的数据库会话：

~~~~python
db = db_session_factory()
doc = db.query(Document).filter(Document.id == document_id).first()
doc.status = "processing"
db.commit()
~~~~

这样做是必要的：上传请求结束后，后台函数仍需要自己的数据库会话。

如果状态一直是 pending，检查：

1. add_task 是否执行到。
2. Web 服务是否在响应后立即退出。
3. SessionLocal 是否能连接 PostgreSQL。
4. 后台函数是否拿到正确的 document_id。
5. 后端日志是否出现异常。

FastAPI BackgroundTasks 依附于当前 Web 进程，不是独立任务队列。进程崩溃或容器重启时，任务可能中断，也没有自动重试和持久化保证。

---

## 4. 第三层：按 DocMind 阶段定位

源码位置：backend/app/service/docmind_service.py。

process_document_with_docmind 大致按以下顺序执行：

1. 创建 DocMindService。
2. submit_job 提交解析任务。
3. wait_for_completion 轮询 DocMind 状态。
4. collect_all_results 收集文本。
5. chunk_text 切片。
6. generate_embedding 生成向量。
7. 构造 Milvus 文档对象。
8. milvus.insert_documents 写入向量库。

| 失败位置 | 应检查 |
|---|---|
| submit_job | DocMind 地址、凭据、网络和文件路径 |
| wait_for_completion | DocMind 任务状态、超时、轮询接口 |
| collect_all_results | 任务 ID 和增量结果接口 |
| chunk_text | 解析文本是否为空、切片参数 |
| generate_embedding | Embedding 服务、返回数量和向量维度 |
| insert_documents | Milvus 连接、集合 schema、索引和写入权限 |

注意：wait_for_completion 的轮询是 DocMind 内部任务轮询；前端每 3 秒刷新文档列表，是 PostgreSQL 状态轮询。这是两套不同的轮询。

---

## 5. 第四层：确认 Embedding 契约

代码检查两个事实：

~~~~python
if not embeddings:
    result["message"] = "向量生成失败: 返回为空"
    return result

if len(embeddings) != len(chunks):
    result["message"] = "向量数量和切片数量不匹配"
    return result
~~~~

每个文本切片必须对应一个向量。

backend/app/service/milvus_service.py 中固定 vector_dim = 1024，并在集合中声明向量维度为 1024。因此数量正确不代表维度正确；例如返回 10 个 1536 维向量，仍不能插入 1024 维集合。

---

## 6. 第五层：确认 Milvus 集合和写入

MilvusService.create_collection 会：

1. 检查集合是否存在。
2. 不存在则创建字段和向量索引。
3. 调用 collection.load。

insert_documents 会准备字段、调用 collection.insert，再调用 collection.flush。

排错时验证：

- collection_name 是否正确。
- collection 是否存在。
- 向量维度是否是 1024。
- 插入数量是否等于 chunk_count。
- flush 后是否可以查询到数据。
- 查询时是否使用了同一个 collection。

当前代码使用知识库名称生成集合名：

~~~~python
index_name = f"kb_{kb_name}".lower().replace(" ", "_")
~~~~

知识库切片查询也使用同样规则。知识库改名后，旧切片所在集合不会自动迁移，这是设计风险。

---

## 7. 第六层：确认查询过滤条件

Milvus search 可以按 kb_id 过滤：

~~~~python
expr = f'kb_id == "{kb_id}"' if kb_id else None
~~~~

写入时，代码把 kb_id 字段设置为 index_name：

~~~~python
"kb_id": index_name
~~~~

因此搜索传入的 kb_id 必须和写入时的 index_name 具有相同含义和格式。如果一侧传真实 UUID，另一侧保存集合名，过滤条件会让结果为空，即使向量已经写入。

这是典型的“数据存在，但过滤条件不匹配”。

---

## 8. 前端显示层只说明看到了什么

frontend/src/api/knowledge.ts 将 status 限定为 pending、processing、completed、failed。页面根据这个字段显示标签，并在 completed 时允许查看切片。

因此：

- 页面标签是观察结果，不是底层事实。
- 刷新页面只能重新读取 PostgreSQL。
- 改轮询间隔不能修复解析、Embedding 或 Milvus 故障。
- 必须对应检查浏览器响应、后端日志、数据库记录和向量库查询。

---

## 9. 代码审计时要留意的边界

### 9.1 注释和实现名称漂移

process_document 的注释写着存储到 ES，但实际调用的是 Milvus 服务。学习时以执行代码为准，同时记录这类维护风险。

### 9.2 元数据删除和向量删除是两个动作

删除 PostgreSQL 的 Document 记录，不必然删除已经写入 Milvus 的切片。排查删除功能时要单独核对是否调用了 Milvus 的 delete_by_doc_id。

### 9.3 用户可编辑名称参与物理集合命名

知识库名称参与 collection 命名。改名、特殊字符和历史数据迁移都需要单独考虑。

---

## 10. 排错证据顺序

~~~~text
1. 浏览器 Network：上传响应和文档列表响应
2. PostgreSQL：documents.status、chunk_count、error_message
3. 后端日志：process_document 和 DocMind 错误
4. DocMind：task_id 状态和解析结果
5. Embedding：切片数量、向量维度
6. Milvus：collection、实体数量、字段值
7. 聊天请求：检索索引、过滤参数、召回数量
8. React 状态：页面是否把响应正确渲染
~~~~

每检查一层都记录“已证实”或“未证实”，不要把“没有报错”当成“已经成功”。

---

## 11. 小练习

数据库中 Document.status=completed 且 chunk_count=12，但聊天检索结果为空。最值得优先核对哪一项？

A. 把前端 3 秒轮询改成 1 秒

B. 核对 Milvus 中的 collection 名称，以及搜索过滤使用的 kb_id 是否与写入时的值一致

C. 把 React 的 Tag 颜色改成绿色

D. 重新上传同一个文件，不检查任何日志

建议先回答选项字母，再说明为什么数据库完成不代表搜索一定有结果。

---

## 留白：我的排错记录

故障现象：

第一条已确认事实：

下一条要验证的事实：

我看到的日志或字段：

最终根因：

修复后如何验证：

---

## 源码定位

- backend/app/router/knowledge_router.py：后台任务和文档状态
- backend/app/service/docmind_service.py：解析、轮询、切片、Embedding、写入
- backend/app/service/milvus_service.py：collection、插入和向量搜索
- backend/app/models/knowledge.py：文档元数据状态
- frontend/src/api/knowledge.ts：前端状态契约
- frontend/src/pages/knowledge/index.tsx：轮询和展示

