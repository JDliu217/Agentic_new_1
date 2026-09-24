# RAG 服务版本对比

## 📊 功能对比表

| 功能特性 | 简化版 (rag_service_simple.py) | 完整版 (rag_service.py) |
|---------|--------------------------------|------------------------|
| **端口** | 8002 | 8001 |
| **基础 RAG** | ✅ | ✅ |
| **向量检索** | ✅ | ✅ |
| **LLM 问答** | ✅ | ✅ |
| **意图识别** | ❌ | ✅ LLM 驱动 |
| **查询扩展** | ❌ | ✅ 3个扩展查询 |
| **领域过滤** | ❌ | ✅ law/finance/ai |
| **混合搜索** | ❌ | ✅ 向量+关键词 |
| **参考片段** | 基础 | ✅ 详细引用 |
| **置信度评分** | ❌ | ✅ |
| **多轮对话** | ❌ | ✅ |
| **代码复杂度** | 简单 (~150行) | 复杂 (~600行) |
| **响应速度** | 快 | 较慢（多次 LLM 调用） |
| **资源消耗** | 低 | 较高 |

## 🎯 使用场景建议

### 使用简化版的场景：
- ✅ POC 验证和快速原型
- ✅ 简单的问答需求
- ✅ 资源受限的环境
- ✅ 需要快速响应
- ✅ 学习 RAG 基本原理
- ✅ 集成到现有系统作为基础模块

### 使用完整版的场景：
- ✅ 生产环境部署
- ✅ 需要精确的领域分类
- ✅ 复杂的查询需求
- ✅ 需要查询优化和扩展
- ✅ 多领域知识库
- ✅ 需要详细的引用追踪
- ✅ 企业级应用

## 🔧 技术差异

### 简化版架构
```
用户查询 → 向量检索 → LLM 生成 → 返回答案
```

### 完整版架构
```
用户查询 → 意图识别 → 查询扩展 → 向量+关键词检索 →
领域过滤 → 结果融合 → LLM 生成 → 引用标注 → 返回答案
```

## 📝 API 接口对比

### 简化版请求
```json
{
  "question": "什么是人工智能？",
  "top_k": 5
}
```

### 完整版请求
```json
{
  "question": "什么是人工智能？",
  "use_rag": true,
  "top_k": 5,
  "enable_intent_detection": true,
  "enable_query_expansion": true,
  "vector_weight": 0.7,
  "keyword_weight": 0.3
}
```

## 🚀 启动命令

```bash
# 简化版
python rag_service_simple.py  # http://localhost:8002

# 完整版
python rag_service.py         # http://localhost:8001
```

## 💡 选择建议

### 开始时用简化版
如果你是：
- 刚接触 RAG 技术
- 需要快速验证想法
- 资源有限
- 简单的问答场景

### 升级到完整版
当你需要：
- 更准确的答案
- 多领域支持
- 查询优化
- 生产级部署
- 详细的来源追踪

## 🔄 从简化版迁移到完整版

1. **API 兼容性**：完整版向下兼容简化版的基础功能
2. **端口切换**：将请求从 8002 改为 8001
3. **参数升级**：逐步启用高级功能参数
4. **性能优化**：根据需求调整权重和参数

## 📊 性能对比

| 指标 | 简化版 | 完整版 |
|------|--------|--------|
| 平均响应时间 | ~1-2秒 | ~3-5秒 |
| LLM 调用次数 | 1次 | 2-3次 |
| 内存占用 | ~200MB | ~400MB |
| CPU 使用率 | 低 | 中等 |

## 🛠️ 定制建议

### 简化版定制
- 修改 `generate_answer()` 函数调整提示词
- 修改 `retrieve_documents()` 调整检索策略
- 添加简单的后处理逻辑

### 完整版定制
- 扩展 `Domain` 枚举添加新领域
- 自定义 `detect_intent_with_llm()` 逻辑
- 调整查询扩展策略
- 配置混合搜索权重

## 📚 代码示例

### 使用简化版
```python
import requests

response = requests.post(
    "http://localhost:8002/chat",
    json={"question": "什么是 RAG？", "top_k": 3}
)
print(response.json()["answer"])
```

### 使用完整版
```python
import requests

response = requests.post(
    "http://localhost:8001/chat",
    json={
        "question": "什么是 RAG？",
        "use_rag": True,
        "enable_intent_detection": True,
        "enable_query_expansion": True
    }
)
result = response.json()
print(f"领域: {result['domain']}")
print(f"置信度: {result['confidence']}")
print(f"答案: {result['answer']}")
```

## 🔍 调试建议

### 简化版调试
```bash
# 查看日志
python rag_service_simple.py

# 测试端点
curl http://localhost:8002/test
```

### 完整版调试
```bash
# 查看详细日志
tail -f logs/rag_service.log

# 测试意图识别
python test_rag_enhanced.py
```

## 📈 升级路径

1. **第一阶段**：使用简化版验证基础 RAG 功能
2. **第二阶段**：测试完整版的高级功能
3. **第三阶段**：根据业务需求定制功能
4. **第四阶段**：生产环境优化和部署

---

选择适合你需求的版本，随时可以在两个版本间切换！