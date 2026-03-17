"""
文件管理 API - 文件读写、上传和技能列表
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from config import BASE_DIR
from graph import agent_manager
from tools.skills_scanner import scan_skills


router = APIRouter()


# 允许访问的目录前缀
ALLOWED_PREFIXES = [
    "workspace/",
    "memory/",
    "skills/",
    "knowledge/",
    "outputs/",
    "/workspace/",
    "/memory/",
    "/skills/",
    "/knowledge/",
    "/outputs/",
    "./workspace/",
    "./memory/",
    "./skills/",
    "./knowledge/",
    "./outputs/",
]

# 允许的根目录文件
ALLOWED_ROOT_FILES = [
    "SKILLS_SNAPSHOT.md",
]

# 允许上传的文件扩展名
ALLOWED_UPLOAD_EXTENSIONS = {
    # 图片
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp",
    # 文档
    ".txt", ".md", ".pdf", ".csv", ".json", ".xml", ".yaml", ".yml",
    # 代码
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".h",
    ".html", ".css", ".scss", ".vue", ".swift", ".kt", ".rb", ".php",
    # 其他
    ".log", ".sql", ".sh",
}

# 单个文件大小限制 (10MB)
MAX_UPLOAD_FILE_SIZE = 10 * 1024 * 1024


class SaveFileRequest(BaseModel):
    """保存文件请求"""
    path: str
    content: str


def is_path_allowed(path: str) -> bool:
    """
    检查路径是否在白名单中（使用路径解析防止遍历攻击）
    
    Args:
        path: 相对路径
        
    Returns:
        是否允许访问
    """
    # 基本格式检查
    if not path or not isinstance(path, str):
        return False
    
    # 检查根目录文件
    if path in ALLOWED_ROOT_FILES:
        return True
    
    # 检查目录前缀
    prefix_ok = any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)
    if not prefix_ok:
        return False
    
    # 使用 resolve() 验证最终路径确实在 BASE_DIR 内（防止 ../ 遍历）
    try:
        full_path = (BASE_DIR / path).resolve()
        base_resolved = BASE_DIR.resolve()
        # 确保解析后的路径在 BASE_DIR 内
        return str(full_path).startswith(str(base_resolved) + "/") or full_path == base_resolved
    except Exception:
        return False


@router.get("/files")
async def read_file(path: str = Query(..., description="文件路径")):
    """
    读取文件内容
    
    路径白名单：
    - workspace/*
    - memory/*
    - skills/*
    - knowledge/*
    - SKILLS_SNAPSHOT.md
    """
    if not is_path_allowed(path):
        raise HTTPException(status_code=403, detail="Access denied: path not allowed")
    
    file_path = BASE_DIR / path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    try:
        content = file_path.read_text(encoding="utf-8")
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.post("/files")
async def save_file(request: SaveFileRequest):
    """
    保存文件内容
    
    保存 memory/MEMORY.md 时会自动触发索引重建
    """
    if not is_path_allowed(request.path):
        raise HTTPException(status_code=403, detail="Access denied: path not allowed")
    
    file_path = BASE_DIR / request.path
    
    # 确保父目录存在
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        file_path.write_text(request.content, encoding="utf-8")
        
        # 如果是 MEMORY.md，触发索引重建
        if request.path == "memory/MEMORY.md":
            try:
                agent_manager.memory_indexer.rebuild_index()
            except Exception:
                pass
        
        return {"success": True, "path": request.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


@router.get("/skills")
async def list_skills():
    """列出可用技能"""
    skills_dir = BASE_DIR / "skills"
    skills = scan_skills(skills_dir)
    return {"skills": skills}


def validate_upload_file(filename: str, file_size: int) -> tuple:
    """
    验证上传文件是否合法

    Returns:
        (is_valid, error_message)
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return False, f"不支持的文件类型: {ext}"

    if file_size > MAX_UPLOAD_FILE_SIZE:
        return False, f"文件过大: {file_size / 1024 / 1024:.1f}MB (限制: 10MB)"

    if ".." in filename or "/" in filename or "\\" in filename:
        return False, "非法文件名"

    return True, ""


@router.post("/files/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    批量上传文件到 knowledge/uploads/ 目录

    Returns:
        uploaded_files 列表，包含 filename/path/size
    """
    if not files:
        raise HTTPException(status_code=400, detail="未选择文件")

    upload_dir = BASE_DIR / "knowledge" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    uploaded_files = []

    for file in files:
        content = await file.read()
        file_size = len(content)

        is_valid, error_msg = validate_upload_file(file.filename, file_size)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"{file.filename}: {error_msg}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        ext = Path(file.filename).suffix
        original_name = Path(file.filename).stem[:50]
        safe_filename = f"{timestamp}_{unique_id}_{original_name}{ext}"

        file_path = upload_dir / safe_filename
        file_path.write_bytes(content)

        relative_path = f"knowledge/uploads/{safe_filename}"

        uploaded_files.append({
            "filename": file.filename,
            "path": relative_path,
            "size": file_size,
        })

    return {"uploaded_files": uploaded_files}
