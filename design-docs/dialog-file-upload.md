# Dialog File Upload Feature Plan

## Overview
Add file and image upload capability to the chat input. Files are saved to `knowledge/uploads/` on the backend, and their paths are embedded in the user message text so the Agent can read them via `read_file` tool.

## Files to Modify (5 files)

### 1. `backend/api/files.py` - Add upload endpoint

**Add imports**: `UploadFile`, `File` from fastapi; `uuid`, `datetime`, `List` from typing.

**Add constants**:
- `ALLOWED_EXTENSIONS`: set of allowed file extensions (images: jpg/jpeg/png/gif/webp; docs: txt/md/pdf/csv/json/xml/yaml; code: py/js/ts/tsx/jsx/html/css etc.)
- `MAX_FILE_SIZE = 10 * 1024 * 1024` (10MB)

**Add helper function** `validate_file(filename, file_size)` - checks extension whitelist, size limit, path traversal.

**Add endpoint** `POST /files/upload`:
- Accepts `files: List[UploadFile] = File(...)`
- Creates `knowledge/uploads/` dir if not exists
- For each file: validate, generate unique filename (`{timestamp}_{uuid8}_{original_name}{ext}`), save bytes
- Returns `{"uploaded_files": [{"filename": str, "path": str, "size": int}]}`

No changes needed to `app.py` - the route is already registered via `files_router` with `/api` prefix. The `knowledge/` path is already in the whitelist.

---

### 2. `frontend/src/lib/api.ts` - Add upload API function

**Add after `saveFile()`**:
- `UploadedFile` interface: `{filename, path, size}`
- `uploadFiles(files: File[])` function: creates `FormData`, appends files, POSTs to `/api/files/upload` (no Content-Type header - let browser set multipart boundary), returns `{uploaded_files: UploadedFile[]}`

---

### 3. `frontend/src/lib/store.tsx` - Extend Message type and sendMessage

**Add interface** `Attachment`: `{filename, path, size, type: 'image' | 'document'}`

**Extend** `Message` interface: add optional `attachments?: Attachment[]`

**Modify** `AppContextType.sendMessage` signature: `(content: string, attachments?: Attachment[]) => Promise<void>`

**Modify** `sendMessage` implementation:
- Accept `attachments` parameter
- Include `attachments` in user message object (for UI rendering)
- When calling `streamChat()`, append attachment info to message text:
  ```
  {content}\n\n[用户上传了以下文件: filename1 (path1), filename2 (path2)]
  ```
  This lets the Agent know about the files and use `read_file` tool.

---

### 4. `frontend/src/components/chat/ChatInput.tsx` - Major UI changes

**New state**: `selectedFiles: File[]`, `isUploading: boolean`

**New refs**: `fileInputRef` for hidden `<input type="file">`

**New handlers**:
- `handleFileSelect`: merge new files (deduplicate by name+size), reset input
- `removeFile(index)`: remove file from selection
- `formatFileSize(bytes)`: human-readable size

**Modified `handleSubmit`**:
1. If `selectedFiles` not empty, call `uploadFiles()` first
2. Map results to `Attachment[]` (determine type by MIME)
3. Call `sendMessage(content, attachments)`
4. Clear input and selectedFiles
5. Handle errors with alert

**UI structure**:
```
<div className="space-y-2">
  {/* File preview area (above input, shown when files selected) */}
  <div className="flex flex-wrap gap-2">
    {selectedFiles.map(file => (
      <FilePreviewCard>  {/* bg-gray-100, rounded-lg, shows icon+name+size+X button */}
    ))}
  </div>

  {/* Input row */}
  <div className="flex items-end gap-2">
    <div className="flex-1 relative">
      <textarea ... className="...pr-20" />  {/* wider right padding for 2 buttons */}
      <button Paperclip ... className="absolute right-12 bottom-2" />  {/* attach button */}
      <button Send ... className="absolute right-2 bottom-2" />  {/* send button */}
      <input type="file" hidden multiple accept="..." ref={fileInputRef} />
    </div>
  </div>
</div>
```

**Icons**: `Paperclip`, `X`, `FileText`, `Image` from lucide-react (already installed)

---

### 5. `frontend/src/components/chat/ChatMessage.tsx` - Show attachments in user bubbles

**Add imports**: `FileText`, `Image as ImageIcon` from lucide-react

**Add attachment display** between retrievals section and tool_calls section:
```tsx
{message.attachments?.length > 0 && (
  <div className="mb-2 flex flex-wrap gap-2">
    {message.attachments.map(att => (
      <div className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-blue-100 text-blue-800">
        <Icon /> <filename truncated> <size>
      </div>
    ))}
  </div>
)}
```

User messages get `bg-blue-100 text-blue-800` style, consistent with the blue theme.

---

## Agent Integration (no code changes needed)

The uploaded file paths are embedded in the user message text. Example:
```
请帮我分析这个文件

[用户上传了以下文件: data.csv (knowledge/uploads/20260227_abc123_data.csv)]
```

The Agent will naturally use `read_file` tool with the provided path. The `knowledge/` prefix is already whitelisted in `files.py`.

---

## Verification Plan

1. **Backend**: `curl -X POST http://localhost:8002/api/files/upload -F "files=@test.txt"` - verify file saved to `knowledge/uploads/`
2. **Frontend**: Click paperclip, select files, verify preview appears with correct info, verify X button removes file
3. **Send**: Type message + attach file, send, verify:
   - User message bubble shows attachment badges
   - Agent receives file path in message
   - Agent can call `read_file` on the uploaded file
4. **Edge cases**: Upload >10MB file (should error), upload .exe (should error), send with only files and no text (should work)
