# DeepResearch 学习手册：第 104 课

## 项目总图与第一阶段验收

前 103 课已经把项目拆成了主链、支撑链和业务链。现在先把所有链路放回一张图里。

## 1. 项目分层总图

```text
React/Vite 前端
├─ 登录、会话和聊天
├─ DeepResearch 研究详情
├─ 知识库、记忆、数据库、新闻、招投标
└─ ReadableStream/SSE 事件渲染
          ↓ HTTP / SSE
FastAPI Router
├─ auth/session/chat
├─ research V1/V2
├─ knowledge/attachments/memories/database
└─ news/bidding/search/documents
          ↓
Service 层
├─ DeepResearchV2 + 六个 Agent
├─ RAG、DocMind、Embedding、Milvus
├─ Memory、Text2SQL、CodeWizard
├─ 新闻、招投标、股票、Scheduler
└─ Checkpoint、Redis、旧兼容链
          ↓
数据和外部依赖
├─ PostgreSQL：业务记录和检查点
├─ Redis：缓存、旧会话、取消标志
├─ Milvus：向量和相似度检索
├─ DocMind：文档解析
├─ LLM/Embedding：生成和向量化
└─ Bocha/81API/股票 API：外部数据
```

## 2. 三条最重要的用户动作

### 发起深度研究

```text
React
→ POST /research/stream
→ V2 Service
→ ResearchState
→ 六个 Agent
→ asyncio.Queue
→ SSE
→ ResearchDetail
```

### 上传知识库文档

```text
React multipart upload
→ Knowledge Router
→ PostgreSQL Document=pending
→ BackgroundTasks
→ DocMind
→ chunk
→ Embedding
→ Milvus
→ Document=completed
```

### 创建长期记忆

```text
会话消息
→ 验证 ChatSession.user_id
→ LLM 摘要
→ LongTermMemory
→ Embedding
→ Milvus long_term_memories
```

## 3. 版本边界

```text
POST /research/stream 默认 v2
GET /research/stream 默认 v1
```

```text
V1 = ReActController + ToolExecutor
V2 = ResearchState + 六个 Agent
```

V2 当前默认执行：

```text
_run_simplified()
```

## 4. 必须能说清的四个状态容器

| 容器 | 保存什么 |
|---|---|
| `ResearchState` | 单次研究的后端工作状态 |
| `ResearchCheckpoint.state_json` | 可保存的后端状态快照 |
| `ResearchCheckpoint.ui_state_json` | 可恢复的前端研究展示状态 |
| `ChatMessage` | 会话历史中的消息 |

## 5. 当前实现和运行证据

已经完成的源码范围：

```text
backend/app：75 个 Python 文件
frontend/src：81 个 TS/TSX 文件
```

静态和构建检查：

```text
python -m compileall -q backend/app：通过
npm run build：通过
```

前端构建有 bundle 体积警告。Docker、PostgreSQL、Redis、Milvus、DocMind、真实 LLM 和外部 API 的完整端到端运行仍需可用环境验证。

## 6. 第一阶段验收标准

你暂时不需要背所有函数，但应该能做到：

1. 画出一次深度研究请求的前后端数据流。
2. 说出六个 Agent 的输入、输出和状态字段。
3. 解释 SSE 为什么需要浏览器缓冲区。
4. 解释 RAG 中 PostgreSQL 和 Milvus 的区别。
5. 解释页面恢复、取消和节点级恢复的区别。
6. 指出当前至少三个工程风险。
7. 区分源码确认、构建确认和真实运行确认。

## 7. 90 秒项目复述模板

> 这是一个行业信息助手，前端使用 React/Vite，后端使用 FastAPI，数据层使用 PostgreSQL、Redis 和 Milvus。DeepResearch V2 通过 ResearchState 协调规划、搜索、分析、代码执行、写作和审核六个 Agent，并通过 asyncio.Queue 和 SSE 把研究过程推送到前端。知识库文档经过 DocMind 解析、切片和 Embedding 后写入 Milvus；长期记忆把会话摘要同时保存到 PostgreSQL 和 Milvus；Text2SQL 提供结构化数据查询。当前 V2 默认走 `_run_simplified()`，CodeWizard 是进程内简化执行环境，检查点支持状态和 UI 恢复，但还不能直接称为严格的节点级断点续跑。

## 8. 第一阶段作业

请用自己的话回答：

1. 用户输入问题后，数据经过哪些主要层？
2. `ResearchState`、SSE 和 React 研究详情分别承担什么职责？
3. 文档已经显示 `completed`，为什么研究仍可能搜不到它？
4. 说出三个当前项目的工程风险，并给出一个修复方向。
