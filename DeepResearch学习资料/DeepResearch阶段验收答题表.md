# DeepResearch 阶段验收答题表

说明：每题用自己的话回答 3 到 8 行。可以查源码，但每题至少写一个文件或函数名。不会的题写“不会”和卡点，不要猜。

## 一、第116课：主链路

### 116-1 完整主链路

题目：用户输入“分析新能源汽车行业未来三年的竞争格局”后，写出前端函数、HTTP 方法和路径、Router、Service、执行器、共享状态、SSE 和最终页面展示。

源码提示：frontend/src/api/session.ts 的 deepsearch；backend/app/router/research_router.py；backend/app/service/deep_research_v2/service.py；graph.py 的 run 和 _run_simplified。

我的回答：

证据文件或函数：

### 116-2 三个核心对象

题目：分别解释 ResearchState、SSE、React 研究详情页面各自负责什么，并说明各自不负责什么。

源码提示：state.py 的 ResearchState；service.py 的 _format_sse；frontend/src/pages/chat/index.tsx 和 research-detail/visualization.tsx。

我的回答：

证据文件或函数：

### 116-3 状态演化

题目：规划完成、搜索完成、写作完成时，outline、facts、data_points、charts、draft_sections、final_report 分别是什么状态。

我的回答：

证据文件或函数：

### 116-4 版本判断

题目：判断并说明理由：A. POST /research/stream 默认进入 V2；B. V2 当前默认执行 LangGraph astream()；C. 只给 final_report 赋值，前端一定能显示报告；D. 每个 SSE 网络片段都能直接 JSON.parse()。

我的回答：

证据文件或函数：

## 二、第117课：启动和证据

### 117-1 证据边界

题目：判断 A-D 是否严谨，并说明理由：A. GET /hello 返回 200，所以 LLM 可用；B. Text2SQL 页面有数据，所以一定来自 PostgreSQL；C. /research/test-wizard 成功，所以完整研究成功；D. npm run build 成功，所以 SSE 已验证。

我的回答：

需要补充的直接证据：

### 117-2 分层排错

题目：研究请求返回 500，但前端能打开。按顺序写出至少五层检查和每层要看的证据。

我的回答：

## 三、第118课：图表排错

### 118-A

现象：后端日志显示 data_points=2，页面没有图表。

第一检查层：

直接证据：

### 118-B

现象：state.charts 有 2 个，但浏览器 Network 没有 chart 事件。

第一检查层：

直接证据：

### 118-C

现象：Network 收到 charts 事件，但右侧 analyzing 面板为空。

第一检查层：

直接证据：

### 118-D

现象：analyzing 面板有图表对象，但组件显示“图表数据加载中”。

第一检查层：

直接证据：

## 四、我的卡点

我现在最不理解的术语：

我现在最不理解的文件：

我希望用一个实际操作验证的链路：

## 五、批改规则

每题批改会区分：概念是否正确、数据流是否完整、源码证据是否准确、是否把未验证内容说成已验证。完成第116课四题后，再批改第117和第118课。
