# 🔁 长期记忆更新逻辑深度分析

## 执行摘要

Mini-OpenClaw 的长期记忆系统采用"文件即记忆"的设计理念，通过 Agent 自主调用工具 + API 自动触发索引重建的双机制实现记忆更新。

---

## 核心架构图

```
用户/AI 对话 -> Agent 引擎 -> terminal_tool -> memory/MEMORY.md
                                          |
              +---------------------------+---------------------------+
              |                    索引重建触发                        |
              +---------------------------+---------------------------+
              |                           |                           |
        API 保存触发              检索时惰性重建              System Prompt 重建
      (api/files.py)           (memory_indexer.py)         (prompt_builder.py)
              |                           |                           |
              v                           v                           v
     rebuild_index()            _maybe_rebuild()            build_system_prompt()
              |                           |                           |
              +---------------------------+---------------------------+
                                          |
                                          v
                               storage/memory_index/
                               (向量索引持久化)
```

---

## 关键文件与职责

### 1. workspace/AGENTS.md - 记忆协议规范
位置：backend/workspace/AGENTS.md

核心内容:
- 何时更新记忆：用户明确要求、重要偏好、关键信息、任务总结
- 如何更新记忆：使用 terminal 工具执行文件写入操作

---

### 2. graph/agent.py - Agent 执行引擎
关键职责:
- 管理 Agent 生命周期
- 流式执行工具调用
- 支持 RAG 检索注入
- 每次对话重建 System Prompt（确保读取最新 MEMORY.md）

关键代码:
```python
async def astream(self, message: str, session_id: str):
    # RAG 检索（可选）
    if rag_mode:
        results = self.memory_indexer.retrieve(message, top_k=3)
    
    # 构建 Agent（每次重建确保最新 System Prompt）
    agent = self._build_agent()
    
    # 流式执行工具调用
    async for event in agent.astream_events(...):
        if kind == "on_tool_start":
            # 工具调用开始
        elif kind == "on_tool_end":
            # 工具调用结束
```

---

### 3. tools/terminal_tool.py - 记忆写入工具
AI 更新记忆的典型命令:
```bash
echo "## 用户偏好 - 喜欢早上开会" >> memory/MEMORY.md
```

安全机制:
- 命令黑名单过滤（rm -rf /, wget | sh 等）
- 沙箱工作目录限制
- 路径安全检查

---

### 4. api/files.py - API 层自动触发索引
核心逻辑:
```python
@router.post("/files")
async def save_file(request: SaveFileRequest):
    file_path.write_text(request.content, encoding="utf-8")
    
    if request.path == "memory/MEMORY.md":
        agent_manager.memory_indexer.rebuild_index()
    
    return {"success": True}
```

---

### 5. graph/memory_indexer.py - 向量索引管理器

#### 哈希检测机制
```python
def _get_file_hash(self):
    content = self.memory_file.read_bytes()
    return hashlib.md5(content).hexdigest()

def _maybe_rebuild(self):
    current_hash = self._get_file_hash()
    if self._file_hash != current_hash:
        return True  # 需要重建
    return False
```

#### 索引重建流程
1. 配置 Embedding (OpenAI text-embedding-3-small)
2. 读取 MEMORY.md 全文
3. SentenceSplitter 分片 (256 chars, 32 overlap)
4. 向量化并构建 VectorStoreIndex
5. 持久化到 storage/memory_index/

#### 语义检索
```python
def retrieve(self, query: str, top_k: int = 3):
    if self._maybe_rebuild():
        self.rebuild_index()
    
    retriever = self._index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query)
    
    return [{"text": node.text, "score": node.score} for node in nodes]
```

---

### 6. graph/prompt_builder.py - System Prompt 组装
记忆注入逻辑:
- RAG 模式：不直接放入全文，改为检索注入
- 非 RAG 模式：直接读取全文（受 MAX_CONTENT_LENGTH=20000 限制）

---

## 完整更新流程

### 场景 A: AI 自主更新记忆
1. 用户说："请记住，我喜欢早上开会"
2. Agent 分析需要更新记忆
3. 调用 terminal 工具执行：echo "..." >> memory/MEMORY.md
4. terminal_tool.py 安全检查后执行命令
5. Agent 回复用户："已记住您的偏好"
6. 下次对话时 System Prompt 自动包含最新记忆

### 场景 B: 前端 API 更新记忆
1. 前端调用 POST /api/files
2. api/files.py 写入文件
3. 检测到 MEMORY.md 变更，触发 rebuild_index()
4. 向量索引立即更新
5. 下次 RAG 检索可用最新记忆

### 场景 C: RAG 检索时惰性更新
1. 用户提问："我之前说过什么？"
2. memory_indexer.retrieve(query) 检测到文件哈希变更
3. 自动调用 rebuild_index()
4. 执行语义检索，返回相关片段
5. 检索结果注入对话历史

---

## 安全机制

### 1. 命令黑名单
- rm -rf /, rm -rf /*
- mkfs, dd if=
- shutdown, reboot
- wget | sh, curl | sh
- chmod -R 777 /

### 2. 路径白名单
允许访问：
- workspace/*
- memory/*
- skills/*
- knowledge/*
- SKILLS_SNAPSHOT.md

### 3. 沙箱工作目录
所有命令在 backend/ 目录下执行，HOME 环境变量也指向沙箱

---

## 索引构建参数

| 参数 | 值 | 说明 |
|------|-----|------|
| Chunk Size | 256 | 每段字符数 |
| Chunk Overlap | 32 | 段间重叠字符数 |
| Top K | 3 | 默认检索结果数 |
| Embedding 模型 | text-embedding-3-small | OpenAI Embedding |
| 持久化目录 | storage/memory_index/ | 向量索引存储位置 |
| 哈希算法 | MD5 | 文件变更检测 |

---

## 关键设计特点

1. 双重触发机制：主动触发 + 惰性触发
2. 每次对话重建 System Prompt
3. RAG/非 RAG 双模式
4. 透明可控：记忆文件是人类可读的 Markdown
5. 流式兼容：工具调用和检索结果都支持流式输出

---

## 潜在问题与改进

问题 1: AI 写入格式不可控
改进：提供专用的 update_memory 工具

问题 2: 索引重建失败静默
改进：记录失败日志，前端提示

问题 3: 无版本控制
改进：添加 MEMORY.md 版本历史

问题 4: 大文件性能
改进：增量索引，分层索引

---

## 总结

Mini-OpenClaw 的长期记忆更新机制是一个简洁而优雅的设计：

优点:
- 文件即记忆，透明可控
- 双重触发机制，保证索引及时更新
- 安全沙箱，防止恶意操作
- RAG/非 RAG 双模式，灵活适配

注意事项:
- AI 写入格式需引导规范
- 大文件时建议启用 RAG 模式
- 索引重建失败需关注日志

这套机制完美体现了项目的核心设计理念："文件即记忆，技能即插件，透明可控"。
