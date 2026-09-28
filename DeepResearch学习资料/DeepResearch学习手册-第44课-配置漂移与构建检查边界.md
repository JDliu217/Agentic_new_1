# DeepResearch 学习手册：第 44 课

## 配置漂移与构建检查边界

这一课记录两类很容易被忽略的工程事实：同一项目存在多个配置来源，以及“构建成功”不一定等于“类型检查和代码规范全部通过”。

## 1. 两份后端依赖清单

项目同时有：

```text
backend/requirements.txt
backend/app/requirements.txt
```

它们的版本写法和包集合不同。根 README 推荐安装 `backend/requirements.txt`，而 `backend/app/requirements.txt` 更像另一套历史或服务依赖清单。若新手在不同目录执行安装命令，可能得到不同 Python 环境。

排错时应记录：

1. 当前工作目录。
2. 使用了哪一个 requirements 文件。
3. Python 解释器路径和版本。
4. 关键包版本，例如 FastAPI、OpenAI、pymilvus、SQLAlchemy。

不能只说“已经安装依赖”，因为两份清单并不等价。

## 2. Vite build、TypeScript 和 ESLint 的边界

本项目的三个检查命令职责不同：

| 命令 | 当前观察 | 能证明什么 |
|---|---|---|
| `npm run build` | 通过，有 bundle 体积警告 | Vite 能完成模块转换和生产打包 |
| `npx tsc -b --pretty false` | 失败 | 严格 TypeScript 检查发现类型/未使用变量问题 |
| `npm run lint` | 失败 | ESLint 发现规则错误和警告 |

Vite 默认可以在不完成完整 TypeScript 类型检查的情况下打包，因此不能用 build 通过替代 `tsc` 通过。面试或排错报告中要把三者分开写。

## 3. 当前 TypeScript 错误的代表性类别

本次检查发现：

- ECharts 实例可能为 `null`。
- 自定义 `EChartsOption` 与 ECharts 官方类型不完全兼容。
- 多处未使用变量和导入。
- `researching` 与前端 `ResearchStep` 联合类型存在不一致。
- `ChatEnterData` 与 `newchat.tsx` 传入的 `attachmentIds` 不一致。
- `store/device.ts` 的持久化回调签名不匹配。

这些问题说明“页面能被打包”与“类型契约完整”是两个不同的质量维度。当前任务是不修改项目源码，所以只记录证据，不擅自修复。

## 4. 环境变量配置来源

当前至少有：

```text
backend/.env.example
frontend/.env
frontend/vite.config.ts
backend/app/config/llm_config.py
backend/app/service/config.py
```

同一个概念可能有不同命名，例如 LLM Base URL。排查时按实际读取点反向确认，而不是只照抄 `.env.example`。前端变量必须以 `VITE_` 开头才能进入浏览器构建；后端密钥不应暴露给前端。

## 5. README、源码和日志的证据等级

当三者冲突时，建议按以下顺序判断：

```text
实际运行日志 / 请求结果
  > 当前源码和配置文件
  > README 和示例命令
```

README 记录的是作者意图或某个历史状态，源码说明当前默认行为，运行结果才能证明当前环境中的真实行为。三者都要保留，因为 README 的差异本身也是工程风险。

## 6. 本课练习

### 练习 A：依赖清单差异

找出两份 requirements 中三个不同包或版本，并说明你会选择哪一份作为当前启动依据以及为什么。

### 练习 B：设计 CI 检查

给项目设计一个最小 CI 顺序：Python 编译、TypeScript、ESLint、Vite build。说明每一步失败时负责哪一类问题。

### 练习 C：追踪配置

从 `VITE_API_BASE` 和 `DASHSCOPE_BASE_URL` 各追踪到一个实际读取点，并说明它们为什么不能混用。

## 7. 面试追问

1. 为什么 Vite build 通过仍可能存在 TypeScript 错误？
2. 多份 requirements 文件会造成什么问题？
3. 如何在 CI 中防止 README 端口说明与源码长期漂移？
4. 哪些环境变量可以进入前端，哪些必须只留在后端？

