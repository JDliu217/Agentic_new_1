# DeepResearch 学习手册：第 97 课

## LeadWriter 与 CriticMaster：从材料到可信报告

## 1. LeadWriter 不直接把搜索结果拼接起来

源码：

```text
backend/app/service/deep_research_v2/agents/writer.py
```

LeadWriter 先遍历 `state["outline"]`，为每个还没有完成的章节调用 LLM。

每个章节的输入包括：

```text
章节标题和描述
相关 facts
data_points
insights
相关 charts
```

章节结果写入：

```text
state["draft_sections"][section_id]
```

同时把章节状态改为：

```text
drafted
```

## 2. 章节写完后再整合全文

LeadWriter 收集：

```text
draft_sections
references
facts 中的来源
```

然后再次调用 LLM 生成完整报告，写入：

```text
state["final_report"]
```

并发送：

```text
report_draft
```

前端收到这个事件后，才能把完整报告放入研究详情中的报告区域。

## 3. JSON 解析失败时的 fallback

如果整合阶段没有得到预期的 `full_report` 字段，LeadWriter 会按章节内容拼接一个备选报告。

这能提高接口完成率，但也有边界：

```text
接口返回报告
≠ LLM 按完整报告格式成功输出
```

排错时要查看日志和报告来源，不能只看 `final_report` 是否非空。

## 4. CriticMaster 负责判断报告是否可以结束

源码：

```text
backend/app/service/deep_research_v2/agents/critic.py
```

CriticMaster 审核：

```text
报告草稿
研究大纲
facts
data_points
```

审核结果会写入：

```text
critic_feedback
quality_score
unresolved_issues
```

并发送 `review` 和 `critic_feedback` 事件。

## 5. 审核结果决定下一步路由

CriticMaster 不是只给一个分数，它还决定状态机下一步走哪里。

### 通过

```text
verdict = pass
→ phase = completed
```

### 需要补充证据

如果问题属于 `missing_source`、`incomplete` 或 `outdated` 等类型，并且严重程度较高：

```text
phase = re_researching
pending_search_queries = [...]
→ DeepScout 补充搜索
→ LeadWriter 重新写作
```

### 只需要修改文字

```text
phase = revising
→ LeadWriter 根据反馈修订报告
```

### 达到最大迭代次数

即使仍有问题，系统也可能把阶段设为 `completed`，并发送警告。

因此：

```text
completed 不一定等于所有问题都已解决
```

## 6. 完整闭环

```text
搜索事实
→ DataAnalyst 分析
→ CodeWizard 计算或画图
→ LeadWriter 按章节写作
→ LeadWriter 整合 final_report
→ CriticMaster 审核
→ 通过：completed
→ 信息不足：补充搜索
→ 文字问题：修订
```

这就是 V2 的反馈闭环，而不是简单的线性流水线。

## 7. 一个关键的数据流区别

```text
draft_sections = 每个章节的草稿
final_report = 整合后的全文
critic_feedback = 审核发现的问题
pending_search_queries = 审核要求补充搜索的问题
```

如果 `final_report` 有内容但页面没有报告，应该检查：

```text
LeadWriter 是否发送 report_draft
→ graph 是否从队列 yield
→ SSE 原始事件是否到达浏览器
→ React 是否处理 report_draft/research_complete
→ ResearchDetail 是否读取 streamingReport
```

## 8. 本课练习

1. 为什么 LeadWriter 要先生成 `draft_sections`，再生成 `final_report`？
2. CriticMaster 发现缺少官方来源时，状态可能怎样变化？
3. `completed` 为什么不一定代表报告没有问题？
4. 如果 `final_report` 有值但页面空白，你会按什么顺序排查？
