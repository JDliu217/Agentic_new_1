# DeepResearch 第 1 课答题证据索引

这份文件只用于批改第一轮作业。先自己回答，再用这里的证据核对，不要直接把证据当成答案背诵。

## 1. 为什么使用 SSE

核心证据：

- `backend/app/router/research_router.py:80-125`：POST `/research/stream` 返回 `StreamingResponse`，媒体类型是 `text/event-stream`。
- `backend/app/service/deep_research_v2/graph.py:380-447`：`_run_simplified()` 使用 `asyncio.Queue`，Agent 执行期间持续取消息并 yield。
- `frontend/src/pages/chat/index.tsx:270-308`：前端循环调用 `reader.read()`，按换行拆分 `data:` 并解析 JSON。

完整回答必须同时提到：研究过程耗时较长、需要展示中间进度、后端逐步产生事件、前端可以边收边渲染。

## 2. `ResearchState` 的作用

核心证据：

- `backend/app/service/deep_research_v2/state.py:108-158`：`ResearchState` 是 `TypedDict`，包含请求、阶段、规划、事实、数据点、图表、报告、审核和消息字段。
- `backend/app/service/deep_research_v2/state.py:161-205`：`create_initial_state()` 创建完整初始状态。
- `backend/app/service/deep_research_v2/graph.py:403-414`：同一个 `state` 被传给 Agent 的 `process(state)`。

完整回答必须说明：它是共享状态/交接协议，不只是变量容器；Agent 通过读写结构化字段交接成果，消息队列则负责流式输出。

## 3. 当前执行分支

核心证据：

- `backend/app/service/deep_research_v2/graph.py:349-356`：代码注释写明始终使用手写版本，并实际 `async for event in self._run_simplified(state)`。
- `backend/app/service/deep_research_v2/graph.py:358-378`：`_run_with_langgraph()` 存在，但属于另一条可调用分支。

正确结论：设计上有 LangGraph，当前 `run()` 默认走 `_run_simplified()`；理由是简化流程用队列支持实时 SSE。

## 4. DataAnalyst 与 CodeWizard 的分工

核心证据：

- `backend/app/service/deep_research_v2/agents/data_analyst.py:4-11`、`256-317`：从事实提取结构化数据、构建知识图谱、生成 ECharts 配置、写入 `data_points`/`insights`/`charts`，发送图谱和图表事件。
- `backend/app/service/deep_research_v2/agents/wizard.py:28-35`、`1014-1066`、`1088-1242`：生成/检查/执行 Python，捕获 stdout、stderr 和图像。

正确区分：DataAnalyst 负责语义结构化和图表配置；CodeWizard 负责需要实际计算或绘图代码执行的分析。

## 5. 为什么 CodeWizard 不是生产沙箱

核心证据：

- `wizard.py:321-338`：危险模式正则和 `compile()` 检查。
- `wizard.py:1088-1132`：在当前 Python 进程中构造受限执行环境。
- `wizard.py:1236-1242`：最终仍调用 `exec(code, exec_globals)`。

完整回答应指出：正则可能漏检，进程内限制不是操作系统级隔离，资源、网络、文件系统和逃逸风险没有被强边界控制；生产环境应使用独立容器或专用沙箱。

## 6. PostgreSQL 与 Milvus 保存什么

核心证据：

- `backend/app/router/knowledge_router.py:289-375`：上传先创建 PostgreSQL `Document` 记录并返回 `pending`，再通过后台任务处理。
- `backend/app/service/embedding_service.py:4-9`：Embedding 服务生成向量。
- `backend/app/service/milvus_service.py`：负责集合、插入和相似度检索。
- `backend/app/models/knowledge.py`：`KnowledgeBase`/`Document` 保存用户归属、文件信息、处理状态和 `chunk_count` 等元数据。

正确回答：PostgreSQL 管业务元数据和状态；Milvus 管切片向量及用于召回的内容。两者需要通过文档/集合命名和处理流程关联。

## 7. V1 与 V2 的差异

核心证据：

- `backend/app/service/react_controller.py:191-193`：V1 是 `ReActController`。
- `backend/app/service/react_controller.py:737-862`：V1 按 Plan → Execute → Reflect → Synthesize 循环，并通过工具执行器行动。
- `backend/app/service/tool_executor.py:64-106`：V1 用工具名映射到执行函数。
- `backend/app/service/deep_research_v2/graph.py:349-356` 与六个 `agents/*.py`：V2 按固定阶段调用职责明确的 Agent，共享 `ResearchState`。

正确回答：V1 的核心抽象是控制器根据思考选择工具；V2 的核心抽象是多个专业 Agent 按阶段协作并写回共享状态。两者都可能使用 SSE，但事件和状态契约不同。

