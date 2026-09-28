# DeepResearch 学习手册·第 19 课

## React 路由、请求层与研究结果渲染

> 本课依据本地项目 `D:\课\s4-6\industry_information_assistant\frontend` 的源码整理。重点是理解浏览器端如何把用户动作变成后端请求，再把 DeepResearch 的流式事件变成页面上的步骤、来源、图谱、图表和报告。

---

## 1. 本课要解决的问题

读完本课后，你应该能够回答：

1. React 应用从哪个文件启动？
2. 用户访问 `/chat/...` 时，路由如何判断是否登录？
3. 普通 HTTP 请求为什么会自动携带 JWT？
4. DeepResearch 为什么不能简单使用一次 `await response.json()`？
5. 后端的 `research_step`、`search_results`、`charts` 和 `research_complete` 事件分别写入了哪里？
6. 为什么研究详情页面需要 `useState`、`useRef` 和 `researchDataVersion` 同时存在？
7. 刷新浏览器后，研究步骤和报告如何从检查点恢复？

本课的主线是：

```text
浏览器加载
  → React 入口
  → 路由与认证守卫
  → 页面调用 API
  → Axios 插件处理请求
  → Fetch 流读取 SSE
  → ref / state 保存增量数据
  → ResearchDetail 分标签渲染
```

---

## 2. 应用启动：`main.tsx` 到 `App.tsx`

### 2.1 入口文件

文件：`frontend/src/main.tsx`

核心流程是：

```tsx
import App from './App.tsx'
createRoot(document.getElementById('root')!).render(<App />)
```

浏览器加载 Vite 生成的页面后，React 找到 HTML 中的 `#root` 节点，把整个应用挂载进去。`main.tsx` 还加载了 Ant Design 兼容补丁、重置样式、全局样式和主题样式。

### 2.2 应用外壳

文件：`frontend/src/App.tsx`

`App` 做三件事：

```text
ConfigProvider：设置 Ant Design 中文语言和主题
AntdApp：提供 message 等全局 UI 能力
Router：把当前 URL 映射到页面组件
```

同一个文件中的 `MountApi` 把 Ant Design 的全局对象和加载控制函数挂到 `window`：

- `window.$app`：用于调用 `message.error()` 等全局消息。
- `window.$showLoading()`：增加全局加载计数并显示 Spin。
- `window.$hideLoading()`：减少加载计数，计数归零后隐藏 Spin。

这里使用计数而不是简单的布尔值，是因为多个请求可能同时进行。一个请求结束时不能把另一个请求正在使用的全局加载状态提前关闭。

### 2.3 实际前端端口

文件：`frontend/vite.config.ts`

当前开发端口是：

```ts
server: {
  port: 5183,
  host: '0.0.0.0',
}
```

README 中如果写的是 `5173`，应以 Vite 配置和实际启动输出为准。Vite 还根据 `VITE_API_BASE` 和 `VITE_API_PROXY` 配置开发代理。

---

## 3. 路由树和登录保护

文件：

- `frontend/src/router/routes.tsx`
- `frontend/src/router/index.tsx`
- `frontend/src/components/auth-guard/index.tsx`
- `frontend/src/layout/base/index.tsx`

### 3.1 路由树

可以把当前路由简化成：

```text
/login                         LoginPage（不需要登录）
/
├── AuthGuard
│   └── BaseLayout
│       ├── /                    首页
│       ├── /chat                 新聊天
│       ├── /chat/:id             指定会话
│       ├── /knowledge            知识库
│       ├── /memory               记忆库
│       ├── /database             数据库
│       ├── /news                 行业资讯
│       └── /bidding              招投标
└── *                            重定向到 /404
```

`/chat` 和 `/chat/:id` 是同一业务域下的两个页面：前者负责开始新会话，后者负责读取指定会话并显示消息。

### 3.2 `AuthGuard` 的行为

`AuthGuard` 从 Valtio 的 `authState` 读取 `isLoggedIn`：

```tsx
if (!isLoggedIn) {
  return <Navigate to="/login" state={{ from: location }} replace />
}
```

登录守卫只决定浏览器是否渲染页面。它不是后端安全边界，因为用户可以直接调用 API。真正的权限校验仍必须在 FastAPI 路由和服务端完成。

### 3.3 `BaseLayout` 和导航

`BaseLayout` 把页面分为侧边栏和内容区：

```text
BaseLayout
├── sidebar
│   ├── Nav
│   └── Footer
└── content
    └── 当前路由页面
```

`Nav` 除了页面导航，还从 `industryState` 读取当前行业。切换行业会写入 `localStorage`，新闻、招投标和推荐问题等页面会使用这个行业 ID。

---

## 4. Axios 请求插件链

### 4.1 创建请求实例

文件：`frontend/src/api/request/request.ts` 和 `frontend/src/api/request/index.ts`

默认请求实例类似：

```ts
export const request = createRequest({
  baseURL: import.meta.env.VITE_API_BASE,
  loading: true,
  errorToast: true,
  cancelRepeat: true,
  unwrap: true,
})
```

`createRequest()` 创建 Axios 实例，然后安装五个插件：

```text
authPlugin
servicePlugin
loadingPlugin
repeatPlugin
errorToastPlugin
```

项目定义了 `preinstall`、`install` 和 `postinstall` 三个阶段，用于控制拦截器安装顺序。阅读插件时要区分“请求拦截器”和“响应拦截器”。

### 4.2 认证插件：自动加 JWT

文件：`frontend/src/api/request/plugins/auth.ts`

插件从 `localStorage.auth` 读取 token，并加入：

```http
Authorization: Bearer <token>
```

这让业务 API 文件不需要每次手写 token。`authState` 的订阅逻辑负责把登录状态同步到同一个 `auth` 存储键。

### 4.3 服务响应插件：检查业务状态

文件：`frontend/src/api/request/plugins/service.ts`

后端响应如果包含 `status` 字段，插件要求它等于 `success`。否则构造 `ResponseError` 并进入统一错误链。

这说明项目同时存在两层状态：

```text
HTTP 状态：网络层是否成功，例如 200、401、500
业务 status：应用层是否成功，例如 success 或错误状态
```

只判断 HTTP 200 不够，因为后端可能返回 HTTP 200 但业务处理失败。

### 4.4 Loading 插件：全局请求计数

文件：`frontend/src/api/request/plugins/loading.ts`

当请求配置 `loading: true` 时：

```text
请求发出 → requestCount + 1 → 显示全屏 Spin
响应成功或失败 → requestCount - 1
计数归零 → 隐藏 Spin
```

DeepResearch 流请求显式使用 `loading: false`，因为研究过程有自己的消息加载状态和步骤状态，不能用普通短请求的全局 Spin 代替。

### 4.5 重复请求插件

文件：`frontend/src/api/request/plugins/repeat.ts`

插件使用：

```text
请求方法 + URL + repeatKey
```

生成重复请求键。若同一个请求再次发出，前一个请求的 `AbortController` 会被触发。取消重复请求产生的 `CanceledError` 不会向用户弹错误提示。

这适合防止按钮重复点击或组件重复触发查询，但不能把它误认为研究任务取消。研究取消还会调用后端的 `/research/cancel/{session_id}`。

### 4.6 错误提示插件

文件：`frontend/src/api/request/plugins/error-toast.ts`

插件把以下信息统一转成页面提示：

- `ResponseError.message`
- 后端响应中的 `message` 或 `error`
- 网络错误消息
- 特定 HTTP 状态，例如 429

重复请求被取消时不弹提示，否则用户会看到不必要的“错误”。

---

## 5. 状态管理和持久化

### 5.1 认证状态

文件：`frontend/src/store/auth.ts`

`authState` 包含：

```ts
{
  token: string | null,
  user: UserInfo | null,
  isLoggedIn: boolean
}
```

它通过 `proxy()` 创建，通过 `subscribe()` 自动保存到 `localStorage.auth`。登录、退出和更新用户由 `authActions` 统一完成。

当前实现的边界：前端清除 token 不等于服务端撤销 JWT。项目当前没有看到服务端 JWT 黑名单或撤销表，因此 token 的有效期和服务端验证仍是关键安全边界。

### 5.2 搜索模式状态

文件：`frontend/src/store/device.ts`

`deviceState.searchModes` 支持：

```ts
type SearchMode = 'web' | 'local'
```

含义是：

- `web`：允许网络搜索。
- `local`：允许本地知识库检索。

DeepResearch 发送请求时直接把它传给后端：

```ts
search_modes: deviceState.searchModes as string[]
```

因此搜索模式开关不只是界面状态，它会改变后端研究请求的输入。

### 5.3 行业状态

文件：`frontend/src/store/industry.ts`

行业状态提供：

- 当前行业 ID
- 预定义行业列表
- 新闻关键词
- 招投标关键词
- 研究关键词

当前行业 ID 保存在 `localStorage.selected_industry_id`。新聊天页会根据当前行业生成推荐问题，并在请求行业资讯和招投标数据时传入行业 ID。

### 5.4 会话状态

文件：`frontend/src/store/session.ts`

`sessionState` 管理：

```ts
{
  sessions: Session[],
  currentSession: SessionWithMessages | null,
  loading: boolean,
  error: string | null
}
```

它负责调用 `/sessions` 系列接口，但聊天页面自身还维护高频变化的 `chat.list`。两者分工是：

```text
sessionState：服务端会话列表、当前会话和持久化数据
chat.list：当前页面即时显示的用户消息和助手消息
```

---

## 6. 新聊天页如何选择请求类型

文件：`frontend/src/pages/chat/newchat.tsx` 和 `frontend/src/pages/chat/index.tsx`

### 6.1 新聊天页

用户在 `/chat` 输入问题后，新聊天页会：

1. 根据当前行业显示推荐问题和热门资讯。
2. 如果尚未有会话，调用 `createSession()` 创建 PostgreSQL 会话。
3. 如果有附件，先上传到 `/attachments`。
4. 把消息、附件和会话 ID 传到 `/chat/:id`。

### 6.2 三条发送分支

`chat/index.tsx` 的 `sendChat()` 根据消息类型选择接口：

```text
Deepsearch 消息
  → api.session.deepsearch()
  → POST /research/stream

普通消息且有附件
  → api.session.chatWithAttachments()
  → POST /chat/completion/v3

普通消息且无附件
  → api.session.chat()
  → POST /chat/completion
```

DeepResearch 请求的主要数据是：

```json
{
  "query": "用户问题",
  "session_id": "会话 ID",
  "search_modes": ["web", "local"]
}
```

所有三条流式接口都使用 `responseType: 'stream'`、Fetch adapter 和 `Accept: text/event-stream`。

---

## 7. SSE 如何被浏览器解析

### 7.1 为什么使用 `ReadableStream`

研究过程不是一次性结果。后端会先发计划，再发搜索结果、分析结果、报告片段和最终完成事件。因此页面需要边接收边更新。

`sendChat()` 拿到响应后执行：

```ts
const reader = res.data.getReader()
await read(reader)
```

`read()` 的主要逻辑是：

```text
reader.read()
  → TextDecoder 解码字节
  → 追加到 temp 缓冲区
  → 按换行拆分
  → 只处理以 `data: ` 开头的行
  → JSON.parse
  → parseData(json)
```

保留 `temp` 很重要，因为一次网络读取可能只得到半行 JSON，也可能一次得到多行事件。不能假定每次 `reader.read()` 都刚好对应一个完整事件。

### 7.2 `[DONE]` 和流结束

如果事件内容是 `[DONE]`，解析器直接返回。真正的 `done` 会让当前聊天项结束 loading。研究取消时还会：

1. 调用 `reader.cancel()`。
2. 调用后端 `cancelResearch(sessionId)`。
3. 把正在运行的步骤标记为完成。

这体现了前端取消和后端取消的双向处理，单独取消浏览器读取并不能保证服务端 Agent 已经停止。

---

## 8. DeepResearch 事件到前端数据的映射

### 8.1 `research_start`

收到事件后：

- 把当前消息设为研究模式。
- 清空 `researchSteps`。
- 清空 `researchDetailsRef`。
- 清空选中的研究详情。
- 重置 `researchDataVersion`。

它相当于一次研究任务的 UI 初始化边界。

### 8.2 `research_step`

事件中的 `step_type` 可能是 `planning`、`researching`、`analyzing`、`writing` 等。前端做两件事：

```text
researchSteps：保存步骤条、状态和统计数字
researchDetailsRef：为该步骤创建详情对象
```

项目故意使用 `stepType` 作为详情 Map 的 key，使后续事件能够稳定找到 `analyzing` 或 `writing` 对应的数据。

后端 snake_case 统计字段会在此处转换为前端 camelCase，例如：

```text
results_count → resultsCount
charts_count  → chartsCount
word_count    → wordCount
```

### 8.3 `search_results`

前端优先找到 `searching`，否则使用 `researching` 详情，把结果转换成：

```ts
{
  id,
  title,
  source,
  date,
  url,
  snippet
}
```

如果事件声明增量模式，就追加到旧数组；否则替换旧数组。然后更新步骤统计和 `researchDataVersion`。

### 8.4 `knowledge_graph`

前端优先把图谱写入 `analyzing`，若没有该步骤则回退到 `researching` 或 `searching`。图谱包含：

```text
nodes：实体节点
edges：实体关系
stats：实体数和关系数
```

### 8.5 `charts`

图表事件默认写入 `analyzing` 详情，同时复制到当前聊天项的 `target.charts`，这样报告视图也能使用同一组图表。

图表有两种来源：

- `echarts_option`：浏览器调用 ECharts 绘制。
- `image_base64`：浏览器直接显示后端生成的 PNG。

### 8.6 `phase` 和 `outline`

`phase` 用于追加研究过程中的阶段说明，并把写作、审核、补充搜索和修订阶段映射到步骤条。

`outline` 会被格式化成 Markdown，追加到聊天消息的研究过程记录中。它与最终报告不同，前者是计划展示，后者是最终产物。

### 8.7 `research_complete`

完成事件会：

1. 把 `final_report` 写到当前助手消息的 `content`。
2. 把报告写入 `writing` 或 `generating` 详情的 `streamingReport`。
3. 把引用转换为前端 `reference`。
4. 把所有研究步骤标记为 `completed`。
5. 增加 `researchDataVersion`，强制重新计算聚合数据。

---

## 9. 为什么同时使用 State、Ref 和版本计数器

这是本项目最值得理解的前端实现细节之一。

### 9.1 `researchSteps`：控制 React 渲染

```ts
const [researchSteps, setResearchSteps] = useState<ResearchStep[]>([])
```

步骤条需要随事件变化而渲染，所以使用 React state。

### 9.2 `researchDetailsRef`：保存高频增量数据

```ts
const researchDetailsRef = useRef<Map<string, ResearchDetailData>>(new Map())
```

搜索结果、图表和报告可能频繁到达。代码直接修改 Map 中的详情对象，避免每个小事件都复制整个嵌套对象树。

但 `useRef` 的内容变化不会自动触发 React 重新渲染，这就产生了第三个变量。

### 9.3 `researchDataVersion`：显式触发重算

```ts
const [researchDataVersion, setResearchDataVersion] = useState(0)
```

收到搜索结果、图谱、图表或最终报告后，代码调用：

```ts
setResearchDataVersion(v => v + 1)
```

`aggregatedResearchData` 把它放进 `useMemo` 依赖数组，因此 React 会重新读取 ref 中最新的数据。

设计可以概括为：

```text
state：触发结构化 UI 更新
ref：保存高频、可变、跨异步回调的数据
version：告诉 React “ref 里的数据现在值得重新读取了”
```

代价是代码复杂度较高，未来可以考虑使用 reducer 或不可变状态统一管理，但当前实现的意图是减少流式事件下的大对象复制。

---

## 10. 研究详情组件如何渲染

文件：`frontend/src/pages/chat/component/research-detail/index.tsx`

### 10.1 聚合数据

父页面先遍历 `researchDetailsRef`，生成一个 `aggregatedResearchData`：

```text
所有步骤的 searchResults 合并
取最新 knowledgeGraph
所有步骤的 charts 合并
取最新 streamingReport
所有章节 sections 合并
```

这样右侧面板不必让每个标签都自己查找所有步骤。

### 10.2 四个标签页

`ResearchDetail` 提供：

| 标签 | 组件 | 数据 |
|---|---|---|
| 搜索结果 | `SearchResults` | `searchResults` |
| 知识图谱 | `KnowledgeGraph` | `knowledgeGraph` |
| 可视化图表 | `Visualization` | `charts` |
| 过程报告 | `ProcessReport` | `streamingReport`、`sections`、`charts` |

步骤条位于标签页上方。已完成步骤可以点击，父页面通过 `handleResearchStepClick()` 从 Map 中取出对应详情。

### 10.3 知识图谱

`knowledge-graph.tsx` 使用 `echarts-for-react` 的 graph 类型，把节点和边转换成 ECharts option。节点类型会映射成不同颜色，边的 `relation` 作为标签显示。

这意味着后端只需提供结构化的 nodes/edges，具体布局和画布渲染由前端负责。

### 10.4 图表

`visualization.tsx` 按优先级选择渲染方式：

```text
有 image_base64 → <img>
否则有 echarts_option → <ReactECharts>
否则 → 空数据占位
```

这兼容 CodeWizard 生成的 matplotlib 图片和前端 ECharts 配置。

### 10.5 过程报告和图表插入

`process-report.tsx` 支持章节草稿和最终报告两种视图。最终报告中的 Markdown 图片占位符会被解析：

```markdown
![图表标题]()
```

组件会根据占位符文字与图表标题做简单文本相似度匹配，把对应图表插回报告。未匹配的图表还会尝试按章节标题插入，最后均匀分配到章节或参考文献前。

这不是后端 Markdown 引擎自动完成的，而是前端在显示阶段做的内容增强。

---

## 11. 历史消息和检查点恢复

页面进入 `/chat/:id` 后，至少有两条恢复路径。

### 11.1 恢复会话消息

页面优先使用 `sessionState.currentSession` 中预加载的消息；如果没有，则调用：

```text
GET /sessions/{id}
```

消息被转换成 `chat.list`。当前代码对历史助手消息存在一个启发式判断：内容长度超过 1000 时可能标记成 Deepsearch。这个判断不能保证覆盖所有研究消息，因此检查点恢复还会显式把最后一条助手消息改成 `ChatType.Deepsearch`。

### 11.2 恢复研究检查点

页面调用：

```text
GET /research/checkpoint/{session_id}/full
```

如果状态是 `completed` 或 `running`，则从 `ui_state_json` 恢复：

- `research_steps`
- `search_results`
- `charts`
- `knowledge_graph`
- `streaming_report`

如果缺少步骤数据，前端会根据可用信息创建默认的 planning、researching、analyzing、writing 步骤。

恢复后重新构造 `researchDetailsRef`，增加 `researchDataVersion`，再让 `ResearchDetail` 显示恢复出的研究详情。

### 11.3 持久化边界

研究消息写库发生在流读取完成后，前端调用 `addMessage()` 保存用户消息和助手回复。因此如果浏览器在流完成前关闭，不能假定最后一条助手消息一定已经持久化；检查点是否已经保存还取决于后端的 checkpoint 写入时机。

---

## 12. 一次 DeepResearch 请求的浏览器端时序

```text
用户打开 /chat
  → NewChat 创建或准备 session
  → 用户打开 web/local 搜索模式
  → 用户发送问题
  → chat/index.tsx 创建用户消息和空助手消息
  → deepsearch() 发起 POST /research/stream
  → reader.read() 循环接收 SSE
  → research_start 清理旧研究状态
  → research_step 创建步骤和详情 Map
  → search_results 写入搜索详情
  → knowledge_graph 写入分析详情
  → charts 写入分析详情和助手消息
  → phase / outline 更新过程记录
  → research_complete 写入最终报告和引用
  → researchDataVersion 触发聚合
  → ResearchDetail 展示四个标签
  → addMessage() 保存用户消息和助手消息
```

这条时序可以和后端的：

```text
research_router
  → DeepResearchV2Service
  → Graph._run_simplified
  → 六个 Agent
  → SSE
```

首尾拼接起来，形成完整的端到端数据流。

---

## 13. 源码阅读练习

### 练习 1：路由保护

请说明：访问 `/knowledge` 时，为什么页面不会在未登录状态直接显示？请指出 `routes.tsx` 和 `auth-guard/index.tsx` 中的证据。

### 练习 2：请求插件

假设 `/sessions` 返回 HTTP 200，但 JSON 是：

```json
{"status":"error","message":"数据库不可用"}
```

请说明哪个插件会把它变成异常，哪个插件会给用户显示提示。

### 练习 3：SSE 分帧

为什么 `read()` 不能直接对每次 `reader.read()` 的 `value` 执行一次 `JSON.parse()`？请用“半个 JSON 跨两个网络块”的例子解释。

### 练习 4：状态设计

如果只把搜索结果放在 `researchDetailsRef` 中，却不调用 `setResearchDataVersion()`，页面为什么可能不更新？

### 练习 5：后端到组件

请把以下事件各自连到最终组件：

```text
search_results
knowledge_graph
charts
research_complete
```

### 练习 6：恢复边界

浏览器刷新后，哪些数据来自 `/sessions/{id}`，哪些数据来自 `/research/checkpoint/{id}/full`？为什么不能只请求其中一个接口？

---

## 14. 面试官追问

1. 你们为什么选择 SSE，而不是等研究完成后返回一个大 JSON？
2. 前端如何处理一个 SSE 事件被拆成多个网络块的情况？
3. `useRef` 直接修改数据会不会触发 React 渲染？如果不会，项目如何补救？
4. `researchSteps` 和 `researchDetailsRef` 为什么不是同一个数据结构？
5. 前端的 `AuthGuard` 能否保证接口安全？
6. 普通消息、附件聊天和 DeepResearch 分别走哪些接口？
7. 研究完成后，助手消息什么时候写入数据库？中途刷新有什么风险？
8. 图表为什么同时支持 Base64 图片和 ECharts option？
9. 历史消息如何判断是不是 DeepResearch？这种判断有什么风险？
10. 如果后端事件名称改了，前端哪些地方必须同步修改？

---

## 15. 本课结论

这个前端不是简单的“调用接口然后显示文本”。它包含四个关键层次：

```text
路由层：决定用户能进入哪个页面
请求层：统一处理认证、业务错误、加载和重复请求
状态层：保存会话、搜索模式和研究增量数据
渲染层：把结构化研究产物组合成可交互详情
```

真正的 DeepResearch 页面体验来自后端 Agent 事件契约和前端状态映射的共同作用。理解 `research_step → researchDetailsRef → aggregatedResearchData → ResearchDetail` 这条链，就掌握了浏览器端最核心的实现。

---

## 16. 留白与我的笔记

### 16.1 我对前端请求链的理解

<!-- 在这里补充：从哪个按钮或组件发起请求，经过哪些函数，最后进入哪个后端接口。 -->



### 16.2 我还不懂的概念

<!-- 例如：SSE、ReadableStream、Axios 拦截器、Valtio、useRef 与 useState 的差异。 -->



### 16.3 我准备验证的运行现象

<!-- 记录你准备打开的页面、要观察的浏览器 Network 请求、控制台日志和预期结果。 -->



### 16.4 面试回答草稿

<!-- 用自己的话回答本课第 14 节的追问。 -->



