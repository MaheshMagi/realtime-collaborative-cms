from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.domain.entities import User
from documents.application.services import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    update_document,
)
from documents.infrastructure.document_repository import DbDocumentRepository
from documents.interfaces.schemas import (
    CreateDocumentRequest,
    DocumentResponse,
    UpdateDocumentRequest,
)
from shared.dependencies import get_current_user, get_db

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/", response_model=DocumentResponse, status_code=201)
async def create(
    body: CreateDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = DbDocumentRepository(db)
    return await create_document(repo, title=body.title, owner_id=current_user.id)


@router.get("/", response_model=list[DocumentResponse])
async def list_all(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = DbDocumentRepository(db)
    return await list_documents(repo)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_one(
    document_id: UUID,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = DbDocumentRepository(db)
    return await get_document(repo, document_id)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update(
    document_id: UUID,
    body: UpdateDocumentRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = DbDocumentRepository(db)
    return await update_document(
        repo,
        document_id=document_id,
        expected_version=body.expected_version,
        title=body.title,
        status=body.status,
    )


@router.delete("/{document_id}", status_code=204)
async def delete(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = DbDocumentRepository(db)
    await delete_document(repo, document_id=document_id, user_id=current_user.id)
