# DeepResearch 学习手册：第 103 课

## 行业资讯、招投标、股票与定时采集

这些功能属于项目的业务数据域。它们和 DeepResearch 共用配置、数据库、外部 API 和前端状态，但不完全走六个 Agent 的主流程。

## 1. 行业配置是采集任务的输入

源码：

```text
backend/app/config/industry_config.py
```

每个行业配置包含：

```text
id
name
description
news_keywords
bidding_keywords
research_keywords
```

当前配置包括智慧交通、金融科技、医疗健康和能源电力。找不到行业 ID 时会回退到默认行业 `smart_transportation`。

## 2. 新闻采集链路

```text
行业 news_keywords
→ Bocha Web Search API
→ 结果清洗
→ source_url 去重
→ IndustryNews
→ /news/list
→ 前端新闻页
```

新闻的 `source_url` 是去重的重要字段。采集结果通常还需要保存发布时间、采集时间、分类和行业 ID。

## 3. 招投标采集链路

```text
行业 bidding_keywords
→ 81API/阿里云市场接口
→ 招标/中标结果
→ bid_id 去重
→ BiddingInfo
→ /news/bidding/list
→ 前端招投标页
```

新闻和招投标不能只用同一个去重字段：

```text
新闻：source_url
招投标：bid_id
```

## 4. 列表接口的筛选

主要接口：

```text
GET /news/list
GET /news/bidding/list
GET /news/stats
GET /news/check
GET /news/industries
```

新闻支持：

```text
category
industry_id
limit
offset
```

招投标支持：

```text
notice_type
province
industry_id
limit
offset
```

前端选择行业后，把 `industry_id` 作为请求参数发送。

## 5. 手动采集的真实行为

`POST /news/collect` 的文档说明是“异步执行”，函数也声明了 `BackgroundTasks`，但当前代码实际直接等待：

```text
service.collect_all(...)
→ 等待新闻和招投标采集完成
→ 返回 collected 数量和 errors
```

因此它更接近同步请求。`success=true` 也可能同时带有部分错误，因为新闻和招投标是两个子任务。

## 6. 定时采集

启动生命周期会调用调度服务。调度器每天 12:00 执行行业采集；启动时如果数据库没有数据，还可能立即进行初始化采集。

要区分：

```text
启动初始化 = 解决首次没有数据
每日任务 = 定期更新数据
手动接口 = 用户主动触发
```

## 7. 股票行情链路

源码：

```text
backend/app/config/stock_mapping.py
backend/app/service/stock_service.py
backend/app/service/deep_research_v2/agents/scout.py
```

V2 DeepScout 会：

```text
用户问题
→ find_company_in_query()
→ 公司名映射股票代码
→ 聚合数据 API
→ data_points
→ stock_quote SSE
```

当前一轮最多查询两家公司。

行情数据有两个用途：

```text
data_points = 供分析和报告使用
stock_quote = 供前端 StockCard 即时展示
```

前端链路：

```text
stock_quote
→ target.stockQuote
→ result.tsx
→ StockCard
```

## 8. 业务数据域的工程限制

```text
外部 API Key 缺失 → 采集失败或空结果
外部配额耗尽 → 部分任务失败
source_url/bid_id 不规范 → 去重失效
手动采集同步等待 → 请求时间过长
启动立即采集 → 后端启动变慢
股票数据无缓存/时间戳 → 结果可能过期
```

新闻路由当前部分接口没有统一的登录依赖，是否允许公开访问要由产品安全要求明确决定。

## 9. 本课练习

1. 新闻和招投标分别用什么字段去重？为什么不能混用？
2. `success=true` 为什么仍可能带有 `errors`？
3. 启动初始化采集、每日调度和手动采集有什么区别？
4. 股票数据为什么同时写 `data_points` 和发送 `stock_quote`？
5. 如果行业新闻列表为空，你会按什么顺序排查？
