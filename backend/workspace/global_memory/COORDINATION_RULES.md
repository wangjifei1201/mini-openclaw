# 协同规则配置

## Agent注册表

### Primary Agent
- 名称：primary_agent
- 类型：primary
- 职责：用户交互入口，任务拆解与结果汇总
- 状态：running

### Coordinator Agent
- 名称：coordinator_agent
- 类型：coordinator
- 职责：协同规则执行，状态同步与冲突解决
- 状态：running

### Domain Agents

#### data_agent
- 类型：domain
- 职责：数据处理与分析任务
- 技能：数据分析、Python计算、表格处理
- 状态：idle

#### doc_agent
- 类型：domain
- 职责：文档分析与处理任务
- 技能：文档解析、内容提取、格式转换
- 状态：idle

## 任务分发规则

1. 数据处理类任务 → data_agent
2. 文档分析类任务 → doc_agent
3. 复合型任务 → 拆分后分发给多个Agent

## 超时配置

- 任务执行超时：300秒
- Agent响应超时：30秒
- 状态同步间隔：5秒