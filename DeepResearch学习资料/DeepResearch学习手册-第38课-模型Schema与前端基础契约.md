# DeepResearch 学习手册：第 38 课

## 模型、Schema 与前端基础契约

这一课补上项目中不直接产生研究结果、但决定数据能否在各层稳定流动的一组文件。学习主线是：

```text
数据库模型（SQLAlchemy）
  → Router / Service 查询和写入
  → Pydantic Schema 或 JSON
  → Axios 请求 / SSE 运行时数据
  → TypeScript 类型声明
  → React 状态与组件
```

先区分三类“类型”：

1. SQLAlchemy 模型描述数据库表和关系，主要在后端使用。
2. Pydantic Schema 描述 HTTP 请求和响应，负责校验、转换和文档生成。
3. TypeScript 类型只在前端编译期帮助开发者，运行时不会替后端校验数据。

## 1. SQLAlchemy 模型：数据库中的长期事实

入口文件：

```text
D:\课\s4-6\industry_information_assistant\backend\app\models\__init__.py
```

`models/__init__.py` 集中导出 `User`、`ChatSession`、`ChatMessage`、`ChatAttachment`、`LongTermMemory`、`KnowledgeBase`、`Document`、行业数据、`ResearchCheckpoint`、新闻和招投标模型。`app_main.py` 导入模型后，`Base.metadata.create_all()` 才能看到这些表定义。

### 1.1 用户和会话关系

```text
User
 ├─ ChatSession
 │   ├─ ChatMessage
 │   │   └─ ChatAttachment
 │   ├─ ChatAttachment
 │   └─ LongTermMemory
 ├─ KnowledgeBase
 │   └─ Document
 └─ ResearchCheckpoint
```

`ForeignKey` 保存数据库层的归属约束，`relationship` 让 SQLAlchemy 可以从对象层访问关联数据。`ondelete="CASCADE"` 表示删除用户或会话时，相关记录可以级联删除；研究检查点的用户关系则使用可为空的外键，允许检查点在特定场景下没有用户。

### 1.2 三种看起来相似、实际不同的文档

| 对象 | 表 | 用途 |
|---|---|---|
| `Document` | `documents` | 知识库里的文档元数据，后续解析并写入向量库 |
| `ChatAttachment` | `chat_attachments` | 某次聊天上传的附件，归属于会话或消息 |
| `DocumentResponse`（旧 Schema） | 无数据库表 | 旧外部文档服务的接口返回格式 |

看到 `Document` 这个名字不能直接断言它属于同一条链路，要结合导入路径和调用它的 Router 判断。

### 1.3 `ResearchCheckpoint` 的三层保存

`models/research.py` 中的字段有三个需要分开记忆：

- `state_json`：后端 `ResearchState` 的完整快照。
- `ui_state_json`：前端研究步骤、搜索结果、图表、图谱和报告等恢复数据。
- `final_report`：便于列表或完成结果直接读取的报告文本。

这三个字段不是重复保存同一个对象，而是分别服务后端继续处理、前端重建界面和快速展示。

## 2. Pydantic Schema：接口边界上的形状

主要目录：

```text
backend/app/schemas/
```

### 2.1 请求 Schema 和响应 Schema

以聊天为例：

```text
ChatRequest
  session_id?
  question
  search_knowledge
  search_web

ChatResponse
  role
  content
  thinking?
```

`ChatRequest` 是进入后端时校验的形状，`ChatResponse` 是普通聊天响应的形状。研究 SSE 不是靠一个完整的 `ChatResponse` 表达，而是通过事件中的 JSON 字段，因此前端还要对事件类型做运行时分支。

### 2.2 Schema 的三个作用

1. **校验**：缺少必填字段或类型不对时，在进入业务函数前失败。
2. **转换**：例如 UUID、日期和数据库对象可以按响应模型转换成接口可传输的值。
3. **生成文档**：FastAPI 可以根据 Schema 生成 OpenAPI 描述。

`Config.from_attributes = True` 允许响应模型从 SQLAlchemy 对象属性读取数据；它不会自动替业务逻辑补充数据库没有的字段。

### 2.3 兼容接口为什么有两套类型

`schemas/chat.py` 同时存在新的 `SessionResponse` 和 `LegacySessionResponse`。这说明项目保留了旧的 `/chat/session` 或 Redis 会话接口，同时新增了 PostgreSQL 会话接口。学习接口时，必须把“当前主链路”和“兼容旧调用方”分别记录，不能只看类名推断谁在使用。

## 3. 前端声明：让 TypeScript 看懂后端数据

### 3.1 全局 API 类型

`frontend/src/api/type.d.ts` 声明了：

```ts
declare namespace API {
  type Result<T> = T & {
    status: 'success' | 'error'
    message: string
  }
}
```

这只是编译期命名空间。它不会在浏览器中检查后端是否真的返回了 `status` 和 `message`。

`api/session.type.d.ts` 进一步描述 `API.ChatItem`、`ResearchPlan`、`ReactStep`、`ChartConfig`、`StockQuoteData`、`Document` 和 `Reference`。这些字段把普通聊天、V1 ReAct、V2 研究、股票卡片和引用集中映射到前端消息对象上。

一个关键边界是：SSE 中的 `research_step`、`search_results`、`chart` 等事件来自运行时 JSON；TypeScript 声明只能帮助后续代码访问字段，不能防止服务端发送错字段。因此 `chat/index.tsx` 仍然要判断 `json.type`、`json.content` 和字段是否存在。

### 3.2 `vite-env.d.ts` 的全局窗口对象

该文件引用 Vite 类型，并给 `Window` 增加 `$app`、`$showLoading`、`$hideLoading`。这是为了让全局 UI 能力在 TypeScript 中有类型提示。它不负责创建这些对象；真正的赋值逻辑要去 `main.tsx` 或请求插件中查找。

## 4. Axios 请求层：一份请求如何被加工

入口：

```text
frontend/src/api/request/request.ts
frontend/src/api/request/index.ts
frontend/src/api/request/plugins/
```

`createRequest()` 创建 Axios 实例并安装 `authPlugin`、`servicePlugin`、`loadingPlugin`、`repeatPlugin` 和 `errorToastPlugin`。插件的安装顺序由 `installPlugins()` 的生命周期阶段决定：先执行所有 `preinstall`，再执行所有 `install`，最后执行所有 `postinstall`。数组顺序和拦截器实际生效顺序不能简单画成一条调用链，必须再看各插件注册的是请求拦截器还是响应拦截器。

`api/request/index.ts` 的默认配置说明：

- `baseURL` 来自 `VITE_API_BASE`。
- 默认显示加载状态。
- 默认显示错误提示。
- 默认取消重复请求。
- `unwrap: true` 表示响应可能被统一插件解包，调用方不一定拿到原始 Axios 响应。

这也解释了为什么页面中的 API 调用有时直接访问 `res.data`，有时要兼容 `(res as any).data || res`：项目同时存在经过解包和未完全统一的调用方式。

## 5. 导航和一次性页面传值

### 5.1 `NavItem` 和 `Nav`

`layout/base/nav-item.tsx` 是一个可复用链接组件。它接收 `href`、`active`、`onClick` 和可选红点：

- 没有 `onClick` 时，正常通过 React Router 跳转。
- 有 `onClick` 时，先 `preventDefault()`，由回调接管行为。

`nav.tsx` 利用这个分支打开会话抽屉、显示“暂未开放”或进入页面。当前 `/memory` 页面和 API 已存在，但导航项仍通过 `onClick` 显示“暂未开放”，这是入口行为和实际功能不一致的证据。

### 5.2 `usePageTransport`

`utils/usePageTransport.ts` 使用模块级 `Map<Symbol, data>`：

```text
来源页面 setPageTransport(key, data)
  → React Router 跳转
  → 目标页面 usePageTransport(key)
  → 读取一次后删除 Map 中的数据
```

它适合把“从首页进入聊天时要自动发送的初始问题”传给聊天页。它不是 localStorage、数据库或 URL 参数，因此刷新页面、关闭标签页或目标组件未及时挂载时，数据不会被当作持久状态保存。

`pages/chat/shared.ts` 定义了 `transportToChatEnter`，并用自增数字生成前端聊天项 id。这个 id 只用于 React 页面内的 DOM 锚点和列表识别，不等同于数据库中的 UUID。

## 6. 附件选择组件和附件链路

`pages/chat/component/select-file.tsx` 负责展示后端返回的相关合同文档，让用户多选后点击 Add：

```text
API.Document[]
  → Checkbox.Group 保存 document_id[]
  → 过滤回完整 Document[]
  → onSubmit(list)
```

它有三个状态组件：`ChooseFile`、`ChooseFile.Searching` 和 `ChooseFile.Complete`。这里的 `API.Document` 是文档引用的前端结构，不等于浏览器 `File`，也不等于后端 SQLAlchemy `Document`。真正的本地文件上传走 `sender`、`attachment_router.py` 和 `ChatAttachment` 链路；选择相关合同属于研究结果或旧文档检索展示链。

## 7. Valtio 持久化：状态如何写入存储

`store/valtio-persist.ts` 提供通用 `proxyWithPersist()`，核心过程是：

```text
initialState 创建 Valtio proxy
  → 异步 getStorage()
  → 读取 SingleFile 或 MultiFile
  → 对比版本并执行 migrations
  → 监听 proxy 变化
  → setItem/removeItem 写回存储
  → _persist 标记 loaded / error
```

`PersistStrategy.SingleFile` 把一个路径整体写成一个键；`MultiFile` 会按叶子字段拆成多个键。`_persist` 元数据保存版本和加载状态，并且主对象持久化时会排除 `_persist` 本身。

这套工具与 `store/industry.ts` 里直接使用 `localStorage.selected_industry_id` 不是同一机制：`proxyWithPersist()` 是可复用的版本化状态持久化工具，行业状态的 localStorage 读写是具体业务代码。

## 8. 加载动画和枚举

- `components/spin/spinner.tsx` 是纯展示组件，使用 CSS 三个 bounce 元素，不负责请求状态判断。
- `configs/enum.ts` 集中定义 `ChatRole.User/Assistant` 和 `ChatType.Normal/Deepsearch`。
- 枚举值最终会进入 `API.ChatItem.type`，影响普通聊天和 DeepResearch 的布局、SSE 解析、右侧研究详情和恢复逻辑。

## 9. 一次完整的类型与状态追踪

以从首页带问题进入聊天为例：

```text
首页业务对象
  → setPageTransport(transportToChatEnter, { message })
  → /chat 路由
  → usePageTransport 读取并删除临时值
  → chat/index.tsx 的 useEffect 调用 send()
  → API.session.deepsearch()
  → SSE JSON
  → ChatType.Deepsearch + ResearchStep + ResearchDetailData
  → 右侧研究详情和最终报告
```

如果要排查问题，按这条顺序检查：来源页面是否调用了 `setPageTransport`；目标页是否在首次挂载时读取；`send()` 是否收到消息；请求是否进入 `/research/stream`；SSE 的 `type` 和 `content` 是否符合前端分支；`researchDataVersion` 是否递增。

## 10. 本课练习

### 练习 A：区分三种 Document

分别写出 `backend/app/models/knowledge.py`、`backend/app/schemas/knowledge.py`、`backend/app/schemas/document.py` 中文档对象的用途、字段来源和调用方。

### 练习 B：追踪一个深度研究事件

从 `graph.py` 发出的一个 `research_step` 事件开始，找到 `frontend/src/pages/chat/index.tsx` 中更新 `researchSteps` 的代码，再说明它如何影响 `ResearchDetail`。

### 练习 C：解释请求插件

不看答案，说明 `authPlugin`、`loadingPlugin`、`repeatPlugin`、`errorToastPlugin` 分别解决什么问题，并指出它们属于前端体验层还是安全校验层。

### 练习 D：说明持久化边界

回答：为什么 `usePageTransport()` 不能替代 `localStorage`？为什么 `proxyWithPersist()` 的 `_persist.loaded` 不能证明后端数据库可用？

## 11. 面试追问

1. SQLAlchemy 模型、Pydantic Schema、TypeScript interface 三者分别在哪个边界生效？
2. 为什么前端有 `API.ChatItem` 类型，仍然需要对 SSE JSON 做运行时判断？
3. 删除 `ChatSession` 时，哪些关联数据可能级联删除？依据是什么？
4. 为什么 `Document`、`ChatAttachment` 和旧文档服务的 `DocumentResponse` 不能混为一谈？
5. `usePageTransport` 的数据为什么刷新页面会丢失？
6. `researchDataVersion` 在研究详情中解决了什么问题？

## 12. 本课结论

这组基础文件的作用不是创造一个新业务功能，而是把“数据库对象、接口 JSON、前端状态和组件展示”接起来。真正读懂项目时，不能只看 Agent 文件；还要能从一个字段追踪它经过的每个边界，并知道每一层的类型检查是否在运行时真实存在。

