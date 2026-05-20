# 交互式 Chat 卡片设计方案

**日期：** 2026-05-20
**状态：** 待实现
**适用范围：** BaseClaw 对话交互增强

## 1. 目标

在用户与 agent 对话过程中，支持由后端返回结构化交互卡片，前端在 assistant 消息中展示可点击选项。用户点击选项后，系统自动将该选项对应的 prompt 作为下一轮用户消息发送。

首版目标：

- 支持快捷追问卡片；
- 支持单选方案卡片；
- 卡片作为正式对话协议的一部分，通过 SSE 事件返回；
- 卡片随会话历史保存和回放；
- 主 agent 保持自然语言输出，不直接输出 JSON、HTML 或前端协议字段。

## 2. 设计范围

### 2.1 包含

- 后端新增交互卡片数据模型；
- 后端新增 `InteractiveCardService`，在 assistant 回复完成后生成卡片；
- SSE 新增 `interactive_card` 事件；
- session 消息保存 `interactive_cards` 字段；
- 历史接口返回 `interactive_cards`；
- 前端消息模型支持 `interactive_cards`；
- 前端流式处理 `interactive_card` 事件；
- 前端新增 `InteractiveCard` 组件；
- `ChatMessage` 渲染 assistant 消息中的交互卡片；
- 主 agent 系统提示词增加“交互卡片友好输出”规则。

### 2.2 不包含

- 表单式卡片；
- 多选卡片；
- 输入框卡片；
- 卡片编辑；
- 卡片埋点分析；
- 用户点击结果的独立结构化事件存储；
- 让主 agent 直接输出卡片 JSON。

## 3. 总体架构

```text
User message
  ↓
Agent streams natural-language response
  ↓
Assistant response completes
  ↓
InteractiveCardService analyzes user message + assistant response
  ↓
Generated cards are validated and normalized
  ↓
SSE emits interactive_card before done
  ↓
Session stores assistant message with interactive_cards
  ↓
Frontend renders cards below assistant message
  ↓
User clicks option
  ↓
Existing sendMessage(prompt) sends next user message
```

核心原则：

- 主 agent 只负责自然语言回答；
- 卡片服务负责结构化生成；
- 前端只渲染经过后端校验的结构化卡片；
- 卡片点击复用现有聊天发送链路。

## 4. 数据模型

### 4.1 InteractiveCard

```json
{
  "id": "card_20260520_ab12cd34",
  "type": "choice",
  "title": "请选择下一步",
  "description": "你可以选择一个方向继续。",
  "options": [
    {
      "id": "opt_1",
      "label": "生成实现计划",
      "prompt": "请基于上面的方案生成实现计划。"
    }
  ]
}
```

### 4.2 字段约束

`type` 支持：

- `quick_replies`：快捷追问；
- `choice`：方案选择。

约束：

- 每条 assistant 消息最多 1 张卡片；
- 每张卡片最多 3 个选项；
- `title` 必填；
- `label` 必填，最长 30 字；
- `prompt` 必填，最长 500 字；
- 空字段、未知类型、无有效选项的卡片直接丢弃；
- 生成或校验失败不影响正常聊天回复。

## 5. 后端设计

### 5.1 主 agent 系统提示词调整

主 agent 不直接输出卡片 JSON，而是输出更利于卡片服务识别的自然语言结构。

新增规则建议：

```text
当回答适合用户继续选择下一步时，请在正文末尾用自然语言列出 2-3 个明确的下一步选项。
如果回答中存在多个可选方案，请用清晰的编号或小标题描述每个方案。
不要输出 JSON、HTML、按钮代码或任何前端协议字段。
交互卡片由系统根据你的自然语言回答自动生成。
```

这样可以提高卡片生成稳定性，同时避免协议内容污染正文。

### 5.2 InteractiveCardService

新增服务职责：

- 输入本轮用户消息和 assistant 完整回复；
- 判断是否适合生成卡片；
- 生成 `quick_replies` 或 `choice` 卡片；
- 校验并规范化卡片字段；
- 失败时返回空数组；
- 不阻塞正常聊天错误处理。

推荐策略：

- 对解释型、建议型、设计型回复生成 `quick_replies`；
- 对包含明显 A/B/C 或多个方案的回复生成 `choice`；
- 对错误消息、极短回复、纯工具日志不生成卡片；
- 如果同时满足两类，优先生成 `choice`。

### 5.3 SSE 事件

新增事件类型：

```json
{
  "type": "interactive_card",
  "cards": [
    {
      "id": "card_20260520_ab12cd34",
      "type": "choice",
      "title": "请选择下一步",
      "description": "你可以选择一个方向继续。",
      "options": [
        {
          "id": "opt_1",
          "label": "生成实现计划",
          "prompt": "请基于上面的方案生成实现计划。"
        }
      ]
    }
  ]
}
```

发送时机：assistant 正文 token 流结束后，`done` 事件之前。

### 5.4 会话历史

assistant 消息保存时增加字段：

```json
{
  "role": "assistant",
  "content": "...",
  "tool_calls": [],
  "interactive_cards": []
}
```

历史接口返回该字段。旧消息缺失时前端按空数组处理。

## 6. 前端设计

### 6.1 类型扩展

`frontend/src/lib/store.tsx` 中 `Message` 增加：

```ts
interactive_cards?: InteractiveCard[]
```

`frontend/src/lib/api.ts` 中 `StreamEventType` 增加：

```ts
| 'interactive_card'
```

### 6.2 流式处理

`sendMessage()` 中新增事件处理：

```ts
case 'interactive_card':
  setMessages(prev => prev.map(msg =>
    msg.id === assistantMsgId
      ? { ...msg, interactive_cards: data.cards || [] }
      : msg
  ))
  break
```

历史加载时读取 `interactive_cards`，保证卡片可回放。

### 6.3 InteractiveCard 组件

新增组件：`frontend/src/components/chat/InteractiveCard.tsx`。

职责：

- 渲染卡片标题、描述和选项；
- 根据 `type` 使用不同视觉样式；
- 点击选项后调用 `sendMessage(option.prompt)`；
- 流式回复中禁用按钮；
- 点击后展示已选择状态，避免用户误以为没有响应。

展示位置：

- assistant 消息正文下方；
- 工具调用和检索结果之后；
- 用户消息不展示卡片。

### 6.4 交互规则

- 点击卡片选项等价于用户发送一条新消息；
- 发送内容使用 `option.prompt`；
- 当前正在流式回复时按钮禁用；
- 首版允许用户点击同一张卡片的不同选项继续追问，不强制一次性锁死；
- 已点击选项在当前页面状态中标记为选中。

## 7. 错误处理

- 卡片生成失败：返回空卡片，不影响 assistant 回复；
- 卡片字段非法：丢弃该卡片或非法选项；
- SSE 卡片事件解析失败：前端忽略该事件；
- 历史消息缺失 `interactive_cards`：按空数组处理；
- 用户点击时正在流式回复：按钮禁用，不发送消息；
- `prompt` 为空或超长：后端校验时丢弃选项。

## 8. 测试策略

### 8.1 后端

- 校验合法卡片通过；
- 非法类型被丢弃；
- 空标题、空 label、空 prompt 被丢弃；
- 选项数量超过限制时截断；
- 卡片生成失败时不影响 chat 响应；
- SSE 按顺序发送 `interactive_card` 后再发送 `done`；
- session 历史保存并返回 `interactive_cards`。

### 8.2 前端

- `interactive_card` 事件能更新 assistant 消息；
- 历史消息能渲染卡片；
- 点击选项调用现有 `sendMessage(prompt)`；
- `isStreaming` 时按钮禁用；
- 无卡片消息正常渲染；
- 前端构建通过。

## 9. 分阶段实现

### 阶段一：协议级卡片首版

- 新增后端卡片模型和服务；
- 新增 SSE `interactive_card` 事件；
- 保存和回放 `interactive_cards`；
- 前端渲染快捷追问和单选方案卡片；
- 调整主 agent 系统提示词。

### 阶段二：增强能力

- 根据真实使用效果优化卡片生成策略；
- 支持更丰富的卡片样式；
- 如有必要，再增加表单式卡片和用户点击结果结构化记录。

## 10. 验收标准

- agent 回复结束后，在适合场景下出现交互卡片；
- 点击卡片选项能自动发送下一轮消息；
- 卡片随历史消息保存和回放；
- 普通消息、工具调用、检索结果渲染不受影响；
- 主 agent 不输出卡片 JSON 或前端协议字段；
- 非法或生成失败的卡片不会影响正常对话；
- 前端构建通过。
