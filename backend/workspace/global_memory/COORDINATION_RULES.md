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

### Universal Agents

#### code_agent
- 类型：universal
- 职责：代码开发、审查与调试
- 技能：代码生成、代码审查、调试、测试、重构
- 状态：idle

#### research_agent
- 类型：universal
- 职责：信息检索与文档处理
- 技能：信息检索、文档解析、内容提取、事实核查、报告生成
- 状态：idle

#### creative_agent
- 类型：universal
- 职责：内容创作与文案
- 技能：内容创作、文案写作、翻译、文档生成、创意设计
- 状态：idle

## 任务分发规则

1. 数据处理类任务 → data_agent
2. 代码开发类任务 → code_agent
3. 信息检索/文档分析类任务 → research_agent
4. 内容创作类任务 → creative_agent
5. 复合型任务 → 拆分后分发给多个Agent

## 超时配置

- 任务执行超时：300秒
- Agent响应超时：30秒
- 状态同步间隔：5秒