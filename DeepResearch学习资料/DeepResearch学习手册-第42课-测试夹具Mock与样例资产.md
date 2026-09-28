# DeepResearch 学习手册：第 42 课

## 测试夹具、Mock 与样例资产

项目中还有一组不属于主业务源码、但会影响开发和验证的文件：前端 Mock、后端测试脚本、测试文档、Excel 和根目录 PDF。它们必须和真实运行证据分开。

## 1. 前端 Mock SSE

入口：

```text
frontend/mock/session.ts
frontend/mock/data/chat
frontend/mock/data/deepsearch
```

Mock 暴露模拟的 `/api/chat/session`、`/api/chat/completion` 和 `/api/research/stream`。它们按行读取本地文件，设置 `text/event-stream`，每行延迟后写入响应。

```text
本地 mock 文件
  → Vite Mock 插件
  → SSE 文本
  → 前端 ReadableStream 解析器
```

它很适合验证前端的加载状态、SSE 拆包、研究步骤和报告渲染，但不能证明 FastAPI、LLM、搜索、数据库或 Milvus 已经工作。`vite.config.ts` 当前 `viteMockServe({ enable: false })`，所以默认开发模式并不会自动启用这些 Mock。

## 2. Mock 数据与真实事件的差异

`mock/data/deepsearch` 中的事件包含旧格式的 `status`、`subqueries` 等示例。当前 V2 主链路还使用 `research_start`、`research_step`、`search_results`、`knowledge_graph`、`chart` 和 `research_complete` 等事件。

因此，看到 Mock 能在页面显示，不代表它覆盖了当前后端所有事件契约。测试前应先核对 Mock 事件是否仍与 `chat/index.tsx` 的分支一致。

## 3. 后端 V2 测试脚本

`backend/app/scripts/test_deep_research_v2.py` 名称虽然包含测试，但它不是纯单元测试：

1. 要求真实 `DASHSCOPE_API_KEY` 和 `BOCHA_API_KEY`。
2. 会创建真实的 `DeepResearchV2Service`。
3. 会调用真实 LLM 和搜索 API。
4. 会检查阶段事件、最终报告和错误数量。
5. 还会按顺序单独调用 ChiefArchitect、DeepScout 和 CodeWizard。

运行它需要外部网络、配额、正确模型和环境变量。没有这些依赖时失败不能直接归因于 Agent 代码。

## 4. 后端 `test/` 目录

`backend/test/` 中的 PDF、Excel 和 PNG 是测试输入或历史生成结果：

- `test_doc.pdf` 可以用于文档上传和解析实验。
- `数据.xlsx` 可以用于表格解析或数据分析实验。
- PNG 可以作为 CodeWizard 或图表生成的输出样例。

文件存在不等于当前测试会自动读取它们。必须从脚本、路径和 API 调用确认实际使用关系。

## 5. 根目录 `data/` PDF

根 `data/` 中的几份行业研究 PDF 是样例知识资产。它们可以用于知识库上传、文档切片和本地召回实验，但不能直接说明已写入 Milvus。要证明导入成功，至少需要：

```text
上传响应成功
  → Document 状态 completed
  → chunk_count 有值
  → Milvus 集合中能查到向量/切片
  → 查询返回相关内容
```

## 6. 如何区分四种证据

| 证据 | 能证明什么 |
|---|---|
| Mock SSE 能渲染 | 前端事件解析和组件展示在该样例下可工作 |
| 后端脚本通过 | 指定环境和外部服务下的一次测试通过 |
| 测试文件存在 | 有可供实验的输入或历史输出 |
| 真实端到端请求成功 | 当前环境中的完整链路确实连通 |

不能把第一、二种证据扩大解释成第四种。

## 7. 本课练习

### 练习 A：关闭后端的前端演示

说明如何启用或替换前端 Mock，并记录它能验证哪些层、不能验证哪些层。

### 练习 B：核对事件契约

从 Mock 的一条 `data:` 记录出发，找到 `chat/index.tsx` 的解析分支，并判断它是否属于当前 V2 事件格式。

### 练习 C：设计知识库验证证据

用根目录 PDF 写出从上传到 Milvus 召回的四个必须观察点。

## 8. 面试追问

1. Mock SSE 为什么不能证明后端 SSE 正常？
2. 如何判断一个脚本是单元测试、集成测试还是端到端测试？
3. 测试 PDF 存在为什么不能证明知识库已经可检索？
4. 如何避免旧 Mock 事件掩盖前后端契约已经变化？

