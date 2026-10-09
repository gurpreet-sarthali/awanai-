import React, { useState, useEffect } from 'react';
import { Search, Database, MessageSquare, Save, FileText, Briefcase, BarChart3, Star, Clock } from 'lucide-react';
import { globalSearch, GlobalSearchResponse, SearchResultItem, toggleFavorite } from '../services/searchApi';

export function SearchPage({ activeWorkspaceId }: { activeWorkspaceId?: string }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GlobalSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const q = params.get('q');
    if (q) {
      setQuery(q);
      performSearch(q);
    }
  }, []);

  const performSearch = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await globalSearch(q, undefined, activeWorkspaceId);
      setResults(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    window.history.pushState(null, '', `/search?q=${encodeURIComponent(query)}`);
    performSearch(query);
  };

  const handleFavorite = async (item: SearchResultItem, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await toggleFavorite(item.type, item.id, item.workspace_id, item.favorite);
      // Optimistic update
      setResults(prev => {
        if (!prev) return prev;
        const newResults = { ...prev.results };
        for (const [key, list] of Object.entries(newResults)) {
          newResults[key as keyof typeof newResults] = list.map((r: SearchResultItem) => 
            r.id === item.id && r.type === item.type ? { ...r, favorite: !r.favorite } : r
          );
        }
        return { ...prev, results: newResults };
      });
    } catch (err) {
      console.error(err);
    }
  };

  const renderIcon = (type: string) => {
    switch (type) {
      case 'dataset': return <Database size={16} />;
      case 'conversation': return <MessageSquare size={16} />;
      case 'saved_query': return <Save size={16} />;
      case 'report': return <FileText size={16} />;
      case 'workspace': return <Briefcase size={16} />;
      case 'analytics_result': return <BarChart3 size={16} />;
      default: return <Search size={16} />;
    }
  };

  const renderItems = (items: SearchResultItem[]) => {
    if (!items || items.length === 0) return null;
    return items.map(item => (
      <div key={`${item.type}-${item.id}`} className="search-result-card" style={{ padding: '16px', border: '1px solid #eee', borderRadius: '8px', marginBottom: '12px', background: '#fff', display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
        <div style={{ padding: '10px', background: '#f5f7fa', borderRadius: '8px', color: '#6f7d86' }}>
          {renderIcon(item.type)}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: '0 0 4px 0', fontSize: '15px' }}>{item.title}</h3>
            <button onClick={(e) => handleFavorite(item, e)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: item.favorite ? '#f59e0b' : '#ccc' }}>
              <Star size={16} fill={item.favorite ? '#f59e0b' : 'none'} />
            </button>
          </div>
          <p style={{ margin: '0 0 8px 0', fontSize: '13px', color: '#6f7d86' }}>{item.description}</p>
          <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: '#888' }}>
            <span style={{ textTransform: 'capitalize' }}>{item.type.replace('_', ' ')}</span>
            {item.workspace_name && <span>Workspace: {item.workspace_name}</span>}
            <span>Updated: {new Date(item.updated_at).toLocaleDateString()}</span>
          </div>
        </div>
      </div>
    ));
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '32px' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '16px' }}>Global Search</h1>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '8px' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={18} style={{ position: 'absolute', left: '12px', top: '10px', color: '#888' }} />
            <input 
              type="text" 
              value={query} 
              onChange={e => setQuery(e.target.value)}
              placeholder="Search datasets, conversations, reports..." 
              style={{ width: '100%', padding: '10px 10px 10px 40px', borderRadius: '8px', border: '1px solid #ccc', fontSize: '15px' }}
            />
          </div>
          <button type="submit" className="button primary" disabled={loading}>
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>
      </div>

      {results && (
        <div>
          <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', borderBottom: '1px solid #eee', paddingBottom: '8px' }}>
            <button onClick={() => setActiveTab('all')} style={{ background: 'none', border: 'none', padding: '4px 8px', cursor: 'pointer', fontWeight: activeTab === 'all' ? 600 : 400, color: activeTab === 'all' ? '#102a43' : '#6f7d86', borderBottom: activeTab === 'all' ? '2px solid #102a43' : '2px solid transparent' }}>All Results ({results.total})</button>
            <button onClick={() => setActiveTab('datasets')} style={{ background: 'none', border: 'none', padding: '4px 8px', cursor: 'pointer', fontWeight: activeTab === 'datasets' ? 600 : 400, color: activeTab === 'datasets' ? '#102a43' : '#6f7d86', borderBottom: activeTab === 'datasets' ? '2px solid #102a43' : '2px solid transparent' }}>Datasets ({results.results.datasets.length})</button>
            <button onClick={() => setActiveTab('conversations')} style={{ background: 'none', border: 'none', padding: '4px 8px', cursor: 'pointer', fontWeight: activeTab === 'conversations' ? 600 : 400, color: activeTab === 'conversations' ? '#102a43' : '#6f7d86', borderBottom: activeTab === 'conversations' ? '2px solid #102a43' : '2px solid transparent' }}>Conversations ({results.results.conversations.length})</button>
          </div>

          <div>
            {activeTab === 'all' && (
              <>
                {renderItems(results.results.datasets)}
                {renderItems(results.results.conversations)}
                {renderItems(results.results.saved_queries)}
                {renderItems(results.results.reports)}
                {renderItems(results.results.workspaces)}
                {renderItems(results.results.analytics_results)}
              </>
            )}
            {activeTab === 'datasets' && renderItems(results.results.datasets)}
            {activeTab === 'conversations' && renderItems(results.results.conversations)}
            {results.total === 0 && <p style={{ color: '#6f7d86', textAlign: 'center', marginTop: '48px' }}>No results found for "{results.query}".</p>}
          </div>
        </div>
      )}
    </div>
  );
}
