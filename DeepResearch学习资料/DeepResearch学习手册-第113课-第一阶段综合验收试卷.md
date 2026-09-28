# DeepResearch 学习手册·第 113 课：第一阶段综合验收试卷

## 说明

这不是考名词，而是检查你能否把“概念、源码、运行结果”连起来。可以查源码，但每道题都要写出至少一个文件或函数；不能只写“调用了 AI”“存到数据库”这种泛化描述。

建议先独立作答，再查材料补充。每题回答 3 至 8 行即可。

## A. 主链路（20 分）

### 1. 完整数据流（10 分）

用户在 React 页面输入：

```text
分析新能源汽车行业未来三年的竞争格局
```

请从前端发送开始，一直写到最终报告显示。至少包含：

```text
前端 API
HTTP 路由
V2 Service
Graph/执行器
六个 Agent
共享状态
SSE
React 展示
```

### 2. 版本边界（10 分）

解释以下三条链的区别：

```text
POST /research/stream
GET /research/stream
V1 ReAct
V2 _run_simplified()
```

指出你依据的源码位置。

## B. 状态与 Agent（20 分）

### 3. 状态演化（10 分）

研究刚完成规划、刚完成搜索、刚完成写作时，分别说明这些字段应该怎样变化：

```text
outline
facts
data_points
charts
draft_sections
final_report
```

### 4. Agent 责任（10 分）

用一句话分别说明以下 Agent 的输入、主要输出和一个跳过/失败条件：

```text
ChiefArchitect
DeepScout
DataAnalyst
CodeWizard
LeadWriter
CriticMaster
```

## C. RAG、SSE 与控制面（25 分）

### 5. RAG 链路（10 分）

按顺序解释：

```text
上传文件
→ Document 状态
→ DocMind
→ 切片
→ Embedding
→ Milvus
→ DeepScout 召回
```

并解释为什么 `Document.status=completed` 仍可能查不到结果。

### 6. SSE 分块（5 分）

浏览器两次读取分别得到：

```text
data: {"type":"research_sta
rt"}\n\n
```

为什么第一次不能直接 `JSON.parse()`？项目的前端如何处理？

### 7. 检查点和恢复（10 分）

说明以下字段各保存什么：

```text
state_json
ui_state_json
final_report
```

再解释为什么当前 `resume=True` 不能直接称为严格的节点级断点续跑。

## D. 工程判断（20 分）

### 8. CodeWizard 安全（5 分）

说明 LLM、`compile()`、危险模式检查、`exec()` 和图表捕获各自负责什么，并指出为什么当前实现不是生产级沙箱。

### 9. 启动证据（5 分）

分别说明下面命令能证明什么、不能证明什么：

```text
python -m compileall -q app
npm run build
GET /hello
```

### 10. 故障排查（10 分）

研究请求返回 500，但前端可以打开。请按合理顺序写出你会检查的至少五层，并说明每层看什么证据。

## E. 模块边界与风险（20 分）

### 11. 四类功能边界（10 分）

分别说明普通聊天、普通附件、长期记忆和 Text2SQL 的：

```text
输入
主要存储/数据源
核心处理
输出
```

### 12. 工程风险（10 分）

写出至少三个当前源码中的真实风险，每个风险包含：

```text
源码证据
实际影响
修复方向
```

可选方向：用户归属校验、CORS、JWT 默认密钥、集合命名、CodeWizard、Mock fallback、resume、BackgroundTasks、硬编码外部 Key。

## 作答格式

请直接按下面格式回复，不需要一次写得很长：

```text
1. ...
2. ...
...
12. ...
```

如果暂时不会，写“不会”并说明卡在哪里，不要用猜测替代源码证据。

## 评分标准

```text
90-100：可以进入源码深挖和面试模拟
75-89：主链路基本掌握，需要补齐边界和排错
60-74：能复述名词，但数据流或源码证据不足
<60：回到主链路和基础概念重新学习
```

即使总分达到 75 分，以下任一项错误也不能进入面试阶段：

- 把 V2 说成默认使用 LangGraph；
- 把 `Document.completed` 说成 Milvus 一定可召回；
- 把前端 AuthGuard 说成后端权限校验；
- 把 mock 数据说成真实数据库结果；
- 把 `resume=True` 说成严格节点级恢复。

