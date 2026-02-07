import pytest

from auth.application.services import register_user
from auth.infrastructure.user_repository import DbUserRepository
from collaboration.application.services import (
    create_snapshot,
    load_document_state,
    persist_update,
)
from collaboration.infrastructure.crdt_storage_repository import DbCrdtStorageRepository
from collaboration.infrastructure.yjs_adapter import create_doc, encode_state_as_update, get_text
from documents.application.services import create_document
from documents.infrastructure.document_repository import DbDocumentRepository


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
async def doc(db, user):
    repo = DbDocumentRepository(db)
    return await create_document(repo, title="Test Doc", owner_id=user.id)


@pytest.fixture
def crdt_repo(db):
    return DbCrdtStorageRepository(db)


async def test_load_empty_document(crdt_repo, doc):
    ydoc = await load_document_state(crdt_repo, doc.id)
    assert get_text(ydoc) == ""


async def test_persist_and_load_update(crdt_repo, doc, user):
    # Create an update from a local doc edit
    local = create_doc()
    with local.transaction():
        local["content"] += "Hello from CRDT"
    update_bytes = encode_state_as_update(local)

    await persist_update(crdt_repo, doc.id, user.id, update_bytes)

    # Load state from DB and verify
    loaded = await load_document_state(crdt_repo, doc.id)
    assert get_text(loaded) == "Hello from CRDT"


async def test_multiple_updates(crdt_repo, doc, user):
    local = create_doc()

    with local.transaction():
        local["content"] += "First"
    await persist_update(crdt_repo, doc.id, user.id, encode_state_as_update(local))

    with local.transaction():
        local["content"] += " Second"
    await persist_update(crdt_repo, doc.id, user.id, encode_state_as_update(local))

    loaded = await load_document_state(crdt_repo, doc.id)
    assert get_text(loaded) == "First Second"


async def test_create_snapshot(crdt_repo, doc, user):
    local = create_doc()
    with local.transaction():
        local["content"] += "Snapshot me"
    await persist_update(crdt_repo, doc.id, user.id, encode_state_as_update(local))

    snapshot = await create_snapshot(crdt_repo, doc.id)
    assert snapshot.document_id == doc.id
    assert snapshot.update_seq == 1
    assert len(snapshot.snapshot) > 0

    # After snapshot, updates should be pruned
    updates = await crdt_repo.get_updates_since(doc.id, 0)
    assert len(updates) == 0

    # But state is still recoverable from snapshot
    loaded = await load_document_state(crdt_repo, doc.id)
    assert get_text(loaded) == "Snapshot me"


async def test_snapshot_then_more_updates(crdt_repo, doc, user):
    local = create_doc()

    with local.transaction():
        local["content"] += "Before"
    await persist_update(crdt_repo, doc.id, user.id, encode_state_as_update(local))
    await create_snapshot(crdt_repo, doc.id)

    with local.transaction():
        local["content"] += " After"
    await persist_update(crdt_repo, doc.id, user.id, encode_state_as_update(local))

    loaded = await load_document_state(crdt_repo, doc.id)
    assert get_text(loaded) == "Before After"
