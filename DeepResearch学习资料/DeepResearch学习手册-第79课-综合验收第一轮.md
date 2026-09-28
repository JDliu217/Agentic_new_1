# DeepResearch 学习手册：第 79 课

## 综合验收第一轮：从页面动作到最终结果

前 78 课已经覆盖源码和主要数据流。本课不再增加新模块，而是检查能否把模块连起来。

### 验收规则

每道题建议包含三部分：

```text
我的理解：用自己的话解释
源码证据：写出文件、函数或字段
不确定点：明确哪些地方只是推断
```

回答不要求一次完美，但必须能区分：

```text
当前代码真实行为
设计目标
尚未完成的运行验证
```

## 第一组：主链路

### 1. 从用户发送问题开始，写出 V2 DeepResearch 的完整调用链

至少包含：

```text
React 页面
请求方法
FastAPI 路由
V2 服务
Graph
ResearchState
六个 Agent
SSE
React 展示
```

### 2. 为什么项目要使用 `ResearchState`

请说明它如何解决：

```text
Agent 之间传递中间结果
检查点保存
恢复
工程排错
```

### 3. 当前 V2 默认执行哪一条流程？

请同时回答：

```text
LangGraph 图和 `_run_simplified()` 的关系
源码中哪里能证明
为什么当前选择手写流程
```

## 第二组：字段和 Agent

### 4. 给定一次研究状态，解释这些字段分别处于什么位置

```text
outline
raw_sources
facts
data_points
insights
charts
code_executions
draft_sections
final_report
references
critic_feedback
```

### 5. 如果 `facts` 有值、`data_points` 为空、`charts` 为空，可能是正常还是异常？

请根据问题类型说明判断方法，并指出下一条证据。

### 6. DataAnalyst 和 CodeWizard 的职责有什么不同？

要求同时说明：

```text
结构化图表配置
Python 执行
code_executions
charts 事件
```

## 第三组：事件和前端

### 7. `search_result_item` 从后端到页面经过哪些步骤？

请从 `asyncio.Queue` 一直写到 `Source` 或研究详情区域。

### 8. 为什么 `reader.read()` 需要缓冲区？

请解释网络分块和 SSE 事件边界为什么不是一回事。

### 9. 后端日志显示已经生成事件，但页面没有显示，你按什么顺序排查？

至少写出五层，并说明每层看什么证据。

## 第四组：RAG 和存储

### 10. 上传知识库文档后，完整链路是什么？

必须包含：

```text
Document 状态
BackgroundTasks
DocMind
切片
Embedding
Milvus
检索
DeepScout
```

### 11. PostgreSQL、Redis、Milvus 分别保存什么？

请额外说明：

```text
为什么 Document completed 不能单独证明可检索
为什么集合名需要重点检查
```

### 12. 如果普通聊天能查到知识库，但 DeepResearch 查不到，你先比较什么？

要求指出具体集合命名和调用路径。

## 第五组：代码执行和控制面

### 13. CodeWizard 的执行链是什么？

说明：

```text
LLM
compile()
危险模式检查
exec()
stdout/stderr
图片
自修复
```

### 14. 为什么进程内 `exec()` 不是生产级沙箱？

至少指出三个独立风险。

### 15. 取消、检查点和恢复分别解决什么问题？

请明确：

```text
reader.cancel
Redis key
state_json
ui_state_json
resume=True
```

## 第六组：工程判断

### 16. Text2SQL 和 CodeWizard 有什么相似点和不同点？

请比较：

```text
LLM 输出
执行环境
安全边界
结果类型
```

### 17. 新闻、招投标和股票三条业务链分别如何工作？

请指出：

```text
外部 API
去重字段
持久化方式
前端事件或页面
```

### 18. 目前项目中至少有哪些尚未通过真实端到端验证的部分？

不要只写“没测试”，而要说明缺少什么运行依赖。

## 评分标准

```text
主链路：能否讲清谁调用谁
状态：能否讲清字段怎样变化
事件：能否从后端追到 React
存储：能否区分三种存储
排错：能否提出下一条可验证证据
诚实性：能否区分源码确认和运行确认
```

本轮不是背诵考试。若某题不会，写“不会”并说明你认为缺少哪部分证据，比编造一个确定答案更好。

