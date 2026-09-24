# RAG 服务使用指南

## 🏗️ 系统架构

```
┌─────────────────────────────────────┐
│         应用层（你的应用）            │
│    Web App / Mobile / Bot / API     │
└────────────┬────────────────────────┘
             │ HTTP (8001)
┌────────────▼────────────────────────┐
│      RAG 业务服务层                  │
│      rag_service.py                 │
│  • 意图识别 (LLM)                   │
│  • 查询扩展                         │
│  • 领域过滤                         │
│  • 答案生成                         │
└────────────┬────────────────────────┘
             │ HTTP (8000)
┌────────────▼────────────────────────┐
│     向量数据库 API 层                │
│      milvus_api.py                  │
│  • 向量检索                         │
│  • CRUD 操作                        │
└────────────┬────────────────────────┘
             │ gRPC (19530)
┌────────────▼────────────────────────┐
│      Milvus 向量数据库               │
│    docker-compose.yml               │
└─────────────────────────────────────┘
```

## 🚀 快速启动

### 前置准备

```bash
# 1. 确保已安装 conda
conda --version

# 2. 确保已安装 Docker
docker --version
```

### 步骤 1：环境配置

```bash
# 创建并激活 conda 环境
conda create -n milvus-rag python=3.9 -y
conda activate milvus-rag

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
echo "DASHSCOPE_API_KEY=你的API密钥" > .env
```

### 步骤 2：启动服务（按顺序）

#### 2.1 启动 Milvus 数据库

```bash
# 方式一：使用脚本
./start_milvus.sh
# 选择 1 启动

# 方式二：直接用 Docker
docker compose up -d
```

等待 30 秒，测试连接：
```bash
python test_milvus.py
```

访问 Attu 可视化面板：http://localhost:3000

#### 2.2 导入知识库数据

```bash
# 导入默认数据（ai_dev.md）
python milvus_insert.py

# 或导入自定义文件
# 修改 milvus_insert.py 中的 file_path
```

#### 2.3 启动 Milvus API 服务

```bash
# 新开终端，激活环境
conda activate milvus-rag

# 启动 API 服务（端口 8000）
python milvus_api.py
```

访问 API 文档：http://localhost:8000/docs

#### 2.4 启动 RAG 服务

```bash
# 再开新终端，激活环境
conda activate milvus-rag

# 启动 RAG 服务（端口 8001）
python rag_service.py
```

访问 RAG API 文档：http://localhost:8001/docs

## ✅ 验证服务状态

```bash
# 测试基础 RAG 功能
python test_rag.py

# 测试高级功能（意图识别、查询扩展等）
python test_rag_enhanced.py
```

## 📡 API 使用示例

### 1. 基础对话

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是人工智能？",
    "use_rag": true,
    "top_k": 5
  }'
```

### 2. 高级对话（带意图识别和查询扩展）

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "人工智能在医疗领域的应用",
    "use_rag": true,
    "top_k": 5,
    "enable_intent_detection": true,
    "enable_query_expansion": true
  }'
```

### 3. Python 客户端示例

```python
import requests

# RAG 服务地址
RAG_URL = "http://localhost:8001"

# 发送请求
response = requests.post(
    f"{RAG_URL}/chat",
    json={
        "question": "大模型训练需要什么？",
        "use_rag": True,
        "top_k": 5,
        "enable_intent_detection": True,
        "enable_query_expansion": True
    }
)

# 获取结果
result = response.json()
print(f"领域: {result['domain']}")
print(f"回答: {result['answer']}")
print(f"引用来源: {result['sources']}")
```

## 🎯 核心功能

### 意图识别
- 自动识别问题领域：`law`、`finance`、`ai`、`general`
- LLM 驱动，返回置信度和理由
- 低置信度通用问题直接 LLM 回答

### 查询扩展
- 基于领域背景生成 3 个扩展查询
- 提高检索覆盖度和召回率
- 多查询结果融合去重

### 参考片段
- 明确标注引用来源
- 显示相关度分数
- 回答中包含参考编号

### 多轮对话
- 支持会话历史管理
- 上下文理解和延续
- `/chat/with-history` 端点

## 📊 服务端口汇总

| 服务 | 端口 | 说明 | 访问地址 |
|------|------|------|----------|
| Milvus | 19530 | 向量数据库 | gRPC 协议 |
| Attu | 3000 | 数据可视化 | http://localhost:3000 |
| MinIO | 9001 | 对象存储 | http://localhost:9001 |
| Milvus API | 8000 | 向量检索 API | http://localhost:8000/docs |
| RAG Service | 8001 | RAG 对话服务 | http://localhost:8001/docs |

## 🔧 常见问题

### Q1: 服务启动失败
```bash
# 检查端口占用
lsof -i :8000
lsof -i :8001

# 杀死占用进程
kill -9 <PID>
```

### Q2: Milvus 连接失败
```bash
# 检查 Docker 容器
docker ps | grep milvus

# 查看日志
docker compose logs milvus-standalone
```

### Q3: API Key 错误
```bash
# 检查环境变量
cat .env

# 确保格式正确
DASHSCOPE_API_KEY=sk-xxxxx
```

### Q4: 内存不足
```bash
# 检查 Docker 资源
docker system df

# 清理未使用资源
docker system prune -a
```

## 🛑 停止服务

```bash
# 停止 RAG 服务
# 在运行 rag_service.py 的终端按 Ctrl+C

# 停止 Milvus API
# 在运行 milvus_api.py 的终端按 Ctrl+C

# 停止 Milvus
docker compose down

# 完全清理（包括数据）
docker compose down -v
```

## 📝 开发指南

### 添加新的知识库

1. 准备 Markdown 文件
2. 修改 `milvus_insert.py` 中的 `file_path`
3. 运行 `python milvus_insert.py`

### 自定义领域

编辑 `rag_service.py`：
```python
class Domain(str, Enum):
    LAW = "law"
    FINANCE = "finance"
    AI = "ai"
    MEDICAL = "medical"  # 新增领域
    GENERAL = "general"
```

### 调整模型参数

编辑 `rag_service.py`：
```python
completion = llm_client.chat.completions.create(
    model="qwen-plus",        # 模型选择
    temperature=0.7,          # 创造性 (0-1)
    max_tokens=2000          # 最大长度
)
```

## 📚 项目文件说明

| 文件 | 功能 |
|------|------|
| `docker-compose.yml` | Milvus 服务配置 |
| `milvus_config.py` | 数据库配置 |
| `milvus_insert.py` | 数据导入 |
| `milvus_query.py` | 查询测试 |
| `milvus_api.py` | 向量检索 API |
| `rag_service.py` | RAG 核心服务 |
| `test_rag.py` | 基础测试 |
| `test_rag_enhanced.py` | 高级功能测试 |

## 🚦 启动检查清单

- [ ] Docker 已启动
- [ ] Conda 环境已激活
- [ ] .env 文件已配置
- [ ] Milvus 运行正常（端口 19530）
- [ ] 数据已导入（运行 insert 脚本）
- [ ] Milvus API 运行中（端口 8000）
- [ ] RAG 服务运行中（端口 8001）

## 💡 最佳实践

1. **服务启动顺序**：Milvus → 导入数据 → API → RAG
2. **使用 tmux/screen**：保持服务在后台运行
3. **监控日志**：实时查看服务输出
4. **定期备份**：导出重要的向量数据
5. **性能优化**：根据需求调整 top_k 和 vector_weight

## 📞 获取帮助

- 查看 API 文档：http://localhost:8001/docs
- 查看数据：http://localhost:3000 (Attu)
- 测试查询：`python test_rag_enhanced.py`
- 查看日志：服务终端输出

---

**祝你使用愉快！** 🎉