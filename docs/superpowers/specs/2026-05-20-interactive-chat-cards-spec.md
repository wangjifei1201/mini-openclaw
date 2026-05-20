# 交互式 Chat 卡片设计规格

**日期：** 2026-05-20
**状态：** 已确认，待实现
**适用范围：** BaseClaw 对话交互增强

## 1. 背景

用户希望在与 agent 对话过程中加入 chat 卡片式交互问答能力。经过方案比较，确认采用协议级方案：后端生成结构化卡片，通过 SSE 事件返回给前端，前端将卡片渲染在 assistant 消息中，用户点击选项后自动发送下一轮消息。

该能力将作为 BaseClaw 的正式交互协议，而不是仅依赖 Markdown 约定块。

## 2. 目标

- 在 agent 回复结束后，根据上下文生成交互卡片；
- 支持快捷追问和单选方案选择；
- 卡片通过正式 SSE 事件返回；
- 卡片随 session 历史保存和回放；
- 用户点击卡片选项后复用现有 `sendMessage(prompt)` 发送下一轮对话；
- 主 agent 输出自然语言，不直接输出 JSON、HTML、按钮代码或前端协议字段。

## 3. 非目标

首版不实现：

- 表单式卡片；
- 多选卡片；
- 输入框卡片；
- 卡片编辑；
- 卡片埋点；
- 用户点击结果的独立结构化事件存储；
- 前端从 Markdown 代码块解析交互卡片。

## 4. 用户体验

assistant 消息回复完成后，如果系统判断适合继续引导用户，会在消息正文下方显示一张交互卡片。

卡片类型：

1. `quick_replies`
   - 用于快捷追问；
   - 按按钮组展示；
   - 示例：生成实现计划、总结要点、分析风险。

2. `choice`
   - 用于方案选择；
   - 按纵向选项列表展示；
   - 示例：方案 A、方案 B、方案 C。

点击卡片选项后：

- 前端把该选项的 `prompt` 作为用户消息发送；
- 当前正在流式回复时按钮禁用；
- 点击过的选项显示选中态；
- 首版不强制一张卡片只能点击一次。

## 5. 数据模型

```json
{
  "id": "card_ab12cd34",
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

字段约束：

- `type` 只能是 `quick_replies` 或 `choice`；
- 每条 assistant 消息最多 1 张卡片；
- 每张卡片最多 3 个选项；
- `title` 必填；
- `label` 必填，最长 30 字；
- `prompt` 必填，最长 500 字；
- 非法卡片或非法选项直接丢弃；
- 生成失败返回空卡片，不影响正常聊天。

## 6. 后端设计

### 6.1 InteractiveCardService

新增 `backend/graph/interactive_cards.py`。

职责：

- 接收本轮用户消息和 assistant 完整回复；
- 判断是否需要生成卡片；
- 调用 LLM 生成候选卡片 JSON；
- 解析 Markdown fence 或原始 JSON；
- 校验字段、类型、长度、数量；
- 返回合法卡片数组；
- 失败时返回空数组。

生成策略：

- assistant 回复过短时不生成；
- 错误消息不生成；
- 多方案内容优先生成 `choice`；
- 建议型、解释型、设计型回复生成 `quick_replies`；
- 同时满足时优先 `choice`。

### 6.2 AgentManager 集成

`backend/graph/agent.py` 新增：

- 初始化 `InteractiveCardService`；
- 暴露 `generate_interactive_cards(user_message, assistant_response)`；
- chat API 在回复完成后调用该方法。

### 6.3 主 agent 系统提示词

`backend/graph/prompt_builder.py` 追加交互卡片友好输出规则：

```text
当回答适合用户继续选择下一步时，请在正文末尾用自然语言列出 2-3 个明确的下一步选项。
如果回答中存在多个可选方案，请用清晰的编号或小标题描述每个方案。
不要输出 JSON、HTML、按钮代码或任何前端协议字段。
交互卡片由系统根据你的自然语言回答自动生成。
```

主 agent 不直接输出卡片 JSON，避免协议内容污染正文。

### 6.4 SSE 事件

新增事件类型：`interactive_card`。

示例：

```json
{
  "type": "interactive_card",
  "cards": [
    {
      "id": "card_ab12cd34",
      "type": "quick_replies",
      "title": "你可以继续：",
      "options": [
        {
          "id": "opt_1",
          "label": "生成计划",
          "prompt": "请生成详细实现计划。"
        }
      ]
    }
  ]
}
```

发送顺序：

```text
token ...
interactive_card
done
```

也就是 assistant 正文 token 流结束后、`done` 前发送。

### 6.5 Session 持久化

assistant 消息增加可选字段：

```json
{
  "role": "assistant",
  "content": "...",
  "tool_calls": [],
  "interactive_cards": []
}
```

历史接口原样返回该字段。旧消息没有该字段时前端按空数组处理。

## 7. 前端设计

### 7.1 类型扩展

`frontend/src/lib/api.ts` 新增：

```ts
export interface InteractiveCardOption {
  id: string
  label: string
  prompt: string
}

export interface InteractiveCard {
  id: string
  type: 'quick_replies' | 'choice'
  title: string
  description?: string
  options: InteractiveCardOption[]
}
```

`StreamEventType` 新增：

```ts
| 'interactive_card'
```

`frontend/src/lib/store.tsx` 的 `Message` 新增：

```ts
interactive_cards?: InteractiveCard[]
```

### 7.2 流式处理

收到 `interactive_card` 事件时，将 `cards` 挂到当前 assistant 消息：

```ts
case 'interactive_card':
  setMessages(prev => prev.map(msg =>
    msg.id === assistantMsgId
      ? { ...msg, interactive_cards: data.cards || [] }
      : msg
  ))
  break
```

历史加载时读取 `msg.interactive_cards`。

### 7.3 UI 组件

新增 `frontend/src/components/chat/InteractiveCard.tsx`。

职责：

- 渲染卡片标题、描述、选项；
- `quick_replies` 使用横向/换行按钮组；
- `choice` 使用纵向选项列表；
- 点击选项后调用 `sendMessage(option.prompt)`；
- 流式中禁用按钮；
- 点击后显示选中态。

`ChatMessage.tsx` 在 assistant 消息正文下方渲染卡片。

## 8. 错误处理

- LLM 卡片生成失败：返回空数组；
- JSON 解析失败：返回空数组；
- 非法卡片字段：丢弃；
- 非法选项字段：丢弃；
- 所有选项都非法：丢弃整张卡片；
- 前端收到未知或空卡片：不渲染；
- 正在 streaming 时用户点击：按钮禁用，不发送。

## 9. 测试要求

后端：

- 卡片 JSON 解析；
- Markdown fence JSON 解析；
- 非法卡片丢弃；
- 数量和长度限制；
- service 调用 LLM 时包含用户消息和 assistant 回复；
- LLM 失败返回空数组；
- SSE 中 `interactive_card` 在 `done` 前发送；
- session 保存 `interactive_cards`；
- 非流式响应包含 `interactive_cards`。

前端：

- 类型构建通过；
- `interactive_card` 事件更新当前 assistant 消息；
- 历史消息可显示卡片；
- 点击卡片选项发送 prompt；
- streaming 时按钮禁用；
- 无卡片消息不受影响。

## 10. 验收标准

- agent 回复完成后，适合场景下能出现交互卡片；
- 卡片按钮点击后自动发送下一轮消息；
- 卡片能随历史消息回放；
- 普通 Markdown、工具调用、检索结果渲染不受影响；
- 主 agent 不输出卡片 JSON 或按钮协议；
- 后端卡片生成失败不影响聊天；
- 后端相关单测通过；
- 前端构建通过。
