# DeepResearch 学习手册：第 105 课

## 第一阶段标准答案与零基础心智模型

## 1. 先用生活化方式理解项目

把系统想成一个研究团队：

```text
前端 = 用户接待窗口
Router = 分发柜台
Service = 业务主管
Agent = 不同专业的工作人员
ResearchState = 团队共享白板
PostgreSQL = 正式档案室
Redis = 便签和临时信号
Milvus = 可以按“意思相近”查找的资料库
SSE = 工作人员边做边向用户汇报
```

用户不需要知道每个工作人员如何实现，但要知道问题如何被接收、处理、保存和展示。

## 2. 第一阶段四题标准答案

### 题目一：用户输入后经过哪些主要层

标准链路：

```text
React 页面
→ HTTP POST /research/stream
→ FastAPI research_router
→ DeepResearchV2Service
→ DeepResearchGraph.run
→ _run_simplified
→ 六个 Agent
→ ResearchState 和消息队列
→ SSE
→ 浏览器 ReadableStream
→ React 研究详情组件
```

回答时至少要说清三类边界：

```text
前端发请求
后端编排任务
前端接收事件并渲染
```

### 题目二：ResearchState、SSE、React 研究详情的职责

```text
ResearchState：保存研究过程中产生的事实、图表、报告和阶段
SSE：把后端发生的事件按顺序推送给浏览器
React 研究详情：把事件转换成步骤、来源、图表、图谱和报告
```

三者不能互相替代：

```text
没有 ResearchState，Agent 之间没有稳定的共享数据
没有 SSE，页面只能等待最终结果或主动轮询
没有 React 映射，后端事件不会自动变成页面组件
```

### 题目三：文档 completed 但研究搜不到

可能原因：

```text
文档只在 PostgreSQL 中完成状态更新
Milvus 写入失败或集合不存在
上传写入 kb_<知识库名称>
DeepScout 却查询固定集合 knowledge_base
查询 Embedding 失败
kb_id 过滤不匹配
```

所以必须继续检查向量库和实际查询，而不是只看 `Document.status`。

### 题目四：三个工程风险和修复方向

可以这样回答：

| 风险 | 修复方向 |
|---|---|
| 研究接口部分路径缺少直接用户归属校验 | JWT 当前用户 + session/user_id 联合查询 |
| CORS 允许任意来源并开启凭证 | 通过环境变量配置明确来源列表 |
| CodeWizard 进程内执行 LLM 代码 | 独立进程/容器、资源和网络隔离 |
| 集合名称上传和召回不一致 | 使用稳定 kb_id 统一生成集合名 |
| Text2SQL 可能返回 Mock 数据 | 响应标明数据来源，生产环境禁用静默 fallback |
| resume 重新进入简化流程 | 记录节点完成状态并实现幂等的节点级恢复 |

## 3. 零基础必须掌握的五个词

### HTTP

浏览器和后端之间传递请求和响应的规则。

```text
请求：我要做什么，以及附带什么数据
响应：你处理得怎么样，以及返回什么数据
```

### API

后端提供给前端调用的地址和数据格式。

例如：

```text
POST /research/stream
```

### 数据库

保存结构化业务数据的系统。项目中的 PostgreSQL 保存用户、会话、文档和检查点。

### 向量检索

先把文本转换成数字向量，再查找语义相近的文本。项目使用 Embedding 和 Milvus 完成这件事。

### 异步

程序发起一个耗时操作后，不必阻塞整个服务等待；完成后通过事件、队列或回调继续处理。项目的 SSE 和 Agent 流程都大量使用异步代码。

## 4. 用一个最小例子理解 SSE

普通 JSON 响应像这样：

```text
用户等待 60 秒
后端一次返回完整报告
```

SSE 像这样：

```text
data: {"type":"research_start"}
data: {"type":"outline"}
data: {"type":"search_results"}
data: {"type":"chart"}
data: {"type":"report_draft"}
data: {"type":"research_complete"}
```

用户可以边等待边看到进度，前端也能更早发现研究卡在哪一步。

## 5. 学习项目时的三层回答法

以后遇到任何模块，都按这个顺序回答：

```text
概念：它解决什么问题？
源码：哪个文件、哪个函数实现？
运行：一次请求中它什么时候执行，失败会怎样？
```

例如 CodeWizard：

```text
概念：让系统用代码分析数据
源码：agents/wizard.py 的 process 和 _execute_code
运行：读取 data_points，生成 Python，执行并发送 chart/code_result；失败会重试
```

## 6. 本课练习

请用“概念—源码—运行”格式解释：

1. `ResearchState`
2. Milvus
3. SSE

不要求一次写得很长，但每项都要包含三个层次。
