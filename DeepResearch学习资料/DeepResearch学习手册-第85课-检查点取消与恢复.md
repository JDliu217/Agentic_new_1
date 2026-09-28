# DeepResearch 学习手册：第 85 课

## 检查点、取消和恢复：研究任务的控制面

研究任务可能运行很久，所以项目同时提供三种控制能力：保存中间结果、请求停止、从最近状态重新开始。它们解决的是三个不同问题。

## 1. 检查点解决什么问题

检查点保存的是“某个阶段完成时的可持久化状态”，避免页面刷新或服务中断后所有结果都丢失。

Graph 在规划、搜索、分析和写作等阶段结束时调用检查点服务。

文件：`backend/app/service/checkpoint_service.py`

### 后端状态

```text
state_json
```

保存 `ResearchState` 中的查询、大纲、事实、数据点、图表、报告、审核反馈等内容，供后端继续处理。

### 前端状态

```text
ui_state_json
```

保存研究步骤、搜索结果、图表、知识图谱和流式报告，供前端直接恢复界面。

### 状态元数据

检查点记录还包括：

```text
session_id、query、phase、iteration、status、final_report、error_message
```

## 2. 保存检查点的实际边界

Graph 会把 `_message_queue` 等不可直接持久化的对象清理掉，再写入 PostgreSQL。保存失败时，当前实现通常记录日志并继续研究流程；因此：

```text
研究流程继续 ≠ 检查点一定可靠保存
```

排错时要同时看 Agent 业务日志和 `[CheckpointService] 保存成功/失败` 日志。

## 3. 取消的实际链路

用户点击停止时，前端做两件事：

```text
reader.cancel()
→ 停止浏览器继续读取响应

POST /research/cancel/{session_id}
→ Redis 写入 research:cancel:<session_id>
```

文件：`frontend/src/pages/chat/index.tsx`、`backend/app/router/research_router.py`

Graph 在启动 Agent 前、Agent 执行期间以及阶段切换前调用 `is_research_cancelled()`。发现 Redis 标志后，会取消当前 asyncio task，并发送 `research_cancelled`。

## 4. 为什么 `reader.cancel()` 不等于服务器停止

`reader.cancel()` 只影响浏览器读取端。它不能单独杀掉后端任务；后端是否停止要依赖：

```text
取消 API 成功
→ Redis 标志可被后端读取
→ Graph 到达下一次取消检查
→ 当前 Agent task 被取消
```

如果 Agent 正在同步阻塞的外部调用或线程工作中，协作式检查可能要等调用返回后才能生效。它不是操作系统级强制终止。

## 5. 恢复的实际链路

恢复接口：

```text
POST /research/resume/{session_id}
→ 查询检查点元数据
→ service_v2.research(..., resume=True)
→ graph.run(..., resume=True)
→ _load_checkpoint(session_id)
→ yield research_resumed
```

当前 `graph.run()` 加载旧 `ResearchState` 后，仍然进入 `_run_simplified(state)`。而 `_run_simplified()` 会从规划阶段开始执行手写流程。因此当前恢复更准确的理解是：

```text
加载旧状态作为输入，再重新进入简化流程
```

它不等于 LangGraph 那种精确跳到上次中断节点继续运行。

## 6. 一个完整场景

假设搜索阶段结束并成功保存检查点：

```text
state_json 中有 outline、facts、references
ui_state_json 中有 planning/searching 步骤和来源
```

随后浏览器断开：

1. 页面可以调用检查点接口恢复 UI 数据。
2. 如果调用 resume，后端加载 `state_json`。
3. 后端发送 `research_resumed`。
4. 当前实现仍可能再次执行规划和后续阶段。

因此恢复功能有两个层次：

```text
页面恢复：把已保存的内容显示回来
流程恢复：从准确节点继续计算
```

项目目前前者更明确，后者存在重新执行边界。

## 7. 排错顺序

### 点击停止后页面停了，但 CPU 仍很高

检查：

```text
reader.cancel 是否执行
取消 API 是否返回成功
Redis key 是否存在
Graph 是否打印 Research cancelled
Agent 是否卡在不可中断的同步调用
```

### 页面恢复了，但后端又重新搜索

检查：

```text
resume=True 是否真正传入
state_json 是否成功加载
graph.run 是否仍调用 _run_simplified
简化流程是否没有节点级跳转逻辑
```

### 检查点接口成功，但页面缺图表

比较：

```text
state_json.charts
ui_state_json.charts
前端恢复代码是否读取了正确字段
```

## 8. 本课练习

请解释：

1. `reader.cancel()` 和 Redis 取消标志分别负责什么？
2. `state_json` 和 `ui_state_json` 为什么要分开？
3. 当前 `resume=True` 为什么不等于精确的节点级续跑？
