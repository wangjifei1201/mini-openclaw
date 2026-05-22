# Backend Output File Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make backend-generated `/outputs/...` links in chat messages resolve to the frontend-configured backend URL, with PDFs opening in a new tab and non-PDF files downloading when possible.

**Architecture:** Add small URL helper functions to the frontend API module and reuse them in chat Markdown link rendering. Keep backend output serving unchanged because FastAPI already mounts `backend/outputs` at `/outputs`. Update the `table-generator` skill to instruct agents to return `/outputs/...` Markdown links after generating files.

**Tech Stack:** Next.js 14, React, TypeScript, ReactMarkdown, FastAPI static files, backend skill Markdown.

---

## File Structure

- Modify `frontend/src/lib/api.ts`
  - Export the backend base URL helper currently hidden as `getApiBase`.
  - Add safe output-link normalization helpers.
- Modify `frontend/src/components/chat/ChatMessage.tsx`
  - Use the output-link helpers in Markdown `<a>` rendering.
  - Add `download` only for non-PDF backend output links.
- Modify `backend/skills/table-generator/SKILL.md`
  - Clarify that confirmed generated files must be returned as Markdown links using `/outputs/<filename>`.
- Verify with TypeScript/Next build.

---

### Task 1: Add Backend Output URL Helpers

**Files:**
- Modify: `frontend/src/lib/api.ts:5-13`

- [ ] **Step 1: Add exported helpers in `frontend/src/lib/api.ts`**

Replace the current API base block:

```ts
// 动态获取 API 地址，支持本机和局域网访问
const getApiBase = () => {
  if (typeof window === 'undefined') {
    return 'http://localhost:8002'
  }
  return `http://${window.location.hostname}:8002`
}

const API_BASE = getApiBase()
```

with:

```ts
// 动态获取 API 地址，支持本机和局域网访问
export const getBackendBaseUrl = () => {
  if (typeof window === 'undefined') {
    return 'http://localhost:8002'
  }
  return `http://${window.location.hostname}:8002`
}

export const isBackendOutputPath = (href?: string | null) => {
  if (!href) return false

  const trimmed = href.trim()
  if (!trimmed || trimmed.includes('..')) return false

  if (trimmed.startsWith('/outputs/')) return true
  if (trimmed.startsWith('outputs/')) return true

  try {
    const url = new URL(trimmed)
    return url.pathname.startsWith('/outputs/') && !url.pathname.includes('..')
  } catch {
    return false
  }
}

export const resolveBackendOutputUrl = (href?: string | null) => {
  if (!isBackendOutputPath(href)) return null

  const trimmed = href!.trim()
  let outputPath = trimmed
  if (trimmed.startsWith('outputs/')) {
    outputPath = `/${trimmed}`
  } else if (!trimmed.startsWith('/outputs/')) {
    outputPath = new URL(trimmed).pathname
  }

  return `${getBackendBaseUrl()}${outputPath}`
}

export const isPdfOutputPath = (href?: string | null) => {
  if (!isBackendOutputPath(href)) return false
  const path = href!.split('?')[0].toLowerCase()
  return path.endsWith('.pdf')
}

const API_BASE = getBackendBaseUrl()
```

- [ ] **Step 2: Build to verify helper types**

Run:

```bash
npm run build --prefix frontend
```

Expected: build passes. If running from `backend/`, use:

```bash
npm run build --prefix ../frontend
```

---

### Task 2: Resolve Chat Markdown Output Links

**Files:**
- Modify: `frontend/src/components/chat/ChatMessage.tsx:9-12`
- Modify: `frontend/src/components/chat/ChatMessage.tsx:200-211`

- [ ] **Step 1: Import the helpers**

Change the import area from:

```ts
import { Message } from '@/lib/store'
import ThoughtChain from './ThoughtChain'
import RetrievalCard from './RetrievalCard'
import InteractiveCard from './InteractiveCard'
```

to:

```ts
import { Message } from '@/lib/store'
import { isBackendOutputPath, isPdfOutputPath, resolveBackendOutputUrl } from '@/lib/api'
import ThoughtChain from './ThoughtChain'
import RetrievalCard from './RetrievalCard'
import InteractiveCard from './InteractiveCard'
```

- [ ] **Step 2: Update the Markdown link renderer**

Replace the current `a` component:

```tsx
a({ children, ...props }) {
  return (
    <a
      {...props}
      className={`underline ${isUser ? 'text-blue-200' : 'text-klein-blue'}`}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  )
},
```

with:

```tsx
a({ children, href, ...props }) {
  const resolvedHref = resolveBackendOutputUrl(href) || href
  const shouldDownload = isBackendOutputPath(href) && !isPdfOutputPath(href)

  return (
    <a
      {...props}
      href={resolvedHref}
      className={`underline ${isUser ? 'text-blue-200' : 'text-klein-blue'}`}
      target="_blank"
      rel="noopener noreferrer"
      download={shouldDownload ? true : undefined}
    >
      {children}
    </a>
  )
},
```

- [ ] **Step 3: Build to verify ReactMarkdown component typing**

Run:

```bash
npm run build --prefix frontend
```

Expected: build passes.

---

### Task 3: Update Table Generator Skill Link Guidance

**Files:**
- Modify: `backend/skills/table-generator/SKILL.md:64-68`

- [ ] **Step 1: Update output-path instructions**

Replace this section:

```markdown
## 输出路径

- 文件应保存到后端 `outputs/` 目录。
- 返回路径时使用项目已有静态文件服务可访问的路径。
- 如果无法确认下载 URL，至少返回本地文件路径。
```

with:

```markdown
## 输出路径

- 文件应保存到后端 `outputs/` 目录。
- 回复用户时必须使用 Markdown 链接，并使用 `/outputs/<filename>` 形式的相对输出路径。
- 不要返回 `localhost`、IP 地址、前端地址或本地绝对路径。
- Excel 示例：`已生成文件：[下载 Excel](/outputs/table-20260521.xlsx)`。
- PDF 示例：`已生成文件：[查看 PDF](/outputs/report-20260521.pdf)`。
```

- [ ] **Step 2: Validate skill**

Run from repo root:

```bash
python3 backend/skills/skill-creator/scripts/quick_validate.py backend/skills/table-generator
```

Expected:

```text
Skill is valid!
```

---

### Task 4: Final Verification

**Files:**
- Verify: `frontend/src/lib/api.ts`
- Verify: `frontend/src/components/chat/ChatMessage.tsx`
- Verify: `backend/skills/table-generator/SKILL.md`

- [ ] **Step 1: Run frontend build**

Run:

```bash
npm run build --prefix frontend
```

Expected: Next.js build completes successfully.

- [ ] **Step 2: Validate table-generator skill**

Run:

```bash
python3 backend/skills/skill-creator/scripts/quick_validate.py backend/skills/table-generator
```

Expected:

```text
Skill is valid!
```

- [ ] **Step 3: Inspect final diff**

Run:

```bash
git diff -- frontend/src/lib/api.ts frontend/src/components/chat/ChatMessage.tsx backend/skills/table-generator/SKILL.md
```

Expected:

- `api.ts` exports backend URL resolution helpers.
- `ChatMessage.tsx` resolves `/outputs/...` links via backend API base.
- `table-generator` instructs agents to return `/outputs/<filename>` Markdown links.

- [ ] **Step 4: Commit implementation**

Only stage files for this feature:

```bash
git add frontend/src/lib/api.ts frontend/src/components/chat/ChatMessage.tsx backend/skills/table-generator/SKILL.md
git commit -m "支持后端生成文件链接下载与预览。"
```

Do not stage unrelated files such as `backend/memory/MEMORY.md` or `.vscode/`.

---

## Self-Review

- Spec coverage: frontend URL normalization, PDF new-tab behavior, non-PDF download hint, backend output path convention, and skill guidance are covered.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: helper names are consistent across `api.ts` and `ChatMessage.tsx`.
