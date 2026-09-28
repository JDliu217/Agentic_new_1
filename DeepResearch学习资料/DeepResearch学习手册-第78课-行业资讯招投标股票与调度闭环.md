# DeepResearch 学习手册：第 78 课

## 行业资讯、招投标、股票与调度闭环

这部分是项目的业务数据域。它和 DeepResearch 的临时搜索不同：数据会被采集、去重、写入 PostgreSQL，再由页面按行业和类型查询。

## 1. 行业配置是入口

文件：

```text
backend/app/config/industry_config.py
```

每个行业配置包括：

```text
id
name
description
news_keywords
bidding_keywords
research_keywords
```

当前预设行业包括智慧交通、金融科技、医疗健康和能源电力。没有传行业 ID 时，默认使用 `smart_transportation`。

行业配置不是新闻内容，而是采集任务的搜索参数来源。

## 2. 新闻采集链

```text
IndustryConfig.news_keywords
→ Bocha web-search
→ 过滤有效 URL 和摘要
→ 解析发布时间
→ 分类新闻
→ IndustryNews
→ PostgreSQL
```

每条新闻主要保存：

```text
industry_id、title、content、source、source_url、category、department、publish_time、collected_at、keywords
```

采集时按照 `IndustryNews.source_url` 检查重复。不同关键词搜到同一网页时，会跳过重复写入。这个规则不能识别换 URL 的转载文章。

## 3. 招投标采集链

```text
IndustryConfig.bidding_keywords
→ search_bid_notices()
→ search_win_bids()
→ BiddingInfo
→ PostgreSQL
```

招投标记录主要保存：

```text
industry_id、bid_id、title、notice_type、province、city、publish_time、source、collected_at
```

采集时按照 `BiddingInfo.bid_id` 去重，数据库模型还把 `bid_id` 设置为唯一索引。新闻使用 URL，招投标使用项目 ID，这两个身份字段不能混用。

如果 API 配额用尽，服务会记录错误并停止后续关键词。因此 `success=true` 仍可能伴随 `errors`。

## 4. 采集任务记录

`NewsCollectionTask` 保存：

```text
task_type、status、total_collected、error_message、started_at、completed_at
```

单个关键词失败时，服务可能记录错误后继续处理其他关键词，所以：

```text
任务 completed ≠ 每个关键词都成功
```

## 5. 手动采集和定时采集

`scheduler_service.py` 使用 APScheduler 注册：

```text
每天 12:00
→ _daily_collection_task()
→ collect_all(max_news=20, max_bidding=20)
```

应用启动时还会检查数据库：

```text
没有 IndustryNews 或 BiddingInfo
→ 立即执行一次采集
```

因此第一次启动可能不必等到中午就调用外部 API。

`/news/collect` 路由虽然声明了 `BackgroundTasks`，但当前代码实际直接 `await service.collect_all(...)`，会等待采集完成后才返回。

## 6. 股票行情是独立链路

股票服务使用 `JUHE_STOCK_API_KEY` 调用聚合数据 API。代码标准化规则是：

```text
6 开头 → sh
0 或 3 开头 → sz
```

例如：

```text
601009 → sh601009
000001 → sz000001
```

DeepScout 会从用户问题中识别公司，最多查询两家公司：

```text
find_company_in_query()
→ StockService.get_stock_by_code()
→ data_points 添加股价、涨跌幅、成交量
→ 发送 stock_quote 事件
```

前端链路是：

```text
stock_quote SSE
→ chat/index.tsx
→ currentChatItem.stockQuote
→ StockCard
```

股票行情是研究期间的即时 API 查询，不等同于新闻和招投标的定时入库链。

## 7. 三种数据不要混淆

| 数据域 | 来源 | 主要落点 |
|---|---|---|
| 行业新闻 | Bocha | PostgreSQL `IndustryNews`、新闻页 |
| 招投标 | 81API | PostgreSQL `BiddingInfo`、招投标页 |
| 股票行情 | 聚合数据 API | DeepResearch `data_points`、股票卡片 |

## 8. 排错顺序

### 新闻列表为空

```text
industry_id 是否正确
BOCHA_API_KEY 是否配置
Bocha 是否返回 webPages.value
source_url 是否被判定为重复
IndustryNews 是否 commit
前端筛选是否使用同一 industry_id
```

### 招投标列表为空

```text
BID_APP_CODE 是否配置
API 是否配额用尽
结果是否 success
item.id 是否存在
bid_id 是否已存在
notice_type/province 筛选是否过严
```

### 调度没有运行

```text
FastAPI lifespan 是否启动 scheduler
APScheduler 是否 running
/news/scheduler/status 是否有 job
系统时区是否符合 CronTrigger
外部 API 和数据库是否可用
```

### 没有股票卡片

```text
公司名是否在静态映射中
股票代码是否标准化
JUHE_STOCK_API_KEY 是否存在
行情 API 是否成功
stock_quote 是否到达前端
StockCard 是否收到 stockQuote
```

## 9. 本课练习

1. 新闻和招投标分别使用什么字段去重？为什么？
2. 为什么采集接口返回 `success=true` 仍可能有错误？
3. 启动时数据库没有数据会发生什么？
4. 为什么股票行情不能和行业资讯表当成同一条数据链？
5. `/news/collect` 为什么当前可能等待采集完成？

## 10. 本课结论

业务数据域是：

```text
行业配置
→ 关键词
→ 外部 API
→ 去重
→ PostgreSQL
→ 新闻/招投标页面
```

股票是另一条即时链：

```text
用户问题
→ 公司识别
→ 行情 API
→ stock_quote SSE
→ 股票卡片
```

