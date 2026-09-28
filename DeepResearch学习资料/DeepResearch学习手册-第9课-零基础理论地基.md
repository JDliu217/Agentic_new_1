# DeepResearch 学习手册：第 9 课

## 零基础理论地基

这节课专门解释项目中反复出现的概念。阅读代码前先把这些概念分清，后面看到 `async`、`StreamingResponse`、`Milvus` 或 `ResearchState` 时，才知道它们解决的工程问题是什么。

---

## 1. 程序是怎样协作的

这个项目不是一个 Python 文件单独完成工作，而是多个程序通过网络协作：

```text
浏览器中的 React
        ↕ HTTP / SSE
FastAPI 后端
        ↕
PostgreSQL / Redis / Milvus
        ↕
LLM / 搜索 / Embedding / DocMind
```

可以把每一层理解为一个有明确职责的部门：

- React 负责把信息展示给用户、收集输入。
- FastAPI 负责接收请求、组织业务流程。
- 数据库负责保存数据。
- LLM 负责理解和生成文本或代码。
- 搜索和向量库负责提供证据。
- Agent 负责按照任务职责调用这些能力。

学习工程项目时，先问“谁调用谁、传了什么数据、返回到哪里”，再问“这段代码具体怎么写”。

---

## 2. HTTP：浏览器和后端的普通对话

一次普通 HTTP 请求包含：

```text
请求方法 + URL + 请求头 + 请求体
                         ↓
                    后端处理
                         ↓
响应状态码 + 响应头 + 响应体
```

本项目常见方法：

| 方法 | 常见用途 | 项目例子 |
|---|---|---|
| GET | 获取资源 | 获取会话、记忆、文档列表 |
| POST | 创建或执行操作 | 登录、上传文档、开始研究 |
| PUT | 修改资源 | 修改会话标题、知识库描述 |
| DELETE | 删除资源 | 删除会话、文档或记忆 |

常见状态码：

- `200`：请求成功。
- `201`：创建成功。
- `204`：成功但没有响应体。
- `401`：没有有效身份认证。
- `403`：身份存在但没有权限。
- `404`：资源不存在。
- `422`：请求数据不符合后端 Schema。
- `500`：后端执行过程中发生异常。

在本项目中，前端 API 文件负责组织请求，FastAPI Router 负责接收请求，Pydantic Schema 负责验证请求体。

---

## 3. JSON：程序之间约定的数据格式

JSON 只是结构化数据的文本表示：

```json
{
  "query": "研究问题",
  "session_id": "会话 ID",
  "search_modes": ["web", "local"]
}
```

前后端必须对字段名称和类型达成一致。例如后端等待 `query`，前端却发送 `question`，请求就可能在业务逻辑前失败。

本项目的 Schema 位于：

```text
backend/app/schemas/
backend/app/router/research_router.py 中的 ResearchRequest
frontend/src/api/*.ts
```

阅读一个接口时，至少同时看三处：前端请求类型、后端请求模型、后端返回对象。

---

## 4. 同步、异步和等待

### 4.1 同步

同步代码像排队办事：当前任务没有完成，后面的代码不能继续。

```python
result = call_model()
print(result)
```

### 4.2 异步

异步代码允许程序在等待网络、数据库或模型响应时处理其他工作：

```python
result = await call_model()
```

`await` 不是让模型变快，而是告诉事件循环：这里正在等待，可以把执行机会让给其他任务。

### 4.3 本项目为什么需要异步

一次研究会反复等待：

- LLM 返回。
- 搜索 API 返回。
- Embedding API 返回。
- 数据库或 Redis 返回。
- Agent 把消息放入队列。

所以研究服务、Agent `process()`、FastAPI 流式接口都使用异步形式。

相关文件：

```text
backend/app/service/deep_research_v2/graph.py
backend/app/service/deep_research_v2/agents/*.py
backend/app/router/research_router.py
```

---

## 5. SSE：后端连续推送消息

普通 JSON 响应是：

```text
请求 → 等待全部工作 → 返回一个结果
```

SSE 是：

```text
请求 → 事件 1 → 事件 2 → 事件 3 → ... → 完成
```

项目中的事件大致包括：

```text
research_start
research_step
search_results
knowledge_graph
chart / code_result
research_complete
research_cancelled
```

SSE 适合“服务器持续产生、浏览器持续接收”的场景，例如研究进度、日志、报告增量。它与 WebSocket 不同：本项目主要是服务器向浏览器单向推送，停止研究另走取消接口。

后端使用 `StreamingResponse`，前端使用 `ReadableStream` 和 `reader.read()`。

---

## 6. 数据库：保存结构化业务数据

关系型数据库把数据放在表中，用主键和外键表达关系。

本项目中的关系大致是：

```text
User
 ├─ ChatSession
 │   ├─ ChatMessage
 │   └─ ChatAttachment
 ├─ KnowledgeBase
 │   └─ Document
 ├─ LongTermMemory
 └─ ResearchCheckpoint
```

例如一个会话属于一个用户，一条消息属于一个会话，一个知识库包含多份文档。

SQLAlchemy 模型位于 `backend/app/models/`，数据库连接位于 `backend/app/core/database.py`。

关系数据库适合保存：

- 用户和身份信息。
- 会话、消息和附件状态。
- 知识库和文档元数据。
- 研究检查点。
- 行业统计、公司和政策数据。

---

## 7. Redis：快速、短期的状态

Redis 是内存型键值存储，适合保存需要快速读写的数据。

本项目用它处理：

- 缓存。
- 短期状态。
- 研究取消标志。

用户点击停止时，后端写入类似 `research:cancel:<session_id>` 的键。研究流程执行前和执行期间读取它。

Redis 中的取消标志和 PostgreSQL 中的检查点不是一回事：

```text
Redis：现在是否应该尽快停止
PostgreSQL：研究已经走到哪里，之后如何恢复
```

---

## 8. Embedding 和向量检索

### 8.1 Embedding 是什么

Embedding 模型把文本转换成一串数字：

```text
“新能源汽车销量增长” → [0.12, -0.04, 0.87, ...]
```

含义相近的文本，通常在向量空间中距离更近。

### 8.2 RAG 的基本流程

```text
文档
  → 切片
  → 每个切片生成向量
  → 保存到 Milvus

用户问题
  → 生成问题向量
  → 在 Milvus 查相似切片
  → 把切片交给 LLM 或 Agent
```

这个项目中，PostgreSQL 保存文档元数据，Milvus 保存向量检索所需的数据。检索结果是证据候选，不能自动等于事实；后续 Agent 仍需要整理、判断来源和引用。

相关文件：

```text
backend/app/service/embedding_service.py
backend/app/service/milvus_service.py
backend/app/service/retrieval_service.py
backend/app/service/docmind_service.py
```

---

## 9. LLM、工具和 Agent 的区别

### 9.1 LLM

LLM 主要做理解和生成：根据输入文本生成文本、JSON、SQL 或 Python 代码。

### 9.2 工具

工具是可以实际执行外部动作的程序，例如：

- 调用搜索 API。
- 查询 PostgreSQL。
- 查询 Milvus。
- 生成图表。
- 获取网页内容。

### 9.3 Agent

Agent 是“模型 + 提示词 + 状态读写 + 工具调用 + 错误处理”的工作单元。

在这个项目中，`DeepScout` 不是搜索引擎本身，而是决定如何搜索、如何整理结果并把事实写入状态的 Agent。

`CodeWizard` 也不是 Python 解释器本身，而是由 LLM 生成代码，再交给受限执行器运行的 Agent。

---

## 10. 状态机：研究流程为什么能分阶段

状态机由两部分构成：

```text
状态：当前处于 planning / researching / analyzing ...
转换：什么条件下进入下一个状态
```

本项目的主要阶段：

```text
INIT
  → PLANNING
  → RESEARCHING
  → ANALYZING
  → WRITING
  → REVIEWING
  → COMPLETED
```

审核不通过时可能转到：

```text
RE_RESEARCHING 或 REVISING
```

状态机的好处是：

- 能知道任务进行到哪里。
- 能决定下一步调用谁。
- 能保存检查点。
- 能让前端展示进度。
- 能在取消或失败后恢复或排错。

---

## 11. 你必须建立的四个区分

### 区分一：模型和工具

模型可以生成“搜索代码”或“SQL”，但它不会自动拥有真实网络或数据库访问权。工具才负责执行外部动作。

### 区分二：状态和事件

状态保存工作成果，事件通知用户当前发生的变化。事件丢了，可能仍有检查点；状态没保存，页面再收到事件也无法恢复。

### 区分三：设计图和执行代码

LangGraph 图描述一种流程设计；`_run_simplified()` 是当前 `run()` 真正调用的执行路径。

### 区分四：元数据和向量

PostgreSQL 保存“这份文档是谁上传、叫什么、什么状态”；Milvus 保存“文本切片在向量空间中的表示”。

---

## 12. 零基础学习顺序

建议按以下顺序掌握，不要跳到 Agent Prompt：

1. 先理解浏览器、HTTP、JSON 和状态码。
2. 再理解 Python 函数、类、异常、异步和生成器。
3. 再理解 SQL、表、主键、外键和事务。
4. 再理解前端状态、组件和请求流。
5. 再理解 LLM、Embedding、RAG 和工具调用。
6. 最后理解 Agent 编排、状态机、SSE 和检查点。

项目的学习顺序可以不同于理论的学习顺序，但每次遇到陌生名词，都要把它放回上述六层中的一层。

---

## 13. 本课练习

### 练习 A：画层次图

把以下对象放到“界面、接口、业务、智能能力、数据基础设施”五层：

```text
React
FastAPI Router
DeepResearchGraph
DeepScout
PostgreSQL
Milvus
LLM
SSE
```

### 练习 B：解释一次失败

假设页面显示“请求失败”，但后端没有收到请求。优先检查哪一层？

假设后端已经输出 `research_complete`，但页面没有最终报告。优先检查哪一层？

### 练习 C：用一句话解释

请分别用一句自己的话解释：

- SSE
- ResearchState
- Embedding
- Agent
- checkpoint

如果一句话中出现“就是一个很智能的东西”之类的模糊描述，说明概念还没有落到工程职责上。

