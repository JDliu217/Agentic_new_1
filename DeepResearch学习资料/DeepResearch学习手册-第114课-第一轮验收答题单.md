# DeepResearch 学习手册·第 114 课：第一轮验收答题单

## 使用方式

本轮只回答 4 题。每题写 3 到 8 行即可。可以查源码，但要用自己的话说明，不要只复制课程原文。

## 1. 追踪一次研究请求

用户输入“分析新能源汽车行业未来三年的竞争格局”后，请补全：

```text
前端调用的函数：
HTTP 方法和路径：
后端接收它的 Router：
默认版本：
进入的 Service：
共享状态：
最终返回浏览器的传输方式：
```

提示：查看 `frontend/src/api/session.ts`、`backend/app/router/research_router.py` 和 `backend/app/service/deep_research_v2/service.py`。

## 2. 解释三个核心对象

分别用三句话解释：

```text
ResearchState 是什么，保存什么？
SSE 解决什么问题，后端事件如何到浏览器？
React 研究详情页面负责什么？
```

提示：不要把 `ResearchState` 说成数据库；不要把 SSE 说成双向 WebSocket；不要把 React 页面说成生成研究结果的地方。

## 3. RAG 为什么可能“状态成功但搜不到”

假设 PostgreSQL 中某文档是 `completed`，但 DeepScout 返回 0 条结果，请写：

```text
completed 代表什么：
还不能证明什么：
至少检查的四项证据：
当前源码中最值得怀疑的集合名差异：
```

提示：查看 `knowledge_router.py`、`docmind_service.py`、`milvus_service.py` 和 `agents/scout.py`。

## 4. 判断实现边界

判断正误，并写一句理由：

```text
A. V2 当前默认执行 LangGraph 的 astream()。
B. AuthGuard 可以代替后端权限校验。
C. Text2SQL 数据库连接不可用时可能返回 mock 数据。
D. resume=True 就是严格的节点级断点续跑。
```

提示：至少引用一个源码文件或函数作为依据。

## 回复格式

```text
1. ...
2. ...
3. ...
4. A：...；B：...；C：...；D：...
```

完成这 4 题后，我会给出：

```text
每题得分
正确之处
错误之处
对应源码
下一轮补课内容
```

