# DeepResearch 学习手册：第 93 课

## 场景排错：`final_report` 有值，但页面没有显示报告

这是综合验收中的一个典型问题。已知 `final_report` 有值，只能说明 LeadWriter 已经生成了报告；它不能证明报告经过事件、网络和 React 状态后已经渲染。

## 1. 先定位最后一个已确认节点

```text
最后确认有值的字段：ResearchState.final_report
最可能完成的 Agent：LeadWriter
下一条边界：report_draft / research_complete 事件是否发出并被前端消费
```

## 2. 后端事件检查

LeadWriter 在整合报告后调用：

```python
self.add_message(state, "report_draft", {
    "content": state["final_report"],
    ...
})
```

Graph 完成整个流程后还会 yield：

```python
{
  "type": "research_complete",
  "final_report": state.get("final_report", ""),
  ...
}
```

因此先看日志：

```text
[SSE] Queued event: report_draft
[SSE YIELD] [LeadWriter] ... report_draft
```

以及网络响应中是否真的出现：

```text
data: {"type":"report_draft", ...}
data: {"type":"research_complete", "final_report":"..."}
```

## 3. 前端事件分支检查

文件：`frontend/src/pages/chat/index.tsx`

### `report_draft` 分支

前端从 `json.content` 读取报告内容：

```text
reportContent = eventContent.content
```

然后：

```text
writing 或 generating detail.streamingReport = reportContent
target.content = reportContent
setSelectedResearchDetail(...)
setResearchDataVersion(...)
```

### `research_complete` 分支

前端直接读取：

```text
json.final_report
```

并把它写入聊天项和写作详情的 `streamingReport`。

所以要检查事件结构是否被错误地写成：

```json
{"type":"research_complete", "content":{"final_report":"..."}}
```

当前分支期待的是顶层 `json.final_report`。

## 4. 完整排错顺序

```text
1. LeadWriter 是否把 final_report 写入 state
2. report_draft 是否入队
3. Graph 是否 yield report_draft
4. Service 是否包装为 data: {...}
5. 浏览器 Network 是否收到完整事件
6. 前端 SSE 缓冲是否正确取出 data 行
7. report_draft 是否读取 content.content
8. research_complete 是否读取顶层 final_report
9. writing detail 是否已经创建
10. setSelectedResearchDetail / researchDataVersion 是否触发更新
11. ResearchDetail 是否显示 ProcessReport
12. 是否被错误的后续状态覆盖
```

## 5. 最可能的三类原因

### 事件没有发出

`final_report` 只存在于后端内存，`add_message()` 或队列转发失败。

### 事件格式和前端契约不一致

例如 `report_draft` 的内容层级不对，或者 `research_complete` 把报告放在 `content` 内，而前端读取顶层字段。

### 前端详情对象不存在

`report_draft` 分支优先查找 `writing` 或 `generating` 详情。如果对应 `research_step` 事件没有先创建，报告可能已经写入聊天项，却没有写入研究详情面板。

## 6. 合格验收答案

```text
现象：final_report 有值，但页面没有显示报告。
最后确认有值的字段：ResearchState.final_report，说明 LeadWriter 已生成报告。
下一步查哪个 Agent 或事件：先查 LeadWriter 的 report_draft 入队和 Graph yield，再查 research_complete 的 SSE 和前端分支。
需要的证据：后端队列/yield 日志、Network 中的 report_draft/research_complete 原始 data 行、前端解析日志、writing detail 和 streamingReport 状态。
```

这份答案体现了正确的边界：不因为后端有报告，就直接把问题归因于 React；也不因为页面没显示，就回头重跑 LLM。
