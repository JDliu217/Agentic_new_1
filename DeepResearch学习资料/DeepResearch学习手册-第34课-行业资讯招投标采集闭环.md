# DeepResearch 学习手册·第 34 课

## 行业资讯、招投标与定时采集闭环

这一课阅读 DeepResearch 的业务数据外围：行业配置如何决定搜索词，新闻和招投标怎样从外部 API 采集，怎样去重后写入 PostgreSQL，以及前端如何筛选和刷新这些数据。

源码依据：

    D:\课\s4-6\industry_information_assistant\backend\app\config\industry_config.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\news_collection_service.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\bidding_service.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\scheduler_service.py
    D:\课\s4-6\industry_information_assistant\backend\app\router\news_router.py
    D:\课\s4-6\industry_information_assistant\backend\app\models\news.py
    D:\课\s4-6\industry_information_assistant\frontend\src\api\news.ts
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\news\index.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\bidding\index.tsx

---

## 1. 先建立总链路

```text
前端选择行业
  → industry_id 进入列表或采集请求
  → industry_config 提供新闻/招投标关键词
  → NewsCollectionService 调用 Bocha 和 BiddingService
  → 外部结果标准化
  → source_url 或 bid_id 去重
  → IndustryNews / BiddingInfo 写入 PostgreSQL
  → /news/list 或 /news/bidding/list 返回分页和统计
  → React 页面更新列表、筛选和统计卡片
```

这条链路和 DeepResearch 搜索不是同一件事。它是“先采集、入库、再浏览”的行业资讯业务；DeepResearch V2 的 Scout 是在一次研究请求中即时搜索并分析。

---

## 2. 行业配置是关键词中心

`industry_config.py` 用 `IndustryConfig` 描述一个行业：

- `id`：机器使用的稳定标识。
- `name`：页面显示名称。
- `description`：行业说明。
- `news_keywords`：新闻采集关键词。
- `bidding_keywords`：招投标采集关键词。
- `research_keywords`：研究相关关键词。

当前预置：

```text
smart_transportation  智慧交通
finance               金融科技
healthcare            医疗健康
energy                能源电力
```

`get_industry_config(None)` 使用 `smart_transportation` 默认行业；传入未知 ID 时也会回退到默认行业并记录 warning。这样页面没有选择行业时仍能工作，但错误的行业 ID 不会被静默当成一个新行业。

---

## 3. 新闻采集：Bocha 到 IndustryNews

`NewsCollectionService._bocha_search()` 从环境变量读取：

```text
BOCHA_API_KEY
```

它向 Bocha 的 Web Search 接口发送关键词、摘要开关、数量和页码，之后把结果统一成：

```text
url / title / summary / snippet / siteName / datePublished
```

`collect_news()` 对当前行业的每个 `news_keywords` 循环搜索，并根据 `max_items` 计算每个关键词的采集额度。每一条结果会经过：

1. URL 是否存在检查。
2. 查询 `IndustryNews.source_url`，跳过已存在的 URL。
3. 解析发布时间；解析失败时尝试从摘要提取日期。
4. 根据标题和内容判断分类。
5. 推断发布部门。
6. 创建 `IndustryNews` 对象并加入当前事务。

资讯模型主要保存标题、摘要、来源、URL、分类、部门、发布时间、采集时间、关键词和已读状态。`source_url` 是当前新闻去重的关键字段。

---

## 4. 招投标采集：81API 到 BiddingInfo

`BiddingService` 从环境变量读取：

```text
BID_APP_CODE
```

它使用 81API 的三个端点：

```text
/queryWinBid       中标查询
/queryBid          招标查询
/queryBidDetail    标书详情
```

API 返回的字段名被 `BidInfo.from_dict()` 转成项目内部字段：

| 外部字段 | 内部字段 |
|---|---|
| `bid` | `id` |
| `title` | `title` |
| `noticeType` | `notice_type` |
| `province` | `province` |
| `city` | `city` |
| `publishTime` | `publish_time` |

`collect_bidding()` 对每个行业招投标关键词分别查询招标公告和中标信息。它按 `BiddingInfo.bid_id` 查询已有记录，避免同一项目重复写入。

如果 API 返回 403 且响应头表明 quota exhausted，服务会返回 `quota_exhausted=True`，采集循环停止，并把配额耗尽信息交给上层。

当前客户端使用 `verify=False` 访问 81API，因为源码注释说明该 API 的 SSL 证书和域名不匹配。这是明确的运行和安全边界，生产环境应重新评估证书和代理方案。

---

## 5. 采集任务记录和部分成功

新闻和招投标采集开始时都会创建 `NewsCollectionTask(status="running")`，结束时写入：

- `completed` 或 `failed`。
- `total_collected`。
- `error_message`。
- `started_at` 和 `completed_at`。

`collect_all()` 先执行新闻采集，再按 `BID_APP_CODE` 是否存在决定是否跳过招投标采集。返回结构同时包含 `news` 和 `bidding` 结果。

这里的 `success=True` 不代表每个关键词都成功。采集函数可以一边保存成功结果，一边把部分关键词的错误放进 `errors`；路由只把错误列表截取前 10 条返回前端。因此排查时要同时看成功数量和 errors。

---

## 6. 后端接口和一个容易忽略的细节

路由前缀是 `/news`：

| 接口 | 作用 |
|---|---|
| `GET /news/list` | 新闻分页、分类和行业筛选 |
| `GET /news/bidding/list` | 招投标分页、类型、省份和行业筛选 |
| `GET /news/stats` | 新闻和招投标统计 |
| `POST /news/collect` | 手动触发完整采集 |
| `GET /news/scheduler/status` | 查询定时任务 |
| `GET /news/check` | 检查是否有数据和近 24 小时新闻数 |
| `GET /news/industries` | 获取行业列表 |
| `GET /news/industries/{industry_id}` | 获取一个行业的关键词配置 |

`POST /news/collect` 的函数签名里声明了 `BackgroundTasks`，并定义了一个 `run_collection()`，但当前代码实际直接调用并等待 `service.collect_all()`，没有把这个函数加入 `background_tasks`。因此页面会等待采集结果返回，而不是立即拿到后台任务 ID。

---

## 7. 定时任务和启动初始化

`SchedulerService` 使用 APScheduler：

```text
每天 12:00 → _daily_collection_task()
```

每日任务创建独立数据库会话，执行默认行业的 `collect_all(max_news=20, max_bidding=20)`，结束后关闭会话。

应用启动时 `init_scheduler_and_check_data()` 会：

1. 启动调度器。
2. 创建数据库会话。
3. 检查是否已有新闻或招投标数据。
4. 没有数据时立即执行一次初始采集。
5. 最后关闭数据库会话。

所以“应用启动”可能触发外部 API 请求和数据库写入。启动成功不只取决于 HTTP 路由是否能导入，还取决于数据库和采集依赖是否可用。

---

## 8. 前端新闻页和招投标页

两个页面共用 `frontend/src/api/news.ts` 的 API 封装和采集结果模态框，但各自保存自己的状态。

新闻页：

- 使用 `category` 选择全部、政策、研报或新闻。
- 请求 `/news/list`。
- 显示总数、24 小时更新数和分类统计。
- 点击新闻打开 `source_url`。
- 行业切换或分类切换会重新请求并把页码重置为 1。

招投标页：

- 使用 `notice_type` 选择招标或中标。
- 使用 `province` 过滤省份。
- 请求 `/news/bidding/list`。
- 显示总数、招标数、中标数和省份覆盖数。
- 行业切换、类型或省份变化会重新请求并把页码重置为 1。

两个页面的“立即采集”都会调用 `POST /news/collect`，成功后刷新自己当前的列表。由于这个接口同时采集新闻和招投标，刷新新闻页并不表示招投标页面已经在当前页面刷新，反之亦然。

---

## 9. 当前实现的限制和风险

1. 新闻模型没有对 `source_url` 声明数据库唯一约束，去重主要依赖应用层查询；并发采集时仍可能产生竞态。
2. 招投标 `bid_id` 有唯一约束，重复写入更容易在数据库层暴露。
3. 外部 API 失败、配额耗尽和空结果都可能混在 `errors` 中，需要结合日志区分。
4. 每次手动采集是同步等待，关键词较多时请求可能持续很久。
5. 启动时初始采集会拉长应用进入稳定状态的时间。
6. 定时任务默认使用默认行业，没有从页面当前选择读取行业。
7. 81API 请求跳过 TLS 证书验证，需要在部署环境重新设计。
8. 前端列表展示的是已入库数据，不是每次打开页面都直接向外部 API 查询。

这些是源码阅读结论；当前机器没有完成真实 Bocha、81API 和 PostgreSQL 联通验证，因此不把采集成功写成已经运行验证。

---

## 10. 最小练习

### 练习 A：接口追踪

回答：

1. 页面点击“立即采集”进入哪个接口？
2. 哪个服务决定搜索关键词？
3. 新闻和招投标分别用什么字段去重？
4. 为什么 `success=True` 仍可能有错误？

### 练习 B：启动排错

假设应用启动后日志出现 `BOCHA_API_KEY 环境变量未设置`：

1. 行业列表接口是否一定不可用？不一定。
2. 新闻初始采集是否能拿到外部结果？不能正常拿到。
3. 已有 PostgreSQL 数据还能不能被页面读取？理论上可以，取决于数据库可用性。
4. 应该查看哪个接口确认库里是否有数据？`GET /news/check`。

### 练习 C：设计改进

如果把同步采集改成真正的后台任务，至少需要：

1. 返回任务 ID。
2. 保存任务状态和错误。
3. 增加任务查询接口或轮询机制。
4. 防止同一个行业重复启动采集。
5. 让前端在完成后刷新新闻和招投标两个列表。

---

## 11. 留给你的笔记区

### 行业配置和关键词



### 新闻采集链路



### 招投标采集链路



### 我想改进的地方



