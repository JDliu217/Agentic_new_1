# DeepResearch 学习手册·第 54 课

## 取消、检查点和恢复：三个容易混淆的控制面

本课区分三个概念：

1. 取消：让正在运行的研究尽快停止。
2. 检查点：把研究数据和页面状态保存下来。
3. 恢复：从保存的数据重新发起研究请求。

它们有关联，但不是同一件事。

---

## 1. 用户点击停止时，前端做了什么

源码：frontend/src/pages/chat/index.tsx 的 handleStop。

前端先取消当前 ReadableStream reader：

~~~~tsx
await readerRef.current.cancel()
~~~~

这会停止浏览器继续读取当前 SSE 流，但它本身不一定能停止服务器端已经在执行的 Agent。

所以前端随后还调用：

~~~~tsx
api.session.cancelResearch(currentSessionIdRef.current)
~~~~

最后更新本地 UI：

- loading 设为 false。
- 如果没有内容，显示“已停止生成”。
- 把仍为 running 的研究步骤标成 completed。

这里要注意：把 UI 步骤标记为 completed 是页面层面的即时反馈，不等于后端所有 Agent 已完成。真正的后端停止要靠 Redis 取消标志被 Graph 检查到。

---

## 2. 后端取消接口做了什么

源码：backend/app/router/research_router.py。

POST /research/cancel/{session_id} 不直接持有 Agent task，也不强制杀掉 Python 线程。它把一个带过期时间的标志写入 Redis：

~~~~python
cancel_key = f"research:cancel:{session_id}"
cache.set(cancel_key, {"cancelled": True}, expire=300)
~~~~

这是一种协作式取消：

~~~~text
前端请求取消
  ↓
Redis 写入 cancelled=true
  ↓
Graph 定期查询标志
  ↓
发现取消后停止当前 Agent 或不启动下一个 Agent
~~~~

它不是操作系统级别的 kill，也不能保证恰好在任意一行代码立即中断。

---

## 3. Graph 在哪里检查取消

源码：backend/app/service/deep_research_v2/graph.py。

开始执行每个 Agent 前，run_agent_with_streaming 会调用 check_cancelled。

Agent 执行期间，Graph 每次等待消息时也会检查：

~~~~text
Agent task 正在运行
  ↓
每轮读取 Queue 前检查 Redis
  ↓
发现取消
  ↓
task.cancel()
  ↓
等待 CancelledError
  ↓
结束当前阶段
~~~~

阶段之间也会检查取消，例如：

- planning 后
- researching 后
- analyzing 后
- writing 后
- reviewing 循环中

因此取消的响应速度取决于：

- Redis 是否可用。
- Graph 是否正在检查。
- Agent 内部是否有不能快速取消的同步操作。
- 当前事件循环是否被其他同步代码阻塞。

---

## 4. 取消和状态事件

Graph 检测到取消时，会 yield：

~~~~json
{
  "type": "research_cancelled",
  "message": "研究已取消"
}
~~~~

前端可以收到这个事件，也可能因为用户先取消 reader 而看不到后续事件。

因此排错时要分别观察：

- 浏览器是否停止读取。
- Redis 是否有取消标志。
- 后端日志是否打印 cancelled。
- 检查点 status 是否被更新。
- 当前 Agent 是否还在调用外部服务。

“页面停止显示”不能单独证明“服务器任务停止”。

---

## 5. 检查点保存什么

模型：backend/app/models/research.py 的 ResearchCheckpoint。

数据库一条检查点主要包括：

| 字段 | 含义 |
|---|---|
| state_json | 后端 ResearchState |
| ui_state_json | 前端研究步骤、搜索结果、图表、图谱和流式报告 |
| final_report | 当前最终报告 |
| phase | 保存时阶段 |
| iteration | 审核迭代次数 |
| status | running、paused、completed、failed |
| error_message | 失败原因 |

Graph 在主要阶段完成后调用 save_checkpoint_async，保存：

- 规划完成
- 搜索完成
- 分析完成
- 写作完成

检查点服务会清理不可 JSON 序列化的内容，例如内部 asyncio.Queue 不应被保存到 JSONB。

---

## 6. 为什么要分 state_json 和 ui_state_json

后端状态和前端状态的用途不同。

### state_json

回答：

- 已经收集了哪些 facts？
- 有哪些 data_points？
- outline 是什么？
- final_report 到哪里？
- 当前 phase 和 iteration 是什么？

### ui_state_json

回答：

- 页面显示了哪些研究步骤？
- 已经展示了哪些搜索结果？
- 图表和知识图谱是什么？
- 当前过程报告显示什么？

如果只保存 state_json，后端可能能继续处理，但刷新页面后很难完整恢复用户看到的过程细节。

如果只保存 ui_state_json，页面可以恢复外观，却没有完整的研究工作数据。

---

## 7. 恢复请求实际做什么

Graph.run 收到 resume=true 时，会先尝试：

~~~~python
state = self._load_checkpoint(session_id)
~~~~

如果加载成功，发送 research_resumed 事件。

如果加载失败，则重新创建初始状态。

但是当前 graph.run 随后仍然调用：

~~~~python
async for event in self._run_simplified(state):
    yield event
~~~~

而 _run_simplified 的阶段代码从规划阶段开始执行。因此源码可以确认：

- 恢复会载入旧的 ResearchState。
- 页面可以读取旧的检查点。
- 当前默认手写执行器不等同于真正的节点级断点续跑。
- 不能直接宣称“从中断的 Agent 精确继续”。

这就是“状态恢复”和“执行位置恢复”的区别。

---

## 8. 检查点 status 的生命周期

常见状态：

~~~~text
开始保存阶段检查点 → running
研究正常结束 → completed
异常 → failed
~~~~

模型和服务还定义了 paused，但取消接口本身主要写 Redis 标志。是否会把当前检查点改成 paused，要结合具体运行路径和检查点更新日志确认，不能只根据状态注释推断。

研究正常结束时，Graph 会调用 checkpoint_service.update_status(session_id, "completed")。

异常时会更新为 failed，并写入错误信息。

---

## 9. 恢复页面和恢复计算不是一回事

前端调用 full checkpoint API 可以拿到：

- checkpoint 元信息
- state_json
- ui_state_json
- final_report

页面可以据此重新显示研究步骤、来源、图表、图谱和报告。

但如果用户再次点击继续研究，后端是否从某个中间 Agent 接着执行，要看后端的 resume 实现。当前源码的简化执行器从规划入口开始，所以页面恢复得很完整，也不代表计算只从断点之后继续。

---

## 10. 一次取消故障的排查顺序

现象：用户点击停止，页面停止了，但后端仍有搜索日志。

按这个顺序检查：

1. 前端是否调用 reader.cancel。
2. 前端是否发送 POST /research/cancel/{session_id}。
3. Redis 是否写入 research:cancel:{session_id}。
4. Graph 是否在等待 Queue 时读取到标志。
5. 当前 Agent 是否正在同步外部调用。
6. 后端是否发出 research_cancelled。
7. 检查点最终 status 是什么。

如果 1 和 2 成功，但 4 没有发生，问题在 Redis 连接、session_id 不一致或检查时机。

---

## 11. 小练习

下面哪句话最准确？

A. reader.cancel 一调用，服务器上的所有 Agent 会立即被杀死。

B. 检查点保存了 state_json，所以一定能从中断的那一行代码继续执行。

C. 当前项目使用 Redis 标志和 Graph 协作式取消；检查点保存研究数据和 UI 状态，但当前简化执行器不等于精确节点级续跑。

D. 只要页面显示“已停止”，就能证明后端任务已经停止。

建议回答选项，并说明为什么取消、持久化和恢复必须分别验证。

---

## 留白：控制面笔记

取消请求：

Redis key：

Graph 检查位置：

检查点后端状态：

UI 状态保存在哪里：

当前恢复的真实限制：

---

## 源码定位

- frontend/src/pages/chat/index.tsx：reader.cancel、取消 API、前端即时状态
- frontend/src/api/session.ts：cancelResearch 和检查点请求
- backend/app/router/research_router.py：取消接口和 Redis 标志
- backend/app/service/deep_research_v2/graph.py：取消检查、检查点调用和恢复入口
- backend/app/service/checkpoint_service.py：保存、加载和更新状态
- backend/app/models/research.py：ResearchCheckpoint 字段

