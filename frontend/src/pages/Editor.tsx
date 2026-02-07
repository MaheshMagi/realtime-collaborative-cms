import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Collaboration from '@tiptap/extension-collaboration';
import { getDocument, updateDocument, type Document } from '../lib/api';
import { useCollaboration } from '../lib/useCollaboration';

export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<Document | null>(null);
  const [saving, setSaving] = useState(false);
  const { ydoc, connected, synced } = useCollaboration(id);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Collaboration.configure({ document: ydoc }),
    ],
  }, [synced]);

  useEffect(() => {
    if (!id) return;
    getDocument(id).then(setDoc).catch(() => navigate('/'));
  }, [id, navigate]);

  const handleSaveTitle = async () => {
    if (!doc) return;
    const title = prompt('New title:', doc.title);
    if (!title || title === doc.title) return;
    setSaving(true);
    try {
      const updated = await updateDocument(doc.id, {
        title,
        expected_version: doc.version,
      });
      setDoc(updated);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  if (!doc) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <header>
        <button onClick={() => navigate('/')}>Back</button>
        <h1 onClick={handleSaveTitle} title="Click to rename">
          {doc.title}
        </h1>
        <span className="doc-status">{doc.status}</span>
        <span className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? (synced ? 'Synced' : 'Syncing...') : 'Disconnected'}
        </span>
        {saving && <span>Saving...</span>}
      </header>
      <div className="editor-container">
        {synced ? (
          <EditorContent editor={editor} />
        ) : (
          <p>Connecting...</p>
        )}
      </div>
    </div>
  );
}
