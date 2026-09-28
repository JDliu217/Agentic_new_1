# DeepResearch 学习手册：第 89 课

## 行业资讯、招投标、股票与定时采集

这些功能共同组成项目的业务数据域。它们有自己的 API、数据库模型和前端页面，不等于 DeepResearch 的搜索过程。

## 1. 行业资讯链路

文件：`backend/app/service/news_collection_service.py`

```text
行业配置
→ news_keywords
→ Bocha Web Search API
→ 结果清洗
→ source_url 去重
→ IndustryNews 写入 PostgreSQL
→ /news/list 查询
→ React 新闻页面展示
```

行业配置提供行业名称、资讯关键词和招投标关键词。每个关键词会请求 Bocha，结果至少需要 URL 和摘要或片段，之后写入标题、来源、摘要、分类、日期、行业 ID 等字段。

资讯去重的核心字段是 `source_url`。同一个 URL 已经存在时，服务跳过插入。

## 2. 招投标链路

```text
行业配置
→ bidding_keywords
→ 81API 招投标服务
→ bid_id 去重
→ BiddingInfo 写入 PostgreSQL
→ /news/bidding/list 查询
→ React 招投标页面展示
```

招投标服务还提供中标、招标公告和详情查询。去重重点是外部接口返回的 `bid_id`，不是标题。

前端可以按公告类型、省份和行业筛选，并通过统计接口显示总量和分类数据。

## 3. 手动采集的实际行为

路由声明接收 `BackgroundTasks`，但当前实现中手动 `/news/collect` 直接等待 `collect_all()`，因此请求会等采集结束后返回结果。

返回结构可能同时包含：

```text
success
news_collected
bidding_collected
errors
```

所以 `success=true` 不等于每个关键词都成功；还要检查 `errors` 和实际入库数量。

## 4. 定时采集

文件：`backend/app/service/scheduler_service.py`

启动时创建 APScheduler 的 `AsyncIOScheduler`，添加：

```text
每日 12:00 -> _daily_collection_task()
```

任务创建数据库会话，调用 `NewsCollectionService.collect_all()`，完成后关闭会话。

启动初始化还会检查数据库是否已有资讯数据：

```text
没有数据 -> 立即执行一次采集
已有数据 -> 跳过初始采集
```

这解释了为什么服务刚启动就可能发起外部 API 请求。

## 5. 股票行情链路

股票行情是实时查询链，不等于新闻入库链。

### 独立查询

`StockService` 调用聚合数据股票 API，根据股票代码标准化：

```text
6 开头 -> sh
0 或 3 开头 -> sz
```

返回当前价格、涨跌额、涨跌幅、开盘价、最高价、最低价、成交量和成交额。

### DeepResearch 中的自动识别

DeepScout 会通过公司名映射检查用户问题。如果识别到最多两家公司，就调用 StockService，并发送：

```text
stock_quote
```

前端聊天页有对应分支，把它显示成股票卡片。股票数据通常不会作为 `IndustryNews` 保存。

## 6. 三条链路对比

| 链路 | 外部来源 | 去重或身份字段 | 主要存储 | 前端入口 |
|---|---|---|---|---|
| 行业资讯 | Bocha | `source_url` | `IndustryNews` / PostgreSQL | 新闻页 |
| 招投标 | 81API | `bid_id` | `BiddingInfo` / PostgreSQL | 招投标页 |
| 股票 | 聚合数据 API | 股票代码 | 通常即时返回 | 股票卡片 |

## 7. 工程排错

### 新闻列表为空

检查行业配置、`BOCHA_API_KEY`、Bocha 响应结构、URL 去重和数据库提交。

### 招投标数量为零

检查 `bidding_keywords`、81API key、接口状态、`bid_id` 是否存在以及筛选条件。

### 股票卡片不显示

检查公司名映射、股票代码标准化、`JUHE_STOCK_API_KEY`、`stock_quote` SSE 事件和前端分支。

### 启动很慢

检查启动时是否发现数据库没有数据，从而触发了立即采集，以及外部 API 是否超时。

## 8. 本课练习

请回答：

1. 新闻和招投标为什么使用不同的去重字段？
2. 为什么手动 `/news/collect` 返回 `success=true` 时仍要检查 `errors`？
3. 股票行情为什么不应该和行业新闻入库混为一谈？
