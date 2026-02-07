from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class CrdtSnapshot:
    document_id: UUID
    snapshot: bytes
    state_vector: bytes
    update_seq: int
    id: int | None = field(default=None)
    created_at: datetime | None = field(default=None)


@dataclass
class CrdtUpdate:
    document_id: UUID
    update_data: bytes
    update_seq: int
    user_id: UUID
    id: int | None = field(default=None)
    created_at: datetime | None = field(default=None)
