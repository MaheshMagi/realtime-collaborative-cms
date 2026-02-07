from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from collaboration.domain.entities import CrdtSnapshot, CrdtUpdate
from collaboration.infrastructure.models import CrdtSnapshotModel, CrdtUpdateModel


class DbCrdtStorageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest_snapshot(self, document_id: UUID) -> CrdtSnapshot | None:
        result = await self.session.execute(
            select(CrdtSnapshotModel)
            .where(CrdtSnapshotModel.document_id == document_id)
            .order_by(CrdtSnapshotModel.update_seq.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return _snapshot_to_entity(model) if model else None

    async def get_updates_since(self, document_id: UUID, since_seq: int) -> list[CrdtUpdate]:
        result = await self.session.execute(
            select(CrdtUpdateModel)
            .where(
                CrdtUpdateModel.document_id == document_id,
                CrdtUpdateModel.update_seq > since_seq,
            )
            .order_by(CrdtUpdateModel.update_seq.asc())
        )
        return [_update_to_entity(m) for m in result.scalars().all()]

    async def save_update(self, update: CrdtUpdate) -> CrdtUpdate:
        model = CrdtUpdateModel(
            document_id=update.document_id,
            update_data=update.update_data,
            update_seq=update.update_seq,
            user_id=update.user_id,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return _update_to_entity(model)

    async def save_snapshot(self, snapshot: CrdtSnapshot) -> CrdtSnapshot:
        model = CrdtSnapshotModel(
            document_id=snapshot.document_id,
            snapshot=snapshot.snapshot,
            state_vector=snapshot.state_vector,
            update_seq=snapshot.update_seq,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return _snapshot_to_entity(model)

    async def delete_updates_before(self, document_id: UUID, up_to_seq: int) -> None:
        await self.session.execute(
            delete(CrdtUpdateModel).where(
                CrdtUpdateModel.document_id == document_id,
                CrdtUpdateModel.update_seq <= up_to_seq,
            )
        )
        await self.session.commit()

    async def get_next_seq(self, document_id: UUID) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.max(CrdtUpdateModel.update_seq), 0))
            .where(CrdtUpdateModel.document_id == document_id)
        )
        return result.scalar_one() + 1


def _snapshot_to_entity(model: CrdtSnapshotModel) -> CrdtSnapshot:
    return CrdtSnapshot(
        id=model.id,
        document_id=model.document_id,
        snapshot=model.snapshot,
        state_vector=model.state_vector,
        update_seq=model.update_seq,
        created_at=model.created_at,
    )


def _update_to_entity(model: CrdtUpdateModel) -> CrdtUpdate:
    return CrdtUpdate(
        id=model.id,
        document_id=model.document_id,
        update_data=model.update_data,
        update_seq=model.update_seq,
        user_id=model.user_id,
        created_at=model.created_at,
    )
