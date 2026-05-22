# Session-Scoped Outputs Design

## Background

Chat sessions already have a UUID `session_id`. The backend currently exposes the shared `backend/outputs/` directory at `/outputs`, and generated files can be linked from chat messages. Because all generated files currently live in the same output directory, different sessions can overwrite or expose similarly named files.

## Goals

- Generated files are isolated by chat session.
- New generated files are saved under `backend/outputs/<session_id>/`.
- Chat links use `/outputs/<session_id>/<filename>`.
- Existing `/outputs/<filename>` links remain usable for historical messages.
- The frontend continues deriving the backend host from the existing backend base URL helper.

## Non-goals

- No authentication or signed download URLs in this iteration.
- No migration of existing files from `backend/outputs/` into session directories.
- No new file storage backend.
- No per-user permission system.

## Current Session Model

The app already has a session ID flow:

- `backend/api/sessions.py` creates a UUID session ID when a new session is created.
- `frontend/src/lib/store.tsx` stores the current session ID and sends it with chat requests.
- `backend/api/chat.py` receives `session_id` on every chat request.
- `backend/graph/agent.py` receives `session_id` in `AgentManager.astream(...)`.

No new session identity mechanism is needed.

## Recommended Approach

Use the existing session ID as the output namespace.

For session `123e4567-e89b-12d3-a456-426614174000`, generated files must be written to:

```text
backend/outputs/123e4567-e89b-12d3-a456-426614174000/<filename>
```

The assistant should return links like:

```markdown
[查看 PDF](/outputs/123e4567-e89b-12d3-a456-426614174000/report.pdf)
[下载 Excel](/outputs/123e4567-e89b-12d3-a456-426614174000/table.xlsx)
```

Because FastAPI already mounts `backend/outputs` at `/outputs`, no new static mount is required.

## Backend Design

### Ensure Session Output Directory

Before agent execution starts, the chat API or agent manager should ensure:

```text
backend/outputs/<session_id>/
```

exists.

The session ID must be validated as a UUID or otherwise restricted to a safe directory name before using it in a filesystem path.

### Inject Runtime Output Context

Agent execution should receive a runtime system message that includes the current session output rule:

```text
当前会话 ID: <session_id>
生成文件必须保存到 outputs/<session_id>/ 目录。
回复用户时必须使用 Markdown 链接，并使用 /outputs/<session_id>/<filename> 形式。
不要写入 outputs/ 根目录，不要返回 localhost、IP 地址、前端地址或本地绝对路径。
```

This should be injected at runtime, not persisted to session history.

### Update Static Prompt Guidance

Update developer-facing guidance that currently tells agents to write to global `outputs/`:

- `backend/workspace/AGENTS.md`
- `backend/skills/table-generator/SKILL.md`

The static guidance should explain the placeholder convention:

```text
outputs/<session_id>/<filename>
/outputs/<session_id>/<filename>
```

The runtime injected message supplies the concrete session ID.

## Frontend Design

The frontend already accepts and resolves `/outputs/...` links through the configured backend base URL. That should continue to work for both:

```text
/outputs/<filename>
/outputs/<session_id>/<filename>
```

The link renderer should keep existing behavior:

- PDF output links open in a new tab without `download`.
- Non-PDF output links get `download` when possible.
- Unsafe traversal patterns are rejected by the URL helper.

The existing normalization for malformed historical links like `{http://ip:port}/outputs/...` should continue to preserve the full `/outputs/...` path, including session-scoped paths.

## Compatibility

- Existing historical links such as `/outputs/report.pdf` remain valid if the file still exists in `backend/outputs/`.
- New generated links should use `/outputs/<session_id>/<filename>`.
- Existing files are not moved.

## Security

- Session IDs must not be blindly interpolated into filesystem paths unless validated.
- The output directory must be created only under `backend/outputs/`.
- Frontend output link helpers should continue rejecting traversal, including encoded traversal.
- Agents should not return local absolute paths or hard-coded hostnames.

## Tests

Recommended backend tests:

- Chat execution creates `outputs/<session_id>/` for a valid session ID.
- Runtime agent context includes `outputs/<session_id>/` and `/outputs/<session_id>/<filename>` instructions.
- Invalid session IDs are rejected or sanitized before filesystem use.

Recommended frontend/helper checks:

- `/outputs/<session_id>/report.pdf` resolves to backend base URL.
- `/outputs/<session_id>/report.xlsx` resolves and is treated as downloadable.
- Encoded traversal under session output paths is rejected.

## Acceptance Criteria

- A generated PDF in session A is saved under `backend/outputs/<session_a>/...` and linked as `/outputs/<session_a>/...`.
- A generated file with the same filename in session B is saved under `backend/outputs/<session_b>/...`.
- Session A and B links do not collide.
- Historical `/outputs/<filename>` links continue to render and resolve.
- Frontend build and backend tests pass.
