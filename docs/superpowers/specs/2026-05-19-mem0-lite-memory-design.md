# Mem0-lite Memory Optimization Design

**Date:** 2026-05-19

## Goal

Upgrade the current `MEMORY.md`-based memory system into a Mem0-inspired, semi-automatic, structured memory system while keeping the existing file-driven transparency and without adding user/project isolation yet.

## Current State

The current system has two memory modes:

1. Normal mode: `backend/memory/MEMORY.md` is read by `PromptBuilder` and injected into the System Prompt.
2. RAG mode: `MemoryIndexer` indexes `MEMORY.md` as one document, splits it with LlamaIndex, retrieves top-k chunks, and injects the retrieved snippets into the current conversation history.

Relevant files:

- `backend/graph/prompt_builder.py`
- `backend/graph/memory_indexer.py`
- `backend/graph/agent.py`
- `backend/api/files.py`
- `backend/api/config_api.py`
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/components/editor/InspectorPanel.tsx`
- `frontend/src/lib/api.ts`

## Scope

Included:

- Add structured memory storage in `backend/memory/memories.jsonl`.
- Keep `backend/memory/MEMORY.md` for backward compatibility and human-readable summary use.
- Add a backend memory store with ADD / UPDATE / DELETE lifecycle operations.
- Add semi-automatic memory extraction after assistant responses.
- Change RAG indexing to index active structured memories instead of raw `MEMORY.md` text.
- Add `GET /api/memories` for frontend structured memory viewing.
- Add a “结构化记忆” entry in the frontend “记忆文件” section.
- Add structured table-style viewing for `memory/memories.jsonl` in the Inspector panel.
- Preserve raw JSONL viewing as a fallback/debug mode.

Excluded:

- User isolation.
- Project isolation.
- Frontend editing/deleting/restoring memories.
- Database migration.
- Advanced reranking beyond similarity retrieval.
- Full Mem0 package integration.

## Architecture

The design introduces a structured memory layer while preserving the existing file-first philosophy.

```text
Conversation
  ↓
Assistant response completes
  ↓
Memory reflection step
  ↓
Memory operations: ADD / UPDATE / DELETE / NONE
  ↓
backend/memory/memories.jsonl
  ↓
MemoryIndexer indexes active memories
  ↓
RAG retrieval injects relevant memory items
```

`MEMORY.md` remains available for ordinary file inspection and compatibility. The new source of truth for structured memory retrieval is `memories.jsonl`.

## Memory Record Schema

Each line in `backend/memory/memories.jsonl` is one JSON object:

```json
{
  "id": "mem_20260519_ab12cd34",
  "type": "preference",
  "content": "用户偏好半自动记忆写入，只保存明显的长期偏好、事实和项目约束。",
  "status": "active",
  "source": "auto",
  "confidence": 0.85,
  "created_at": "2026-05-19T12:00:00",
  "updated_at": "2026-05-19T12:00:00"
}
```

Allowed `type` values:

- `preference`: user preferences about assistant behavior or workflow.
- `project`: long-lived project facts, constraints, or product decisions.
- `feedback`: explicit corrections or confirmations from the user about assistant behavior.
- `reference`: external resources or durable pointers.

Allowed `status` values:

- `active`: participates in retrieval.
- `deleted`: retained for audit but excluded from retrieval.

Allowed `source` values:

- `auto`: created by semi-automatic reflection.
- `manual`: created through explicit user request or future API/UI actions.

## Backend Components

### MemoryStore

Add a focused backend module, for example `backend/graph/memory_store.py`.

Responsibilities:

- Load JSONL records.
- Validate records.
- Generate stable memory ids.
- List all records.
- List only active records.
- Add a memory.
- Update an existing memory.
- Mark a memory as deleted.
- Write changes atomically enough for local file use by writing to a temp file and replacing the original.

It should not perform embedding, retrieval, or LLM extraction.

### MemoryIndexer

Update `backend/graph/memory_indexer.py` so RAG mode indexes active structured memory records from `memories.jsonl`.

Index document text should include useful metadata in natural language, for example:

```text
[type: preference]
用户偏好半自动记忆写入，只保存明显的长期偏好、事实和项目约束。
```

Each LlamaIndex document/node should preserve metadata:

```json
{
  "id": "mem_...",
  "type": "preference",
  "source": "auto"
}
```

Retrieval results should return memory records or record-like snippets, not arbitrary Markdown chunks.

Deleted memories must not be indexed.

### Memory Reflection

Add a semi-automatic reflection step after a normal assistant response completes.

Input:

- Current user message.
- Final assistant response.
- A small set of existing active memories, preferably retrieved or all active if small.

Output:

```json
{
  "operations": [
    {
      "action": "ADD",
      "type": "preference",
      "content": "用户希望回答简洁直接。",
      "confidence": 0.86
    }
  ]
}
```

Allowed actions:

- `ADD`
- `UPDATE`
- `DELETE`
- `NONE`

Rules:

- Only store durable preferences, durable project constraints, explicit feedback, or stable references.
- Do not store one-off task progress.
- Do not store command output, stack traces, or transient errors.
- Do not store facts that can be read from code or git history.
- If confidence is below a conservative threshold, do not write.
- If a new memory conflicts with an existing one, update the existing memory instead of adding a duplicate.

The reflection step should be best-effort: failures should be logged but must not break chat responses.

### API

Add a backend API module or extend an existing one with:

```http
GET /api/memories
```

Response:

```json
{
  "memories": [
    {
      "id": "mem_20260519_ab12cd34",
      "type": "preference",
      "content": "...",
      "status": "active",
      "source": "auto",
      "confidence": 0.85,
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

First version is read-only for frontend viewing.

## Frontend Design

### Sidebar

In `frontend/src/components/layout/Sidebar.tsx`, keep the existing memory entry:

```tsx
<FileItem path="memory/MEMORY.md" label="长期记忆" />
```

Add:

```tsx
<FileItem path="memory/memories.jsonl" label="结构化记忆" />
```

### API Client

In `frontend/src/lib/api.ts`, add:

```ts
export interface MemoryRecord {
  id: string
  type: 'preference' | 'project' | 'feedback' | 'reference'
  content: string
  status: 'active' | 'deleted'
  source: 'auto' | 'manual'
  confidence: number
  created_at: string
  updated_at: string
}

export async function getMemories() {
  return request<{ memories: MemoryRecord[] }>('/api/memories')
}
```

### InspectorPanel

When `currentFile === 'memory/memories.jsonl'`, render a structured memory viewer instead of the default Monaco editor.

Viewer requirements:

- Show memories in a table/list.
- Display type, content, source, confidence, status, and updated time.
- Provide filters:
  - all
  - active
  - deleted
  - preference
  - project
  - feedback
  - reference
- Provide a “查看原始 JSONL” toggle that falls back to Monaco text viewing of the file content.
- First version is read-only; no edit/delete buttons.

## Data Flow

### Chat write path

```text
User sends message
  ↓
Agent streams response
  ↓
Response completes
  ↓
Memory reflection runs in best-effort mode
  ↓
MemoryStore applies accepted operations
  ↓
MemoryIndexer rebuilds or marks index stale
```

### Retrieval path

```text
User sends message
  ↓
RAG mode enabled?
  ↓ yes
MemoryIndexer retrieves top 3 active structured memories
  ↓
Formatted memory snippets are appended to transient history
  ↓
Agent receives message with relevant memory context
```

### Frontend viewing path

```text
User clicks 结构化记忆
  ↓
InspectorPanel detects memory/memories.jsonl
  ↓
GET /api/memories
  ↓
Render structured viewer
  ↓
Optional raw JSONL toggle uses existing readFile path
```

## Error Handling

- Invalid JSONL lines should be skipped with a log entry, not crash the app.
- Missing `memories.jsonl` should behave as an empty memory list.
- Reflection failures must not affect user-visible chat completion.
- Memory write failures should be logged and should not retry in a tight loop.
- If embedding/index rebuild fails, RAG retrieval returns an empty list and the system continues without memory context.
- Frontend memory viewer should show a friendly empty state when no records exist.

## Testing Strategy

Backend tests:

- `MemoryStore` loads empty/missing files.
- `MemoryStore` adds, updates, and marks records as deleted.
- Deleted records are excluded from active list.
- Invalid JSONL lines do not crash loading.
- `MemoryIndexer` indexes active structured memories and excludes deleted ones.
- `GET /api/memories` returns records in a stable shape.
- Reflection parser accepts only allowed action/type/status values.

Frontend tests/build verification:

- Sidebar includes “结构化记忆”.
- Inspector renders structured viewer for `memory/memories.jsonl`.
- Filters work for status and type.
- Raw JSONL toggle preserves existing file viewing behavior.
- `npm run build` passes.

## Migration

No destructive migration is required.

Initial behavior:

- If `memories.jsonl` does not exist, it is treated as empty.
- Existing `MEMORY.md` remains unchanged.
- Future structured memories are written to `memories.jsonl`.

Optional later migration:

- Add a one-time tool to convert selected `MEMORY.md` bullet points into structured records.

## Acceptance Criteria

- The app still works when only `MEMORY.md` exists.
- Semi-automatic memory writes create structured records in `memory/memories.jsonl` only for durable information.
- RAG mode retrieves active structured memory records.
- Deleted memories are not retrieved.
- Frontend “记忆文件” section includes a “结构化记忆” entry.
- Clicking “结构化记忆” shows a readable table/list view of `memories.jsonl` contents.
- The viewer supports basic filters and raw JSONL fallback.
- No user/project isolation is introduced.
