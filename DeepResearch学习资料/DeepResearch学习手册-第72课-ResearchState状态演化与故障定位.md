# DeepResearch 学习手册：第 72 课

## ResearchState 状态演化与故障定位

上一课追踪了请求的整体路径。本课只关注一个工程问题：当结果不符合预期时，怎样通过状态字段判断故障大概在哪一层。

## 1. 把状态当成一组检查点

研究状态不是只有一个“成功/失败”字段。它把中间产物分开保存：

```text
规划：outline、research_questions
检索：raw_sources、facts、references
分析：data_points、insights、knowledge_graph、charts
执行：code_executions
写作：draft_sections、final_report
审核：critic_feedback、quality_score、unresolved_issues
```

排错时先问：最后一个正常产生的字段是什么？第一个缺失的字段是什么？这比直接重试请求更有信息量。

## 2. 状态演化示例

假设用户的问题是“分析新能源汽车电池价格趋势”。状态大致经历：

```text
初始：query 有值，其余结果字段为空
规划后：outline / research_questions 有值
搜索后：raw_sources / facts / references 有值
分析后：data_points / insights / charts 可能有值
写作后：draft_sections / final_report 有值
审核后：quality_score / critic_feedback 有值
```

这里的“可能”很重要：某次问题没有足够的数值资料时，可以有 `facts`，但没有 `data_points`；没有数值数据时，CodeWizard 不一定应该执行绘图。

## 3. 故障案例一：页面有搜索来源，但报告为空

建议检查顺序：

```text
1. raw_sources 是否有内容
2. facts 是否有结构化事实
3. references 是否形成引用
4. LeadWriter 是否执行
5. draft_sections 是否生成
6. final_report 是否为空
7. research_complete 事件是否发出
```

如果 `raw_sources` 有值但 `facts` 为空，问题更接近 DeepScout 的整理阶段；如果 `facts` 和 `draft_sections` 都有值但 `final_report` 为空，问题更接近 Writer 的合并或完成事件。

## 4. 故障案例二：有事实，但没有图表

先区分两种正常情况：

```text
事实是定性描述，没有可计算数字
  → 没有图表可能是正常的

事实包含年度数值，但 charts 为空
  → 需要检查 DataAnalyst、CodeWizard 和图表事件
```

第二种情况的检查顺序：

```text
data_points
  → DataAnalyst 是否生成 ECharts 配置
  → CodeWizard 是否写入 code_executions
  → compile / 安全检查 / exec 是否成功
  → state["charts"] 是否增加
  → charts 或 chart 事件是否发送
  → 前端是否写入 analyzing detail
```

`code_executions` 为空不能单独证明没有图表，因为 DataAnalyst 可以走结构化图表配置路径；同样，`data_points` 有值也不能保证 CodeWizard 一定成功。

## 5. 故障案例三：后端日志有事件，页面没有显示

这通常不是 Agent 业务逻辑的第一嫌疑，而是事件传输或前端映射问题。按以下层次检查：

```text
Agent 是否调用 add_message()
  → message_queue 是否收到消息
  → _run_simplified() 是否 yield
  → StreamingResponse 是否发送 data: 行
  → 浏览器 Network 是否收到 SSE
  → reader.read() 是否继续读取
  → 缓冲区是否遇到换行
  → JSON.parse 是否成功
  → detail key 是否为 searching/analyzing/writing
  → React state 是否触发更新
```

例如 `search_result_item` 已经收到，但前端还没有对应的 `searching` 或 `researching` detail，就可能追加不到正确的目标对象。

## 6. 故障案例四：搜索结果很多，但证据覆盖不完整

当前 `DeepScout.process()` 每次最多处理一部分待研究章节。因而可能出现：

```text
outline 有 7 个章节
pending_sections 只处理前 3 个
LeadWriter 仍然遍历整个 outline
```

这时“报告已经生成”不等于每个章节都有同等证据。排查时需要比较：

```text
outline 的章节数量
已处理的 pending_sections
每个章节对应的 facts / references
draft_sections 的覆盖情况
```

## 7. 故障案例五：恢复后又从规划开始

检查点包含：

```text
state_json
ui_state_json
final_report
phase
status
```

但当前简化执行器加载旧状态后，仍然进入 `_run_simplified()` 的手写流程入口。工程上应准确表述为：

```text
支持载入检查点状态和恢复展示
不等于已经实现精确的节点级断点续跑
```

如果用户认为恢复后重复规划，这是当前实现边界，而不一定是前端错误。

## 8. 用状态字段组织日志

调试一次研究请求时，建议每个阶段至少记录：

```text
session_id
phase
agent name
输入字段长度或数量
输出字段长度或数量
错误信息
是否发送关键事件
checkpoint_id
```

不要只打印“研究失败”。更有用的日志是：

```text
DeepScout completed: facts=18, references=12, data_points=0
DataAnalyst completed: insights=4, charts=1
CodeWizard completed: executions=1, charts=0, retries=3
```

## 9. 本课练习

请判断下面问题最可能位于哪一层，并写出你要检查的第一个字段：

1. `outline` 为空，页面却显示开始搜索。
2. `facts` 有 20 条，`data_points` 为空，但用户问题完全是定性问题。
3. `data_points` 有值，`code_executions` 记录了 3 次失败，`charts` 为空。
4. `charts` 有值，后端发送了 `charts` 事件，但页面图表区域为空。
5. `final_report` 有值，刷新后报告消失，但数据库中 `state_json` 有内容。

参考思路：

```text
1. 规划或事件顺序问题，先看 outline 和 research_step
2. 可能是正常状态，先看问题是否需要数值分析
3. CodeWizard 执行链，先看 code_executions 的 error
4. 前端事件解析、detail key 或 ECharts 渲染链
5. 检查 ui_state_json、恢复接口和前端映射，而不是只看 state_json
```

## 10. 本课结论

`ResearchState` 的价值不仅是让 Agent 共享数据，也让工程师可以观察每个阶段的中间结果。掌握“字段从空到有的顺序”，就能把一个模糊的“研究失败”拆成可验证的问题：

```text
规划缺失
→ 搜索缺失
→ 事实整理缺失
→ 数据分析缺失
→ 代码执行失败
→ 写作缺失
→ SSE 或 React 展示失败
```

