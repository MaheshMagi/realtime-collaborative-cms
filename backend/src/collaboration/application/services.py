from uuid import UUID

from pycrdt import Doc

from collaboration.domain.entities import CrdtSnapshot, CrdtUpdate
from collaboration.domain.repository import CrdtStorageRepository
from collaboration.infrastructure.yjs_adapter import (
    apply_update,
    create_doc,
    encode_state_as_update,
    encode_state_vector,
)

SNAPSHOT_INTERVAL = 50  # create a snapshot every N updates


async def load_document_state(repo: CrdtStorageRepository, document_id: UUID) -> Doc:
    """Load the latest CRDT state from snapshot + pending updates."""
    doc = create_doc()

    snapshot = await repo.get_latest_snapshot(document_id)
    since_seq = 0
    if snapshot:
        apply_update(doc, snapshot.snapshot)
        since_seq = snapshot.update_seq

    updates = await repo.get_updates_since(document_id, since_seq)
    for update in updates:
        apply_update(doc, update.update_data)

    return doc


async def persist_update(
    repo: CrdtStorageRepository,
    document_id: UUID,
    user_id: UUID,
    update_data: bytes,
) -> CrdtUpdate:
    """Save an incremental CRDT update and trigger snapshot if needed."""
    seq = await repo.get_next_seq(document_id)

    update = CrdtUpdate(
        document_id=document_id,
        update_data=update_data,
        update_seq=seq,
        user_id=user_id,
    )
    saved = await repo.save_update(update)

    if seq % SNAPSHOT_INTERVAL == 0:
        await create_snapshot(repo, document_id)

    return saved


async def create_snapshot(repo: CrdtStorageRepository, document_id: UUID) -> CrdtSnapshot:
    """Rebuild the full doc state and persist a snapshot, then prune old updates."""
    doc = await load_document_state(repo, document_id)

    snapshot_data = encode_state_as_update(doc)
    state_vector = encode_state_vector(doc)

    # Get the current max seq to record what this snapshot covers
    next_seq = await repo.get_next_seq(document_id)
    current_seq = next_seq - 1

    snapshot = CrdtSnapshot(
        document_id=document_id,
        snapshot=snapshot_data,
        state_vector=state_vector,
        update_seq=current_seq,
    )
    saved = await repo.save_snapshot(snapshot)

    # Prune updates that are now covered by the snapshot
    await repo.delete_updates_before(document_id, current_seq)

    return saved
