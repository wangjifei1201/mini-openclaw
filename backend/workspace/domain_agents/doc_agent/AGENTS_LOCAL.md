# Doc Agent - 行为准则与记忆操作指南

## 日常行为准则

### 任务接收流程

1. 监听任务目录：`workspace/coordination/tasks/`
2. 读取分配给自己的任务文件
3. 更新任务状态为processing
4. 执行任务
5. 生成响应文件
6. 更新任务状态为finished

### 错误处理

- 任务执行失败时，记录错误信息
- 更新任务状态为failed
- 在响应文件中说明失败原因

## 记忆操作指南

### 记忆文件位置

- 专属记忆：`workspace/domain_agents/doc_agent/memory/MEMORY.md`

### 记录内容

- 重要文档处理经验
- 常用处理模板
- 用户偏好设置

## 任务响应格式

```markdown
# 响应：TASK_xxx

## 执行结果

{结果内容}

## 过程日志

{执行步骤}

## 生成文件

- 文件路径1
- 文件路径2
```