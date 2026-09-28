# DeepResearch 学习手册：第 76 课

## 检查点、取消与恢复的真实边界

研究任务可能运行较长时间，因此项目同时设计了三种能力：

```text
检查点：保存已经完成的研究状态
取消：让正在运行的任务尽快停止
恢复：重新读取保存的状态并继续发起流程
```

它们相互关联，但不是同一件事。

## 1. 三类数据不要混淆

一次研究涉及三类数据：

| 数据 | 保存内容 | 主要用途 |
|---|---|---|
| `ResearchState` | Agent 中间结果、阶段、事实、图表和报告 | 后端继续处理 |
| `ui_state_json` | 研究步骤、搜索结果、图谱、图表和流式报告 | 页面刷新后恢复展示 |
| `ChatMessage` | 用户问题和助手消息 | 普通会话历史 |

如果只保存聊天消息，无法完整恢复右侧研究面板；如果只保存 UI 状态，后端也没有完整研究数据可继续处理。

## 2. 检查点写在哪里

模型：

```text
backend/app/models/research.py::ResearchCheckpoint
```

关键字段：

```text
session_id
user_id
query
phase
iteration
state_json
ui_state_json
final_report
status
error_message
```

`state_json` 保存后端的 `ResearchState`；`ui_state_json` 保存前端需要的展示结构；`final_report` 单独保存最终报告文本，便于快速读取。

## 3. 什么时候保存检查点

当前 `_run_simplified()` 在主要阶段之后调用 `save_checkpoint_async()`：

```text
规划完成
→ 保存
搜索完成
→ 保存
分析完成
→ 保存
写作完成
→ 保存
```

保存过程是：

```text
Agent 修改 state
→ update_ui_state()
→ 合并当前 research_steps
→ CheckpointService.save_checkpoint()
→ 发送 checkpoint_saved 事件
```

检查点服务会清理不能直接写入 JSONB 的对象，例如内部队列和其他运行时对象。

## 4. 为什么要有两个 JSON

后端状态和前端状态的字段结构不同。

### 后端 `state_json`

它更关注：

```text
outline
facts
data_points
charts
draft_sections
final_report
references
phase
iteration
```

### 前端 `ui_state_json`

它更关注：

```text
research_steps
search_results
charts
knowledge_graph
streaming_report
references
```

页面恢复时，前端需要的是“应该显示什么”；后端继续研究时，需要的是“已经完成了什么”。两者相关，但不应强行使用同一个结构。

## 5. 用户点击停止时发生什么

前端 `handleStop` 大致执行：

```text
reader.cancel()
→ 停止浏览器继续读取当前 SSE
→ POST /research/cancel/{session_id}
→ 页面立即关闭 loading
```

`reader.cancel()` 只影响浏览器读取流，不能单独证明服务器端 Agent 已经停止。

## 6. 后端怎样响应取消

取消接口把标志写入 Redis：

```text
research:cancel:<session_id>
→ {"cancelled": true}
→ TTL 300 秒
```

Graph 在这些时机检查：

```text
启动 Agent 前
Agent 执行期间等待消息时
主要阶段切换前
审核和补充搜索循环中
```

发现取消后，当前实现可能：

```text
task.cancel()
→ 等待 CancelledError
→ 返回 research_cancelled 事件
→ 结束当前生成器
```

这是协作式取消，不是操作系统级强制杀进程。正在执行的外部 HTTP、LLM 或同步计算不一定能在标志写入后立刻停止。

## 7. 页面停止不等于后端完成停止

可能出现这样的时序：

```text
用户点击停止
→ 浏览器停止读取
→ Redis 标志写入成功
→ 后端当前外部调用仍未返回
→ Graph 下一次检查时才发现取消
```

因此排错需要同时观察：

```text
浏览器 reader 是否取消
取消接口是否返回成功
Redis 是否有对应 key
Graph 是否读到 key
Agent 是否仍在调用外部服务
检查点最终 status 是什么
```

## 8. 页面刷新怎样恢复展示

聊天页通常分别加载：

```text
/sessions/{session_id}
/research/checkpoint/{session_id}/full
```

第一条恢复聊天消息；第二条恢复研究 UI。

前端会从 `ui_state_json` 重建：

```text
researchSteps
searching/researching detail
analyzing detail 中的图表和图谱
writing detail 中的报告
```

如果会话消息为空，前端还会根据检查点的 query、final_report、references 和 charts 构造临时聊天消息。

因此：

```text
页面能恢复，不代表会话消息一定已经持久化
```

## 9. `resume=True` 当前到底做了什么

恢复接口：

```text
POST /research/resume/{session_id}
```

它会查询检查点，然后调用 V2 服务的 `research(..., resume=True)`。

`DeepResearchGraph.run()` 在 `resume=True` 时先执行：

```text
load_checkpoint(session_id)
→ 读取 state_json
→ 发送 research_resumed
```

随后当前实现仍然调用：

```text
_run_simplified(state)
```

而 `_run_simplified()` 的代码入口仍从规划阶段开始。于是源码能证明的是：

```text
旧状态被加载
页面状态可以恢复
```

但不能把它描述成：

```text
从上次中断的精确 Agent 节点继续，且不会重复执行前面的阶段
```

这叫“状态恢复”，还不是完整的“节点级断点续跑”。

## 10. 检查点状态的一个陷阱

保存阶段检查点时，服务会把记录状态设为 `running`。正常完成后，Graph 再调用：

```text
update_status(session_id, "completed")
```

取消分支主要发送 `research_cancelled` 并返回。从当前代码看，不能仅凭取消事件断言数据库已经更新为 `paused`；需要实际检查 `ResearchCheckpoint.status`。

## 11. 真实断点续跑需要补什么

要实现真正的节点级续跑，至少要保存：

```text
当前阶段或节点名
已处理的章节 ID
已执行的搜索查询和来源 ID
哪些 Agent 输出已经写入
重试次数
取消后的明确状态
幂等键或去重规则
```

恢复时要根据阶段选择入口，例如：

```text
planning 完成 → 从 researching 开始
researching 完成 → 从 analyzing 开始
writing 完成 → 从 reviewing 开始
```

同时要避免重复追加 facts、references、charts 和报告章节。

## 12. 本课排错流程

### 用户点击停止，但后端仍有日志

```text
1. 检查 reader.cancel 是否调用
2. 检查 cancel API 是否成功
3. 检查 Redis key 是否存在
4. 检查 session_id 是否一致
5. 检查 Graph 是否到达取消检查点
6. 检查当前 Agent 是否阻塞在外部调用
```

### 刷新后步骤恢复但图表为空

```text
1. 检查数据库 ui_state_json.charts
2. 检查 state_json.charts
3. 检查前端是否创建 analyzing detail
4. 检查 detail key 是否一致
5. 检查 researchDataVersion 是否触发更新
```

### 恢复后重复搜索

```text
1. 查看 Graph.run() 是否加载旧 state
2. 查看 _run_simplified() 是否无条件从 planning 开始
3. 查看 state.phase 是否被用于路由入口
4. 检查 facts/references 是否有重复数据
```

## 13. 本课练习

1. `reader.cancel()` 为什么不能单独证明服务器任务已经停止？
2. `state_json` 和 `ui_state_json` 分别服务于谁？
3. 为什么页面恢复完整，不代表计算已经从精确节点继续？
4. 如果取消事件已经发送，但数据库 status 仍是 `running`，你如何解释？
5. 真正实现断点续跑至少需要保存哪些信息？

## 14. 一句话总结

```text
取消控制执行，检查点保存状态，恢复重建上下文；当前项目已经具备前两者和状态恢复，但还不能证明实现了精确节点级续跑。
```

