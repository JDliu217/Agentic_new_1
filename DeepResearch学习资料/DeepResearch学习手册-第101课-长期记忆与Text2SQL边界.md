# DeepResearch 学习手册：第 101 课

## 长期记忆与 Text2SQL：两个外围能力

这两个功能都使用 LLM，但它们解决的问题不同：

```text
长期记忆：让系统记住用户过去的重要信息
Text2SQL：让用户用自然语言查询结构化数据库
```

## 1. 长期记忆从对话创建

源码：

```text
backend/app/router/memory_router.py
backend/app/service/memory_service.py
```

创建记忆时，接口先验证：

```text
JWT 用户
→ session_id
→ ChatSession.user_id == 当前用户
→ 读取 ChatMessage
```

然后 MemoryService 把对话交给 LLM 总结，提取：

```text
summary
key_insights
user_preferences
topics
```

## 2. 长期记忆同时保存两份

### PostgreSQL

`LongTermMemory` 保存业务记录：

```text
memory_id
user_id
session_id
summary
key_insights
token_count
created_at
```

### Milvus

把摘要或洞察向量化，写入固定集合：

```text
long_term_memories
```

向量记录带有 `user_id`，检索时必须用当前用户过滤。

因此：

```text
PostgreSQL 负责可管理、可审计的记忆记录
Milvus      负责按语义相似度找到相关记忆
```

## 3. 记忆检索的安全边界

搜索接口从 JWT 取得当前用户，再把：

```text
user_id + query + top_k
```

传给 MemoryService。

不能让客户端提交任意 `user_id` 来搜索别人的记忆。数据库列表、详情、删除接口也都按当前用户过滤。

## 4. 长期记忆和聊天历史的区别

```text
ChatMessage = 原始短期对话记录
LongTermMemory = 对历史对话压缩后的长期知识
```

短期历史适合恢复当前会话，长期记忆适合跨会话语义召回。长期记忆不是把所有聊天消息永久塞进每次 Prompt。

## 5. Text2SQL 的完整链路

源码：

```text
backend/app/service/text2sql_service.py
backend/app/router/database_router.py
```

链路是：

```text
自然语言问题
→ LLM 生成 SQL、解释、预期列和 visualization_hint
→ SQL 校验
→ 真实数据库执行或 Mock fallback
→ 返回 data、columns 和可视化提示
→ 前端表格或图表
```

例如：

```text
“查询新能源汽车 2020 到 2024 年销量”
```

LLM 可能生成：

```sql
SELECT year, metric_value
FROM industry_stats
WHERE industry_name = '新能源汽车'
ORDER BY year;
```

## 6. SQL 校验做了什么

项目会检查 SQL 是否为空、是否是允许的查询形式，并拦截明显的写操作或危险关键词。

这能降低风险，但字符串检查不是完整的数据库安全方案。更可靠的生产方案还需要：

```text
只读数据库账号
表和列白名单
参数化查询
查询超时
行数限制
数据库网络隔离
```

## 7. Mock fallback 改变了结果含义

如果 `db_engine` 不存在，`execute_sql()` 会调用：

```text
_get_mock_data(sql)
```

返回演示数据。

所以接口返回：

```text
success = true
```

并不能单独证明 SQL 查询过真实数据库。必须查看：

```text
db_engine 是否初始化
执行日志
真实 SQL
是否进入 _get_mock_data
```

## 8. Text2SQL 与 DeepResearch CodeWizard 的区别

| 维度 | Text2SQL | CodeWizard |
|---|---|---|
| 输入 | 自然语言数据库问题 | 研究阶段的数据点 |
| LLM 输出 | SQL 和查询说明 | Python 代码 |
| 执行对象 | 数据库 | Python 执行环境 |
| 主要结果 | 行列数据 | 分析输出和图片图表 |
| 安全重点 | 只读、表权限、SQL 注入 | 代码隔离、资源限制、系统调用 |
| 页面用途 | 数据库页表格/图表 | DeepResearch 研究详情 |

不要因为两者都能“生成代码”就把它们当成同一个功能。

## 9. 本课练习

1. 为什么长期记忆要同时存 PostgreSQL 和 Milvus？
2. 为什么短期聊天历史不能完全替代长期记忆？
3. Text2SQL 从自然语言到结果要经过哪些步骤？
4. 如果 Text2SQL 返回成功数据，怎样证明这些数据不是 Mock？
5. CodeWizard 和 Text2SQL 的安全重点分别是什么？
