import React, { useState, useEffect } from 'react';
import { Database, Search, Star, Clock, Tags, Filter } from 'lucide-react';
import { getDatasetCatalog, toggleFavorite } from '../services/searchApi';

export function CatalogPage({ activeWorkspaceId }: { activeWorkspaceId?: string }) {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  useEffect(() => {
    loadCatalog();
  }, [activeWorkspaceId]);

  const loadCatalog = async (q = '') => {
    setLoading(true);
    try {
      const res = await getDatasetCatalog(q, activeWorkspaceId) as any;
      setDatasets(res.datasets || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadCatalog(query);
  };

  const handleFavorite = async (dataset: any, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await toggleFavorite('dataset', dataset.dataset_id, undefined, dataset.favorite);
      setDatasets(prev => prev.map(d => d.dataset_id === dataset.dataset_id ? { ...d, favorite: !d.favorite } : d));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '32px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, margin: '0 0 8px 0' }}>Dataset Catalog</h1>
          <p style={{ color: '#6f7d86', margin: 0 }}>Discover, search, and manage datasets across your workspaces.</p>
        </div>
      </div>

      <div style={{ marginBottom: '24px', display: 'flex', gap: '16px' }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '8px', flex: 1 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={18} style={{ position: 'absolute', left: '12px', top: '10px', color: '#888' }} />
            <input 
              type="text" 
              value={query} 
              onChange={e => setQuery(e.target.value)}
              placeholder="Search dataset catalog..." 
              style={{ width: '100%', padding: '10px 10px 10px 40px', borderRadius: '8px', border: '1px solid #ccc', fontSize: '15px' }}
            />
          </div>
          <button type="submit" className="button primary">Search</button>
        </form>
        <button className="button ghost" style={{ padding: '0 16px' }}>
          <Filter size={16} style={{ marginRight: '8px' }} /> Filters
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '64px 0', color: '#6f7d86' }}>
          <span className="spinner" /> Loading catalog...
        </div>
      ) : datasets.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '64px 0', color: '#6f7d86' }}>
          No datasets found in the catalog.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
          {datasets.map(dataset => (
            <div key={dataset.dataset_id} style={{ padding: '20px', border: '1px solid #eee', borderRadius: '12px', background: '#fff', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Database size={18} color="#102a43" />
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>{dataset.dataset_name}</h3>
                </div>
                <button onClick={(e) => handleFavorite(dataset, e)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: dataset.favorite ? '#f59e0b' : '#ccc' }}>
                  <Star size={18} fill={dataset.favorite ? '#f59e0b' : 'none'} />
                </button>
              </div>
              <p style={{ margin: 0, fontSize: '13px', color: '#6f7d86', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                {dataset.description || dataset.filename}
              </p>
              
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: 'auto' }}>
                {dataset.tags && dataset.tags.map((tag: string) => (
                  <span key={tag} style={{ background: '#f0f4f8', color: '#102a43', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 500 }}>
                    #{tag}
                  </span>
                ))}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#888', borderTop: '1px solid #f0f4f8', paddingTop: '12px', marginTop: '4px' }}>
                <span>{dataset.rows?.toLocaleString()} rows</span>
                <span>v{dataset.version}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
