# Milvus RAG 系统

基于 Milvus 向量数据库的 RAG（检索增强生成）知识库系统，支持向量检索、关键词检索和混合检索。

## 快速开始

### 1. 环境准备

```bash
# 创建 conda 环境
conda create -n milvus-rag python=3.9 -y

# 激活环境
conda activate milvus-rag

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

创建 `.env` 文件：
```bash
echo "DASHSCOPE_API_KEY=your-api-key-here" > .env
```

### 3. 启动 Milvus

```bash
# 方法一：使用脚本（推荐）
chmod +x start_milvus.sh
./start_milvus.sh
# 选择 1 启动服务

# 方法二：直接使用 Docker Compose
docker compose up -d
```

等待 30 秒后测试连接：
```bash
python test_milvus.py
```

### 3.1 访问可视化面板 Attu

启动 Milvus 后，可以通过 Attu 面板查看数据：
```
http://localhost:3000
```

在 Attu 中可以：
- 逐条查看数据详情
- 执行向量搜索
- 管理集合和索引
- 查看系统状态

### 4. 导入数据

```bash
python milvus_insert.py
```

### 5. 测试查询

```bash
# 交互式查询
python milvus_query.py

# 或启动 API 服务
python milvus_api.py
# 访问 http://localhost:8000/docs 查看 API 文档
```

## 项目结构

```
RAG/
├── milvus.doc/
│   └── ai_dev.md          # 知识库源文件
├── milvus_config.py       # 配置文件
├── milvus_insert.py       # 数据导入
├── milvus_query.py        # 查询检索
├── milvus_delete.py       # 数据删除
├── milvus_view.py         # 数据查看
├── milvus_api.py          # API 服务
├── test_milvus.py         # 连接测试
├── docker-compose.yml     # Docker 配置（含 Attu）
├── start_milvus.sh        # 启动脚本
├── requirements.txt       # Python 依赖
├── .env                   # 环境变量
└── README.md              # 本文件
```

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Milvus | 19530 | 向量数据库主服务 |
| Attu | 3000 | Web 可视化管理界面 |
| MinIO | 9001 | 对象存储控制台 |
| API | 8000 | FastAPI 服务 |

## 功能特性

- **多种检索模式**：向量检索、关键词检索、混合检索
- **智能文档切分**：按章节层级自动切分
- **RESTful API**：完整的 CRUD 接口
- **中文支持**：jieba 分词 + 阿里 embedding

## 常用命令

```bash
# 查看数据库
python milvus_view.py

# 删除数据
python milvus_delete.py

# 停止 Milvus
docker compose down

# 清理所有数据
docker compose down -v

# 退出 conda 环境
conda deactivate

# 删除 conda 环境（如需要）
conda remove -n milvus-rag --all
```

## API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/query` | 查询知识库 |
| POST | `/insert` | 插入文档 |
| POST | `/insert_file` | 上传文件 |
| DELETE | `/delete` | 删除文档 |
| GET | `/collection/info` | 集合信息 |
| GET | `/collection/stats` | 集合统计 |

## API 请求示例（Postman）

### 1. 健康检查
```
GET http://localhost:8000/health
```

响应示例：
```json
{
  "status": "healthy",
  "milvus": "connected",
  "collections_count": 1
}
```

### 2. 查询知识库
```
POST http://localhost:8000/query
Content-Type: application/json

{
  "query": "人工智能发展",
  "top_k": 5,
  "search_type": "hybrid",
  "vector_weight": 0.7,
  "rerank": false
}
```

参数说明：
- `query`: 查询文本（必填）
- `top_k`: 返回结果数量（默认10）
- `search_type`: 搜索类型 `vector` | `keyword` | `hybrid`（默认hybrid）
- `vector_weight`: 向量权重0-1（默认0.7）
- `rerank`: 是否重排序（默认false）

### 3. 插入文档
```
POST http://localhost:8000/insert
Content-Type: application/json

{
  "text": "这是要插入的文档内容",
  "source": "manual_input",
  "section": "测试章节"
}
```

### 4. 上传文件
```
POST http://localhost:8000/insert_file
Content-Type: multipart/form-data

file: [选择.md文件]
```

### 5. 删除文档
```
DELETE http://localhost:8000/delete
Content-Type: application/json

{
  "delete_type": "id",
  "value": [462232663569990436, 462232663569990437]
}
```

删除类型：
- `delete_type`: `id` | `source` | `section`
- `value`: 根据类型提供ID列表、来源名或章节名

示例（按来源删除）：
```json
{
  "delete_type": "source",
  "value": "ai_dev.md"
}
```

示例（按章节删除）：
```json
{
  "delete_type": "section",
  "value": "前言"
}
```

### 6. 获取集合信息
```
GET http://localhost:8000/collection/info
```

### 7. 获取集合统计
```
GET http://localhost:8000/collection/stats
```

## 系统要求

- Python 3.8+
- Conda (Anaconda/Miniconda)
- Docker & Docker Compose
- 内存 8GB+
- 磁盘 10GB+

## 故障排查

1. **连接失败**：确保 Milvus 已启动（等待 30 秒）
2. **端口占用**：检查 19530 端口
3. **内存不足**：至少需要 8GB 内存
4. **API Key 错误**：检查 `.env` 文件配置

## License

MIT