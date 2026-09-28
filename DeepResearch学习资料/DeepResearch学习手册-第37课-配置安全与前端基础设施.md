# DeepResearch 学习手册·第 37 课

## 配置、安全与前端基础设施

这一课把“业务代码之外的基础能力”串起来：后端如何读取 LLM、数据库和 JWT 配置，前端如何定义请求扩展和全局类型，以及页面之间如何传递一次性数据。

源码依据：

    D:\课\s4-6\industry_information_assistant\backend\app\config\llm_config.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\config.py
    D:\课\s4-6\industry_information_assistant\backend\app\core\database.py
    D:\课\s4-6\industry_information_assistant\backend\app\core\security.py
    D:\课\s4-6\industry_information_assistant\frontend\src\api\request\axios-extend.d.ts
    D:\课\s4-6\industry_information_assistant\frontend\src\api\session.type.d.ts
    D:\课\s4-6\industry_information_assistant\frontend\src\store\valtio-persist.ts
    D:\课\s4-6\industry_information_assistant\frontend\src\utils\usePageTransport.ts
    D:\课\s4-6\industry_information_assistant\frontend\src\configs\enum.ts

---

## 1. 后端配置的三种来源

项目里的配置大致分三层：

```text
环境变量
  → .env / Docker / 运行环境

配置对象
  → LLMConfig、ServiceConfig

业务服务
  → Graph、Agent、Router、数据库和外部 API
```

环境变量适合放密钥和部署差异；配置对象适合统一默认值和 Agent 参数；业务服务只应该消费配置，不应该在业务函数中散落密钥。

---

## 2. `LLMConfig` 管理什么

`llm_config.py` 用数据类集中管理：

- LLM API Key。
- LLM Base URL。
- Bocha 搜索 Key。
- 默认模型。
- 六个 Agent 的模型、temperature 和 max_tokens。
- 最大审核迭代次数。
- 每章节搜索数量。
- 最大图表数。
- 是否启用代码执行。
- 质量评分阈值。

六个 Agent 可以使用不同模型：规划、分析、代码、审核、写作通常使用较强模型，搜索阶段使用更快模型。这解释了为什么研究图构造时需要 `config.agents.architect.model`、`config.agents.scout.model` 等独立字段，而不是全流程只用一个模型。

`get_config()` 返回进程内单例；`reload_config()` 才会重新从环境变量创建配置。

---

## 3. 一个配置命名陷阱

`LLMConfig.base_url` 读取的是：

```text
LLM_BASE_URL
```

而项目示例环境配置主要写的是：

```text
DASHSCOPE_BASE_URL
```

其他服务又直接读取 `DASHSCOPE_BASE_URL`。如果部署时只设置其中一个，部分路径可能使用默认 URL，另一部分路径使用显式 URL。

学习和排错时必须把“变量名、读取位置、最终传入 OpenAI 客户端的值”连起来，不要只看 `.env.example` 的注释。

---

## 4. `ServiceConfig` 和旧兼容服务

`service/config.py` 给旧的 `ResearchService` 和外部文档服务提供：

- 外部文档服务 Base URL。
- RAGFlow 兼容 API Key。
- 默认数据集 ID。
- Serper API Key。
- Milvus 主机和端口。
- 政策集合名。
- Bocha 和 DashScope 配置。

这是一套兼容层配置，和 V2 `LLMConfig` 并不是同一个配置对象。阅读调用方时要确认它是 V1/旧文档链还是 V2 多 Agent 链。

当前实现对部分外部服务保留了硬编码默认值。即使环境变量会覆盖它们，也不应把密钥写进源码。正确做法是删除真实默认密钥、缺失时显式报错，并把示例值放在 `.env.example`。

---

## 5. 数据库连接和会话

`core/database.py` 根据 PostgreSQL 环境变量拼出连接 URL，创建：

```python
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(..., bind=engine)
Base = declarative_base()
```

FastAPI 路由通过 `get_db()` 获得请求级 Session，并在 `finally` 中关闭。

`pool_pre_ping=True` 只能帮助连接池发现失效连接，不能在 PostgreSQL 根本不可达时让应用自动启动。`app_main.py` 的导入阶段仍可能调用 `Base.metadata.create_all()`，所以数据库连通性是后端监听端口前的依赖。

---

## 6. JWT 和密码安全

`core/security.py` 使用：

- bcrypt 生成和校验密码哈希。
- JWT 编码访问令牌。
- `exp` 字段控制过期时间。
- `sub` 保存用户 ID。
- `username` 作为附加声明。

`decode_token()` 失败时返回 `None`，上层权限依赖再转换成未认证错误。

默认 JWT 密钥只是开发占位值，生产环境必须由环境变量提供随机密钥。前端保存 token 并自动附加 `Authorization: Bearer ...`，但前端 AuthGuard 不能替代后端 JWT 校验。

---

## 7. 前端 Axios 扩展不是后端字段

`axios-extend.d.ts` 为 Axios 增加项目自己的请求选项：

| 选项 | 用途 |
|---|---|
| `loading` | 是否显示全局加载遮罩 |
| `errorToast` | 请求失败时是否提示 |
| `cancelRepeat` | 是否取消重复请求 |
| `repeatKey` | 自定义重复请求键 |
| `unwrap` | 是否展开统一响应的 `data` |

这是 TypeScript 类型扩展。真正的行为由 request plugins 实现；声明文件本身不会改变运行时。

`session.type.d.ts` 则声明聊天、研究计划、图表、股票行情和引用的前端结构，帮助 SSE 处理代码在不同事件之间共享字段约定。

---

## 8. Valtio 持久化工具

`store/valtio-persist.ts` 提供通用的 `proxyWithPersist()`：

1. 创建带 `_persist` 元数据的 Valtio proxy。
2. 从存储引擎读取单文件或多文件状态。
3. 监听 proxy 变化。
4. 把变更写回存储。
5. 保存版本号。
6. 根据版本执行迁移函数。

它是一个通用工具，不代表每个 store 都自动持久化。要判断某个状态是否实际保存，必须继续找它是否调用了 `proxyWithPersist()`、使用了哪种存储引擎和版本迁移。

当前行业状态使用 `localStorage` 直接保存 `selected_industry_id`；这和通用持久化工具是两条不同实现。

---

## 9. 页面间一次性传值

`usePageTransport.ts` 用一个模块级 `Map<Symbol, data>` 做页面间临时传输：

```text
setPageTransport(key, data)
  → 目标页面 usePageTransport(key)
  → 首次挂载读取
  → 读取后删除
```

聊天页的 `shared.ts` 用它定义 `transportToChatEnter`，用于把进入聊天页时的初始消息传过去。

它不是 URL 参数、Redux 状态或数据库持久化；刷新页面、跨标签页或目标组件不挂载时，数据都不能当成可靠存储。

---

## 10. 前端类型和运行时的边界

例如 `API.ChatItem` 声明了 `stockQuote`、`charts`、`researchPlan` 等字段，但接口数据仍来自运行时 JSON。TypeScript 类型不会验证后端真的发来了这些字段；SSE 解析代码仍需处理缺失、空值和旧事件格式。

同理，`ChatRole` 和 `ChatType` 枚举只约束前端状态值，不会改变后端的 `role` 字符串或数据库列。

---

## 11. 配置排错方法

当 Agent 或数据库连接失败时按以下顺序：

1. 找到调用方使用的配置类或直接读取的环境变量。
2. 打印非敏感配置摘要：变量是否存在、URL、模型名、主机和端口。
3. 检查 `.env` 是否真的被 `load_dotenv()` 加载。
4. 确认不同兼容链路没有使用不同变量名。
5. 验证外部依赖连通性。
6. 查看请求是否在导入阶段、路由阶段还是 Agent 执行阶段失败。

不要把完整 API Key 打进日志；项目中的配置打印函数只输出前八位摘要，这种做法应保持。

---

## 12. 最小练习

### 练习 A：变量追踪

分别追踪 `DASHSCOPE_API_KEY`、`BOCHA_API_KEY`、`POSTGRES_HOST` 和 `JWT_SECRET_KEY`：写出它们在哪个文件被读取、传到哪个对象、最终被什么组件使用。

### 练习 B：识别假安全

解释以下说法为什么不成立：

```text
前端有 AuthGuard，所以后端接口安全。
TypeScript 声明了字段，所以 SSE 一定符合契约。
默认配置能连接本地，所以生产配置不需要检查。
```

### 练习 C：修复配置漂移

设计一个统一配置方案，使 LLM Base URL 只保留一个明确变量名，并让 V1、V2 和 Embedding 使用同一份配置读取逻辑。

---

## 13. 留给你的笔记区

### 我的环境变量地图



### 一个请求从前端类型到后端服务的路径



### 我发现的安全风险



