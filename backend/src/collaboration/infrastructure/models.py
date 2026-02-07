import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database import Base


class CrdtSnapshotModel(Base):
    __tablename__ = "document_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    snapshot: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    state_vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    update_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class CrdtUpdateModel(Base):
    __tablename__ = "document_updates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    update_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    update_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
