# DeepResearch 学习手册·第 25 课

## CodeWizard 源码逐步追踪与执行边界

第 10 课解释了代码解释器的整体概念，本课继续按真实函数调用顺序阅读 `wizard.py`。目标是让你能从一段 `data_points` 追踪到一次代码执行、一个图表事件，以及一次失败重试。

源码：

```text
D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\agents\wizard.py
```

---

## 1. 先区分四个角色

```text
LLM
  生成 Python 字符串，解释错误并提出修复版本

CodeWizard
  组织提示词、清理代码、调用执行器、写回 ResearchState

Python 运行时
  compile() 检查语法，exec() 执行代码

执行环境
  当前进程、线程、预导入模块、受限 globals、输出和图片捕获
```

所以“代码解释器”在这个项目中不是一个单独的 API，而是 Agent、LLM、Python 运行时和图表捕获逻辑共同组成的链路。

---

## 2. `process()` 是入口

`CodeWizard.process(state)` 的第一步是检查阶段和数据量：

```text
如果 phase 不是 analyzing：
    data_points >= 3 → 把 phase 改成 analyzing
    data_points < 3  → 记录警告并直接返回
```

这说明 CodeWizard 不是无条件执行。它至少需要三个数据点才会主动把非分析阶段切到 `analyzing`；如果上游已经把 `phase` 设为 `analyzing`，则继续执行。

通过检查后，它发送一条 `thought` 消息，然后依次调用：

```text
_analyze_data(state)
_generate_charts(state)
```

这两个函数都可能调用 LLM 和执行代码。

---

## 3. `_analyze_data()`：先让 LLM 生成分析代码

### 3.1 输入如何整理

代码把每个数据点压缩成文本：

```text
- 指标名称: 数值 单位 (年份)
```

然后把用户问题和数据摘要填入 `ANALYSIS_PROMPT`。提示词要求 LLM 返回 JSON，至少包含：

```json
{
  "analysis_plan": "分析计划",
  "code": "Python代码",
  "expected_outputs": ["预期输出"]
}
```

当前提示词还要求不要写 import，直接使用预先提供的 `pd`、`np`、`plt`、`sns`。

### 3.2 LLM 返回后发生什么

调用顺序是：

```text
call_llm()
  → parse_json_response()
  → 取 result["code"]
  → list 转字符串或其他类型转字符串
  → _clean_code()
  → compile()
  → 长度和行数等简单有效性检查
  → _execute_with_self_correction()
```

`BaseAgent.parse_json_response()` 会处理 Markdown 代码块、外层大括号、尾随逗号和部分转义问题。它解决的是“LLM 返回格式不稳定”，不是代码安全问题。

### 3.3 代码事件何时发送

清理后的代码通过以下事件进入消息队列：

```json
{
  "type": "code",
  "content": {
    "language": "python",
    "code": "...",
    "purpose": "..."
  }
}
```

这个事件主要用于前端展示“正在执行什么代码”，真正的运行还没有结束。

---

## 4. `_execute_with_self_correction()`：失败后怎样修复

当前实现最多执行 `max_retries=3` 次修复循环：

```text
current_code = 初始代码
retries = 0

执行 current_code
  ├─ 成功 → 返回 output、charts、final_code
  └─ 失败
       ├─ 已达到最大重试 → 返回失败
       └─ 未达到最大重试
            → 把 error 和 stdout 放进修复提示词
            → 调用 LLM 得到 fixed_code
            → 发送 code_fix 消息
            → retries += 1
            → 执行修复后的代码
```

失败时前端可能收到：

```text
thought      代码执行失败，正在自动修复
code_fix     错误分析、修复说明和重试编号
code_result  最终执行是否成功、输出摘要和图表标记
```

注意：这是“让模型根据错误再生成一次代码”，不是 Python 解释器自动修复代码。修复是否有效仍然取决于 LLM 和执行环境。

---

## 5. `_execute_code()` 的真实检查顺序

### 5.1 类型和代码清理

如果 LLM 返回的是列表，代码先用换行拼接；不是字符串则转成字符串。之后 `_clean_code()` 会处理代码围栏和部分转义格式。

### 5.2 `compile()`：语法检查，不是运行

```python
compile(code, '<string>', 'exec')
```

它把源代码解析成代码对象，能发现语法问题，例如括号不匹配或缩进错误。它不访问数据，也不验证结果，更不提供安全隔离。

### 5.3 `_is_code_safe()`：正则过滤

源码用 `FORBIDDEN_PATTERNS` 匹配一些明显危险操作，例如：

```text
os、sys、subprocess
open()
exec()、eval()
requests、urllib、socket
pathlib、pickle、glob
__builtins__、__globals__、__code__
```

匹配到任何一个模式，就返回失败，不进入执行器。

正则过滤有两个固有限制：

1. 变形写法或间接调用可能绕过简单字符串匹配。
2. 正常代码可能因为包含相似文本而被误拦截。

它是“减少明显风险”的规则，不是可证明安全的隔离边界。

---

## 6. `_execute_in_sandbox()`：名字叫沙箱，但仍在后端进程内

执行函数通过 `asyncio.to_thread()` 放到线程中运行。线程可以减少阻塞事件循环，但不等于操作系统隔离，也不等于容器。

函数准备了：

```text
pandas → pd
numpy → np
matplotlib.pyplot → plt
seaborn → sns
datetime、math、statistics、json、collections、re
```

然后把这些对象和一组受限内置函数放入 `exec_globals`：

```python
exec(code, exec_globals)
```

内置函数中把 `open` 设置为 `None`，并提供了自定义 `__import__`。输出通过 `redirect_stdout` 和 `redirect_stderr` 捕获，matplotlib 图像则从当前 figure 保存到内存，再编码成 Base64。

最终执行器返回：

```json
{
  "success": true,
  "output": "stdout",
  "error": null,
  "charts": ["base64图片"]
}
```

### 6.1 为什么线程不是安全沙箱

当前代码仍然共享：

- 后端进程的 Python 解释器。
- 进程内存和导入模块。
- 操作系统用户权限。
- 进程的 CPU 和文件描述符等资源。

代码没有在这里看到独立容器、系统调用过滤、网络命名空间、CPU 配额、内存配额或强制超时。因此无限循环、超大内存分配和某些运行时攻击仍可能影响后端。

---

## 7. 两个源码级边界，必须会指出

### 7.1 语法错误记录后没有立即返回

在 `_execute_code()` 中，`compile()` 捕获 `SyntaxError` 后会记录调试信息，但当前代码没有在该分支直接 `return`。它随后仍会继续进行安全检查，并可能进入 `_execute_in_sandbox()`。

这意味着：

```text
语法检查失败 ≠ 当前函数立即结束
```

最终是否再次失败由后续执行决定。更严谨的实现通常会在语法错误处直接返回结构化错误，避免重复执行明显无效的代码。

### 7.2 `ALLOWED_MODULES` 与真正 import 白名单不完全一致

类属性 `ALLOWED_MODULES` 声明了 `wordcloud` 和 `jieba`，但 `_execute_in_sandbox()` 中的 `allowed_base_modules` 只包含：

```text
pandas、numpy、matplotlib、seaborn、datetime、math、statistics、json、collections、re
```

因此即使上层声明了词云和中文分词模块，代码中的 `import wordcloud` 或 `import jieba` 仍会被 `safe_import` 拒绝。这个例子说明：阅读配置常量还不够，必须继续追到真正消费它的执行代码。

---

## 8. 图表怎样回到前端

当 `_execute_data()` 或 `_generate_charts()` 得到 Base64 图像后，CodeWizard 会：

1. 创建图表记录并追加到 `state["charts"]`。
2. 把执行过程追加到 `state["code_executions"]`。
3. 发送 `chart` 消息到 `state["messages"]` 和消息队列。
4. `_run_simplified()` 从队列取出消息并向 SSE 生成器 `yield`。
5. FastAPI 把事件写进 `text/event-stream`。
6. React 将图片放入 `researchDetailsRef.current.get("analyzing").charts`。
7. React 增加 `researchDataVersion`，重新计算研究详情并渲染图表。

完整链路是：

```text
LLM代码
 → _execute_code
 → Base64图片
 → state["charts"]
 → chart消息
 → asyncio.Queue
 → SSE
 → researchDetailsRef
 → researchDataVersion
 → 图表组件
```

---

## 9. 如果你要把它改成生产方案

不要只增加更多正则。至少需要重新设计执行边界：

```text
请求进程
  → 独立 worker / 容器
  → 只读输入目录和临时输出目录
  → 禁止或严格代理网络
  → CPU、内存、运行时间和输出大小限制
  → 任务结束销毁执行环境
  → 只返回结构化 stdout、stderr、图表和错误
```

同时要保留：

- 代码版本和执行记录。
- 依赖版本。
- 超时、取消和失败状态。
- 结果大小限制。
- 不可信代码和数据的权限边界。

这也是为什么本地 Agent 通常调用成熟执行服务、Docker worker 或专用沙箱，而不是自己重写 Python 解释器。

---

## 10. 练习

请用自己的话回答：

1. `compile()`、`_is_code_safe()` 和 `exec()` 分别解决什么问题？
2. 为什么 `asyncio.to_thread()` 不能等同于 Docker 沙箱？
3. 当前代码中声明允许 `jieba`，为什么实际导入仍可能失败？
4. 图表从 CodeWizard 到 React 页面至少经过哪些对象或事件？
5. 如果 LLM 生成的代码有语法错误，当前实现会发生什么？你会怎样改进？

