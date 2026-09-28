# DeepResearch 学习手册·第 62 课

## 启动验收：从代码可运行到系统可用

“项目能启动”有不同强度，不能只看一个命令返回成功。本课建立一套从弱到强的证据等级。

---

## 1. 五个证据等级

### 等级 1：文件存在

能看到 `backend`、`frontend`、Compose、环境变量示例和初始化脚本。

只能证明项目文件在磁盘上。

### 等级 2：静态检查通过

后端：

```bash
python -m compileall -q app
```

前端：

```bash
npm run build
```

本次核对结果：Python 编译通过，Vite 构建通过；前端只有 bundle 体积警告。

这能证明语法和生产构建基本可生成，不能证明外部服务可用。

### 等级 3：进程可访问

例如访问 FastAPI `/hello` 或打开 Vite 页面。

这只能证明某个进程响应了请求，不能证明 PostgreSQL、Redis、Milvus、LLM 和搜索服务正常。

### 等级 4：基础设施健康

需要分别验证：

```text
PostgreSQL：pg_isready 或实际 SQL
Redis：redis-cli ping
Milvus：/healthz
Elasticsearch：/_cluster/health
```

容器状态为 `running` 仍不等于服务已经 ready。

### 等级 5：业务端到端成功

最终要验证：

```text
登录
→ 创建会话
→ POST /research/stream
→ 收到多个 SSE 事件
→ 六个 Agent 执行
→ 检查点写入 PostgreSQL
→ 页面显示报告、图表和来源
```

只有这一层才足以说明 DeepResearch 主链路真实可用。

---

## 2. 项目启动脚本做了什么

文件：`start-services.sh`。

它的主要流程是：

```text
检查 docker info
→ docker-compose up -d
→ 固定 sleep 10 秒
→ 检查 PostgreSQL、Redis、Milvus、Elasticsearch
```

脚本会打印服务状态，但部分健康检查失败时只是输出 warning，并不一定让整个启动流程失败。因此“脚本显示启动完成”仍需要人工核对具体健康接口。

此外，脚本只启动中间件：

- 后端仍需单独启动。
- 前端仍需单独启动。

---

## 3. Compose 中各服务的职责

根目录 `docker-compose.yml` 包含：

| 服务 | 作用 | 典型端口 |
|---|---|---:|
| PostgreSQL | 用户、会话、消息、检查点和业务数据 | 5432 |
| Redis | 取消标志、缓存和兼容会话能力 | 6379 |
| Milvus | 文档、知识库和长期记忆向量 | 19530 |
| etcd | Milvus 元数据依赖 | 2379 |
| MinIO | Milvus 对象存储依赖 | 9000/9001 |
| Elasticsearch | 可选全文检索 | 宿主机 1200 映射到容器 9200 |

Docker Compose 不包含 FastAPI 和 Vite 应用进程，这是项目启动时最容易误判的地方。

---

## 4. 分层启动顺序

建议按以下顺序收集证据：

```text
1. 环境变量和依赖文件
2. Docker/中间件
3. PostgreSQL 初始化表
4. FastAPI 导入和 /hello
5. Vite 页面和代理
6. 登录与 JWT
7. 普通聊天
8. 知识库上传和召回
9. DeepResearch SSE
10. 外部搜索、LLM、Embedding 和 DocMind
```

如果第 2 层失败，不要直接调 Agent；如果第 5 层失败，不要先查 Milvus；如果第 9 层失败，再根据 SSE 事件定位 Agent 或外部服务。

---

## 5. 当前机器的真实验证结果

已完成：

- `python -m compileall -q app`：通过。
- `npm run build`：通过。

未完成：

- 当前机器找不到 `docker` 命令。
- 因此无法启动 Compose 基础设施。
- PostgreSQL、Redis、Milvus、Elasticsearch、DocMind、外部搜索和真实 LLM 尚未做本机端到端验证。

这不是“源码有问题”的证据，而是运行环境缺少 Docker，导致更高等级的验证无法进行。

---

## 6. 面试中如何诚实表达验证程度

推荐表达：

> 我完成了后端 Python 编译和前端 Vite 构建检查，并通过源码确认了 V2 的请求、Agent、SSE、检查点和前端恢复链路。但当前验证环境没有 Docker，所以 PostgreSQL、Redis、Milvus、DocMind、外部搜索和真实 LLM 的端到端结果还没有被本机运行证据证明。代码路径和真实运行结果我会分开描述。

这比简单说“项目已经跑通”更准确，也更符合工程排查和面试要求。

---

## 综合练习

如果 `npm run build` 通过，但页面登录后请求 `/research/stream` 返回 500，你应该如何判断？

至少按以下顺序回答：

1. 构建通过证明了什么？
2. 它没有证明什么？
3. 第一批要查看哪些后端日志和依赖健康状态？
4. 为什么不能因为前端构建成功，就断言 DeepResearch 可用？

参考方向：构建只证明前端静态产物能生成；应检查 FastAPI 堆栈、配置导入、PostgreSQL/Redis、LLM Key 和 `/research/stream` 请求参数，再根据错误阶段继续定位。

