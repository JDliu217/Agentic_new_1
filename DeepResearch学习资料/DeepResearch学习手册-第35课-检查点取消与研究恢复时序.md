# DeepResearch 学习手册·第 35 课

## 检查点、取消与研究恢复时序

这一课解决一个工程问题：研究请求运行很久时，用户刷新页面、点击取消或重新打开会话，项目到底保存和恢复了什么？

源码依据：

    D:\课\s4-6\industry_information_assistant\backend\app\router\research_router.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\checkpoint_service.py
    D:\课\s4-6\industry_information_assistant\backend\app\models\research.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\graph.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\service.py
    D:\课\s4-6\industry_information_assistant\frontend\src\api\session.ts
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\chat\index.tsx

---

## 1. 先分清三类数据

一次研究同时有三种不同的数据：

```text
ResearchState
  → 后端继续研究需要的事实、章节、图表、引用和阶段

ui_state_json
  → 前端右侧研究步骤、搜索结果、图谱、图表和流式报告

ChatSession / ChatMessage
  → 普通会话历史中保存的用户消息和最终助手消息
```

它们不是同一个对象，也不是同一张表。只恢复聊天消息，不能重建右侧研究面板；只恢复检查点，也不能假定普通会话历史已经写入最终助手消息。

---

## 2. PostgreSQL 检查点表保存什么

`ResearchCheckpoint` 的关键字段：

| 字段 | 作用 |
|---|---|
| `session_id` | 关联研究会话 |
| `user_id` | 可选的用户归属 |
| `query` | 原始研究问题 |
| `phase` | 当前阶段，如 planning、researching、writing |
| `iteration` | 审核/修订轮次 |
| `state_json` | 完整后端 `ResearchState` |
| `ui_state_json` | 前端研究 UI 状态 |
| `final_report` | 最终报告文本 |
| `status` | running、paused、completed、failed |
| `error_message` | 失败原因 |

当前保存策略是同一个 `session_id` 更新同一条检查点记录，而不是每个阶段插入一条历史快照。`updated_at` 记录最近保存时间。

---

## 3. 阶段结束时怎样保存

V2 手写流程在规划、搜索、分析和写作阶段结束后调用 `save_checkpoint_async()`：

```text
Agent 执行
  → state 发生变化
  → update_ui_state()
  → 合并当前研究步骤
  → CheckpointService.save_checkpoint()
  → 发出 checkpoint_saved 事件
```

`update_ui_state()` 会把后端状态转换成面向前端的结构：

- `state.charts` → `ui_state_json.charts`
- `state.final_report` → `ui_state_json.streaming_report`
- `state.knowledge_graph` → `ui_state_json.knowledge_graph`
- `state.facts` → `ui_state_json.search_results`
- `state.references` → `ui_state_json.references`

保存前还会把不可序列化的字段清理成可存 JSON 的结构。这样数据库不需要保存 Python 对象或异步队列。

---

## 4. 检查点接口的职责

| 接口 | 返回内容 | 用途 |
|---|---|---|
| `GET /research/checkpoint/{session_id}` | 元信息，不含完整状态 | 查看阶段和状态 |
| `GET /research/checkpoint/{session_id}/full` | 后端状态、UI 状态和报告 | 页面恢复 |
| `GET /research/checkpoints` | 检查点列表 | 管理或排查 |
| `DELETE /research/checkpoint/{session_id}` | 删除结果 | 清理研究记录 |
| `POST /research/resume/{session_id}` | SSE 流 | 尝试恢复研究 |

前端打开聊天会话时调用 `/full`，因为它需要同时恢复右侧步骤和最终报告。后端恢复执行时则只通过 `load_checkpoint()` 取 `state_json`。

---

## 5. 页面刷新时前端怎样恢复

`chat/index.tsx` 的恢复逻辑大致是：

1. 先加载 `/sessions/{id}` 的会话消息。
2. 再加载 `/research/checkpoint/{id}/full`。
3. 只有检查点状态是 `completed` 或 `running` 时才恢复研究 UI。
4. 根据 `ui_state_json.research_steps` 重建步骤数组。
5. 把搜索结果放到 searching/researching 详情。
6. 把知识图谱放到 analyzing 或 research 详情。
7. 把图表放到 analyzing 详情。
8. 把流式报告或最终报告放到 writing 详情。
9. 如果聊天列表为空，根据检查点构造用户消息和助手消息。
10. 如果聊天消息已经存在，则给最后一条助手消息补上图表并标记为 Deepsearch。

这解释了为什么恢复逻辑里既有 `chat.list`，又有 `researchDetailsRef`、`researchStepsRef` 和 `researchDataVersion`：它们分别负责聊天消息、步骤引用、步骤快照和强制触发详情组件更新。

---

## 6. 取消请求怎样工作

前端调用：

```text
POST /research/cancel/{session_id}
```

后端把以下对象写入 Redis，过期时间 300 秒：

```text
research:cancel:<session_id> → {"cancelled": true}
```

V2 图流程在主要阶段开始前和审核循环中调用 `is_research_cancelled()`。如果读到标志，就发出：

```json
{"type": "research_cancelled", "message": "研究已取消"}
```

并从当前生成器返回。研究开始时可以调用 `clear_cancel_flag()` 清掉旧标志，避免上一次取消影响新请求。

这里的取消是协作式取消：它不会强制杀掉正在进行的 HTTP、LLM 或外部搜索调用，而是在代码检查点生效。

---

## 7. `resume` 当前到底恢复到哪里

恢复接口会：

1. 查询检查点元信息。
2. 如果不存在则返回 400。
3. 如果状态是 `completed` 则拒绝恢复。
4. 创建 V2 服务。
5. 传入 `resume=True` 和同一个 `session_id`。

`DeepResearchGraph.run()` 在 `resume=True` 时会先加载 `state_json`，并发出 `research_resumed` 事件。随后当前实现仍然进入 `_run_simplified(state)`。

要特别注意：`_run_simplified()` 的手写流程从规划阶段代码开始执行，并没有按照已保存的 `phase` 精确跳转到某个 Agent。也就是说，源码能证明“保存了状态并重新载入”，但不能把当前实现描述成“从中断的具体节点无重复地继续”。它更接近“带有旧状态的再次执行”。

这是当前项目的重要实现边界，后续如果要实现真正的断点续跑，需要保存可恢复的节点位置，并根据阶段选择入口，同时处理重复搜索、重复写作和幂等更新。

---

## 8. 状态更新中的两个细节

### 8.1 保存检查点会把状态设为 running

`CheckpointService.save_checkpoint()` 更新已有记录时会把 `status` 设回 `running`。研究最终完成后，图流程再调用 `update_status(session_id, "completed")`。

因此应区分：

- 阶段检查点写入成功。
- 整个研究最终完成。

### 8.2 取消返回不等于检查点变成 paused

当前图流程发现取消后直接 yield `research_cancelled` 并返回；从所读代码看，没有在这个分支自动调用 `update_status(session_id, "paused")`。如果取消发生在两个阶段保存之间，数据库中的检查点可能仍然是 `running`。

这也是为什么不能只根据前端看到的取消事件推断数据库状态已经正确更新。

---

## 9. 与聊天消息持久化的区别

普通会话消息使用 `/sessions/{id}/messages`。聊天页面通常在 SSE 读取完成后，才把最终用户消息和助手消息写入会话。

因此可能出现：

```text
检查点已经保存了研究状态
但浏览器在流结束前关闭
会话消息还没有写入
```

页面恢复时，代码会优先读取已有会话消息；如果没有消息，就用检查点里的 `query`、`final_report`、`references` 和图表构造一个临时前端消息。

---

## 10. 真实限制和验证边界

源码可以确认：

- 检查点表结构和保存字段。
- 阶段保存位置。
- Redis 取消标志的 key 和 TTL。
- 前端恢复字段映射。
- resume 的当前入口行为。

当前不能仅靠静态阅读确认：

- PostgreSQL 中是否已经存在真实检查点记录。
- Redis 取消标志在当前机器上是否能被真实读写。
- 浏览器刷新后是否在所有事件顺序下都能正确恢复。
- 外部服务中断时检查点是否总能成功提交。

这些需要 PostgreSQL、Redis、后端和前端都启动后，用真实请求验证。

---

## 11. 最小练习

### 练习 A：字段归类

把下面字段放入正确位置：

```text
facts、charts、research_steps、final_report、messages、phase、references
```

要求分别说明它们属于 `state_json`、`ui_state_json` 或会话消息中的哪一类，以及为什么。

### 练习 B：刷新恢复

回答：

1. 为什么页面恢复需要 `/sessions/{id}` 和 `/research/checkpoint/{id}/full` 两个请求？
2. 如果 `ui_state_json.charts` 有数据但会话消息为空，图表最终放在哪里？
3. 如果检查点 status 是 `failed`，当前前端恢复逻辑会不会自动恢复？

### 练习 C：恢复设计

设计真正的断点续跑至少需要记录：

1. 当前阶段或节点名。
2. 已完成的章节、搜索查询和来源 ID。
3. Agent 输出是否已经写入，避免重复追加。
4. 重试和取消后的状态转换。
5. 恢复接口的幂等策略。

---

## 12. 留给你的笔记区

### 三类数据的区别



### 页面刷新时序图



### 我认为 resume 需要怎样改



