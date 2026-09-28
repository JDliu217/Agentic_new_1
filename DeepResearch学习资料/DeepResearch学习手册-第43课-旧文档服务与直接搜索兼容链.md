# DeepResearch 学习手册：第 43 课

## 旧文档服务与直接搜索兼容链

项目同时保留了新知识库链和较早的文档/搜索接口。它们名称相近，但数据模型、外部服务和返回契约不同。本课专门训练“沿 import 和调用方识别真实链路”的能力。

## 1. 旧文档 Router 的入口

文件：

```text
backend/app/router/document_router.py
```

接口：

```text
POST /documents/upload
GET  /documents/list
POST /documents/delete
POST /documents/retrieve
```

Router 通过 `ServiceConfig.get_api_config()` 创建 `DocumentService`，并取得默认 dataset id。上传接口支持 PDF、DOCX、XLSX、XLS 和 TXT，读取文件后暂存到 `/tmp`，再调用 `process_document_with_docmind()`，最后删除临时文件。

## 2. 旧上传链路

```text
multipart file
  → 扩展名检查
  → /tmp/文件名
  → process_document_with_docmind()
  → 文档解析/切片/向量或索引写入
  → 返回处理数量
```

这个接口和新知识库上传的关键区别：

| 维度 | 旧 `/documents/upload` | 新 `/knowledge-bases/{kb_id}/documents` |
|---|---|---|
| 归属 | 默认外部 dataset/index | PostgreSQL `KnowledgeBase` |
| 文档元数据 | 外部 `DocumentService` 返回 | 本地 `Document` 表 |
| 处理状态 | 响应中直接返回结果 | `pending → processing → completed/failed` |
| 用户权限 | Router 没有强制用户依赖 | 按当前用户检查知识库归属 |
| 前端入口 | 兼容页面/旧聊天链 | 新知识库页面 |

不要因为两者都使用 DocMind 或“文档”这个词，就认为它们会自动共享文档记录。

## 3. 旧接口的响应与异常边界

`document_router.py` 使用 `UploadDocumentResponse`、`DocumentListResponse` 和 `DeleteDocumentsResponse`。列表接口对“document None”这类外部服务错误做了特殊降级，返回空列表；其他错误才转成 HTTP 异常。

这意味着页面看到空列表时，可能有两种原因：确实没有文档，或外部服务返回了被代码识别的特定错误。排错时要看后端日志和原始外部响应，不能只看页面结果。

源码还显示上传临时路径直接使用文件名：

```python
temp_file_path = f"/tmp/{file.filename}"
```

这会带来同名并发覆盖、特殊路径字符和跨平台路径差异等工程风险。生产实现应使用安全的临时文件 API、随机文件名、大小限制和路径清理。

## 4. 直接 Web 搜索接口

文件：

```text
backend/app/router/search_router.py
backend/app/service/web_search_service.py
```

接口：

```text
POST /search/web
```

请求由 `WebSearchRequest` 描述，包括 query、地区语言、纠错、页码和 search_type。Router 创建 `WebSearchService`，读取 `serper_api_key`，调用搜索并把结果格式化为 `WebSearchResponse`。

## 5. Serper 搜索和 V2 Scout 搜索不是同一契约

```text
/search/web
  → WebSearchService
  → Serper API
  → WebSearchResponse

/research/stream
  → DeepScout
  → 项目配置的 Bocha/本地检索/股票查询等
  → ResearchState + SSE search_results / stock_quote
```

前者是一个独立的 JSON 搜索工具接口，后者是研究流程中的一个 Agent 阶段。即使两者最终都返回网页来源，字段名、调用时机、来源聚合方式和前端处理方式都可能不同。

## 6. 为什么保留兼容链

项目演进过程中可能已经存在：

- 旧聊天页面依赖旧文档服务。
- 早期接口使用外部数据集或 Elasticsearch 兼容格式。
- 新知识库需要 PostgreSQL 元数据和 Milvus 集合管理。
- V2 研究需要把搜索结果写入共享状态并通过 SSE 展示。

兼容代码可以让旧调用方继续工作，但也会带来配置漂移、重复模型和权限不一致。阅读项目时要给每条链标注：当前主路径、兼容路径、独立工具还是未接通路径。

## 7. 本课排错方法

### 旧文档上传失败

```text
文件扩展名
  → /tmp 文件是否创建
  → DocMind 凭证/请求
  → ServiceConfig dataset 配置
  → 外部服务返回 code/message
```

### `/search/web` 返回空结果

```text
SERPER_API_KEY
  → WebSearchService.search()
  → 原始 search_results 是否包含 error
  → extract_search_results()
  → WebSearchResponse
```

### V2 搜索阶段失败

不要只调用 `/search/web` 复现。应检查 `DeepScout`、Bocha Key、研究开关、Redis/Milvus 本地检索和 SSE 事件日志。

## 8. 本课练习

### 练习 A：比较两条文档链

从两个上传 Router 出发，列出它们的模型、处理状态、集合/数据集命名、权限依赖和前端入口。

### 练习 B：比较两个搜索入口

说明 `/search/web` 和 `DeepScout` 分别使用什么 API、返回什么契约、如何进入前端。

### 练习 C：识别安全风险

指出旧文档上传临时路径的三个风险，并写出安全替代方案。

## 9. 面试追问

1. 为什么一个项目会同时存在两套知识库或文档接口？
2. 为什么搜索结果为空不一定代表搜索服务返回了空数组？
3. `/search/web` 和 V2 搜索 Agent 的事件契约为什么不能直接复用？
4. 如何改造 `/tmp/{filename}` 以避免并发覆盖和路径穿越？

