from uuid import uuid4

import pytest

from auth.application.services import register_user
from auth.infrastructure.user_repository import DbUserRepository
from documents.application.services import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    update_document,
)
from documents.domain.entities import DocumentStatus
from documents.infrastructure.document_repository import DbDocumentRepository
from shared.exceptions import AuthorizationError, ConflictError, NotFoundError


@pytest.fixture
async def user(db):
    repo = DbUserRepository(db)
    return await register_user(
        repo,
        username="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
        password="secret123",
    )


@pytest.fixture
def repo(db):
    return DbDocumentRepository(db)


async def test_create_document(repo, user):
    doc = await create_document(repo, title="My Doc", owner_id=user.id)
    assert doc.id is not None
    assert doc.title == "My Doc"
    assert doc.status == DocumentStatus.DRAFT
    assert doc.owner_id == user.id
    assert doc.version == 1


async def test_get_document(repo, user):
    created = await create_document(repo, title="My Doc", owner_id=user.id)
    doc = await get_document(repo, created.id)
    assert doc.id == created.id
    assert doc.title == "My Doc"


async def test_get_document_not_found(repo):
    with pytest.raises(NotFoundError):
        await get_document(repo, uuid4())


async def test_list_documents(repo, user):
    await create_document(repo, title="Doc 1", owner_id=user.id)
    await create_document(repo, title="Doc 2", owner_id=user.id)
    docs = await list_documents(repo)
    assert len(docs) == 2


async def test_update_document(repo, user):
    doc = await create_document(repo, title="Old Title", owner_id=user.id)
    updated = await update_document(
        repo, document_id=doc.id, expected_version=1, title="New Title"
    )
    assert updated.title == "New Title"
    assert updated.version == 2


async def test_update_document_status(repo, user):
    doc = await create_document(repo, title="My Doc", owner_id=user.id)
    updated = await update_document(
        repo, document_id=doc.id, expected_version=1, status=DocumentStatus.PUBLISHED
    )
    assert updated.status == DocumentStatus.PUBLISHED


async def test_update_document_conflict(repo, user):
    doc = await create_document(repo, title="My Doc", owner_id=user.id)
    await update_document(repo, document_id=doc.id, expected_version=1, title="V2")
    with pytest.raises(ConflictError):
        await update_document(repo, document_id=doc.id, expected_version=1, title="V2 again")


async def test_delete_document(repo, user):
    doc = await create_document(repo, title="To Delete", owner_id=user.id)
    await delete_document(repo, document_id=doc.id, user_id=user.id)
    with pytest.raises(NotFoundError):
        await get_document(repo, doc.id)


async def test_delete_document_wrong_owner(repo, user, db):
    doc = await create_document(repo, title="My Doc", owner_id=user.id)
    other_user = await register_user(
        DbUserRepository(db),
        username="bob",
        email="bob@example.com",
        first_name="Bob",
        last_name="Jones",
        password="secret123",
    )
    with pytest.raises(AuthorizationError):
        await delete_document(repo, document_id=doc.id, user_id=other_user.id)
