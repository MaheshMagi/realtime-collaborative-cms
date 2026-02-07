from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from documents.domain.entities import DocumentStatus


class CreateDocumentRequest(BaseModel):
    title: str


class UpdateDocumentRequest(BaseModel):
    title: str | None = None
    status: DocumentStatus | None = None
    expected_version: int


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    status: DocumentStatus
    owner_id: UUID
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
