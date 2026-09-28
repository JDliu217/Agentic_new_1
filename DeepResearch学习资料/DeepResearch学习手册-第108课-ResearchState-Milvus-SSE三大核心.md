# DeepResearch 学习手册·第 108 课：ResearchState、Milvus 与 SSE

## 0. 为什么先学这三个东西

一次 DeepResearch 请求同时需要：

- 记住规划、搜索、分析和写作产生的中间结果；
- 根据用户问题找回知识库中的相关片段；
- 在任务尚未结束时，把阶段进度推给浏览器。

在本项目中，这三个问题分别由 `ResearchState`、Milvus 和 SSE 解决。它们不是三个互相独立的名词，而是同一条请求链上的三个位置：

```text
ResearchState：后端工作台，保存研究过程
Milvus：知识库索引，保存并查找向量化文本
SSE：实时传输通道，把后端事件送到前端
```

## 1. ResearchState：所有 Agent 共用的工作台

### 1.1 用生活例子理解

把一次研究想成一个小组共同写报告。`ResearchState` 就是放在桌上的项目文件夹：

- ChiefArchitect 把目录和子问题放进去；
- DeepScout 把事实、网页来源和数据点放进去；
- DataAnalyst 把洞察和结构化图表放进去；
- CodeWizard 把代码执行记录和图片放进去；
- LeadWriter 把章节草稿和最终报告放进去；
- CriticMaster 把评分、问题和补充搜索要求放进去。

Agent 不是通过互相直接调用来传递全部结果，而是依次读取和更新同一个状态对象。

### 1.2 源码证据

文件：`backend/app/service/deep_research_v2/state.py:108-158`

关键字段可以分成五组：

```text
身份与控制：query, session_id, phase, iteration, max_iterations
规划：outline, research_questions, hypotheses, key_entities
证据：facts, data_points, raw_sources
分析与写作：charts, code_executions, insights, draft_sections, final_report
审核与控制：critic_feedback, unresolved_issues, quality_score, pending_search_queries
```

`create_initial_state()` 在 `state.py:161-205` 创建空状态。空列表不是错误，它表示这一步还没有产物：例如刚开始时 `facts=[]`、`charts=[]`、`final_report=""`。

### 1.3 运行时如何演化

假设问题是“新能源汽车行业未来三年的竞争格局”：

```text
初始：outline=[], facts=[], final_report=""
规划后：outline 有章节，research_questions 有待研究问题
搜索后：facts/raw_sources/data_points 增长
分析后：insights/charts/code_executions 增长
写作后：draft_sections 和 final_report 有值
审核后：quality_score、critic_feedback、pending_search_queries 更新
```

当前 V2 服务在 `backend/app/service/deep_research_v2/graph.py:316-356` 中先恢复检查点或创建初始状态，然后始终调用 `_run_simplified()`。因此要记住：`ResearchState` 是真实运行时的共享状态；LangGraph 图是代码中的另一条设计路径，但不是当前默认执行器。

### 1.4 常见误解

`ResearchState` 不是数据库。研究运行期间它主要是 Python 内存对象；检查点服务才把它序列化到 PostgreSQL 的 `state_json`。所以：

```text
内存中的 state：当前任务正在使用
数据库中的 state_json：用于检查点、恢复和审计
```

## 2. Milvus：把“文字相似”变成“向量相似”

### 2.1 先理解向量

计算机不容易直接判断两段文字的语义是否相近。Embedding 模型会把一段文字转换成一串数字，例如：

```text
“新能源车电池成本下降” -> [0.12, -0.04, ...]  共 1024 个数
```

语义相近的文字通常在向量空间中距离更近。Milvus 负责保存这些向量，并快速找到与查询向量最相近的若干文本切片。它不是大模型，也不是关系数据库；它是向量检索服务。

### 2.2 源码证据

文件：`backend/app/service/milvus_service.py`

- `20-37`：从 `MILVUS_HOST` 和 `MILVUS_PORT` 连接服务。
- `39-82`：创建集合、字段和向量索引。
- `57-65`：集合保存 `id`、`doc_id`、`kb_id`、文件名、文本、切片序号和 `vector`。
- `70-76`：使用 `COSINE` 相似度和 `IVF_FLAT` 索引。
- `84-123`：批量插入文档切片和向量。
- `125-183`：把查询向量送入集合，返回内容和相似度分数。

这里的 `vector_dim=1024` 必须和实际 Embedding 模型输出维度一致。维度不一致时，插入或搜索会失败。

### 2.3 从上传到召回

```text
上传文件
  -> PostgreSQL Document=pending
  -> DocMind 读取文本
  -> 文本切片
  -> Embedding 模型生成 1024 维向量
  -> Milvus insert
  -> Document=completed

用户提问
  -> 查询文本生成向量
  -> Milvus search(top_k, kb_id)
  -> 返回相似切片
  -> DeepScout 把切片作为证据继续研究
```

### 2.4 本项目必须记住的真实风险

`MilvusService.search()` 会检查集合是否存在，并可按 `kb_id` 过滤。但项目不同链路中存在集合命名差异：上传链路可能写入 `kb_<知识库名称>`，DeepScout 某条路径可能查询固定集合 `knowledge_base`。因此出现“文档状态 completed，但搜索没有结果”时，不能只看 PostgreSQL 状态，还要检查：

1. 实际写入的集合名；
2. 实际查询的集合名；
3. `kb_id` 是否一致；
4. 向量维度和集合是否已 load。

## 3. SSE：让浏览器边接收边显示

### 3.1 为什么不用普通 JSON

普通 JSON 通常在函数全部完成后一次性返回。研究要经历搜索、分析、写作，可能需要很久。SSE 允许服务器保持 HTTP 连接，连续发送多条事件：

```text
data: {"type":"research_start",...}\n\n
data: {"type":"research_step",...}\n\n
data: {"type":"search_results",...}\n\n
data: {"type":"report_draft",...}\n\n
```

这仍然是服务器到浏览器的单向通道，不是双向聊天协议。取消研究时，前端另外调用 `/research/cancel/{session_id}`。

### 3.2 后端事件从哪里来

`backend/app/service/deep_research_v2/agents/base.py:237-262` 的 `add_message()` 先创建统一事件对象：

```python
{
    "type": event_type,
    "agent": self.name,
    "timestamp": ...,
    "content": content,
}
```

事件会同时写入 `state["messages"]`，并在存在 `_message_queue` 时调用 `put_nowait()`。`graph.py:380-457` 的 `_run_simplified()` 创建 `asyncio.Queue`，执行 Agent 的同时不断读取队列，再把事件 yield 给上层。

`research_router.py:80-150` 用 `StreamingResponse` 返回流，响应媒体类型是 `text/event-stream`。上层服务给出的每个事件最终被包装成 SSE 数据块。

### 3.3 前端如何还原事件

文件：`frontend/src/pages/chat/index.tsx:270-308`

前端通过 `reader.read()` 读取字节流，用 `TextDecoder` 转成文本，再把数据暂存到 `temp`。因为一次网络读取可能只拿到半条消息，所以必须先缓冲，直到找到换行符，再解析 `data: ` 后面的 JSON。

研究事件随后在 `index.tsx:322` 之后按 `json.type` 分支：

- `research_start`：初始化研究面板；
- `research_step`：创建或更新步骤；
- `search_results`：更新搜索结果；
- 图表和报告事件：更新详情与报告展示。

### 3.4 最容易出现的前端 bug

如果后端已经有 `final_report`，但前端页面没有显示，问题不一定在大模型。应按顺序检查：

```text
Agent 是否写入 state.final_report
  -> 是否生成 report_draft/research_complete 事件
  -> SSE 是否按完整行解析
  -> 前端是否按正确 type 分支
  -> React state/ref 是否触发重新渲染
  -> 报告组件是否读取正确字段
```

## 4. 三者放在一起

```text
用户问题
  -> create_initial_state() 得到 ResearchState
  -> DeepScout 用问题向量查询 Milvus，写回 facts/raw_sources
  -> Agent.add_message() 把进度写入 state.messages 和 asyncio.Queue
  -> Graph 读取 Queue，StreamingResponse 发 SSE
  -> React 解析 SSE，更新研究步骤和详情
  -> 其他 Agent 继续读写同一个 ResearchState
```

一句话背诵：

> `ResearchState` 保存“研究做到哪了”，Milvus 负责“从知识库找什么”，SSE 负责“把做到哪了告诉浏览器”。

## 5. 课后练习

请用自己的话回答，不要只抄上面的定义。

### 练习 A：三段式

对 `ResearchState`、Milvus、SSE 各写三行：

```text
概念：
源码：
运行：
```

### 练习 B：字段追踪

研究刚完成搜索但还没有写作时，判断以下字段哪些应该已经有值，哪些可能仍为空，并说明原因：

```text
outline
facts
raw_sources
data_points
charts
draft_sections
final_report
```

### 练习 C：故障定位

已知 PostgreSQL 中某文档是 `completed`，但 DeepScout 返回 0 条结果。请按证据顺序写出至少四个检查点。

### 练习 D：SSE 分块

如果浏览器第一次 `reader.read()` 得到：

```text
data: {"type":"research_sta
```

第二次得到：

```text
rt"}\n\n
```

为什么不能在第一次读取后直接 `JSON.parse()`？前端应如何处理？

