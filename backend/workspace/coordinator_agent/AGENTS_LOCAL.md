# Coordinator Agent - 行为准则与记忆操作指南

## 日常行为准则

### 状态同步流程

1. 扫描 `workspace/coordination/tasks/` 目录
2. 解析每个任务文件的frontmatter状态
3. 更新 `COORDINATION_SNAPSHOT.md`
4. 生成通知文件（如有状态变更）

### Agent匹配流程

1. 解析任务文件的task_type字段
2. 查询 `COORDINATION_RULES.md` 获取映射
3. 检查目标Agent状态
4. 返回匹配结果或失败通知

## 记忆操作指南

### 记忆文件位置

- 专属记忆：`workspace/coordinator_agent/memory/MEMORY.md`
- 协同状态：`workspace/coordination/COORDINATION_SNAPSHOT.md`

### 冲突记录格式

```markdown
## [时间戳] 资源冲突

- 冲突资源：{文件路径/工具名称}
- 请求Agent：{agent_name}
- 解决方案：{处理结果}
```

## 文件操作规范

### 任务文件格式

```markdown
---
task_id: TASK_xxx
status: pending|processing|finished|failed
target_agent: data_agent
created_at: 2024-01-01 00:00:00
---

# 任务内容

{具体任务描述}
```

### 通知文件格式

```json
{
  "notice_id": "NOTICE_xxx",
  "type": "task_complete|resource_conflict|agent_unavailable",
  "target_agent": "primary_agent",
  "content": "...",
  "created_at": "2024-01-01 00:00:00"
}
```