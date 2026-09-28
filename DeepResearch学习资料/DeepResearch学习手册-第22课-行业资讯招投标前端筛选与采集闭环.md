# DeepResearch 学习手册·第 22 课

## 行业资讯、招投标前端筛选与采集闭环

> 本课把第 18 课的后端采集服务连接到前端页面，说明行业配置如何影响筛选、手动采集、分页和统计展示。

---

## 1. 业务数据从哪里来

```text
行业配置
  → 新闻关键词 / 招投标关键词
  → Bocha Web Search / 81API
  → 去重和字段归一化
  → PostgreSQL IndustryNews / BiddingInfo
  → FastAPI 列表与统计接口
  → React 页面筛选、分页和统计卡片
```

项目把新闻和招投标存为两张不同的业务表：

```text
industry_news
bidding_info
```

采集任务另外记录在 `news_collection_tasks`，用于保存任务类型、状态、采集数、错误信息和开始/结束时间。

---

## 2. 行业选择如何影响页面

前端 `industryState.currentIndustryId` 默认从 `localStorage.selected_industry_id` 读取，导航栏切换行业后更新它。

NewsPage 和 BiddingPage 都监听当前行业 ID：

```text
currentIndustryId 改变
  → useCallback 依赖改变
  → useEffect 重新请求列表
  → 页面显示新行业数据
```

行业配置包含：

```text
id
name
description
newsKeywords
biddingKeywords
researchKeywords
```

前端显示行业名称，后端采集服务使用同一个行业 ID 找到对应关键词。

---

## 3. 行业资讯页面

文件：`frontend/src/pages/news/index.tsx` 和 `frontend/src/api/news.ts`。

### 3.1 列表请求

页面维护：

```text
newsList
newsCategory
newsPage
newsTotal
newsStats
```

请求：

```http
GET /news/list
  ?category=政策
  &industry_id=smart_transportation
  &limit=20
  &offset=0
```

后端按行业、分类和分页查询，返回：

```json
{
  "success": true,
  "data": [],
  "total": 0,
  "stats": {
    "total": 0,
    "recent_24h": 0,
    "by_category": {}
  }
}
```

### 3.2 页面展示

页面提供：

- 资讯总数。
- 24 小时更新数。
- 政策数量。
- 研报数量。
- 全部、政策、研报、新闻筛选。
- 20 条一页的分页。
- 标题、摘要、发布日期、部门、来源和分类。

点击条目会用 `window.open(item.source_url, '_blank')` 打开原始来源。

### 3.3 手动采集

“立即采集”调用：

```http
POST /news/collect?max_news=50&max_bidding=50&industry_id=...
```

页面在采集期间禁用按钮并显示进度 Modal。成功后重新拉取当前资讯列表。

返回的 `CollectionResponse` 包含：

```text
success
message
news_collected
bidding_collected
errors
```

`success=true` 只表示整体服务返回成功，不等于每个关键词和每个外部请求都成功；`errors` 仍可能非空。

---

## 4. 招投标页面

文件：`frontend/src/pages/bidding/index.tsx`。

页面维护：

```text
biddingList
biddingType
biddingProvince
biddingPage
biddingTotal
biddingStats
```

请求：

```http
GET /news/bidding/list
  ?notice_type=招标
  &province=江苏
  &industry_id=smart_transportation
  &limit=20
  &offset=0
```

页面展示：

- 招投标总数。
- 招标数量。
- 中标数量。
- 省份覆盖数。
- 公告类型筛选。
- 省份筛选。
- 项目标题、公告类型、省市、发布日期和 `bid_id`。

后端对“招标”和“中标”不是简单完全相等匹配：

```text
招标 → 可能匹配包含 招标、采购、询价 的公告类型
中标 → 可能匹配包含 中标、结果 的公告类型
```

因此页面筛选项和数据库真实值之间存在业务映射。

---

## 5. 后端采集新闻

文件：`backend/app/service/news_collection_service.py`。

### 5.1 Bocha 请求

新闻采集读取 `BOCHA_API_KEY`。每个行业关键词调用：

```http
POST https://api.bochaai.com/v1/web-search
```

请求包含：

```json
{
  "query": "行业关键词",
  "summary": true,
  "count": 结果数,
  "page": 1
}
```

结果被归一化成 URL、标题、摘要、站点和发布时间。

### 5.2 去重和分类

新闻主要按 `source_url` 去重。已有相同 URL 时跳过，不会再次插入。

服务还会：

- 解析发布时间。
- 从标题和内容推断政策、研报或新闻分类。
- 推断部门。
- 写入行业 ID、关键词和采集时间。

### 5.3 采集任务记录

采集开始时创建 `NewsCollectionTask(status=running)`；完成后更新：

```text
status = completed
total_collected
completed_at
error_message（如果有部分错误）
```

未捕获的整体异常会把任务标记为 failed。

---

## 6. 后端采集招投标

招投标使用 `bidding_service` 调用 81API 相关能力。对每个关键词可能分别查询：

```text
招标公告
中标信息
```

招投标主要按 `bid_id` 去重。记录包含：

```text
industry_id
bid_id
title
notice_type
province
city
publish_time
source
collected_at
```

如果 API 配额耗尽，服务会记录错误并停止继续请求。若 `BID_APP_CODE` 未配置，`collect_all()` 会跳过招投标采集并返回跳过信息。

这解释了一个常见现象：新闻能够采集成功，但招投标数量为 0，并不一定是页面故障，也可能是 API 配置缺失或配额耗尽。

---

## 7. 定时采集和手动采集

文件：`backend/app/service/scheduler_service.py`。

### 7.1 每日任务

APScheduler 配置每日 12:00 执行 `collect_all(max_news=20, max_bidding=20)`。

### 7.2 启动时检查

应用启动期间执行 `init_scheduler_and_check_data()`：

```text
启动调度器
  → 检查数据库是否有行业数据
  → 没有数据：立即采集
  → 有数据：跳过初始化采集
```

这意味着第一次启动可能主动访问外部 API，不能只以“应用端口已打开”作为启动完成的判断。

### 7.3 手动触发

页面手动采集和定时任务都调用 `NewsCollectionService.collect_all()`，但触发来源不同：

```text
页面按钮 → POST /news/collect
APScheduler → _daily_collection_task
```

调度器还提供：

```http
GET /news/scheduler/status
```

用于查看任务 ID、名称、下一次运行时间和触发器。

---

## 8. 数据字段和时间含义

新闻和招投标同时有多个时间字段：

| 字段 | 含义 |
|---|---|
| `publish_time` | 原始内容发布时间，可能为空或解析失败 |
| `collected_at` | 系统抓到并写入数据库的时间 |
| `created_at` | 数据库记录创建时间 |
| `started_at` | 采集任务开始时间 |
| `completed_at` | 采集任务结束时间 |

前端列表通常优先显示 `publish_time`，没有时回退到 `collected_at`。排序和统计需要明确使用哪个字段，不能把“发布时间”和“采集时间”混为一谈。

---

## 9. 完整数据流示例

用户当前行业选择“智慧交通”，打开行业资讯页面并点击立即采集：

```text
industryState.currentIndustryId
  → handleCollect()
  → POST /news/collect?industry_id=smart_transportation
  → get_industry_config()
  → 读取智慧交通 news_keywords / bidding_keywords
  → Bocha 和 81API
  → source_url / bid_id 去重
  → IndustryNews / BiddingInfo 入库
  → 返回 collected 数量和 errors
  → NewsPage 或 BiddingPage 重新请求列表
  → 统计卡片和列表刷新
```

这条链包含前端状态、HTTP、外部 API、数据库事务和页面刷新，适合用来练习端到端排错。

---

## 10. 当前实现边界

1. 采集依赖外部 API Key，源码构建通过不代表真实采集可用。
2. 手动采集接口虽然接收 `BackgroundTasks`，当前实现实际直接等待 `collect_all()` 并返回结果。
3. `success=true` 可能同时有部分关键词错误。
4. Bocha 结果发布时间可能为空，需要回退或解析摘要。
5. 招投标 API 配额和 `BID_APP_CODE` 会影响结果数量。
6. 页面省份筛选选项由当前统计结果生成，统计为空时没有完整省份列表。
7. 新闻点击打开来源 URL，来源链接失效时页面没有本地详情兜底。
8. 调度器和手动按钮可能同时触发采集，需要考虑并发任务和重复请求。

---

## 11. 练习

1. 新闻按 `source_url` 去重，招投标按 `bid_id` 去重，为什么不能只使用数据库自增 ID 去重？
2. 页面显示“采集完成但 errors 不为空”时，应该如何解释？
3. 切换行业后，哪些前端状态需要重置？当前页面重置了页码吗？
4. 为什么第一次启动可能比后续启动慢？
5. 手动采集和每日采集如何共享相同的服务逻辑？
6. 如何验证数据库中一条新闻的 `publish_time` 是否来自原始源站，而不是采集时间？

---

## 12. 面试官追问

1. 你们如何设计资讯采集的幂等性？
2. 外部 API 部分失败时，为什么任务仍可能标记 completed？
3. 如何避免定时任务和手动任务并发重复采集？
4. Bocha 搜索结果的摘要和原文可信度如何评估？
5. 招投标 API 配额耗尽时，系统如何向用户解释？
6. 为什么列表查询要把 `total` 和 `data` 一起返回？
7. 如果 `publish_time` 为空，排序应使用什么字段？
8. 如何为新闻和招投标增加重试、退避和监控？

---

## 13. 留白与我的笔记

### 13.1 我画的采集闭环

<!-- 补充行业配置、外部 API、任务表、业务表和前端页面之间的箭头。 -->



### 13.2 我需要检查的配置

<!-- 记录 BOCHA_API_KEY、BID_APP_CODE、数据库和调度器的运行配置。 -->



### 13.3 我会如何处理部分失败

<!-- 写下重试、错误展示、任务状态和幂等策略。 -->



### 13.4 面试回答草稿

<!-- 用自己的话回答本课第 12 节问题。 -->



