# DeepResearch 学习手册：第 70 课

## 前端 Mock SSE 与无 Docker 验证

这一课回答一个实际问题：当 PostgreSQL、Redis、Milvus、LLM 或 Docker 还没有在本机完整启动时，怎样继续验证 DeepResearch 的前端事件链？

答案是使用项目自带的前端 Mock 数据，但必须准确说明它能证明什么，不能证明什么。

## 1. Mock 文件在哪里

主要文件：

```text
frontend/mock/session.ts
frontend/mock/data/chat
frontend/mock/data/deepsearch
frontend/vite.config.ts
frontend/src/api/session.ts
frontend/src/pages/chat/index.tsx
```

`frontend/mock/session.ts` 使用 `vite-plugin-mock` 注册模拟接口。其中研究接口是：

```text
POST /api/research/stream
```

它读取 `frontend/mock/data/deepsearch`，按换行切分文件内容，然后每隔约 10 毫秒写出一行。响应头设置为：

```text
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

这正是在模拟后端逐步推送研究事件。

## 2. Mock 数据模拟了什么

样例文件中的事件大致顺序是：

```text
status
status
status
subqueries
search
search_result_item
search_result_item
...
search_results
```

事件含义如下：

| 事件 | 前端用途 |
|---|---|
| `status` | 显示“开始研究”“开始迭代”等阶段状态 |
| `subqueries` | 显示规划 Agent 拆出的子问题 |
| `search` | 显示当前正在搜索的子问题 |
| `search_result_item` | 追加单条来源、标题、摘要和 URL |
| `search_results` | 表示某个子问题的搜索结果汇总完成 |

因此，Mock 可以帮助观察前端如何接收并聚合流式数据。

## 3. 前端怎样读取 SSE

`frontend/src/api/session.ts` 的 `deepsearch()` 以 `POST` 请求研究接口，并声明接受 `text/event-stream`。聊天页面拿到响应后调用 `response.body.getReader()`，通过 `ReadableStream` 分块读取数据。

网络分块不一定正好以一条事件结束，所以页面不能假设每次 `reader.read()` 就得到一条完整 JSON。当前代码使用缓冲区累积文本，再按换行拆分，识别类似下面的行：

```text
data: {"type":"status","content":"开始研究"}
```

去掉 `data:` 后再执行 JSON 解析，最后根据 `json.type` 分派到不同的状态更新逻辑。

## 4. 事件如何变成页面内容

以搜索结果为例：

```text
Mock 文件中的 search_result_item
  → ReadableStream 分块
  → 缓冲区按换行拆分
  → JSON.parse
  → chat/index.tsx 找到当前研究详情
  → 追加 search_results 数组
  → ResearchDetail / Source 组件重新渲染
```

`search_result_item` 事件通常包含：

```json
{
  "subquery": "智慧交通的定义是什么",
  "url": "https://example.com/article",
  "name": "文章标题",
  "summary": "摘要",
  "snippet": "片段",
  "siteName": "来源网站"
}
```

这能验证来源列表的聚合和显示。它不能验证后端是否真的调用了 Bocha、Serper、网页抓取或向量检索。

## 5. 为什么当前不能直接把 Mock 当成真实运行

`frontend/vite.config.ts` 中目前是：

```ts
viteMockServe({
  enable: false,
})
```

所以当前默认开发配置不会启用 Mock 路由。即使手动打开 Mock，也只能替代前端请求的后端响应，不能替代：

1. FastAPI Router 和认证校验。
2. `DeepResearchV2Service` 和六个 Agent。
3. LLM 的规划、搜索决策和结构化输出。
4. PostgreSQL、Redis、Milvus、DocMind 等基础设施。
5. 外部搜索、行情和行业采集 API。

Mock 的证据等级是“前端协议和展示验证”，不是“业务端到端成功”。

## 6. 无 Docker 时可以验证哪些内容

可以验证：

- 页面是否能发出研究请求。
- `ReadableStream` 是否正确处理分块。
- 不完整 JSON 是否会留在缓冲区等待下一块。
- `status`、`subqueries`、`search_result_item`、`search_results` 是否进入正确状态。
- 来源列表、研究步骤和部分研究详情是否能渲染。
- 前端 build 是否通过。

暂时不能据此验证：

- JWT 是否正确授权。
- 后端是否能连接数据库。
- 文档是否真的写入 Milvus。
- Agent 是否真的调用了 LLM。
- CodeWizard 是否生成并执行了 Python。
- 检查点是否保存成功。
- 真实 SSE 是否由 FastAPI 持续输出。

## 7. 推荐的证据阶梯

没有 Docker 时，按以下顺序记录证据：

```text
源码静态检查
  → 前端 npm run build
  → Mock SSE 前端展示
  → 后端 python -m compileall -q app
  → 单独启动可用的 FastAPI
  → 接通数据库和缓存
  → 接通 LLM、搜索和向量库
  → 真实 /research/stream 完整验证
```

越靠后，越接近真实业务；不能用前面的证据替代后面的证据。

## 8. 这一课的最小练习

请回答下面四个问题：

1. 为什么 `reader.read()` 一次得到的内容不一定是一条完整 SSE 事件？
2. `search_result_item` 和 `search_results` 在前端聚合中分别承担什么作用？
3. 如果 Mock 页面能显示搜索来源，能否据此证明 DeepScout 已经调用了真实搜索 API？为什么？
4. `viteMockServe({ enable: false })` 对本地验证有什么影响？

标准理解应包含：网络分块与事件边界无关；前者追加单条来源，后者表示某个子问题的汇总；Mock 只证明前端协议和展示；关闭配置意味着默认不会拦截并返回 Mock 数据。

## 9. 与真实主链路的对应关系

Mock 只替代了主链路中的这一段：

```text
真实后端 SSE 事件
```

它仍然保留了后半段：

```text
SSE 文本
  → ReadableStream
  → JSON 解析
  → React 状态
  → 研究步骤、来源和详情组件
```

因此，学习时要把 Mock 当作“前端观察窗”，而不是把它当成完整 DeepResearch 引擎。

