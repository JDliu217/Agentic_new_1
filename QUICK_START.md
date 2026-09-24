# RAG 快速启动指南 🚀

## 一键启动所有服务

```bash
./start_rag_all.sh
```

## 或手动启动（4个步骤）

### 步骤 1: 启动 Milvus
```bash
docker compose up -d
# 等待 30 秒
python test_milvus.py
```

### 步骤 2: 导入数据
```bash
python milvus_insert.py
```

### 步骤 3: 启动 API 服务
```bash
# 新终端
python milvus_api.py
```

### 步骤 4: 启动 RAG 服务

#### 选项 A: 完整版 RAG（带高级功能）
```bash
# 新终端
python rag_service.py
```

#### 选项 B: 简化版 RAG（仅基础功能）
```bash
# 新终端
python rag_service_simple.py
```

## 测试服务

```bash
# 测试完整版 RAG（高级功能）
python test_rag.py
python test_rag_enhanced.py

# 测试简化版 RAG（基础功能）
python test_rag_simple.py
```

## 访问地址

- **完整版 RAG API**: http://localhost:8001/docs
- **简化版 RAG API**: http://localhost:8002/docs
- **向量 API**: http://localhost:8000/docs
- **数据可视化**: http://localhost:3000

## 测试请求

### Postman/curl

#### 完整版 RAG（带高级功能）
```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是人工智能？",
    "use_rag": true,
    "enable_intent_detection": true,
    "enable_query_expansion": true
  }'
```

#### 简化版 RAG（仅基础功能）
```bash
curl -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是人工智能？",
    "top_k": 5
  }'
```

### Python

#### 完整版 RAG
```python
import requests

response = requests.post(
    "http://localhost:8001/chat",
    json={
        "question": "AI大模型的发展趋势",
        "use_rag": True,
        "enable_intent_detection": True,
        "enable_query_expansion": True
    }
)
print(response.json()["answer"])
```

#### 简化版 RAG
```python
import requests

response = requests.post(
    "http://localhost:8002/chat",
    json={
        "question": "AI大模型的发展趋势",
        "top_k": 5
    }
)
print(response.json()["answer"])
```

## 停止所有服务

```bash
./stop_rag_all.sh
```

## 常见命令

```bash
# 查看日志
tail -f logs/rag_service.log

# 检查端口
lsof -i :8001  # 完整版 RAG
lsof -i :8002  # 简化版 RAG

# 查看 Docker
docker ps | grep milvus

# 激活环境
conda activate milvus-rag
```

## ⚠️ 注意事项

1. 确保 `.env` 文件包含 `DASHSCOPE_API_KEY`
2. 端口不能被占用（8000, 8001, 8002, 3000, 19530）
3. Docker 需要至少 8GB 内存
4. 首次启动需要等待 30 秒

---
详细文档：[README_RAG.md](README_RAG.md)