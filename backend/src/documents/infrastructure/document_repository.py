from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from documents.domain.entities import Document, DocumentStatus
from documents.infrastructure.models import DocumentModel
from shared.exceptions import ConflictError


class DbDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, document_id: UUID) -> Document | None:
        result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def list_all(self) -> list[Document]:
        result = await self.session.execute(
            select(DocumentModel).order_by(DocumentModel.created_at.desc())
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def create(self, document: Document) -> Document:
        model = DocumentModel(
            title=document.title,
            status=document.status.value,
            owner_id=document.owner_id,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return _to_entity(model)

    async def update(self, document: Document, expected_version: int) -> Document:
        result = await self.session.execute(
            update(DocumentModel)
            .where(
                DocumentModel.id == document.id,
                DocumentModel.version == expected_version,
            )
            .values(
                title=document.title,
                status=document.status.value,
                version=expected_version + 1,
            )
        )
        if result.rowcount == 0:
            raise ConflictError("Document was modified by another user")

        await self.session.commit()

        refreshed = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == document.id)
        )
        return _to_entity(refreshed.scalar_one())

    async def delete(self, document_id: UUID) -> None:
        result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self.session.delete(model)
            await self.session.commit()


def _to_entity(model: DocumentModel) -> Document:
    return Document(
        id=model.id,
        title=model.title,
        status=DocumentStatus(model.status),
        owner_id=model.owner_id,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
