# DeepResearch 学习手册：第 84 课

## CodeWizard：从数据点到 Python 执行结果

CodeWizard 不是“让 LLM 自己运行代码”。它是一个 Agent：先让 LLM 生成代码，再由项目进程负责检查、执行、收集输出，最后把结果写回 `ResearchState` 并通过 SSE 发给前端。

## 1. 它在什么时候执行

文件：`backend/app/service/deep_research_v2/agents/wizard.py`

`process()` 进入分析阶段后，依次调用：

```text
_analyze_data(state)
_generate_charts(state)
```

如果数据点数量不足，Agent 可能跳过分析。因此看到没有图表时，先检查 `state["data_points"]` 数量和当前 `phase`。

## 2. 第一条执行链：数据分析代码

### 2.1 准备输入

CodeWizard 从 `state["data_points"]` 提取指标名、数值、单位和年份，拼成提示词，传给 LLM。

### 2.2 LLM 返回代码

项目要求 LLM 返回 JSON，其中包含：

```json
{
  "analysis_plan": "分析计划",
  "code": "Python代码",
  "expected_outputs": ["预期结果"]
}
```

项目提示词要求代码使用预先提供的 `pd`、`np`、`plt`、`sns`，并生成图表。

### 2.3 清理代码

`_clean_code()` 会处理 Markdown 代码块标记、转义换行和 LLM 常见格式问题。代码字段中的换行需要被还原成真正的 Python 换行。

### 2.4 `compile()` 只做语法检查

项目调用：

```python
compile(code, '<string>', 'exec')
```

它可以发现语法错误，但不会执行代码，也不能证明代码安全。例如，语法正确的无限循环仍然可能阻塞；语法正确的高内存操作仍然可能耗尽资源。

当前实现中，语法错误会被记录，后续执行还会由 `_execute_code()` 返回错误，再进入自修复链路。因此不能把 `compile()` 叫作真正的执行隔离。

## 3. 安全检查

`_is_code_safe()` 使用正则表达式拦截一些模式，例如：

```text
os、sys、subprocess、socket
open、eval、exec
__import__、__builtins__、__globals__
pathlib、shutil、pickle、glob
```

这是一层输入过滤，不是安全边界。正则匹配可能漏掉变形写法，且 Python 对象和库本身存在复杂的间接能力。

## 4. 实际执行环境

文件：`_execute_in_sandbox()`

项目在当前 Python 进程的线程中执行：

```python
await asyncio.to_thread(self._execute_in_sandbox, code)
```

它创建了一个受限的 `exec_globals`：

- 预先提供 `pandas`、`numpy`、`matplotlib`、`seaborn` 等模块。
- 只允许白名单基础模块通过自定义 `safe_import()` 导入。
- 把 `open` 设置为 `None`。
- 重写部分内置函数。
- 使用 `redirect_stdout` 和 `redirect_stderr` 捕获输出。

执行代码后，项目检查 Matplotlib 当前图形，把 PNG 编码成 Base64。

## 5. 执行结果怎样回到状态

一次执行会返回：

```text
success
output
error
charts
```

CodeWizard 把它追加到：

```python
state["code_executions"]
```

其中记录代码、输出、错误、图表和重试次数。如果得到图表，还会写入：

```python
state["charts"]
```

并发送：

```text
code_result
chart
```

前端收到 `chart` 事件后，把 Base64 图片添加到分析详情和当前聊天项。

## 6. 第二条执行链：按章节生成图表

`_generate_charts()` 从大纲中找 `requires_chart` 的章节，最多处理两个章节。每个章节会：

```text
找相关事实和数据
→ LLM 生成图表代码
→ _execute_code()
→ state["charts"].append(...)
→ add_message(..., "chart", ...)
```

因此项目中图表可能来自两条路径：

```text
_analyze_data：通用数据分析图表
_generate_charts：按研究章节生成图表
```

## 7. 失败后的自修复

`_execute_with_self_correction()` 最多重试三次：

```text
执行代码
→ 失败
→ 把错误和 stdout 交给 LLM
→ LLM 返回 fixed_code
→ 再次执行
```

每次修复会发送 `thought` 和 `code_fix` 事件。最终仍失败时，`code_executions` 会保留错误和重试次数，流程通常继续交给后续 Agent。

## 8. 为什么这不是生产级沙箱

当前代码注释已经明确说这是简化沙箱。至少存在这些独立风险：

1. 代码仍在应用进程的线程中执行，进程级内存和权限没有真正隔离。
2. 没有可靠的 CPU、内存和执行时间限制；无限循环或大数组可能拖垮服务。
3. 正则过滤和受限 builtins 不是完整的 Python 安全模型，不能抵抗所有绕过方式。
4. 允许的第三方库本身可能产生大量资源消耗或间接副作用。
5. 线程任务无法像独立进程一样被可靠地强制杀死。

生产方案通常应使用单独容器或专用代码执行服务，并设置 CPU、内存、时间、网络、文件系统、用户权限和进程回收策略。

## 9. 面试时如何回答“LLM 和环境谁决定能力”

可以这样回答：

```text
LLM 决定生成什么代码以及如何分析问题；执行环境决定这些代码能否运行、能使用哪些库、能访问哪些资源，以及结果怎样被捕获。CodeWizard 是二者之间的编排层。当前项目的环境是进程内受限 exec，功能可用，但隔离强度不足以作为生产级安全边界。
```

## 10. 本课练习

请解释：

1. `compile()` 和 `exec()` 的区别是什么？
2. 为什么 `code_executions` 有记录，仍然可能没有 `charts`？
3. CodeWizard 自修复时，错误信息经过哪几个步骤回到新的代码？
