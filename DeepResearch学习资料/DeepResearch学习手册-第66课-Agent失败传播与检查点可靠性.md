# DeepResearch 学习手册·第 66 课

## Agent 失败传播与检查点可靠性

工程排错不能只看“有没有日志”或“后面还有没有事件”。本课关注两个问题：Agent 失败后流程会不会继续，以及检查点失败后用户能不能恢复。

---

## 1. Agent 异常当前怎样处理

文件：`backend/app/service/deep_research_v2/graph.py`。

`run_agent_with_streaming()` 会创建异步任务：

```python
task = asyncio.create_task(agent.process(state))
```

任务完成后，代码等待它并捕获异常：

```python
try:
    await task
except Exception as e:
    logger.error(f"Agent {agent.name} error: {e}")
```

当前行为是：记录错误后，函数仍可能清空剩余消息并返回，外层 `_run_simplified()` 继续执行后续阶段。

这带来一个重要判断：

```text
后续出现了 writing 事件
≠
前面的 analyzing Agent 一定成功
```

后续 Agent 可能拿着不完整的状态继续工作。

---

## 2. 为什么“继续执行”可能产生假成功

假设 CodeWizard 执行失败：

```text
DataAnalyst 已写入部分 charts
CodeWizard 生成代码失败
run_agent_with_streaming 只记录日志
LeadWriter 仍然开始
CriticMaster 可能继续审核
```

最终页面可能出现：

- 有报告但没有代码图表。
- 有 `research_complete` 但 `code_executions` 中存在错误。
- 质量评分存在，但分析输入不完整。

因此验收时不能只检查最后一个 `research_complete`，还要检查：

- `errors`
- `code_executions[*].error`
- `code_result.success`
- `charts` 的来源和数量
- 每个阶段的 checkpoint 状态

---

## 3. CodeWizard 自愈和最终失败

CodeWizard 的执行链是：

```text
执行代码
  → 失败
  → 将 error/stdout 交给 LLM
  → 生成修复代码
  → 再执行
  → 最多重试 3 次
```

最终失败时会返回：

- `success: false`
- `error`
- `output`
- `charts: []`
- `retries`
- 最终代码

随后这些信息会写入 `state["code_executions"]`，并通过 `code_result` 事件告诉前端。

自愈机制解决的是“代码可以修复”的普通错误，不等于所有错误都能解决：

- 缺少 Python 依赖。
- 代码超时。
- 资源消耗过大。
- 违反安全拦截。
- LLM 连续生成同样的错误代码。

---

## 4. 检查点什么时候保存

简化流程在主要阶段结束后调用 `save_checkpoint_async()`：

```text
planning 完成
  → 保存

researching 完成
  → 保存

analyzing 完成
  → 保存

writing 完成
  → 保存
```

保存前会把当前状态转成两份数据：

- `state_json`：后端 `ResearchState`。
- `ui_state_json`：研究步骤、搜索结果、图表、图谱、报告等前端状态。

`ResearchCheckpoint` 还保存：

- `session_id`
- `user_id`
- `query`
- `phase`
- `iteration`
- `final_report`
- `status`

---

## 5. 检查点保存失败时的边界

`CheckpointService.save_checkpoint()` 捕获数据库异常，回滚并返回 `None`。

Graph 收到 `False/None` 后记录：

```text
[检查点保存失败]
```

但当前流程可能继续产生 SSE。于是可能出现：

```text
页面实时看到结果
  但 PostgreSQL 没有最新 checkpoint
  刷新或恢复时数据丢失
```

所以“页面显示正常”不能证明恢复能力正常；必须单独检查数据库记录和 `/research/checkpoint/{session_id}/full`。

---

## 6. 检查点状态的语义

阶段保存时，已有检查点会被更新为 `running`。研究最终结束时 Graph 设置为 `completed`；异常路径会尝试设置为 `failed`。

需要区分：

```text
checkpoint_saved
  = 一次状态写入成功

status=completed
  = 流程最终标记完成

final_report 非空
  = 报告文本存在
```

它们不是同一件事。报告可能存在但检查点最终状态没有更新，或者阶段检查点保存成功但最终完成更新失败。

---

## 7. 修复 Agent 失败传播的思路

如果目标是生产级可靠性，可以把当前“记录后继续”改成显式状态传播：

```text
Agent 异常
  → state.errors.append(...)
  → state.phase = failed
  → 保存失败检查点
  → 发送 error/research_failed
  → 停止后续 Agent
```

或者根据错误类型分级：

- 可恢复的 LLM JSON 错误：在 Agent 内部重试。
- 可选图表失败：记录 warning，允许继续写作。
- 核心搜索失败：停止或明确降级。
- 检查点数据库失败：至少发出持久化失败告警，不要假装可恢复。

关键是把“可继续”和“必须终止”定义清楚。

---

## 8. 修复后的验收标准

一个可靠的失败处理修复，至少要验证：

1. Agent 抛异常时，后续 Agent 是否停止符合预期。
2. 前端能收到明确的失败事件，而不是永远停在 loading。
3. `ResearchCheckpoint.status` 与实际结果一致。
4. `state_json` 中保留错误阶段和错误原因。
5. 刷新页面后能区分失败研究和未开始研究。
6. 可选图表失败不会误报整个研究失败。
7. 检查点写入失败不会被悄悄当作成功。

---

## 9. 综合排错场景

现象：

```text
页面收到了 CodeWizard 的 code_result(success=false)
随后又收到了 research_complete
刷新页面后没有 charts
```

合理判断：

1. CodeWizard 执行失败已经被前端观察到。
2. Graph 当前实现可能没有把该异常升级为终止状态。
3. LeadWriter 可能在缺少 CodeWizard 图片图表的情况下继续生成报告。
4. 刷新后没有 charts 还要检查 `ui_state_json` 是否保存了 DataAnalyst 图表，以及检查点保存是否成功。

不能直接说“前端丢图了”，因为后端可能从未产生完整图表，或者 checkpoint 根本没有保存最新 UI 状态。

---

## 练习

请回答：

1. Agent 异常被日志记录后，为什么后续仍可能出现 `research_complete`？
2. `checkpoint_saved` 和 `status=completed` 有什么不同？
3. 页面实时看到报告，但刷新后消失，应该检查哪两份数据？

参考答案：当前 Graph 捕获 Agent 异常后可能继续流程；`checkpoint_saved` 只是某次保存成功，`status=completed` 是最终状态标记；应检查 PostgreSQL 的 `state_json/ui_state_json` 和完整检查点接口返回。

