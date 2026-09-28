# DeepResearch 学习手册·第 33 课

## 股票行情自动识别与前端卡片链路

这一课追踪一个完整的外围能力：当用户的问题里出现“茅台”“比亚迪”等已配置的 A 股公司时，DeepResearch V2 会尝试读取实时行情，并把结果显示为聊天消息中的股票卡片。

源码依据：

    D:\课\s4-6\industry_information_assistant\backend\app\config\stock_mapping.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\stock_service.py
    D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\agents\scout.py
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\chat\index.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\pages\chat\component\result.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\components\stock-card\index.tsx
    D:\课\s4-6\industry_information_assistant\frontend\src\api\session.type.d.ts

---

## 1. 先看完整数据流

```text
用户问题
  → find_company_in_query()
  → 股票名称映射为 sh/sz 股票代码
  → StockService.get_stock_by_code()
  → 聚合数据股票 API
  → DeepScout 写入 data_points
  → DeepScout 发出 stock_quote 消息
  → 研究流转换成 SSE/JSON 事件
  → chat/index.tsx 保存 target.stockQuote
  → result.tsx 判断 item.stockQuote
  → StockCard 展示价格、涨跌和成交信息
```

这里有两个不同的数据用途：

1. `data_points` 供研究状态、分析和后续写作使用。
2. `stock_quote` 供前端直接绘制股票卡片使用。

因此“写入研究数据”与“显示卡片”是同一次后端查询产生的两种输出。

---

## 2. 公司名称识别不是 LLM 完成的

`backend/app/config/stock_mapping.py` 维护一个静态字典，例如：

```python
"茅台": "sh600519"
"贵州茅台": "sh600519"
"比亚迪": "sz002594"
"宁德时代": "sz300750"
```

`find_company_in_query(query)` 会遍历字典，判断公司名称是否是用户问题的子串，并只返回股票代码不为 `None` 的公司。

这意味着：

- “请分析茅台近期表现”可以命中“茅台”。
- “腾讯怎么样”不会走当前 A 股行情链，因为腾讯被配置为 `None`，项目注释说明港股暂不支持。
- 没有写入映射表的公司不会被自动识别。
- 同一个问题可能命中多个公司，但 Scout 当前最多查询前两只。

这是规则匹配，不是开放式公司实体识别。公司简称、别名、错别字和新上市公司都可能漏检。

---

## 3. 股票代码怎样标准化

`StockService._normalize_stock_code()` 接受带市场前缀和不带前缀的代码：

| 输入 | 结果 |
|---|---|
| `sh601009` | `sh601009` |
| `601009` | `sh601009` |
| `000001` | `sz000001` |
| `300750` | `sz300750` |

当前规则是：6 开头归上海，0 或 3 开头归深圳。这个规则满足项目当前支持的 A 股场景，但它不是对所有证券市场的通用标准化方案。

---

## 4. StockService 如何调用外部 API

服务从环境变量读取：

```text
JUHE_STOCK_API_KEY
```

单只股票查询使用：

```text
http://web.juhe.cn/finance/stock/hs
```

请求参数包含：

```text
gid = 标准化股票代码
key = API Key
```

请求使用 `httpx.AsyncClient(timeout=10.0)`。当返回码是 `200` 且有结果时，代码把外部字段转成 `StockInfo`：

| 外部字段 | 含义 |
|---|---|
| `nowPri` | 当前价格 |
| `increase` | 涨跌额 |
| `increPer` | 涨跌幅 |
| `todayStartPri` | 今日开盘 |
| `yestodEndPri` | 昨日收盘 |
| `todayMax` | 今日最高 |
| `todayMin` | 今日最低 |
| `traAmount` | 成交量 |
| `traNumber` | 成交额 |

失败时统一返回 `success=False`、`error` 和 `data=None`；超时会返回“请求超时”，其他异常会返回异常文本。这样调用方不必依赖异常才能判断查询失败。

---

## 5. DeepScout 在什么时候触发股票查询

V2 `DeepScout.process()` 在正常研究阶段先调用：

```python
await self._fetch_stock_data_if_relevant(state)
```

然后才把阶段推进到 `researching` 并执行网页或本地知识库搜索。

`_fetch_stock_data_if_relevant()` 的流程是：

1. 从 `state["query"]` 取用户问题。
2. 调用 `find_company_in_query()`。
3. 没找到支持的公司就直接返回。
4. 获取 `StockService` 单例。
5. 最多查询两只股票。
6. 查询成功后追加三条 `data_points`：当前股价、涨跌幅、今日成交量。
7. 发送 `stock_quote` 消息。
8. 再发送一条 `thought` 消息，说明已获取实时行情。

如果外部 API 失败，Scout 只记录 warning，不会因为股票行情失败而让整个研究请求失败。这是一个可选增强能力，主研究搜索仍可继续。

---

## 6. `stock_quote` 的事件字段

Scout 发出的消息字段如下：

```json
{
  "type": "stock_quote",
  "content": {
    "code": "sh600519",
    "name": "贵州茅台",
    "price": "...",
    "change": "...",
    "change_percent": "...",
    "high": "...",
    "low": "...",
    "volume": "...",
    "turnover": "...",
    "open": "...",
    "prev_close": "..."
  }
}
```

具体外层事件如何被研究服务包装，仍要结合研究流的统一事件转换代码阅读；前端已经兼容 `json.content || json`，所以它可以接受“字段在 content 内”或“字段直接位于事件对象”的形状。

---

## 7. 前端怎样保存事件

`frontend/src/pages/chat/index.tsx` 处理到 `json.type === 'stock_quote'` 时，会把字段复制到当前回答对象：

```ts
target.stockQuote = {
  code: content.code,
  name: content.name,
  price: content.price,
  change: content.change,
  change_percent: content.change_percent,
  high: content.high,
  low: content.low,
  volume: content.volume,
  turnover: content.turnover,
  open: content.open,
  prev_close: content.prev_close,
}
```

类型声明位于 `frontend/src/api/session.type.d.ts` 的 `StockQuoteData`。它允许价格和涨跌额是字符串或数字，因为外部 API 的数字字段当前以字符串为主。

---

## 8. React 最终怎样展示卡片

`result.tsx` 中有明确的渲染条件：

```tsx
{item.stockQuote ? <StockCard data={item.stockQuote} /> : null}
```

`StockCard` 会：

- 用 `parseFloat()` 转换价格和涨跌额。
- 根据涨跌额决定“涨、跌、平”状态。
- 显示当前价、涨跌额、涨跌幅。
- 显示今开、昨收、最高、最低、成交量和成交额。
- 在界面底部标记数据来源为聚合数据股票 API。

项目样式使用红色表示上涨、绿色表示下跌，符合 A 股常见展示习惯；这只是前端视觉约定，不影响后端数值含义。

---

## 9. V1 和 V2 的边界

项目还有 `tool_executor.py` 中的 `execute_stock_query()`，并注册了 `ToolType.STOCK_QUERY`。这属于 V1 工具执行体系。它能把查询结果追加到 V1 的 `ReActContext.collected_data`，但“工具已经注册”不等于每一次 V1 请求都会自动调用股票查询。

当前能从源码明确确认的是：

- V2 Scout 有一条直接的自动识别和查询路径。
- V1 有股票工具处理能力。
- 两者使用的状态对象和调用调度方式不同。

阅读项目时要沿调用方继续追踪，不能看到一个工具函数就断言所有请求都会执行它。

---

## 10. 这条链路的实际限制

1. 映射表是静态的，覆盖范围有限。
2. 只支持映射表中已有的 A 股公司；港股、美股和未上市公司被明确标为不支持或没有代码。
3. 需要 `JUHE_STOCK_API_KEY` 和外部网络服务。
4. API 返回字段主要是字符串，前端只做了简单数字转换。
5. 行情查询没有缓存和重试策略，最多两只股票的查询仍可能增加请求延迟。
6. 外部 API 失败时只记录日志，前端不会得到一个专门的“行情不可用”卡片。
7. “实时”来自第三方接口的返回语义，项目本身没有校验行情时间戳。

截至当前阅读，已确认源码逻辑，但本机没有完成带真实 Key 的外部行情端到端验证。因此不能据此声称实时行情在当前环境已经成功展示。

---

## 11. 最小练习

### 练习 A：静态追踪

不启动服务，回答：

1. 为什么问题“分析茅台和比亚迪”最多查询两只股票？
2. 哪个函数决定“腾讯”不会进入当前 A 股行情查询？
3. `data_points` 和 `stockQuote` 分别服务于什么？
4. 哪个组件最终把 `stockQuote` 画成卡片？

### 练习 B：故障定位

假设日志出现：

```text
警告: JUHE_STOCK_API_KEY 环境变量未设置
```

请按顺序判断：

1. 公司名识别是否仍然可能成功？可以。
2. 外部行情请求是否有有效认证？通常没有。
3. Scout 是否一定会让整个研究失败？不会，失败路径只记录 warning。
4. 前端是否一定有股票卡片？没有成功的 `stock_quote` 事件就不会有。

### 练习 C：扩展一个公司

如果要支持“某个新的 A 股公司”，至少要检查：

1. 在 `COMPANY_STOCK_MAP` 加入公司名和正确市场代码。
2. 确认 `StockService` 能接受该代码。
3. 保证后端事件字段与 `StockQuoteData` 一致。
4. 用可控的 mock 响应测试成功、超时和错误返回。

---

## 12. 面试官可能追问

### 问：为什么不让 LLM 直接判断股票代码？

答：当前实现使用静态映射，结果可预测且不会因为模型幻觉产生错误代码。代价是覆盖范围有限，后续可以引入证券主数据服务，并保留代码校验和市场校验。

### 问：为什么行情失败不应该阻塞研究？

答：股票行情只是可选数据增强。主研究依赖搜索和分析；把它作为非关键依赖可以避免第三方接口短暂故障拖垮整条研究链。

### 问：进程内单例 `get_stock_service()` 解决了什么？

答：它复用服务对象和配置读取，减少重复初始化。它没有提供分布式缓存、请求限流或跨进程共享状态。

### 问：怎样把这条能力做得更可靠？

答：统一事件 Schema，补充行情时间戳和市场字段，增加短 TTL 缓存、超时重试、限流和指标监控；把公司识别从静态子串匹配升级为可维护的证券主数据查询，并用 mock 和契约测试覆盖前后端字段。

---

## 13. 留给你的笔记区

### 我的链路图

（在这里画：问题 → 映射 → API → Scout → SSE → React → StockCard）


### 我还不理解的字段



### 下一步想修改或扩展的地方



