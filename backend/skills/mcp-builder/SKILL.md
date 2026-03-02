---
name: mcp-builder
description: 创建高质量MCP（模型上下文协议）服务器的指南，使LLM能够通过精心设计的工具与外部服务交互。在构建MCP服务器以集成外部API或服务时使用，无论是Python（FastMCP）还是Node/TypeScript（MCP SDK）。
license: 完整条款见 LICENSE.txt
---

# MCP服务器开发指南

创建MCP（模型上下文协议）服务器，使LLM能够通过精心设计的工具与外部服务交互。MCP服务器的质量取决于它使LLM完成现实世界任务的能力。

## 概述

创建高质量的MCP服务器涉及四个主要阶段：

### 阶段1：深入研究与规划

#### 1.1 理解现代MCP设计

**API覆盖范围 vs. 工作流程工具：**
平衡全面的API端点覆盖与专门的工作流程工具。工作流程工具对于特定任务可能更方便，而全面的覆盖使代理具有灵活性以组合操作。性能因客户端而异——一些客户端从组合基本工具执行中受益，而其他客户端通过更高级的工作流程更好地工作。不确定时，优先考虑全面的API覆盖。

**工具命名与可发现性：**
清晰、描述性的工具名称有助于代理快速找到正确的工具。使用一致的前缀（例如，`github_create_issue`、`github_list_repos`）和面向动作的命名。

**上下文管理：**
代理从简明的工具描述和能够过滤/分页结果中受益。设计返回专注、相关数据的工具。一些客户端支持代码执行，这可以帮助代理有效地过滤和处理数据。

**可操作错误消息：**
错误消息应引导代理朝向具体建议的解决方案和后续步骤。

#### 1.2 研究MCP协议文档

**导航MCP规范：**
从站点地图开始，以查找相关页面：`https://modelcontextprotocol.io/sitemap.xml`

然后获取带`.md`后缀的特定页面以获得markdown格式（例如，`https://modelcontextprotocol.io/specification/draft.md`）。

需要审查的关键页面：
- 规范概述和架构
- 传输机制（可流式HTTP，用于远程服务器的stdio）
- 工具、资源和提示定义

#### 1.3 学习框架文档

**推荐技术栈：**
- **语言**：TypeScript（高质量SDK支持、在许多执行环境中都有良好兼容性、AI模型擅长生成TypeScript代码、广泛的静态类型和良好的检查工具）
  - [⚡ TypeScript指南](./reference/node_mcp_server.md) - TypeScript模式、示例
  - [🐍 Python指南](./reference/python_mcp_server.md) - Python模式、示例
  - **MCP最佳实践**：[📋 查看最佳实践](./reference/mcp_best_practices.md) - 核心指南，包括：
    - 服务器和工具命名约定
    - 响应格式指南（JSON vs Markdown）
    - 分页最佳实践
    - 传输选择（可流式HTTP vs stdio）
    - 安全和错误处理标准

**传输**：可流式HTTP用于远程服务器，使用无状态JSON（impler to scale and maintain），与有状态会话形成对比。用于本地服务器的stdio。

**加载框架文档**：
使用WebFetch加载`https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md`

### 阶段2：实施

#### 2.1 设置项目结构

**理解API：**
审查服务的API文档以识别关键端点、身份验证需求和数据模型。

**工具选择：**
优先考虑全面的API覆盖。列出要实现的端点，从最常见的操作开始：

#### 2.2 实现核心基础设施

为每个工具创建共享工具：
- API客户端身份验证
- 错误处理助手
- 响应格式化（JSON/Markdown）
- 分页支持

#### 2.3 实现工具

对于每个工具：

**输入模式：**
使用Zod（TypeScript）或Pydantic（Python）进行严格的类型定义
在字段描述中包含约束和清晰说明

**输出模式：**
定义`outputSchema`，在可能的情况下使用`structuredContent`进行结构化数据输出

**工具描述：**
功能性的简洁摘要
参数描述（带约束）
返回类型模式

**实现：**
使用现代SDK的异步/await进行I/O操作

### 阶段3：审查与测试

#### 3.1 代码质量

**不要重复代码（DRY原则）：**
没有重复的代码片段（DRY原则）
共享实用程序和错误处理
一致的数据验证

#### 3.2 使用MCP检查器

使用`npx @modelcontextprotocol/inspector`测试服务器

#### 3.3 创建评估

**加载[✅ 评估指南](./reference/evaluation.md)**
获取完整的评估指南以创建评估

#### 3.4 输出格式

创建带以下结构的XML文件：
```xml
<evaluation>
   <qa_pair>
     <question>找到关于具有特定安全命名的AI模型发布的讨论。一个模型需要特定的安全指定，使用格式ASL-X。X号是哪个模型被确定的编号？</question>
     <answer>3</answer>
   </qa_pair>
   <!-- 更多qa_pairs... -->
</evaluation>
```

#### 3.5 评估要求

确保每个问题：
- **独立性**：不依赖于其他问题
- **真实性**：基于现实世界的用例，可通过字符串比较验证
- **复杂性**：需要多次工具调用和深度探索
- **可验证**：单一、清晰的答案，可通过字符串比较验证
- **稳定性**：在不同用例下产生一致的答案

### 阶段4：创建评估

加载评估指南并使用提供的脚本运行综合评估。

---

## 📚 参考文档库

在开发期间加载这些资源：

**核心MCP文档（首先加载）：**
- [📋 MCP最佳实践](./reference/mcp_best_practices.md) - 通用MCP指南
- [🐍 Python实现指南](./reference/python_mcp_server.md) - Python/FastMCP特定模式
- [⚡ TypeScript实现指南](./reference/node_mcp_server.md) - TypeScript/Node.js特定模式

**SDK文档（阶段1/2中按需加载）：**
- 完整的TypeScript和Python SDK参考
- 模式和示例集合

**评估指南（阶段3/4中按需加载）：**
- 完整的评估创建和测试框架

---

# 高级工作流程

创建MCP服务器使代理能够：
- 通过精心设计的工具高效地与外部服务交互
- 维护服务状态和一致性
- 处理复杂的操作序列
- 提供结构化、可验证的数据输出

关键是以代理为中心的设计，而非以代码为中心的方法。每个工具都应该旨在增强代理完成现实世界任务的能力。