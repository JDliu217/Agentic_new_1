# DeepResearch 学习手册：第 75 课

## CodeWizard：从 LLM 到执行结果

这一课把项目中的“代码解释器”拆成一条具体执行链：模型提出代码，后端检查代码，Python 环境运行代码，结果再回到研究状态。

## 1. CodeWizard 不是一个编译器项目

项目没有自己实现 Python 语言，也没有自己写 Python 编译器。它调用 Python 运行时已有的能力：

```text
compile()
exec()
matplotlib
pandas
numpy
```

CodeWizard 负责的是 Agent 编排：

```text
什么时候需要代码
给 LLM 什么数据
怎样检查返回的代码
怎样执行
失败后怎样重试
结果写回哪里
怎样通知前端
```

## 2. 一次执行的真实顺序

入口文件：

```text
backend/app/service/deep_research_v2/agents/wizard.py
```

完整过程可以写成：

```text
ResearchState.data_points
  → CodeWizard.process()
  → LLM 生成 JSON
  → 取出 code 字段
  → 清理代码
  → compile() 语法检查
  → 正则危险模式检查
  → asyncio.to_thread()
  → _execute_in_sandbox()
  → exec(code, exec_globals)
  → stdout/stderr/PNG
  → code_executions/charts
  → chart/code_result 事件
```

## 3. 为什么先看 `data_points`

CodeWizard 不是所有问题都执行代码。当前代码在没有足够数据点时会跳过分析：

```text
data_points 数量不足
→ 记录警告
→ 不执行绘图代码
```

这意味着：

```text
用户看不到图表，不一定是执行器坏了
也可能是前面的搜索和数据抽取没有形成足够的结构化数据
```

排错时要先看：

```text
state["data_points"]
```

## 4. LLM 负责生成什么

LLM 可能返回类似这样的结构：

```json
{
  "analysis_plan": "比较年度电池价格并绘制趋势图",
  "code": "import matplotlib.pyplot as plt\nyears = [2021, 2022, 2023]\nprices = [1200, 900, 700]\nplt.plot(years, prices)"
}
```

LLM 负责：

```text
选择分析方法
选择图表类型
组织 Python 语句
根据错误尝试修改代码
```

LLM 不负责：

```text
保证代码安全
保证库一定安装
保证数据真实
保证代码一定运行成功
```

## 5. `compile()` 只做语法检查

代码中有：

```python
compile(cleaned_code, '<string>', 'exec')
```

它能发现：

```text
括号不匹配
缩进错误
关键字写错
```

它不能证明：

```text
代码没有恶意行为
变量运行时一定存在
代码不会死循环
代码不会消耗过多内存
结果逻辑正确
```

所以：

```text
compile 成功 ≠ 安全
compile 成功 ≠ 运行成功
compile 成功 ≠ 结果正确
```

## 6. 危险模式检查

当前代码用正则拦截一些明显危险操作，例如：

```text
os
sys
subprocess
open()
eval()
exec()
requests
urllib
socket
pathlib
pickle
```

同时设置模块白名单，准备 pandas、numpy、matplotlib、seaborn 等常用模块，并通过自定义 `safe_import()` 限制导入。

这属于应用层过滤，优点是简单，缺点是不能提供强隔离。

## 7. 为什么 `exec()` 不是生产级沙箱

当前执行仍然发生在后端 Python 进程中：

```python
exec(code, exec_globals)
```

即使限制了 globals，仍然存在工程风险：

1. Python 对象模型复杂，字符串过滤不等于完整安全证明。
2. 代码可能制造巨大对象，耗尽内存。
3. 代码可能长时间计算，阻塞资源。
4. 进程内异常可能影响后端服务。
5. 规则可能误伤正常代码，也可能漏掉变形写法。

生产环境应使用独立的 Docker/容器沙箱或专用代码执行服务，并设置：

```text
CPU 限制
内存限制
超时时间
网络策略
临时文件系统
进程权限
```

## 8. 执行环境决定什么

假设 LLM 生成了正确的 pandas 代码，但服务器没有安装 pandas：

```text
LLM 代码可能合理
执行环境缺少依赖
→ import 失败
→ charts 为空
→ code_executions 记录错误
```

执行环境还决定：

```text
Python 版本
可用库
输入数据
网络和文件权限
CPU/内存/时间
图像输出方式
```

因此代码解释器能力不是单独由 LLM 决定，而是：

```text
LLM 能力
× 执行环境能力
× Agent 编排质量
× 资源和安全限制
```

## 9. 自修复过程

执行失败后，CodeWizard 会把错误反馈给 LLM：

```text
执行失败
→ 读取 error 和 stdout
→ 请求 LLM 分析错误
→ 得到 fixed_code
→ 再次执行
```

当前最多重试 3 次。每次尝试都会记录到：

```text
state["code_executions"]
```

同时会发送：

```text
thought
code_fix
code_result
chart
```

无限重试不可取，因为它会：

```text
增加模型成本
延长请求时间
重复相同错误
扩大执行风险
```

## 10. 图表怎样回到前端

如果执行成功并发现 matplotlib 图形，代码会：

```text
plt.gcf()
→ 保存 PNG 到 BytesIO
→ Base64 编码
→ state["charts"].append(...)
→ add_message(type="chart")
→ SSE
→ React 研究详情图表区域
```

所以图表显示失败可以从四个地方查：

```text
LLM 是否生成绘图代码
执行器是否成功
state["charts"] 是否有数据
前端是否处理 chart/charts 事件
```

## 11. 本地 Agent 应调用 API 还是自己实现解释器

通常不需要自己实现 Python 编译器。选择的是执行方案：

| 场景 | 方案 |
|---|---|
| 快速 Demo | 托管代码执行 API或受控本地实现 |
| 个人学习 | 本地 Python 或 Docker |
| 敏感数据 | 内网 Docker/沙箱 |
| 陌生用户提交代码 | 专用隔离执行服务 |
| 当前项目 | 进程内简化沙箱，适合受控演示 |

真正需要自己设计的是：输入协议、执行权限、资源限制、错误反馈和结果格式，而不是重写 Python 解释器。

## 12. 面试表达模板

可以这样回答：

> CodeWizard 先读取 ResearchState 中的数据点，调用 LLM 生成 Python 分析代码，然后做代码清理和 `compile()` 语法检查，再通过正则规则和受限 globals 做基础过滤，在线程中执行 `exec()`，捕获标准输出、错误和 matplotlib 图片，把结果分别写入 `code_executions`、`charts` 并通过 SSE 发送给前端。代码失败时会把错误反馈给 LLM，最多自动修复三次。当前实现是进程内简化沙箱，不能承担生产级隔离，生产环境需要独立容器或专用执行服务。

## 13. 本课练习

1. LLM 和执行环境在这条链路中分别负责什么？
2. `compile()` 通过为什么不能证明代码安全？
3. 为什么 `data_points` 足够少时，CodeWizard 可能直接跳过？
4. `code_executions` 有失败记录、`charts` 为空时，你会检查什么？
5. 为什么无限自动修复不适合生产环境？

