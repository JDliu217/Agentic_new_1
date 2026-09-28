# DeepResearch 学习手册·第 36 课

## 初始化脚本、测试夹具与前端页面地图

这一课收尾阅读那些容易被忽略、但决定项目能否被学习和运行的文件：数据库初始化 SQL、样例数据脚本、V2 测试脚本、前端路由和各业务页面。

源码依据：

    D:\课\s4-6\industry_information_assistant\docker\init-db\01-init.sql
    D:\课\s4-6\industry_information_assistant\backend\app\scripts\init_industry_data.py
    D:\课\s4-6\industry_information_assistant\backend\app\scripts\seed_industry_data.py
    D:\课\s4-6\industry_information_assistant\backend\app\scripts\test_deep_research_v2.py
    D:\课\s4-6\industry_information_assistant\backend\docker-compose-base.yml
    D:\课\s4-6\industry_information_assistant\frontend\src\router\routes.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\layout\base\nav.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\index\index.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\knowledge\index.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\memory\index.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\database\index.tsx

---

## 1. 数据库初始化分成两层

项目有两种数据库初始化来源：

```text
Docker 首次创建 PostgreSQL
  → docker/init-db/01-init.sql

应用启动/手动脚本
  → SQLAlchemy Base.metadata.create_all()
  → init_industry_data.py / seed_industry_data.py
```

SQL 文件适合创建固定基础表和示例查询数据；SQLAlchemy 模型适合让应用根据模型创建表。两者同时存在时，必须核对表名、列名和约束是否一致，不能默认“模型已经定义”就代表 Docker 初始化脚本也包含了它。

---

## 2. `01-init.sql` 创建了什么

初始化 SQL 包含：

- `users`：用户、密码哈希和权限。
- `chat_sessions`：会话及会话类型。
- `chat_messages`：消息、思考文本、引用 JSON 和图片结果 JSON。
- `knowledge_bases`、`documents`：知识库和文档状态。
- `long_term_memories`：摘要、关键洞察和 Milvus ID 数组。
- `restaurants`、`restaurant_orders`：餐饮 Text2SQL 示例。
- `stocks`、`stock_daily`：金融 Text2SQL 示例。
- `legal_cases`：法律示例。
- `vehicles`、`transport_records`：交通运输示例。

SQL 还创建更新时间触发器，让用户、会话、知识库和文档更新时自动刷新 `updated_at`。

这些示例表服务于数据库浏览和 Text2SQL 练习，不等于新闻、招投标或 DeepResearch 运行时数据。

---

## 3. 两套行业样例脚本不要混淆

### `init_industry_data.py`

它先创建模型表，再插入新能源汽车行业的：

- 行业统计。
- 企业数据。
- 政策数据。

脚本发现已有 `IndustryStats` 记录后会跳过样例插入，具有基本的重复执行保护。

### `seed_industry_data.py`

它面向智慧交通，分别插入：

- 市场规模、增长率、细分市场、投资、区域和季度数据。
- 头部、中型和新兴企业数据。
- 智慧交通政策数据。

这两个脚本的行业、数据量和入口不同。学习时先确认要初始化哪一套，不要连续执行后再把两套样例误认为同一份生产数据。

---

## 4. V2 测试脚本测什么

`test_deep_research_v2.py` 是一个人工端到端测试脚本，不是 pytest 单元测试。它会：

1. 检查 `DASHSCOPE_API_KEY` 和 `BOCHA_API_KEY`。
2. 创建 `DeepResearchV2Service`。
3. 使用较小的 `max_iterations=2`。
4. 发送新能源汽车市场研究问题。
5. 逐条解析 `data: ...` SSE。
6. 记录阶段、大纲、搜索结果、分析结果、报告和错误。
7. 最后检查关键阶段是否出现、是否收到结束标记。

这个脚本需要真实 LLM、搜索 API、数据库和相关中间件时，才能证明完整链路运行成功。没有 Key 时，它只会明确失败退出，不能用“脚本文件存在”证明端到端测试已经通过。

---

## 5. `backend/docker-compose-base.yml` 和根 Compose 的差异

后端目录的 `docker-compose-base.yml` 只启动：

- Redis。
- Milvus 所需的 etcd。
- Milvus 所需的 MinIO。
- Milvus standalone。

根目录 `docker-compose.yml` 还包含：

- PostgreSQL。
- Elasticsearch。

因此 README 中“基础服务全部启动”的理解要结合使用哪一个 Compose 文件。后端 base 文件没有 PostgreSQL，直接只启动它不能满足 `app_main.py` 的数据库依赖。

---

## 6. 前端路由地图

`routes.tsx` 在 `AuthGuard → BaseLayout → Outlet` 下挂载：

| 路由 | 页面 | 主要用途 |
|---|---|---|
| `/` | 首页 | 选择行业并进入聊天 |
| `/chat` | 新聊天 | 创建或开始会话 |
| `/chat/:id` | 聊天详情 | 普通聊天、DeepResearch 和附件 |
| `/knowledge` | 知识库 | 创建知识库、上传文档、查看切片 |
| `/memory` | 记忆库 | 查看、搜索和删除长期记忆 |
| `/database` | 数据库 | 浏览表、查询数据和 Text2SQL |
| `/news` | 行业资讯 | 新闻列表、统计和采集 |
| `/bidding` | 招投标 | 招标/中标列表、筛选和采集 |

未匹配路由跳转到 `/404`；`/login` 在外层单独渲染，不经过主布局。

---

## 7. 首页和行业状态

首页从前端 `INDUSTRY_CONFIGS` 生成四个行业卡片。点击卡片时：

```text
setCurrentIndustry(industryId)
  → Valtio industryState 更新
  → localStorage.selected_industry_id 持久化
  → navigate('/chat?title=...')
```

导航栏同样允许切换行业。新闻、招投标页面从 `industryState.currentIndustryId` 读取行业 ID，再把它作为请求参数传给后端。

前端维护了一份行业配置副本，后端也维护 `industry_config.py`。两份配置当前内容大体对应，但新增行业时需要同时修改，否则首页可能能显示一个行业，后端却回退到默认行业。

---

## 8. 知识库页面的工程动作

知识库页面调用 `store/knowledge.ts` 和 `api/knowledge.ts` 完成：

1. 获取当前用户知识库列表。
2. 创建、编辑、删除知识库。
3. 进入某个知识库后上传文档。
4. 显示 `pending/processing/completed/failed` 状态。
5. 对仍在处理的文档每 3 秒轮询一次。
6. 文档完成后打开切片抽屉。
7. 删除文档并刷新列表。

页面只负责交互和轮询；真正的解析、切片、Embedding 和 Milvus 写入由后端异步任务完成。浏览器显示“上传成功”不等于向量已经可以被检索，必须继续看文档状态。

---

## 9. 记忆页面和导航入口的不一致

`/memory` 页面本身已经实现：

- 获取当前用户记忆列表。
- 关键词语义搜索。
- 展开 `key_insights`。
- 删除记忆。
- 使用 dayjs 显示创建时间和相对时间。

但当前 `layout/base/nav.tsx` 的“记忆库”导航点击处理仍是：

```text
message.info('暂未开放')
```

因此“路由存在、页面存在、导航入口可达”是三个不同事实。直接访问 `/memory` 可以进入页面，点击侧边栏却不会导航，这是代码与产品入口不同步的明确例子。

---

## 10. 数据库页面的定位

数据库页面包含两条操作：

1. 选择表后查看表结构和分页数据。
2. 输入自然语言问题，调用 Text2SQL 并显示 SQL、解释、列和结果。

页面列名还会通过映射表显示中文名称。后端的表白名单、只读校验和 mock 数据路径决定了这个页面能查什么；前端表格本身不是安全边界。

SQL 初始化里的 `restaurants`、`stocks`、`legal_cases` 和 `vehicles` 等示例表，就是这个页面的练习数据来源之一。

---

## 11. 当前工程边界

1. SQL 初始化脚本和 SQLAlchemy `create_all()` 可能同时作用于数据库，迁移管理并不完整。
2. 根 Compose 和 backend base Compose 提供的服务集合不同。
3. 样例数据包含预测或演示数字，不能当作实时行业数据。
4. 前端与后端各有一份行业配置，存在漂移风险。
5. `/memory` 页面已实现，但侧边栏入口仍显示未开放。
6. V2 测试脚本是依赖外部服务的人工检查，不是隔离的自动化测试套件。
7. 当前环境没有完成 Docker、PostgreSQL、Redis、Milvus、LLM 和外部搜索的真实联通验证。

---

## 12. 最小练习

### 练习 A：启动依赖

说明为什么只执行 `backend/docker-compose-base.yml` 不能保证后端能启动；列出缺少的服务。

### 练习 B：页面入口排错

用户说“记忆库功能不存在”，请按顺序检查：

1. `routes.tsx` 是否有 `/memory`。
2. `pages/memory/index.tsx` 是否有实际请求。
3. `layout/base/nav.tsx` 点击是否导航。
4. 最终判断是功能缺失还是入口未接通。

### 练习 C：样例数据追踪

从 SQL 中任选 `stocks` 或 `restaurants`，追踪它如何被数据库页面或 Text2SQL 查询使用，并指出它与实时股票 API 的区别。

---

## 13. 留给你的笔记区

### 项目启动依赖图



### 页面路由地图



### 我发现的代码和产品不一致



