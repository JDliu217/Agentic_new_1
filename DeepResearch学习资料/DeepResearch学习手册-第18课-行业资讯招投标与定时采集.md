# DeepResearch 学习手册·第 18 课

## 行业资讯、招投标与定时采集

本课讲清楚项目中另一条独立业务链：行业关键词如何变成新闻和招投标数据，数据如何入库，前端如何筛选展示，定时任务如何重复执行。

源码根目录：D:\课\s4-6\industry_information_assistant

---

## 1. 这条链路解决什么问题

DeepResearch 是按用户问题临时搜索；行业资讯模块则是定期把行业信息采集到数据库，供用户浏览和后续业务使用。

整体链路：

    行业配置
    → 关键词
    → Bocha 新闻搜索 / 81API 招投标接口
    → 去重、分类、日期解析
    → PostgreSQL
    → React 新闻和招投标页面

这条链路与 V2 DeepResearch 的实时搜索不同，但两者可以使用相同的行业主题和外部搜索能力。

---

## 2. 行业配置

文件：backend/app/config/industry_config.py

IndustryConfig 包含：

    id
    name
    description
    news_keywords
    bidding_keywords
    research_keywords

当前预置行业包括：

- 智慧交通
- 金融科技
- 医疗健康
- 能源电力

每个行业分别配置新闻关键词、招投标关键词和研究关键词。默认行业是 smart_transportation。

### 2.1 获取配置

get_industry_config(industry_id)：

1. 没传行业 ID 时使用默认行业。
2. 找不到 ID 时记录警告并回退默认行业。
3. 返回一个 IndustryConfig。

这说明行业切换不是动态创建数据库表，而是选择内存中的一份关键词配置。

---

## 3. 新闻采集

文件：backend/app/service/news_collection_service.py

### 3.1 Bocha 请求

_bocha_search() 调用 Bocha Web Search API：

    POST https://api.bochaai.com/v1/web-search

请求包含 query、summary、count 和 page。服务把响应中的网页结果规范化为：

    url
    title
    summary
    snippet
    siteName
    datePublished

没有 BOCHA_API_KEY 时，服务直接返回空结果并记录错误。

### 3.2 collect_news()

采集步骤：

1. 根据 industry_id 找到新闻关键词。
2. 为每个关键词分配请求数量。
3. 调用 Bocha。
4. 检查 source_url 是否已经存在。
5. 解析发布时间，必要时从摘要中提取日期。
6. 根据标题和内容判断政策、研报或新闻分类。
7. 创建 IndustryNews。
8. 统一提交事务。

新闻去重的主要键是 source_url。相同 URL 不会重复插入。

### 3.3 IndustryNews 模型

关键字段：

    id
    industry_id
    title
    content
    source
    source_url
    category
    department
    publish_time
    collected_at
    keywords
    is_read

这里保存的是资讯摘要和来源信息，不是完整网页快照。

---

## 4. 招投标采集

文件：backend/app/service/bidding_service.py

81API 提供多个端点：

    queryWinBid       中标查询
    queryBid          招标查询
    queryBidDetail    详情查询

BiddingService 使用 BID_APP_CODE 访问接口。如果没有配置，返回明确的“API 未配置”结果。

### 4.1 collect_bidding()

NewsCollectionService 对每个行业关键词分别查询：

1. 招标公告。
2. 中标信息。
3. 检查接口是否返回配额耗尽。
4. 使用 bid_id 去重。
5. 解析发布时间。
6. 写入 BiddingInfo。

接口配额用尽时，服务停止继续请求，并把原因记录到错误列表。

### 4.2 BiddingInfo 模型

关键字段：

    id
    industry_id
    bid_id
    title
    notice_type
    province
    city
    content
    publish_time
    source
    collected_at
    is_read

bid_id 是外部项目 ID，数据库设置了唯一约束，配合代码查询完成去重。

---

## 5. 采集任务记录

每次新闻或招投标采集会创建 NewsCollectionTask：

    task_type       news 或 bidding
    status          pending / running / completed / failed
    total_collected
    error_message
    started_at
    completed_at

它不是外部 API 的任务 ID，而是本项目自己的采集审计记录。

即使部分关键词失败，collect_news() 或 collect_bidding() 也可能完成并返回 collected 数量和 errors；因此 success、采集数量和错误列表要一起看。

---

## 6. collect_all()

NewsCollectionService.collect_all() 先采集新闻，再判断招投标 API 是否配置：

    collect_news(max_news, industry_id)
    → 没有 BID_APP_CODE：跳过招投标
    → 有配置：collect_bidding(max_bidding, industry_id)

返回结构包含：

    success
    news
    bidding
    industry

这里的 success 是组合结果，不能简单理解成“每条关键词都成功”。

---

## 7. 查询和统计

news_router.py 提供：

    GET /news/list
    GET /news/bidding/list
    GET /news/stats
    GET /news/check
    GET /news/industries
    GET /news/industries/{industry_id}
    POST /news/collect
    GET /news/scheduler/status

### 7.1 新闻列表

GET /news/list 支持：

    category
    industry_id
    limit
    offset

服务按 collected_at 倒序分页，并返回筛选后的 total 和分类统计。

### 7.2 招投标列表

GET /news/bidding/list 支持：

    notice_type
    province
    industry_id
    limit
    offset

notice_type 为“招标”时，会匹配招标、采购和询价；为“中标”时，会匹配中标和结果。

### 7.3 统计

新闻统计包括：

    total
    recent_24h
    by_category

招投标统计包括：

    total
    by_type
    by_province

其中招投标类型会再归类成招标和中标，同时保留原始类型，便于调试。

---

## 8. 定时任务

文件：backend/app/service/scheduler_service.py

FastAPI lifespan 启动 SchedulerService 单例。启动时添加：

    id: daily_news_collection
    trigger: 每天 12:00
    task: _daily_collection_task

每日任务创建独立的数据库会话，调用 collect_all(max_news=20, max_bidding=20)，结束后关闭数据库会话。

### 8.1 手动采集

POST /news/collect 由页面触发，使用传入的 max_news、max_bidding 和 industry_id。

路由最终直接调用 collect_all 并等待结果，因此接口返回前会完成本次采集，而不是只创建一个后台任务。代码中虽然定义了 BackgroundTasks 和 run_collection 函数，但当前主路径没有使用后台任务。

### 8.2 查看调度器

GET /news/scheduler/status 返回任务 ID、任务名称、下一次运行时间和触发器。它只能说明调度器中注册了什么任务，不代表外部 API 下一次一定成功。

---

## 9. 前端如何使用

新闻页：

    frontend/src/pages/news/index.tsx

它会：

1. 读取当前行业 ID。
2. 调用 /news/list。
3. 展示分类、总数和 24 小时更新数。
4. 点击立即采集调用 /news/collect。
5. 采集结束后重新拉取列表。
6. 点击资讯打开 source_url。

招投标页：

    frontend/src/pages/bidding/index.tsx

它会：

1. 调用 /news/bidding/list。
2. 按公告类型和省份筛选。
3. 展示招标、中标、总数和省份覆盖。
4. 点击立即采集后重新拉取列表。

前端页面保存的是当前页面状态；真正的数据持久化发生在 PostgreSQL。

---

## 10. 外部数据质量边界

这一模块不是“搜索到什么就原样保存”：

- 新闻日期可能来自 API，也可能从摘要正则提取。
- 新闻分类由标题和内容的规则判断。
- 招投标结果依赖第三方 API 的字段和配额。
- 同一个项目如果外部 ID 或 URL 不稳定，代码去重仍可能出现重复。
- collected_at 是本项目采集时间，不等于信息的 publish_time。

回答“最新资讯”时，要明确使用的是发布时间还是采集时间。

---

## 11. 排错顺序

页面没有新闻：

    /news/list 是否成功
    → PostgreSQL industry_news 是否有数据
    → 当前 industry_id 是否正确
    → 采集时 BOCHA_API_KEY 是否配置
    → Bocha 响应是否有有效 URL 和摘要

新闻采集返回 0：

    行业配置是否有关键词
    → API Key 是否有效
    → 外部 API 是否返回空结果
    → source_url 是否全部已存在

招投标为空：

    BID_APP_CODE 是否配置
    → 是否配额耗尽
    → 81API 返回状态和 list 字段是否正确
    → bid_id 是否已经去重

定时任务没有运行：

    FastAPI lifespan 是否执行
    → scheduler/status 是否有 daily_news_collection
    → 当前时间和时区是否符合预期
    → 后端日志是否出现每日采集记录

---

## 12. 练习

1. 行业配置中的三类关键词分别给谁使用？
2. 新闻和招投标分别使用什么外部服务？
3. 新闻为什么用 source_url 去重，招投标为什么用 bid_id 去重？
4. collected_at 和 publish_time 有什么区别？
5. 每日任务和手动采集是否完全走同一个入口？
6. 为什么接口返回 success=true 仍可能有 errors？
7. 前端切换行业后，列表为什么会刷新？

### 我的数据链路图

<!-- 画出行业配置、外部 API、PostgreSQL、Router、React 页面之间的箭头 -->


### 我的排错答案

<!-- 任选“新闻为空”或“招投标配额耗尽”写出排查步骤 -->

