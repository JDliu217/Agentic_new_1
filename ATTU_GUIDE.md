# Attu 可视化面板使用指南

## 启动 Attu

```bash
# 确保 Milvus 已启动
docker compose up -d

# 访问 Attu
http://localhost:3000
```

## 连接 Milvus

首次访问时：
1. **Milvus Address**: `localhost:19530` 或 `host.docker.internal:19530`
2. 点击 **Connect** 连接

## 查看数据详情

### 1. 浏览集合
- 左侧菜单选择 **Collections**
- 点击 `ai_knowledge_base` 集合

### 2. 逐条查看数据
- 点击 **Data** 标签
- 可以看到每条数据的所有字段：
  - `id`: 数据ID
  - `text`: 文本内容
  - `source`: 来源文件
  - `section`: 章节
  - `keywords`: 关键词
  - `embedding`: 向量（1024维）

### 3. 数据筛选
- 使用 **Filter** 功能：
  ```
  section == "前言"
  source == "ai_dev.md"
  ```

### 4. 向量搜索
1. 点击 **Vector Search** 标签
2. 输入搜索文本（会自动生成向量）
3. 或直接输入向量数组
4. 设置返回数量（Top K）
5. 点击 **Search**

## 数据管理功能

### 查看索引
- 点击 **Schema** 标签
- 查看字段定义和索引信息

### 查看统计
- **Overview** 显示：
  - 总数据量
  - 内存使用
  - 索引状态

### 数据导出
- 选择数据
- 点击 **Export** 按钮
- 支持 JSON/CSV 格式

## 高级功能

### 执行查询
使用 Query 表达式：
```python
# 查看特定章节
section == "第一章"

# 查看ID范围
id > 100 and id < 200

# 模糊匹配
text like "%人工智能%"
```

### 批量操作
- 批量选择数据
- 批量删除（谨慎使用）

## 常见问题

1. **连接失败**
   - 检查 Milvus 是否启动
   - 尝试 `host.docker.internal:19530`

2. **数据不显示**
   - 确保已运行 `python milvus_insert.py`
   - 刷新页面

3. **向量搜索无结果**
   - 检查集合是否已加载
   - 确认索引已创建