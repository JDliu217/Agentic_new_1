# DeepResearch 项目学习手册

## 第 1 课：一次研究请求是怎样跑完的

这份手册基于本地项目 `D:\课\s4-6\industry_information_assistant` 的源码阅读。飞书课程页面作为补充资料使用；如果页面正文没有被浏览器接口暴露，以本地代码的真实行为为准。

## 1. 先建立总地图

项目的后端入口是 `backend/app/app_main.py`，它创建 FastAPI 应用并注册认证、会话、知识库、附件、记忆、数据库、文档、搜索、聊天、研究和行业资讯路由。

DeepResearch V2 的主链路是：

```text
React 页面
  -> POST /research/stream
  -> research_router.stream_research
  -> DeepResearchV2Service.research
  -> DeepResearchGraph.run
  -> _run_simplified
  -> ChiefArchitect
  -> DeepScout
  -> DataAnalyst
  -> CodeWizard
  -> LeadWriter
  -> CriticMaster
  -> SSE 事件
  -> React 逐条更新研究过程和报告
```

## 2. 前端如何发起请求

`frontend/src/pages/chat/index.tsx` 的 `sendChat` 根据当前聊天类型选择接口。DeepSearch 会调用 `frontend/src/api/session.ts` 的 `deepsearch` 方法，向 `/research/stream` 发送：

```json
{
  "query": "用户的问题",
  "session_id": "当前会话 ID",
  "search_modes": ["web", "local"]
}
```

后端的 `ResearchRequest` 默认使用 `version: "v2"`。`search_modes` 会被转换成两个布尔值：

```text
web   -> search_web
local -> search_local
```

返回不是一个一次性 JSON，而是 `text/event-stream`。每条消息的形式是：

```text
data: {"type":"phase", "phase":"researching", "content":"开始深度搜索..."}

```

前端用 `ReadableStreamDefaultReader` 反复调用 `reader.read()`，按换行拆分 `data: `，再根据 `json.type` 更新界面。

## 3. `ResearchState` 是共享工作台

文件：`backend/app/service/deep_research_v2/state.py`

所有 Agent 都接收并修改同一个 `ResearchState`。它保存：

- 原始问题、会话 ID、当前阶段和迭代次数；
- 研究大纲、关键实体、研究问题和假设；
- 事实、数据点、原始来源；
- 图表、代码执行记录和洞察；
- 章节草稿、最终报告和参考文献；
- 评论家反馈、未解决问题和质量评分；
- 日志、错误和待发送的流式消息。

可以把它理解成一个研究项目的共享文件夹：Agent 之间主要通过读写这个状态交接成果，而不是直接互相调用私有方法。

## 4. V2 的六个 Agent

| Agent | 读取什么 | 写入什么 |
|---|---|---|
| `ChiefArchitect` | 用户问题、当前阶段 | `outline`、`research_questions`、`key_entities`、`hypotheses` |
| `DeepScout` | 大纲、搜索模式、研究假设 | `facts`、`data_points`、`knowledge_graph`、`insights`、`references` |
| `DataAnalyst` | 事实和数据点 | 结构化数据、知识图谱、ECharts 配置、洞察 |
| `CodeWizard` | 数据点和需要图表的章节 | Python 代码执行记录、图片 Base64 图表 |
| `LeadWriter` | 大纲、事实、数据点、图表、洞察 | 章节草稿、最终报告、引用 |
| `CriticMaster` | 报告、大纲、事实和数据点 | 质量评分、反馈、补充搜索查询、下一阶段路由 |

所有 Agent 继承 `BaseAgent`。基类使用 OpenAI 兼容客户端调用 LLM，并提供 JSON 解析、日志、消息队列推送等公共能力。

## 5. 当前真正执行的流程

`DeepResearchGraph` 同时定义了 LangGraph 图和手写异步流程。

LangGraph 的设计图是：

```text
plan -> research -> analyze -> write -> review
                                      |       |
                                    revise  complete
                                      |
                                    review
```

但 `run()` 当前明确注释掉了 `_run_with_langgraph()`，默认调用 `_run_simplified()`，原因是需要实时 SSE 输出。因此当前运行顺序是：

```text
planning
  -> researching
  -> analyzing（DataAnalyst，然后 CodeWizard）
  -> writing
  -> reviewing
  -> re_researching 或 revising
  -> completed
```

这一区别是面试重点：不能只根据设计图描述当前线上执行路径。

## 6. 代码解释器在这个项目里怎样工作

文件：`backend/app/service/deep_research_v2/agents/wizard.py`

它不是一个独立的外部产品 API。当前实现是：

```text
CodeWizard 调用 LLM
  -> LLM 返回 Python 代码
  -> 清理 Markdown 标记和转义换行
  -> compile() 做语法预检查
  -> 正则规则检查危险操作
  -> 受限 globals 中执行 exec()
  -> 捕获 stdout/stderr
  -> 捕获 matplotlib 图像
  -> Base64 写入 state['charts']
  -> 通过 chart/code_result 事件发送到前端
```

限制包括：只允许白名单模块，禁用 `open`，限制 `__import__`，禁止 `subprocess`、网络访问等明显危险模式；图表使用非交互式 `Agg` 后端保存为 PNG。

代码中明确写着这是“简化的沙箱”，生产环境应改成 Docker 容器或专门的代码执行服务。原因是 Python 进程内用正则和受限 builtins 做隔离，不能作为强安全边界。

代码失败时，`_execute_with_self_correction()` 会把错误交给 LLM，最多自动修复并重试 3 次；每次尝试会写入 `state['code_executions']`。

## 7. 搜索和本地知识库

网络搜索由 `DeepScout` 调用 Bocha Search API。搜索结果先进入 LLM 结构化分析，再形成 `facts` 和 `data_points`，而不是把搜索摘要直接当作最终答案。

本地知识库链路是：

```text
上传文件
  -> DocMind 解析
  -> 文本切片
  -> DashScope text-embedding-v4
  -> 1024 维向量
  -> Milvus collection
  -> 查询文本生成向量
  -> COSINE 相似度检索
  -> 返回文档切片
```

`PostgreSQL` 保存知识库和文档的业务元数据；`Milvus` 保存切片向量和内容。两者不能混为同一个数据库。

## 8. 检查点、取消和恢复

每个主要阶段结束时，`_run_simplified()` 会更新 UI 状态并保存检查点。`ResearchCheckpoint` 保存：

- `state_json`：后端研究状态；
- `ui_state_json`：前端步骤、搜索结果、图表和报告；
- `phase`、`iteration`、状态和错误；
- 最终报告。

前端停止研究时先取消流读取，再调用 `/research/cancel/{session_id}`。后端把取消标志写入 Redis，工作流在 Agent 执行期间周期检查并取消任务。

## 9. V1 和 V2 不要混淆

V1 的入口仍然保留在 `backend/app/service/dr_g.py`：

```text
ResearchService
  -> ReActController
  -> ToolExecutor
  -> web_search / knowledge_search / text2sql / data_analyzer / chart_generator
  -> 反思和补充搜索
  -> 最终报告
```

V1 的 ReAct 是“一个控制器选择工具”；V2 是“多个有固定职责的 Agent 顺序协作”。两者都能输出 SSE，但状态结构和事件类型不同。

## 10. 当前源码阅读发现的边界

这些不是课程推测，而是代码当前行为：

1. V2 默认配置的 `max_iterations` 是 1，审核循环通常只允许一轮。
2. `DeepScout.process()` 每次最多处理 3 个 `pending` 章节，后续章节不会自动继续搜索。
3. `DeepScout` 的 `deep_read_url()` 仍是 requests + HTML 提取，代码注释写明还没有接入真正的 Headless Browser。
4. 事实去重目前主要依赖数字和关键词指纹，源码标注后续可以接入向量语义相似度。
5. LangGraph 节点设计中的分析节点只调用 `CodeWizard`，而手写简化流程会先调用 `DataAnalyst` 再调用 `CodeWizard`。
6. 当前已验证后端 Python `compileall` 和前端 `npm run build` 均通过；前端构建只有 bundle 体积较大的性能警告。真实运行仍依赖 Docker、数据库和外部 API。
7. 项目目录本身没有 Git 元数据，因此不能通过提交历史判断哪些功能是已上线版本。

## 11. 第一课练习

请你不用看答案，尝试回答：

1. 为什么 `/research/stream` 返回 SSE，而不是等待最终 JSON？
2. `ResearchState` 为什么比让 Agent 互相直接传字符串更适合这个项目？
3. 当前默认真正执行的是 LangGraph 图，还是 `_run_simplified()`？证据是什么？
4. DataAnalyst 和 CodeWizard 都能生成图表，它们的分工有什么不同？
5. 为什么当前 CodeWizard 的“沙箱”不能当作生产级安全隔离？
6. 文档上传后，PostgreSQL 和 Milvus 各自保存什么？
7. V1 的 ReActController 和 V2 的六个 Agent，架构差异是什么？

下一课会从 `ResearchState` 的字段逐个拆解，再用一个具体问题模拟它在每个阶段怎样变化。
