# 全局行为准则

## 多Agent协同规范

本项目采用去中心化的多Agent协同架构，所有Agent遵循以下核心原则：

### 1. 协同原则

- **去中心化**：无主从Agent层级，各Agent独立拥有核心工具与技能体系
- **文件协议**：协同信息通过标准化文件交互，不引入重型中间件
- **轻量通信**：基于本地文件系统实现Agent间通信，无网络跨进程依赖
- **透明可控**：所有协同过程可追溯，支持前端可视化展示

### 2. Agent类型

| 类型 | 职责 | 工具权限 |
|------|------|----------|
| Primary Agent | 用户交互入口，任务拆解与结果汇总 | 全部工具 |
| Domain Agent | 承接单一领域原子子任务 | 按需启用 |
| Coordinator Agent | 协同规则执行，状态同步与冲突解决 | 仅轻量化工具 |

### 3. 协同流程

1. Primary Agent接收用户指令，判断任务类型
2. 复杂任务拆分为原子子任务，生成TASK文件
3. Coordinator Agent匹配最优Domain Agent
4. Domain Agent执行任务，生成RESPONSE文件
5. Primary Agent汇总结果，反馈给用户

### 4. 通信协议

所有通信基于本地标准化文件实现：

- **TASK_{id}.md**：任务描述文件，包含任务ID、子任务内容、目标Agent、完成标准
- **RESPONSE_{id}.md**：响应文件，包含任务执行结果、过程日志、生成文件路径
- **NOTICE_{id}.json**：通知文件，用于Agent间状态提醒

### 5. 资源冲突解决

- 多Agent同时请求访问同一文件/工具时，通过本地文件级锁分配资源
- 冲突信息记录于Coordinator Agent的MEMORY.md
- 无匹配领域Agent时，由Primary Agent自主完成或提示用户加载对应技能包