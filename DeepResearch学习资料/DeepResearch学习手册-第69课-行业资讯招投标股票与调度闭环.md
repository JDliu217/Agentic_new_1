# DeepResearch 学习手册·第 69 课

## 行业资讯、招投标、股票与定时调度

这部分不是 RAG，而是业务数据采集和展示链路。它们的共同特点是：外部 API 不稳定，数据要落 PostgreSQL，前端按行业和筛选条件读取。

---

## 1. 行业配置是采集入口

文件：`backend/app/config/industry_config.py`。

每个行业配置包含：

- `id`
- `name`
- `description`
- `news_keywords`
- `bidding_keywords`
- `research_keywords`

当前预置行业包括智慧交通、金融科技、医疗健康和能源电力。没有传行业 ID 时使用 `smart_transportation`；传入未知 ID 时也回退到默认行业并记录 warning。

因此行业选择不是只影响页面标题，它会影响采集关键词和部分研究上下文。

---

## 2. 新闻采集链路

```text
industry_id
  → get_industry_config()
  → news_keywords
  → Bocha API
  → 解析标题、摘要、来源、URL、时间
  → source_url 去重
  → IndustryNews 入库
```

新闻去重依据是 `source_url`。同一篇新闻标题略有变化，只要 URL 相同，通常不会重复插入。

`NewsCollectionTask` 记录采集任务状态、数量和错误，便于查看一次采集是否完整成功。

---

## 3. 招投标采集链路

```text
industry_id
  → bidding_keywords
  → 81API 招标/中标接口
  → 解析 bid_id、标题、类型、地区、发布时间
  → bid_id 去重
  → BiddingInfo 入库
```

招投标去重依据是 `bid_id`，不是新闻 URL。

当 API 配额耗尽时，服务可能停止继续请求，并把错误或 warning 放入结果。因而：

```text
success=true
```

不一定代表每个关键词都采集成功，还要看返回的 `errors` 和数量字段。

---

## 4. 前端查询链路

前端 API：

```text
GET /news/list
GET /news/bidding/list
GET /news/stats
```

请求可以携带：

- `industry_id`
- 分类或公告类型
- 省份
- `limit`
- `offset`

后端在 PostgreSQL 查询时按 `industry_id` 过滤，并返回列表、总数和统计信息。

如果行业状态没有正确从首页或全局状态传到 API，页面可能显示默认行业数据，看起来像“采集错了”，实际可能只是请求缺少筛选参数。

---

## 5. 手动采集并非真正后台任务

`news_router.py` 的 `/news/collect` 接收了 `BackgroundTasks` 参数，也定义了 `run_collection()`，但当前代码实际直接调用：

```python
result = await service.collect_all(...)
```

所以浏览器会等待外部 API 请求和入库完成，才收到响应。前端虽然把超时设置为 120 秒，但这仍是同步等待接口。

排错时要区分：

- 接口超时：可能是外部 API 慢或关键词过多。
- 后台任务没执行：当前手动接口并不是这个问题的典型原因。
- 返回 `success=false`：查看 `errors`、Key、配额和网络连接。

---

## 6. APScheduler 和启动初始化

文件：`backend/app/service/scheduler_service.py`。

启动时：

1. 创建 `AsyncIOScheduler`。
2. 添加每日 12:00 的 `daily_news_collection` 任务。
3. 检查数据库是否已有资讯数据。
4. 如果没有数据，立即执行一次采集。

这两个行为不同：

```text
启动时无数据
  → 一次性初始化采集

每日 12:00
  → 定时任务采集
```

应用重启不会因为“已经启动过一次”就自动跳过定时任务；调度器会重新注册任务。

---

## 7. 股票行情链路

股票查询使用单独的行情服务和 `JUHE_STOCK_API_KEY`，不是新闻或招投标入库链路。

大致流程：

```text
公司名称
  → 静态股票映射
  → 标准化股票代码
  → 聚合数据 API
  → stock_quote 事件
  → React 股票卡片
```

它的特点是偏实时查询，不等于 PostgreSQL 中的行业资讯历史数据。缺少 API Key 时，服务会记录警告或返回失败结果。

---

## 8. 时间字段不能混淆

业务记录中可能同时出现：

- `publish_time`：新闻或招标原始发布时间。
- `collected_at`：系统抓到并入库的时间。
- `started_at`：采集任务开始时间。
- `completed_at`：采集任务结束时间。

“按最新排序”如果使用了错误字段，页面可能把刚采集的旧新闻排在前面，或把发布时间较新的记录排错位置。

---

## 9. 业务采集排错顺序

```text
1. 当前 industry_id
2. 关键词配置是否正确
3. 外部 API Key 是否存在
4. 外部 API 状态码、配额和返回结构
5. 去重字段是否为空或错误
6. PostgreSQL commit 是否成功
7. 列表接口过滤和分页
8. 前端状态是否传入同一个 industry_id
```

不要先修改表格组件，因为数据可能根本没有进入数据库。

---

## 练习

场景：手动采集返回 `success=true`，但 `news_collected=0`，`errors` 中有 Bocha API Key 未配置；页面原有新闻仍然能显示。

请判断：

1. 页面旧新闻来自哪里？
2. 这次采集是否算真正成功？
3. 应优先检查哪个环境变量？

参考答案：旧新闻来自 PostgreSQL 已有数据；这次采集不算完整成功，应查看 `errors`；优先检查 `BOCHA_API_KEY`，同时保留已有数据库数据和采集任务错误记录。

