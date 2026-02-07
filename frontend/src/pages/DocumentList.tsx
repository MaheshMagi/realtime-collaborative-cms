import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listDocuments, createDocument, deleteDocument, type Document } from '../lib/api';
import { useAuth } from '../lib/auth';

export default function DocumentList() {
  const [docs, setDocs] = useState<Document[]>([]);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const load = async () => {
    const data = await listDocuments();
    setDocs(data);
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    const title = prompt('Document title:');
    if (!title) return;
    const doc = await createDocument(title);
    navigate(`/documents/${doc.id}`);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this document?')) return;
    await deleteDocument(id);
    load();
  };

  return (
    <div className="page">
      <header>
        <h1>Documents</h1>
        <div>
          <span>{user?.username}</span>
          <button onClick={logout}>Logout</button>
        </div>
      </header>
      <button onClick={handleCreate}>New Document</button>
      <ul className="doc-list">
        {docs.map((doc) => (
          <li key={doc.id}>
            <span className="doc-title" onClick={() => navigate(`/documents/${doc.id}`)}>
              {doc.title}
            </span>
            <span className="doc-status">{doc.status}</span>
            {doc.owner_id === user?.id && (
              <button className="delete-btn" onClick={() => handleDelete(doc.id)}>
                Delete
              </button>
            )}
          </li>
        ))}
        {docs.length === 0 && <li className="empty">No documents yet</li>}
      </ul>
    </div>
  );
}
