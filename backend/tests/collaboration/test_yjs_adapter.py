from collaboration.infrastructure.yjs_adapter import (
    apply_update,
    create_doc,
    encode_state_as_update,
    encode_state_vector,
    get_text,
    merge_updates,
)


def test_create_doc():
    doc = create_doc()
    assert get_text(doc) == ""


def test_apply_and_get_text():
    doc = create_doc()
    with doc.transaction():
        doc["content"] += "Hello, world!"
    assert get_text(doc) == "Hello, world!"


def test_encode_and_restore():
    doc1 = create_doc()
    with doc1.transaction():
        doc1["content"] += "Some text"

    update = encode_state_as_update(doc1)
    assert isinstance(update, bytes)
    assert len(update) > 0

    doc2 = create_doc()
    apply_update(doc2, update)
    assert get_text(doc2) == "Some text"


def test_state_vector():
    doc = create_doc()
    with doc.transaction():
        doc["content"] += "test"
    sv = encode_state_vector(doc)
    assert isinstance(sv, bytes)
    assert len(sv) > 0


def test_merge_updates():
    doc1 = create_doc()
    with doc1.transaction():
        doc1["content"] += "Hello"
    update1 = encode_state_as_update(doc1)

    with doc1.transaction():
        doc1["content"] += " World"
    update2 = encode_state_as_update(doc1)

    merged = merge_updates([update1, update2])
    doc_restored = create_doc()
    apply_update(doc_restored, merged)
    assert get_text(doc_restored) == "Hello World"


def test_concurrent_edits_merge():
    """Two independent docs editing concurrently merge without conflict."""
    doc_a = create_doc()
    doc_b = create_doc()

    with doc_a.transaction():
        doc_a["content"] += "A"
    update_a = encode_state_as_update(doc_a)

    with doc_b.transaction():
        doc_b["content"] += "B"
    update_b = encode_state_as_update(doc_b)

    # Apply each other's updates
    apply_update(doc_a, update_b)
    apply_update(doc_b, update_a)

    # Both should have the same content (order may vary, but both chars present)
    text_a = get_text(doc_a)
    text_b = get_text(doc_b)
    assert text_a == text_b
    assert "A" in text_a
    assert "B" in text_a
