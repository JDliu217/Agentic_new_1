# DeepResearch 学习手册：第 98 课

## 前端如何接收 SSE 并显示研究结果

源码重点：

```text
frontend/src/pages/chat/index.tsx
frontend/src/pages/chat/component/research-detail/index.tsx
frontend/src/pages/chat/component/research-detail/process-report.tsx
frontend/src/pages/chat/component/research-detail/visualization.tsx
```

## 1. 从 Fetch 响应取得流

深度研究请求返回一个 `ReadableStream`。前端调用：

```text
res.data.getReader()
```

然后循环执行：

```text
reader.read()
```

每次读取到的内容不一定刚好是一条完整事件，所以前端先放进临时字符串 `temp`。

## 2. 为什么需要缓冲区

网络可能把一条事件拆成两次返回：

```text
第一次：data: {"type":"research_st
第二次：ep",...}\n\n
```

因此不能把每个 `reader.read()` 的结果直接 `JSON.parse()`。项目的做法是：

```text
读取字节
→ TextDecoder 解码
→ 追加到 temp
→ 查找换行符
→ 取出完整行
→ 处理 data: 行
→ 剩余半条内容继续留在 temp
```

## 3. `researchDetailsRef` 是前端研究工作台

后端的 `ResearchState` 是后端工作台，前端对应的核心容器是：

```text
researchDetailsRef: Map<string, ResearchDetailData>
```

它按步骤保存：

```text
planning
searching/researching
analyzing
writing
reviewing
```

每个步骤可以保存：

```text
searchResults
charts
knowledgeGraph
streamingReport
sections
```

## 4. 事件到前端对象的映射

| SSE 事件 | 前端处理 |
|---|---|
| `research_start` | 初始化深度研究模式并清空旧详情 |
| `research_step` | 创建或更新研究步骤和详情对象 |
| `search_results` | 写入 searching/researching 的搜索结果 |
| `knowledge_graph` | 写入 analyzing 的知识图谱 |
| `charts` | 写入 analyzing 的 ECharts 图表 |
| `section_content` | 写入 writing 的章节草稿和过程报告 |
| `report_draft` | 写入 writing 的完整报告草稿 |
| `chart` | 写入 analyzing 的图片型图表 |
| `research_complete` | 设置聊天内容、报告、引用并结束步骤 |
| `research_cancelled` | 关闭加载状态并显示取消结果 |
| `error` | 显示错误并结束当前请求 |

## 5. 为什么 `researchDataVersion` 很重要

`researchDetailsRef` 是 `useRef`，直接修改 Map 内部对象不会自动触发 React 重新渲染。

因此事件处理后会调用：

```text
setResearchDataVersion(v => v + 1)
```

这个数字不是业务数据，而是一个“数据发生变化”的刷新信号。

`aggregatedResearchData` 依赖它重新计算，把所有步骤合并成：

```text
searchResults
knowledgeGraph
charts
streamingReport
sections
```

然后传给 `ResearchDetail`。

## 6. 研究详情组件怎样显示

源码：

```text
frontend/src/pages/chat/component/research-detail/index.tsx
```

它提供四个主要标签：

```text
搜索结果
知识图谱
可视化
过程报告
```

分别使用：

```text
SearchResults
KnowledgeGraph
Visualization
ProcessReport
```

过程报告使用：

```text
data.streamingReport
data.sections
```

图表使用：

```text
data.charts
```

## 7. “后端有报告但页面空白”的排查顺序

```text
1. LeadWriter 是否写入 state["final_report"]
2. 是否发送 report_draft 或 research_complete
3. graph.py 是否从 asyncio.Queue yield 事件
4. 浏览器 Network 中是否收到 data: 行
5. parseData 是否识别事件类型
6. 是否找到 writing detail
7. 是否写入 detail.streamingReport
8. 是否调用 setResearchDataVersion
9. aggregatedResearchData 是否得到 streamingReport
10. ProcessReport 是否读取并渲染 content
```

## 8. 一个重要的前端状态边界

```text
currentChatItem.content
```

主要用于聊天消息中的最终回答；

```text
researchDetailsRef.current.get("writing").streamingReport
```

主要用于右侧研究详情的过程报告。

两者都可能保存报告，但显示位置不同。只检查聊天气泡，不能证明右侧过程报告一定有值；反过来也一样。

## 9. 本课练习

1. 为什么不能直接对每次 `reader.read()` 的结果执行 `JSON.parse()`？
2. 为什么修改 `researchDetailsRef` 后还要更新 `researchDataVersion`？
3. `report_draft` 和 `research_complete` 在页面上分别起什么作用？
4. 如果 Network 能看到 `report_draft`，但右侧过程报告为空，优先检查哪两个前端对象？
