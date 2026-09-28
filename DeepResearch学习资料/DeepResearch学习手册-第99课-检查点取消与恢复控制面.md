# DeepResearch 学习手册：第 99 课

## 检查点、取消与恢复：研究任务的控制面

研究报告和搜索结果属于“数据面”。系统还需要知道任务是否运行、是否取消、刷新页面后如何恢复，这部分可以称为控制面。

## 1. ResearchCheckpoint 保存什么

源码：

```text
backend/app/models/research.py
backend/app/service/checkpoint_service.py
```

数据库表 `research_checkpoints` 主要保存：

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
created_at
updated_at
```

### `state_json`

保存后端 `ResearchState`，包括：

```text
outline、facts、data_points、charts、draft_sections、final_report、phase 等
```

它用于后端继续处理研究。

### `ui_state_json`

保存前端恢复所需的数据：

```text
research_steps
search_results
charts
knowledge_graph
streaming_report
references
```

它用于页面刷新或重新打开会话后重建研究详情。

### `final_report`

单独保存最终报告，便于列表、恢复和最终结果读取。

因此：

```text
state_json = 后端工作状态
ui_state_json = 前端展示状态
final_report = 便于直接读取的最终报告
```

## 2. 什么时候保存检查点

当前简化流程在这些阶段后保存：

```text
planning
researching
analyzing
writing
```

保存时还会生成一个 `checkpoint_saved` 事件。

检查点保存失败会写日志，但当前流程通常继续运行。工程上要注意：

```text
研究继续完成
≠ 检查点一定保存成功
```

## 3. 用户点击停止时发生什么

前端 `handleStop` 做两件事：

```text
1. reader.cancel()
2. POST /research/cancel/{session_id}
```

### `reader.cancel()`

它只关闭或停止浏览器端的流读取。它不能保证后端 Agent 已停止，也不能撤销已经发出的外部 API 请求。

### Redis 取消标志

后端把标志写入：

```text
research:cancel:<session_id>
```

有效期是 300 秒。

Graph 在启动 Agent 前和 Agent 执行期间轮询这个标志。如果发现已取消：

```text
停止继续读取队列
→ 调用 task.cancel()
→ 发送 research_cancelled
```

这属于协作式取消。代码只有在检查取消标志时才会响应。

## 4. 为什么取消不一定立即生效

如果当前 Agent 正在等待：

```text
外部搜索 HTTP 请求
LLM 请求
DocMind 请求
股票接口
```

取消标志不会自动杀死这些已经发出的请求。只有请求返回、控制权回到 Graph 后，协作式检查才有机会生效。

因此前端显示停止，并不必然等于所有后端工作已经结束。

## 5. 页面刷新时怎样恢复展示

前端调用：

```text
GET /research/checkpoint/{session_id}/full
```

返回：

```text
state_json
ui_state_json
final_report
```

前端重新创建步骤详情，然后把：

```text
ui_state_json.search_results → searching/researching detail
ui_state_json.knowledge_graph → analyzing detail
ui_state_json.charts → analyzing detail
ui_state_json.streaming_report → writing detail
```

最后把最终报告补到聊天消息和右侧过程报告中。

## 6. 恢复展示和恢复执行不是一回事

页面恢复是：

```text
重新把旧数据显示出来
```

执行恢复是：

```text
从上次未完成的节点继续调用 Agent
```

当前代码的 `resume=True` 会加载 `state_json`，然后仍进入 `_run_simplified()`。所以可以确认：

```text
页面状态可以恢复
后端状态可以加载
但当前实现不能直接称为严格的节点级断点续跑
```

## 7. 当前控制面的工程风险

### 用户归属

检查点模型有 `user_id`，但研究检查点的部分路由只按 `session_id` 查询。生产实现应同时校验当前 JWT 用户和检查点归属。

### 状态回退

`save_checkpoint()` 更新现有记录时会把状态设为 `running`。如果流程已经进入暂停语义，保存逻辑需要明确区分普通保存和恢复运行。

### 取消状态

Redis 标志是短期控制信号，不能替代数据库中的最终任务状态。任务结束、失败或暂停时应可靠更新 `ResearchCheckpoint.status`。

### 幂等性

恢复可能重复执行搜索、LLM 调用或写入，因此 Agent 和外部写入需要设计幂等键。

## 8. 本课练习

1. `state_json` 和 `ui_state_json` 为什么不能简单合并成一个字段？
2. `reader.cancel()` 为什么不能单独作为后端取消方案？
3. 页面恢复和节点级执行恢复有什么区别？
4. 如果用户点击停止后，后端仍产生了一条搜索结果，你会如何解释？
