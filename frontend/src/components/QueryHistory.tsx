import { useEffect, useState } from 'react';
import { Clock, MessageSquareText, Trash2, ExternalLink } from 'lucide-react';
import { listConversations, deleteConversation, type ConversationSummary } from '../services/chatApi';

interface QueryHistoryProps {
  onOpen: (id: string) => void;
}

export function QueryHistory({ onOpen }: QueryHistoryProps) {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    listConversations()
      .then(setItems)
      .catch(() => setError('Could not load history.'))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      setItems(prev => prev.filter(c => c.id !== id));
    } catch {
      setError('Could not delete conversation.');
    }
  };

  const filtered = items.filter(c =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  const grouped = filtered.reduce((acc, conv) => {
    const date = new Date(conv.created_at).toLocaleDateString(undefined, {
      month: 'long', day: 'numeric', year: 'numeric'
    });
    if (!acc[date]) acc[date] = [];
    acc[date].push(conv);
    return acc;
  }, {} as Record<string, ConversationSummary[]>);

  return (
    <div className="qh-panel">
      <div className="qh-header">
        <div className="qh-title-row">
          <Clock size={18} />
          <h2 className="qh-title">Query History</h2>
          <span className="qh-count">{items.length} conversations</span>
        </div>
        <input
          className="qh-search"
          placeholder="Search conversations…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {error && <div className="qh-error">{error}</div>}

      {loading ? (
        <div className="qh-loading">
          <span className="spinner" />
          <span>Loading history…</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="qh-empty">
          <MessageSquareText size={32} />
          <p>{search ? 'No conversations match your search.' : 'No query history yet. Start a conversation in "Ask your data".'}</p>
        </div>
      ) : (
        <div className="qh-list">
          {Object.entries(grouped).map(([date, convs]) => (
            <div key={date} className="qh-group">
              <div className="qh-group-label">{date}</div>
              {convs.map(conv => (
                <div
                  key={conv.id}
                  className="qh-item"
                  onClick={() => onOpen(conv.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={e => e.key === 'Enter' && onOpen(conv.id)}
                >
                  <div className="qh-item-icon">
                    <MessageSquareText size={14} />
                  </div>
                  <div className="qh-item-body">
                    <span className="qh-item-title">{conv.title}</span>
                    <span className="qh-item-meta">
                      {new Date(conv.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      {conv.dataset_id && (
                        <span className="qh-dataset-chip">dataset: {conv.dataset_id.slice(0, 8)}…</span>
                      )}
                    </span>
                  </div>
                  <div className="qh-item-actions">
                    <button
                      className="qh-open-btn"
                      title="Open in chat"
                      onClick={e => { e.stopPropagation(); onOpen(conv.id); }}
                    >
                      <ExternalLink size={13} />
                    </button>
                    <button
                      className="qh-delete-btn"
                      title="Delete"
                      onClick={e => handleDelete(conv.id, e)}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
