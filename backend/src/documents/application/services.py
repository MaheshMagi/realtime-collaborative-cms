from uuid import UUID

from documents.domain.entities import Document, DocumentStatus
from documents.domain.repository import DocumentRepository
from shared.exceptions import AuthorizationError, NotFoundError


async def create_document(
    repo: DocumentRepository,
    title: str,
    owner_id: UUID,
) -> Document:
    doc = Document(title=title, owner_id=owner_id)
    return await repo.create(doc)


async def get_document(repo: DocumentRepository, document_id: UUID) -> Document:
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise NotFoundError("Document", str(document_id))
    return doc


async def list_documents(repo: DocumentRepository) -> list[Document]:
    return await repo.list_all()


async def update_document(
    repo: DocumentRepository,
    document_id: UUID,
    expected_version: int,
    title: str | None = None,
    status: DocumentStatus | None = None,
) -> Document:
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise NotFoundError("Document", str(document_id))

    if title is not None:
        doc.title = title
    if status is not None:
        doc.status = status

    return await repo.update(doc, expected_version)


async def delete_document(
    repo: DocumentRepository, document_id: UUID, user_id: UUID
) -> None:
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise NotFoundError("Document", str(document_id))
    if doc.owner_id != user_id:
        raise AuthorizationError("Only the document owner can delete it")
    await repo.delete(document_id)
