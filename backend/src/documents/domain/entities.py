from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass
class Document:
    title: str
    owner_id: UUID
    status: DocumentStatus = DocumentStatus.DRAFT
    version: int = 1
    id: UUID | None = field(default=None)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)
