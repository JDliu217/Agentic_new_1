# DeepResearch 学习手册：第 39 课

## 前端基础展示与路由辅助模块

第 38 课解释了数据契约。本课把那些不承载核心业务算法、但会影响页面能否正确显示和跳转的前端文件串起来。

## 1. 路由辅助模块

### 1.1 `RouterContext`

`frontend/src/router/context.ts` 用 React Context 保存 `createBrowserRouter()` 返回的路由对象。它的作用是让自定义 hook 可以访问当前路由表，而不用把 router 作为每个组件的参数层层传递。

### 1.2 `useRoute()` 和 `useQuery()`

`router/hook.ts` 提供两个读取工具：

- `useRoute()` 通过 `matchRoutes(router.routes, pathname)` 找到当前匹配的最深层路由，因此可以读取路由对象上的自定义元数据。
- `useQuery()` 把 `location.search` 包装成 `URLSearchParams`，组件可以读取 URL 查询参数。

它们只读取路由状态，不负责跳转。跳转仍由 React Router 的 `Link` 或 `useNavigate` 完成。

## 2. 聊天消息的展示层

### 2.1 `ChatMessage`

`pages/chat/component/chat-message.tsx` 根据 `ChatRole` 分支：

```text
user      → UserMessage：显示用户文本
assistant → AssistantMessage：交给 Result，再根据 loading 显示 ComSpinner
```

它只负责消息列表的分派和展示，不负责发送请求。请求发生在父组件 `pages/chat/index.tsx`，这是典型的“父组件管理数据和动作，子组件负责展示”的 React 分层。

### 2.2 `Drawer`、`Section` 和 `Source`

- `Drawer` 提供右侧来源或详情面板的外框和滚动内容区域。
- `Section` 用 Ant Design `Collapse` 把一块详情变成可展开区域，`defaultOpen` 只影响初始展开状态。
- `Source` 接收 `API.ChatItem['search_results']`，把网页来源渲染成可点击链接、站点图标、主机名和标题。

这些组件不改变搜索结果。若来源为空，应回到 `chat/index.tsx` 检查 `search_results` 是否被 SSE 解析或历史消息恢复逻辑写入。

### 2.3 `news.tsx` 的静态数据边界

聊天组件目录中的 `news.tsx` 使用 `configs/data/news.ts` 静态数据，并通过 `useRequest` 包装成页面状态。它显示的统计数字和新闻不是新闻采集服务的实时数据库结果。真实行业资讯页面应看 `pages/news/index.tsx`、`api/news.ts` 和后端 `news_router.py`。

这是一个重要识别方法：同名“新闻”功能可能存在演示组件和真实业务页面，必须沿 import 链判断数据来源。

## 3. 图表类型与数据契约

`components/chart/types.ts` 定义图表展示侧的 `ChartType`、`ChartData`、`EChartsOption`、`ChartConfig` 和 `DataInsight`。

```text
DataInsight.visualization_hint
  → 提示建议图表类型

ChartConfig.echarts_option
  → 具体 ECharts 配置

Chart 组件
  → 把 option 交给 ECharts 实例渲染
```

`visualization_hint` 只是建议，不等于已经生成了图表；V2 研究图表需要沿 DataAnalyst、CodeWizard、SSE `chart` 事件和研究详情组件继续追踪。类型文件没有执行逻辑，也不会验证 ECharts 配置是否真的可渲染。

## 4. 请求错误类型和插件基础设施

`api/request/error.ts` 的 `ResponseError` 在普通 `Error` 上附加可选 Axios 响应。它让错误处理代码既能读取人类可读的错误消息，也能读取状态码或后端响应体。

`api/request/plugins/plugin.ts` 定义插件生命周期：

```text
preinstall → install → postinstall
```

`installPlugins()` 对 `preinstall` 反向遍历，对另外两个阶段正向遍历。理解这一点有助于排查拦截器先后顺序，但真正的认证、加载、重复请求和提示行为仍要看各个具体插件。

## 5. 布局、用户菜单和登出

`layout/base/footer.tsx` 从 `authState` 读取当前用户，显示头像、用户名和邮箱。点击退出时：

```text
authActions.logout()
  → 清理前端认证状态
  → message.success()
  → navigate('/login')
```

这只是前端会话退出。后端 JWT 本身通常是无状态令牌，真正的后端权限仍由每次请求携带的令牌和服务端校验决定。若需要服务端强制失效，还需要黑名单或短时令牌等机制，项目当前不能仅凭这个组件推断已经实现。

## 6. 存储适配器

`store/storage.ts` 把浏览器 `localStorage` 适配成 `ProxyPersistStorageEngine`：

```text
getItem / setItem / removeItem / getAllKeys
```

它本身没有状态业务，只是给第 38 课的 `proxyWithPersist()` 提供存储实现。因此：

- `storage.ts` 负责“在哪里读写”。
- `valtio-persist.ts` 负责“如何版本化、监听和迁移”。
- 具体 store 负责“保存什么业务状态”。

## 7. 静态资源和兜底页

- `configs/data/host.ts` 是站点名称和域名的静态配置，不能当作实时站点可用性检查结果。
- `components/spin/spinner.tsx` 是加载动画，不等同于请求进度。
- `pages/404.tsx` 是未匹配路由的展示兜底，不负责记录后端错误。
- `layout/base/footer.tsx`、`nav.tsx` 和 `page-layout` 共同构成登录后页面的外壳。

## 8. 前端低风险文件的阅读方法

遇到一个小组件时按四个问题判断它是否值得深入：

1. 它是否发起网络请求？若是，继续沿 API 和后端路由追踪。
2. 它是否改变全局状态？若是，追踪 store 和持久化。
3. 它是否改变路由或认证？若是，追踪 Router/AuthGuard/JWT。
4. 它是否只是把 props 显示成 DOM？若是，确认输入来源后即可归档。

按这个标准，`ChatMessage`、`Drawer`、`Section`、`Source` 和 `NotFound` 主要是展示层；`useRoute`、`useQuery` 是路由读取层；`storage` 和 Axios 插件属于基础设施层。

## 9. 本课练习

### 练习 A：定位静态新闻

说明聊天组件 `news.tsx` 和真实行业资讯页分别从哪里取数据，并指出如何避免把演示数据当作数据库数据。

### 练习 B：解释登出边界

说明 `authActions.logout()` 能解决什么问题，为什么不能据此断言已经撤销了服务端 JWT。

### 练习 C：追踪来源展示

从 `API.ChatItem.search_results` 出发，说明 `Source`、`Drawer` 和 `chat/index.tsx` 的关系。

## 10. 面试追问

1. 为什么 `ChatMessage` 不应该直接发起聊天请求？
2. `visualization_hint` 和真正的 ECharts option 有什么区别？
3. `RouterContext` 与 React Router 自带的 `useLocation` 分别解决什么问题？
4. `localStorage` 适配器和持久化策略为什么要拆成两个文件？
5. 如何判断一个“新闻”组件是演示数据还是实时业务数据？

