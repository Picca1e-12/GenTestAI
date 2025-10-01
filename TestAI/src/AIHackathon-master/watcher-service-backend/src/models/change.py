from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class ChangeType(str, Enum):
    MODIFIED = "modified"
    CREATED = "created"
    DELETED = "deleted"

class FileChange(BaseModel):
    id: str
    timestamp: datetime
    repo_path: str
    repo_name: str
    file_path: str
    relative_path: str
    change_type: ChangeType
    git_diff: str
    author: str
    author_email: str
    commit_hash: Optional[str]
    file_extension: str
    lines_added: int
    lines_removed: int
    is_processed: bool = False

class Repository(BaseModel):
    id: str
    name: str
    path: str
    is_watching: bool
    last_change: Optional[datetime]
    total_changes: int