# Backend Output File Links Design

## Background

Backend tools and skills can generate files under `backend/outputs/`. The FastAPI app already exposes that directory at `/outputs`. Chat responses should let users click generated file links directly: Excel/other files should be downloadable, and PDFs should open in a browser tab for viewing.

The frontend must derive the backend file host from the same backend base URL used for API calls. The backend should not hard-code absolute URLs because deployments may use localhost, LAN IPs, or proxy-configured hosts.

## Goals

- Generated files under `backend/outputs/` are clickable from chat messages.
- PDF links open in a new tab and can be viewed by the browser.
- Excel and other generated file links are easy to download.
- File URLs use the frontend-configured backend address.
- Agents and skills can output simple Markdown links without knowing deployment details.

## Non-goals

- No new file storage system.
- No authentication or signed URLs in this iteration.
- No protocol-level file card event yet.
- No automatic conversion of arbitrary local file paths into URLs.

## Recommended Approach

Use frontend-side normalization for backend output links.

Backend and skills should output Markdown links using stable relative output paths:

```markdown
[下载 Excel](/outputs/report.xlsx)
[查看 PDF](/outputs/report.pdf)
```

The frontend Markdown renderer resolves only recognized backend output paths to absolute URLs using the same API base as normal backend requests:

```text
/outputs/report.xlsx -> ${API_BASE}/outputs/report.xlsx
outputs/report.xlsx  -> ${API_BASE}/outputs/report.xlsx
```

This keeps backend-generated content environment-agnostic while ensuring the browser opens the correct backend host.

## Frontend Design

Add URL helpers in `frontend/src/lib/api.ts`:

- `getBackendBaseUrl()` returns the API backend base URL currently used by fetch calls.
- `resolveBackendOutputUrl(href)` returns an absolute backend URL only for safe `/outputs/...` links.

Rules:

- Accept `/outputs/<file>` and `outputs/<file>`.
- Accept absolute URLs only if their path starts with `/outputs/`; normalize them to the configured backend base.
- Reject paths containing `..`.
- Leave all other links unchanged.

Update `ChatMessage.tsx` Markdown link rendering:

- Compute `resolvedHref = resolveBackendOutputUrl(props.href) || props.href`.
- Keep `target="_blank"` and `rel="noopener noreferrer"`.
- For non-PDF `/outputs/...` links, add `download` so files download when possible.
- For PDF `/outputs/...` links, do not add `download`; the browser can open it in a new tab.

## Backend Design

Keep the existing FastAPI static mount:

```python
app.mount("/outputs", StaticFiles(directory=str(outputs_dir)), name="outputs")
```

Ensure `backend/outputs/` exists at startup or before file generation. Generated file skills should write files into this directory and return Markdown links with `/outputs/<filename>`.

## Skill Guidance

Update file-producing skills, starting with `table-generator`, to return links like:

```markdown
已生成文件：[下载 Excel](/outputs/table-20260521.xlsx)
```

For PDFs:

```markdown
已生成文件：[查看 PDF](/outputs/report-20260521.pdf)
```

Skills should not hard-code `localhost`, IP addresses, or frontend hosts.

## Security

- Only `/outputs/...` paths are rewritten.
- Do not rewrite arbitrary filesystem paths such as `backend/outputs/a.xlsx` or `/Users/...`.
- Reject traversal patterns like `/outputs/../secret`.
- Keep external links sanitized by the existing Markdown sanitizer.

## Tests

- Unit-test URL helper behavior:
  - `/outputs/a.xlsx` resolves to backend base.
  - `outputs/a.xlsx` resolves to backend base.
  - `/outputs/a.pdf` resolves and is identified as PDF by renderer logic.
  - `/outputs/../secret` does not resolve.
  - external non-output URLs remain unchanged.
- Frontend build must pass.

## Acceptance Criteria

- A chat message containing `[下载 Excel](/outputs/test.xlsx)` opens `${API_BASE}/outputs/test.xlsx`.
- A chat message containing `[查看 PDF](/outputs/test.pdf)` opens the PDF in a new browser tab.
- The backend host used for links matches the frontend API backend base.
- No arbitrary local paths are exposed or rewritten.
