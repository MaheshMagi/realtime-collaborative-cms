from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class User:
    username: str
    email: str
    first_name: str
    last_name: str
    password_hash: str
    id: UUID | None = field(default=None)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)
