"""
结构化记忆存储 - JSONL 文件持久化
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


ALLOWED_MEMORY_TYPES = {"preference", "project", "feedback", "reference"}
ALLOWED_MEMORY_STATUSES = {"active", "deleted"}
ALLOWED_MEMORY_SOURCES = {"auto", "manual"}


class MemoryStore:
    """管理 backend/memory/memories.jsonl 中的结构化记忆。"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.memory_dir = base_dir / "memory"
        self.memory_file = self.memory_dir / "memories.jsonl"

    def list_all(self) -> List[Dict[str, Any]]:
        """返回所有有效记忆记录，包括 deleted。"""
        return self._load_records()

    def list_active(self) -> List[Dict[str, Any]]:
        """返回 active 记忆记录。"""
        return [record for record in self._load_records() if record["status"] == "active"]

    def add_memory(
        self,
        memory_type: str,
        content: str,
        source: str = "auto",
        confidence: float = 0.8,
    ) -> Dict[str, Any]:
        """新增一条 active 记忆。"""
        now = self._now()
        record = {
            "id": self._generate_id(),
            "type": memory_type,
            "content": content,
            "status": "active",
            "source": source,
            "confidence": float(confidence),
            "created_at": now,
            "updated_at": now,
        }
        self._validate_or_raise(record)
        records = self._load_records()
        records.append(record)
        self._write_records(records)
        return record

    def update_memory(
        self,
        memory_id: str,
        memory_type: Optional[str] = None,
        content: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """更新已有记忆，找不到则返回 None。"""
        records = self._load_records()
        for record in records:
            if record["id"] != memory_id:
                continue
            if memory_type is not None:
                record["type"] = memory_type
            if content is not None:
                record["content"] = content
            if confidence is not None:
                record["confidence"] = float(confidence)
            record["updated_at"] = self._now()
            self._validate_or_raise(record)
            self._write_records(records)
            return record
        return None

    def delete_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """将记忆标记为 deleted，找不到则返回 None。"""
        records = self._load_records()
        for record in records:
            if record["id"] != memory_id:
                continue
            record["status"] = "deleted"
            record["updated_at"] = self._now()
            self._write_records(records)
            return record
        return None

    def _load_records(self) -> List[Dict[str, Any]]:
        if not self.memory_file.exists():
            return []

        records = []
        with self.memory_file.open("r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    print(f"跳过无效记忆 JSONL 行 {line_number}: {exc}")
                    continue
                if not self._is_valid_record(record):
                    print(f"跳过无效记忆记录 {line_number}: {record}")
                    continue
                records.append(record)
        return records

    def _write_records(self, records: List[Dict[str, Any]]) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = self.memory_file.with_suffix(".jsonl.tmp")
        with tmp_file.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                f.write("\n")
        os.replace(tmp_file, self.memory_file)

    def _is_valid_record(self, record: Any) -> bool:
        if not isinstance(record, dict):
            return False
        required = {
            "id",
            "type",
            "content",
            "status",
            "source",
            "confidence",
            "created_at",
            "updated_at",
        }
        if not required.issubset(record.keys()):
            return False
        if record["type"] not in ALLOWED_MEMORY_TYPES:
            return False
        if record["status"] not in ALLOWED_MEMORY_STATUSES:
            return False
        if record["source"] not in ALLOWED_MEMORY_SOURCES:
            return False
        if not isinstance(record["content"], str) or not record["content"].strip():
            return False
        try:
            confidence = float(record["confidence"])
        except (TypeError, ValueError):
            return False
        return 0 <= confidence <= 1

    def _validate_or_raise(self, record: Dict[str, Any]) -> None:
        if not self._is_valid_record(record):
            raise ValueError(f"Invalid memory record: {record}")

    def _generate_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d")
        suffix = uuid.uuid4().hex[:8]
        return f"mem_{timestamp}_{suffix}"

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
