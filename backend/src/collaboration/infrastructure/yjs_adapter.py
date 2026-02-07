from pycrdt import Doc, Text


def create_doc() -> Doc:
    doc = Doc()
    doc["content"] = Text()
    return doc


def apply_update(doc: Doc, update: bytes) -> None:
    doc.apply_update(update)


def encode_state_as_update(doc: Doc) -> bytes:
    return doc.get_update()


def encode_state_vector(doc: Doc) -> bytes:
    return doc.get_state()


def get_text(doc: Doc) -> str:
    return str(doc["content"])


def merge_updates(updates: list[bytes]) -> bytes:
    """Apply multiple updates to a fresh doc and return the merged state."""
    doc = create_doc()
    for update in updates:
        doc.apply_update(update)
    return doc.get_update()
