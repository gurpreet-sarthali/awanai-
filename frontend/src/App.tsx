import { useCallback, useEffect, useRef, useState } from 'react';
import {
  BarChart3,
  Check,
  Copy,
  Database,
  Download,
  Edit2,
  Eye,
  FileSpreadsheet,
  LogOut,
  Menu,
  MessageSquare,
  Moon,
  Paperclip,
  Plus,
  Send,
  Sparkles,
  Sun,
  Table,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import { WelcomeScreen } from './components/WelcomeScreen';
import { UserFeedbackModal } from './components/UserFeedbackModal';
import { useAuth } from './context/AuthContext';
import { useTheme } from './context/ThemeContext';
import { useVisitor } from './context/VisitorContext';
import { DEFAULT_DATASET_ID, useSelectedDataset } from './hooks/useSelectedDataset';
import { apiUrl, assetUrl } from './services/api';
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
  sendMessage,
  type ChatMessage,
  type ConversationDetail,
  type ConversationSummary,
} from './services/chatApi';
import {
  deleteDataset,
  getManagedDataset,
  getManagedPreview,
  getManagedSchema,
  listDatasets,
  uploadDataset,
  type ManagedDatasetColumn,
  type ManagedDatasetSummary,
} from './services/datasetsApi';
import './styles.css';

// ─── SPA Navigation ────────────────────────────────────────────────────────────
function navigate(path: string) {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function usePath() {
  const [path, setPath] = useState(() => window.location.pathname);
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  return path;
}

// ─── Data Preview Modal ───────────────────────────────────────────────────────
function DataPreviewModal({
  datasetId,
  isOpen,
  onClose,
}: {
  datasetId: string;
  isOpen: boolean;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [columns, setColumns] = useState<ManagedDatasetColumn[]>([]);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [datasetName, setDatasetName] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    setError('');

    Promise.all([
      getManagedSchema(datasetId).catch(() => null),
      getManagedPreview(datasetId, 15).catch(() => null),
      getManagedDataset(datasetId).catch(() => null),
    ])
      .then(([schemaRes, previewRes, detailRes]) => {
        if (schemaRes?.columns) setColumns(schemaRes.columns);
        if (previewRes?.rows) setRows(previewRes.rows);
        if (detailRes?.dataset_name) setDatasetName(detailRes.dataset_name);
        else if (schemaRes?.dataset_name) setDatasetName(schemaRes.dataset_name);
        else setDatasetName(datasetId);
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : 'Could not load data preview.');
      })
      .finally(() => setLoading(false));
  }, [isOpen, datasetId]);

  if (!isOpen) return null;

  return (
    <div className="cg-modal-overlay" onClick={onClose}>
      <div className="cg-modal-card" onClick={e => e.stopPropagation()}>
        <div className="cg-modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Database size={18} color="var(--teal)" />
            <h2 className="cg-modal-title">{datasetName || 'Dataset Preview'}</h2>
          </div>
          <button className="cg-item-btn" onClick={onClose} aria-label="Close modal">
            <X size={18} />
          </button>
        </div>
        <div className="cg-modal-body">
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px', gap: '10px' }}>
              <span className="spinner" /> Loading dataset schema and preview…
            </div>
          ) : error ? (
            <div className="auth-error">{error}</div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
                {columns.map(col => (
                  <span
                    key={col.column_name}
                    style={{
                      fontSize: '11px',
                      background: 'var(--paper-muted)',
                      border: '1px solid var(--line)',
                      padding: '4px 8px',
                      borderRadius: '6px',
                      fontFamily: 'DM Mono, monospace',
                    }}
                  >
                    <strong>{col.column_name}</strong> <span style={{ opacity: 0.65 }}>({col.data_type})</span>
                  </span>
                ))}
              </div>

              {rows.length > 0 ? (
                <div style={{ overflowX: 'auto', border: '1px solid var(--line)', borderRadius: '8px' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead>
                      <tr>
                        {Object.keys(rows[0]).map(k => (
                          <th key={k} style={{ padding: '8px 12px', background: 'var(--paper-muted)', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>
                            {k}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => (
                        <tr key={i}>
                          {Object.keys(rows[0]).map(k => (
                            <td key={k} style={{ padding: '8px 12px', borderBottom: '1px solid var(--line)', color: 'var(--ink)' }}>
                              {String(row[k] ?? '—')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p style={{ color: 'var(--muted)', fontSize: '13px' }}>No rows to preview.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}


// --- Smart Metrics Renderer ---------------------------------------------------
function MetricsRenderer({ metrics }: { metrics: unknown }) {
  if (metrics == null) return null;

  // Data Quality Report
  if (typeof metrics === 'object' && !Array.isArray(metrics) && 'quality_score' in (metrics as Record<string, unknown>)) {
    const m = metrics as Record<string, unknown>;
    const breakdown = m.breakdown as Record<string, number> | undefined;
    const cols = m.columns_with_missing as Array<{ column: string; missing: number; pct: number }> | undefined;
    const score = m.quality_score as number;
    const scoreColor = score >= 80 ? '#22c55e' : score >= 60 ? '#f59e0b' : '#ef4444';
    return (
      <div style={{ marginTop: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px', padding: '14px', background: 'var(--paper-muted)', borderRadius: '10px', border: '1px solid var(--line)' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '36px', fontWeight: 800, color: scoreColor }}>{score}</div>
            <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>Quality Score / 100</div>
          </div>
          <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {breakdown && Object.entries(breakdown).map(([k, v]) => (
              <div key={k} style={{ padding: '6px 10px', background: 'var(--bg)', borderRadius: '6px', border: '1px solid var(--line)' }}>
                <div style={{ fontSize: '10px', color: 'var(--muted)', textTransform: 'uppercase' }}>{k}</div>
                <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--ink)' }}>{v}%</div>
              </div>
            ))}
          </div>
        </div>
        <div className="cg-metrics-wrap">
          {(['total_rows', 'total_columns', 'total_missing_cells', 'missing_percentage', 'duplicate_rows'] as const).map(k => {
            const val = (m as Record<string, unknown>)[k];
            if (val == null) return null;
            return (
              <div key={k} className="cg-metric-chip">
                <span className="cg-metric-name">{k.replace(/_/g, ' ')}</span>
                <span className="cg-metric-val">{typeof val === 'number' ? (k.includes('percentage') ? `${val}%` : val.toLocaleString()) : String(val)}</span>
              </div>
            );
          })}
        </div>
        {cols && cols.length > 0 && (
          <div style={{ marginTop: '10px' }}>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)', marginBottom: '6px' }}>Columns with Missing Data</div>
            <div style={{ overflowX: 'auto', border: '1px solid var(--line)', borderRadius: '8px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead><tr>
                  {['Column', 'Missing', '%'].map(h => <th key={h} style={{ padding: '6px 10px', background: 'var(--paper-muted)', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>{h}</th>)}
                </tr></thead>
                <tbody>{cols.map((c, i) => (
                  <tr key={i}>
                    <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', fontFamily: 'DM Mono, monospace' }}>{c.column}</td>
                    <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)' }}>{c.missing}</td>
                    <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', color: c.pct > 30 ? '#ef4444' : c.pct > 10 ? '#f59e0b' : 'inherit' }}>{c.pct}%</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Imputation Plan
  if (typeof metrics === 'object' && !Array.isArray(metrics) && 'imputation_plan' in (metrics as Record<string, unknown>)) {
    const m = metrics as Record<string, unknown>;
    const plan = m.imputation_plan as Array<{ column: string; missing_count: number; missing_pct: number; recommended_strategy: string; suggested_fill?: unknown }>;
    return (
      <div style={{ marginTop: '12px' }}>
        <div className="cg-metrics-wrap">
          {(['total_missing_cells', 'columns_analyzed', 'columns_with_missing'] as const).map(k => {
            const val = (m as Record<string, unknown>)[k];
            return val != null ? (
              <div key={k} className="cg-metric-chip">
                <span className="cg-metric-name">{k.replace(/_/g, ' ')}</span>
                <span className="cg-metric-val">{String(val)}</span>
              </div>
            ) : null;
          })}
        </div>
        {plan?.length > 0 && (
          <div style={{ marginTop: '10px', overflowX: 'auto', border: '1px solid var(--line)', borderRadius: '8px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead><tr>
                {['Column', 'Missing', '%', 'Strategy', 'Fill Value'].map(h => <th key={h} style={{ padding: '6px 10px', background: 'var(--paper-muted)', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>{h}</th>)}
              </tr></thead>
              <tbody>{plan.map((p, i) => (
                <tr key={i}>
                  <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', fontFamily: 'DM Mono, monospace' }}>{p.column}</td>
                  <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)' }}>{p.missing_count}</td>
                  <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', color: p.missing_pct > 30 ? '#ef4444' : p.missing_pct > 10 ? '#f59e0b' : 'inherit' }}>{p.missing_pct}%</td>
                  <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)' }}>{p.recommended_strategy}</td>
                  <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', fontFamily: 'DM Mono, monospace', fontSize: '11px' }}>{p.suggested_fill ? JSON.stringify(p.suggested_fill) : '---'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>
    );
  }

  // Correlation results (all pairs)
  if (typeof metrics === 'object' && !Array.isArray(metrics) && 'correlation_pairs' in (metrics as Record<string, unknown>)) {
    const m = metrics as Record<string, unknown>;
    const pairs = m.correlation_pairs as Array<{ col1: string; col2: string; correlation: number }>;
    return (
      <div style={{ marginTop: '12px', overflowX: 'auto', border: '1px solid var(--line)', borderRadius: '8px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
          <thead><tr>
            {['Column 1', 'Column 2', 'Correlation'].map(h => <th key={h} style={{ padding: '6px 10px', background: 'var(--paper-muted)', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>{h}</th>)}
          </tr></thead>
          <tbody>{(pairs || []).slice(0, 15).map((p, i) => {
            const corColor = p.correlation > 0.5 ? '#22c55e' : p.correlation < -0.5 ? '#ef4444' : 'var(--ink)';
            return (
              <tr key={i}>
                <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', fontFamily: 'DM Mono, monospace' }}>{p.col1}</td>
                <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', fontFamily: 'DM Mono, monospace' }}>{p.col2}</td>
                <td style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)', color: corColor, fontWeight: 600 }}>{p.correlation}</td>
              </tr>
            );
          })}</tbody>
        </table>
      </div>
    );
  }

  // Single-column correlation
  if (typeof metrics === 'object' && !Array.isArray(metrics) && 'correlations' in (metrics as Record<string, unknown>)) {
    const m = metrics as Record<string, unknown>;
    const corrs = m.correlations as Array<{ column: string; correlation: number }>;
    return (
      <div style={{ marginTop: '12px' }}>
        <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)', marginBottom: '6px' }}>Correlations with: <code>{String(m.target_column)}</code></div>
        <div className="cg-metrics-wrap">
          {(corrs || []).slice(0, 10).map((c, i) => {
            const corColor = c.correlation > 0.5 ? '#22c55e' : c.correlation < -0.5 ? '#ef4444' : 'var(--ink)';
            return (
              <div key={i} className="cg-metric-chip">
                <span className="cg-metric-name">{c.column}</span>
                <span className="cg-metric-val" style={{ color: corColor }}>{c.correlation}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Array of objects => table
  if (Array.isArray(metrics) && metrics.length > 0 && typeof metrics[0] === 'object' && metrics[0] !== null) {
    const keys = Object.keys(metrics[0] as object);
    return (
      <div style={{ marginTop: '12px', overflowX: 'auto', border: '1px solid var(--line)', borderRadius: '8px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
          <thead><tr>{keys.map(k => <th key={k} style={{ padding: '6px 10px', background: 'var(--paper-muted)', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>{k.replace(/_/g, ' ')}</th>)}</tr></thead>
          <tbody>{(metrics as Record<string, unknown>[]).slice(0, 30).map((row, i) => (
            <tr key={i}>{keys.map(k => <td key={k} style={{ padding: '6px 10px', borderBottom: '1px solid var(--line)' }}>{typeof row[k] === 'number' ? (row[k] as number).toLocaleString(undefined, { maximumFractionDigits: 3 }) : String(row[k] ?? '---')}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
    );
  }

  // Flat object => chips (skip nested)
  if (typeof metrics === 'object' && !Array.isArray(metrics)) {
    const flat = Object.entries(metrics as Record<string, unknown>).filter(([, v]) => typeof v !== 'object' || v === null);
    if (flat.length > 0) {
      return (
        <div className="cg-metrics-wrap" style={{ marginTop: '10px' }}>
          {flat.map(([k, v]) => (
            <div key={k} className="cg-metric-chip">
              <span className="cg-metric-name">{k.replace(/_/g, ' ')}</span>
              <span className="cg-metric-val">{typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 3 }) : String(v ?? '---')}</span>
            </div>
          ))}
        </div>
      );
    }
  }

  // Scalar value
  return (
    <div className="cg-metrics-wrap" style={{ marginTop: '10px' }}>
      <div className="cg-metric-chip">
        <span className="cg-metric-name">Result</span>
        <span className="cg-metric-val">{typeof metrics === 'number' ? (metrics as number).toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(metrics)}</span>
      </div>
    </div>
  );
}

// ─── Assistant Message Component ──────────────────────────────────────────────
function AssistantBubble({ msg }: { msg: ChatMessage }) {
  const [copied, setCopied] = useState(false);
  const meta = msg.result_metadata;

  const handleCopy = () => {
    navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="cg-msg-row assistant">
      <div className="cg-msg-avatar">A</div>
      <div className="cg-msg-body">
        <div className="cg-msg-bubble">
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.65 }}>{msg.content}</div>

          {/* Generated Chart */}
          {meta?.chart?.file_url && (
            <div className="cg-chart-card">
              <img className="cg-chart-img" src={assetUrl(meta.chart.file_url)} alt={meta.chart.title || 'Data Chart'} />
              <div className="cg-chart-footer">
                <span>{meta.chart.title || 'Chart Visualization'}</span>
                <a
                  className="cg-chart-download-btn"
                  href={assetUrl(meta.chart.file_url)}
                  download="awanai_chart.png"
                  target="_blank"
                  rel="noreferrer"
                >
                  <Download size={13} /> Download
                </a>
              </div>
            </div>
          )}

                    {/* Smart Metrics */}
          {meta?.metrics != null && <MetricsRenderer metrics={meta.metrics} />}

          {/* Key Insights */}
          {Array.isArray(meta?.insights) && meta.insights.length > 0 && (
            <div className="cg-insights-box">
              <div className="cg-insights-title">Key Insights</div>
              <ul>
                {meta.insights.map((ins, i) => (
                  <li key={i}>{ins}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          {Array.isArray(meta?.recommendations) && meta.recommendations.length > 0 && (
            <div className="cg-insights-box" style={{ background: 'rgba(234, 88, 12, 0.05)', borderColor: 'rgba(234, 88, 12, 0.16)' }}>
              <div className="cg-insights-title" style={{ color: 'var(--coral)' }}>Recommendations</div>
              <ul>
                {meta.recommendations.map((rec, i) => (
                  <li key={i}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0 4px' }}>
          <span className="cg-msg-time">
            {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
          <button
            onClick={handleCopy}
            className="cg-item-btn"
            style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '3px' }}
            title="Copy response"
          >
            {copied ? <Check size={12} color="var(--teal)" /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Unified ChatGPT Data Analytics App ───────────────────────────────────────
function ChatGPTApp() {
  const { datasetId, setDatasetId } = useSelectedDataset();
  const { user, logout, token } = useAuth();
  const { visitor, clearVisitor } = useVisitor();
  const { theme, toggleTheme } = useTheme();

  // Conversations State
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConv, setActiveConv] = useState<ConversationDetail | null>(null);
  const [loadingConvs, setLoadingConvs] = useState(true);
  const [loadingMsgs, setLoadingMsgs] = useState(false);

  // Chat Input State
  const [question, setQuestion] = useState(() => sessionStorage.getItem('awanai.draftQuestion') || '');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState('');

  // Datasets State
  const [datasets, setDatasets] = useState<ManagedDatasetSummary[]>([]);
  const [uploadingDataset, setUploadingDataset] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const [previewOpen, setPreviewOpen] = useState(false);

  // Sidebar / UI State
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameVal, setRenameVal] = useState('');

  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Refresh datasets list
  const refreshDatasets = useCallback(() => {
    listDatasets()
      .then(items => setDatasets(items.filter(item => item.status !== 'DELETED')))
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshDatasets();
  }, [refreshDatasets, datasetId]);

  // Load conversations on mount
  const loadConversations = useCallback(async () => {
    setLoadingConvs(true);
    try {
      const list = await listConversations();
      setConversations(list);

      const targetId = sessionStorage.getItem('askmydata.openConvId') || sessionStorage.getItem('awanai.lastActiveConvId');
      if (targetId) {
        sessionStorage.removeItem('askmydata.openConvId');
        const detail = await getConversation(targetId).catch(() => null);
        if (detail) {
          setActiveConv(detail);
        }
      }
    } catch {
      /* ignore */
    } finally {
      setLoadingConvs(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConv?.messages, sending]);

  // Open Conversation
  const openConversation = async (id: string) => {
    sessionStorage.setItem('awanai.lastActiveConvId', id);
    setLoadingMsgs(true);
    setSendError('');
    setSidebarOpen(false);
    try {
      const detail = await getConversation(id);
      setActiveConv(detail);
      if (detail.dataset_id && detail.dataset_id !== datasetId) {
        setDatasetId(detail.dataset_id);
      }
    } catch {
      setSendError('Could not load conversation.');
    } finally {
      setLoadingMsgs(false);
    }
  };

  // Start New Chat
  const handleNewChat = async () => {
    try {
      const conv = await createConversation(datasetId);
      sessionStorage.setItem('awanai.lastActiveConvId', conv.id);
      setConversations(prev => [conv, ...prev]);
      setActiveConv({ ...conv, messages: [] });
      setSendError('');
      setSidebarOpen(false);
    } catch {
      setSendError('Could not create new chat.');
    }
  };

  // Send Message
  const handleSend = async (customQuery?: string) => {
    const text = (customQuery || question).trim();
    if (!text || sending) return;

    setSending(true);
    setSendError('');
    if (!customQuery) {
      setQuestion('');
      sessionStorage.removeItem('awanai.draftQuestion');
    }

    let targetConv = activeConv;
    if (!targetConv) {
      try {
        const created = await createConversation(datasetId);
        targetConv = { ...created, messages: [] };
        setActiveConv(targetConv);
        setConversations(prev => [created, ...prev]);
        sessionStorage.setItem('awanai.lastActiveConvId', created.id);
      } catch {
        setSendError('Failed to initialize conversation.');
        setSending(false);
        return;
      }
    }

    // Optimistic user message bubble
    const tempUserMsg: ChatMessage = {
      id: `tmp-${Date.now()}`,
      conversation_id: targetConv.id,
      role: 'user',
      message_type: 'question',
      content: text,
      dataset_id: datasetId,
      created_at: new Date().toISOString(),
      result_metadata: null,
    };

    setActiveConv(prev => (prev ? { ...prev, messages: [...prev.messages, tempUserMsg] } : prev));

    try {
      await sendMessage(targetConv.id, text, datasetId);
      // Reload updated messages + conversation title
      const updated = await getConversation(targetConv.id);
      setActiveConv(updated);
      setConversations(prev =>
        prev
          .map(c => (c.id === updated.id ? { ...c, title: updated.title, updated_at: updated.updated_at } : c))
          .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      );
    } catch (err) {
      setSendError(err instanceof Error ? err.message : 'Could not analyze question.');
      setActiveConv(prev => (prev ? { ...prev, messages: prev.messages.filter(m => m.id !== tempUserMsg.id) } : prev));
    } finally {
      setSending(false);
    }
  };

  // Upload Dataset Handler
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingDataset(true);
    setUploadMsg(`Uploading ${file.name}…`);
    try {
      const res = await uploadDataset(file);
      setUploadMsg(`✓ Uploaded ${res.dataset_name} (${res.rows.toLocaleString()} rows)`);
      refreshDatasets();
      setDatasetId(res.dataset_id);

      // Create new chat associated with this dataset
      const newConv = await createConversation(res.dataset_id);
      sessionStorage.setItem('awanai.lastActiveConvId', newConv.id);
      setConversations(prev => [newConv, ...prev]);
      setActiveConv({ ...newConv, messages: [] });
      setTimeout(() => setUploadMsg(''), 4000);
    } catch (err) {
      setUploadMsg(`Upload failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setTimeout(() => setUploadMsg(''), 5000);
    } finally {
      setUploadingDataset(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Delete conversation
  const handleDeleteConv = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      setConversations(prev => prev.filter(c => c.id !== id));
      if (activeConv?.id === id) {
        setActiveConv(null);
        sessionStorage.removeItem('awanai.lastActiveConvId');
      }
    } catch {
      /* ignore */
    }
  };

  // Rename conversation
  const commitRename = async (id: string) => {
    const title = renameVal.trim();
    setRenamingId(null);
    if (!title) return;
    try {
      const updated = await renameConversation(id, title);
      setConversations(prev => prev.map(c => (c.id === id ? { ...c, title: updated.title } : c)));
      if (activeConv?.id === id) setActiveConv(prev => (prev ? { ...prev, title: updated.title } : prev));
    } catch {
      /* ignore */
    }
  };

  // Logout handler
  const handleLogout = async () => {
    if (user) {
      await logout();
      window.location.href = '/login';
    } else {
      clearVisitor();
      window.location.replace('/');
    }
  };

  const displayName = user?.name || visitor?.name || 'Guest User';
  const displayEmail = user?.email || visitor?.email || '';
  const currentDatasetMeta = datasets.find(d => d.dataset_id === datasetId);
  const activeDatasetName = currentDatasetMeta?.dataset_name || (datasetId === DEFAULT_DATASET_ID ? 'Demo Placement Dataset' : datasetId);

  // Suggested Prompts
  const suggestedPrompts = [
    { title: 'What is the average CGPA?', icon: BarChart3 },
    { title: 'Plot a chart of placements by internship', icon: Sparkles },
    { title: 'Which factors have highest impact on placement?', icon: Database },
    { title: 'Compare placement rate by communication score', icon: Table },
  ];

  return (
    <div className="cg-shell">
      {/* ── Hidden File Input for Dataset Upload ── */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx,.tsv"
        style={{ display: 'none' }}
        onChange={handleFileUpload}
      />

      {/* ── ChatGPT Sidebar ── */}
      <aside className={`cg-sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="cg-sidebar-header">
          <div className="cg-brand">
            <div className="cg-brand-logo">
              <span className="brand-mark" style={{ width: 26, height: 26, fontSize: 14 }}>A</span>
              <span>AwanAI</span>
            </div>
            <span className="cg-brand-badge">Data AI</span>
          </div>

          <button id="cg-new-chat-btn" className="cg-new-chat-btn" onClick={handleNewChat}>
            <Plus size={16} /> New Chat
          </button>
        </div>

        {/* Dataset Controls in Sidebar */}
        <div className="cg-dataset-section">
          <div className="cg-dataset-header">
            <span className="cg-dataset-label">Active Dataset</span>
            {currentDatasetMeta && (
              <span style={{ fontSize: '10px', color: '#38bdf8' }}>
                {currentDatasetMeta.row_count.toLocaleString()} rows
              </span>
            )}
          </div>

          <select
            className="cg-dataset-select"
            value={datasetId}
            onChange={e => setDatasetId(e.target.value)}
          >
            {datasets.length === 0 && <option value={DEFAULT_DATASET_ID}>Demo Placement Dataset</option>}
            {datasets.map(d => (
              <option key={d.dataset_id} value={d.dataset_id}>
                {d.dataset_name} {d.is_builtin ? '(demo)' : ''}
              </option>
            ))}
          </select>

          <div className="cg-upload-row">
            <button
              className="cg-upload-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingDataset}
              title="Upload CSV or Excel dataset"
            >
              {uploadingDataset ? <span className="spinner" style={{ width: 12, height: 12 }} /> : <Upload size={13} />}
              <span>{uploadingDataset ? 'Uploading…' : 'Upload Data'}</span>
            </button>
            <button
              className="cg-preview-btn"
              onClick={() => setPreviewOpen(true)}
              title="View schema and preview rows"
            >
              <Eye size={13} style={{ marginRight: 4 }} /> View
            </button>
          </div>

          {uploadMsg && (
            <div style={{ fontSize: '11px', marginTop: '6px', color: '#38bdf8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {uploadMsg}
            </div>
          )}
        </div>

        {/* Conversations History List */}
        <div className="cg-history-section">
          <span className="cg-history-title">Chat History</span>
          {loadingConvs ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '20px' }}>
              <span className="spinner" />
            </div>
          ) : conversations.length === 0 ? (
            <div style={{ color: 'var(--sidebar-muted)', fontSize: '12px', textAlign: 'center', padding: '20px 8px' }}>
              No chats yet. Click &ldquo;New Chat&rdquo; to start.
            </div>
          ) : (
            <ul className="cg-history-list">
              {conversations.map(conv => (
                <li
                  key={conv.id}
                  className={`cg-history-item ${activeConv?.id === conv.id ? 'active' : ''}`}
                  onClick={() => openConversation(conv.id)}
                >
                  <MessageSquare size={14} style={{ flexShrink: 0, opacity: 0.7 }} />
                  {renamingId === conv.id ? (
                    <input
                      style={{
                        background: '#1e293b',
                        border: '1px solid var(--teal)',
                        borderRadius: '4px',
                        color: '#fff',
                        fontSize: '12px',
                        padding: '2px 4px',
                        width: '100%',
                        outline: 'none',
                      }}
                      value={renameVal}
                      onChange={e => setRenameVal(e.target.value)}
                      onBlur={() => commitRename(conv.id)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') commitRename(conv.id);
                        if (e.key === 'Escape') setRenamingId(null);
                      }}
                      autoFocus
                      onClick={e => e.stopPropagation()}
                    />
                  ) : (
                    <span
                      className="cg-history-item-title"
                      onDoubleClick={e => {
                        e.stopPropagation();
                        setRenamingId(conv.id);
                        setRenameVal(conv.title);
                      }}
                    >
                      {conv.title}
                    </span>
                  )}

                  <div className="cg-history-actions">
                    <button
                      className="cg-item-btn"
                      onClick={e => {
                        e.stopPropagation();
                        setRenamingId(conv.id);
                        setRenameVal(conv.title);
                      }}
                      title="Rename"
                    >
                      <Edit2 size={12} />
                    </button>
                    <button
                      className="cg-item-btn delete"
                      onClick={e => handleDeleteConv(conv.id, e)}
                      title="Delete"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* User Profile & Theme at bottom */}
        <div className="cg-sidebar-footer">
          <div className="cg-user-pill">
            <div className="cg-user-avatar">
              {displayName.slice(0, 2).toUpperCase()}
            </div>
            <div className="cg-user-meta">
              <span className="cg-user-name">{displayName}</span>
              {displayEmail && <span className="cg-user-email">{displayEmail}</span>}
            </div>
          </div>
          <div className="cg-footer-actions">
            <button
              className="cg-icon-btn"
              onClick={toggleTheme}
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            </button>
            <button
              className="cg-icon-btn"
              onClick={handleLogout}
              title="Logout / Exit"
              aria-label="Logout"
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main Chat Screen ── */}
      <main className="cg-main">
        {/* Topbar */}
        <header className="cg-topbar">
          <div className="cg-topbar-left">
            <button className="cg-mobile-toggle" onClick={() => setSidebarOpen(prev => !prev)}>
              <Menu size={16} />
            </button>
            <button
              className="cg-dataset-chip"
              onClick={() => setPreviewOpen(true)}
              title="Click to view columns and sample data"
            >
              <Database size={13} color="var(--teal)" />
              <span>{activeDatasetName}</span>
              <Eye size={12} style={{ opacity: 0.6 }} />
            </button>
          </div>

          <div className="cg-topbar-right">
            <button
              className="button ghost"
              style={{ padding: '6px 12px', fontSize: '12px', borderRadius: '8px' }}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={13} style={{ marginRight: '4px' }} /> Upload Dataset
            </button>
            <button
              className="button ghost"
              style={{ padding: '6px 10px', fontSize: '12px', borderRadius: '8px' }}
              onClick={() => setFeedbackOpen(true)}
              title="Send feedback"
            >
              <MessageSquare size={13} />
            </button>
          </div>
        </header>

        {/* Message Thread Area */}
        <div className="cg-messages-container">
          <div className="cg-messages-inner">
            {loadingMsgs ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '60px', gap: '10px' }}>
                <span className="spinner" /> Loading conversation…
              </div>
            ) : !activeConv || activeConv.messages.length === 0 ? (
              /* ChatGPT Welcoming Empty State */
              <div className="cg-empty-hero">
                <div className="cg-empty-brand-icon">
                  <Sparkles size={28} />
                </div>
                <div>
                  <h1 className="cg-empty-title">What would you like to analyze today?</h1>
                  <p className="cg-empty-desc">
                    Ask questions in plain English. AwanAI generates verified statistics, AI explanations, and visualizations directly from your data.
                  </p>
                </div>

                {/* Direct Upload Dropzone Card */}
                <div
                  className="cg-dropzone-card"
                  onClick={() => fileInputRef.current?.click()}
                  title="Click to upload CSV or Excel"
                >
                  <FileSpreadsheet size={28} color="var(--teal)" />
                  <span className="cg-dropzone-title">
                    {uploadingDataset ? 'Uploading and validating dataset…' : 'Upload your own CSV / Excel dataset'}
                  </span>
                  <span className="cg-dropzone-subtitle">
                    or ask anything about current dataset ({activeDatasetName})
                  </span>
                </div>

                {/* Suggested Prompts Grid */}
                <div className="cg-prompts-grid">
                  {suggestedPrompts.map(prompt => (
                    <div
                      key={prompt.title}
                      className="cg-prompt-card"
                      onClick={() => handleSend(prompt.title)}
                    >
                      <prompt.icon size={16} className="cg-prompt-icon" />
                      <span>{prompt.title}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              /* Message Stream */
              activeConv.messages.map(msg =>
                msg.role === 'user' ? (
                  <div key={msg.id} className="cg-msg-row user">
                    <div className="cg-msg-body">
                      <div className="cg-msg-bubble">{msg.content}</div>
                      <span className="cg-msg-time">
                        {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className="cg-msg-avatar">
                      {displayName.slice(0, 1).toUpperCase()}
                    </div>
                  </div>
                ) : (
                  <AssistantBubble key={msg.id} msg={msg} />
                )
              )
            )}

            {/* Thinking / Typing Indicator */}
            {sending && (
              <div className="cg-msg-row assistant">
                <div className="cg-msg-avatar">A</div>
                <div className="cg-msg-body">
                  <div className="cg-msg-bubble" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="spinner" style={{ width: 14, height: 14 }} />
                    <span style={{ fontSize: '13px', color: 'var(--muted)' }}>
                      Analyzing dataset with Gemini & calculating verified numbers…
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Error banner if send failed */}
            {sendError && (
              <div className="inline-error" style={{ borderRadius: '10px', padding: '12px 16px' }}>
                {sendError}
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </div>

        {/* ── ChatGPT Floating Composer (Bottom) ── */}
        <div className="cg-composer-wrap">
          <div className="cg-composer-box">
            <button
              className="cg-attach-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingDataset || sending}
              title="Attach / Upload dataset"
              aria-label="Upload dataset"
            >
              <Paperclip size={18} />
            </button>

            <input
              id="cg-prompt-input"
              className="cg-input"
              value={question}
              onChange={e => {
                setQuestion(e.target.value);
                sessionStorage.setItem('awanai.draftQuestion', e.target.value);
              }}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={`Ask anything about ${activeDatasetName}… (e.g. plot profit graph, show average CGPA)`}
              disabled={sending}
              autoFocus
            />

            <button
              id="cg-send-btn"
              className="cg-send-btn"
              onClick={() => handleSend()}
              disabled={!question.trim() || sending}
              title="Send question"
              aria-label="Send message"
            >
              <Send size={16} />
            </button>
          </div>
          <p className="cg-composer-disclaimer">
            AwanAI executes verified SQL and statistical calculations directly from your dataset.
          </p>
        </div>
      </main>

      {/* ── Modals ── */}
      <DataPreviewModal
        datasetId={datasetId}
        isOpen={previewOpen}
        onClose={() => setPreviewOpen(false)}
      />
      <UserFeedbackModal
        isOpen={feedbackOpen}
        token={token}
        onClose={() => setFeedbackOpen(false)}
      />
    </div>
  );
}

// ─── LoginPage (for direct admin/credential logins) ───────────────────────────
function LoginPage() {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(email, password);
      navigate('/');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Login failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) return <div className="auth-loading"><span className="spinner" /></div>;

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand"><span className="brand-mark">A</span><span className="auth-brand-name">AwanAI</span></div>
        <h1 className="auth-title">Admin Sign In</h1>
        <p className="auth-subtitle">Sign in with your admin credentials</p>
        {error && <div className="auth-error" role="alert">{error}</div>}
        <form id="login-form" className="auth-form" onSubmit={submit}>
          <div className="auth-field">
            <label htmlFor="login-email">Email address</label>
            <input id="login-email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required autoComplete="email" autoFocus />
          </div>
          <div className="auth-field">
            <label htmlFor="login-password">Password</label>
            <input id="login-password" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Your password" required autoComplete="current-password" />
          </div>
          <button id="login-submit" type="submit" className="button primary auth-submit" disabled={busy || !email || !password}>
            {busy ? <><span className="spinner" />Signing in…</> : 'Sign in'}
          </button>
        </form>
        <p className="auth-footer"><a href="/" onClick={e => { e.preventDefault(); navigate('/'); }}>← Back to AwanAI</a></p>
      </div>
    </div>
  );
}

// ─── RegisterPage ─────────────────────────────────────────────────────────────
function RegisterPage() {
  const { register, isLoading } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setError('Passwords do not match.'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    setBusy(true);
    setError('');
    try {
      await register(email, name, password);
      navigate('/');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Registration failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) return <div className="auth-loading"><span className="spinner" /></div>;

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand"><span className="brand-mark">A</span><span className="auth-brand-name">AwanAI</span></div>
        <h1 className="auth-title">Create admin account</h1>
        <p className="auth-subtitle">Start analysing your data in minutes</p>
        {error && <div className="auth-error" role="alert">{error}</div>}
        <form id="register-form" className="auth-form" onSubmit={submit}>
          <div className="auth-field">
            <label htmlFor="reg-name">Full name</label>
            <input id="reg-name" type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Jane Smith" required autoComplete="name" autoFocus />
          </div>
          <div className="auth-field">
            <label htmlFor="reg-email">Email address</label>
            <input id="reg-email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required autoComplete="email" />
          </div>
          <div className="auth-field">
            <label htmlFor="reg-password">Password <span className="auth-hint">(min 8 chars)</span></label>
            <input id="reg-password" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Choose a strong password" required autoComplete="new-password" />
          </div>
          <div className="auth-field">
            <label htmlFor="reg-confirm">Confirm password</label>
            <input id="reg-confirm" type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="Repeat your password" required autoComplete="new-password" />
          </div>
          <button id="register-submit" type="submit" className="button primary auth-submit" disabled={busy || !name || !email || !password || !confirm}>
            {busy ? <><span className="spinner" />Creating account…</> : 'Create account'}
          </button>
        </form>
        <p className="auth-footer">Already have an account? <a href="/login" onClick={e => { e.preventDefault(); navigate('/login'); }}>Sign in →</a></p>
      </div>
    </div>
  );
}

// ─── Google OAuth Callback Handler ────────────────────────────────────────────
function GoogleCallbackPage() {
  const { loginWithToken } = useAuth();
  const [status, setStatus] = useState<'loading' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    const expectedState = sessionStorage.getItem('google_oauth_state');
    const oauthError = params.get('error');
    if (oauthError) {
      sessionStorage.removeItem('google_oauth_state');
      setErrorMsg('Google sign-in was cancelled or denied.');
      setStatus('error');
      return;
    }
    if (!code || !state || !expectedState || state !== expectedState) {
      sessionStorage.removeItem('google_oauth_state');
      setErrorMsg('Google sign-in could not be verified. Please try again.');
      setStatus('error');
      return;
    }
    sessionStorage.removeItem('google_oauth_state');
    fetch(apiUrl('/api/v1/auth/google/callback'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, state }),
    })
      .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail?.message || 'Google login failed.');
        loginWithToken(data.access_token, data.user);
        window.location.replace('/');
      })
      .catch(err => {
        setErrorMsg(err.message || 'Google login failed. Please try again.');
        setStatus('error');
      });
  }, [loginWithToken]);

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand"><span className="brand-mark">A</span><span className="auth-brand-name">AwanAI</span></div>
        {status === 'loading' ? (
          <>
            <h1 className="auth-title">Signing you in…</h1>
            <p className="auth-subtitle">Completing Google authentication</p>
            <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}><span className="spinner" /></div>
          </>
        ) : (
          <>
            <h1 className="auth-title">Sign-in failed</h1>
            <div className="auth-error" role="alert">{errorMsg}</div>
            <p className="auth-footer"><a href="/login" onClick={e => { e.preventDefault(); navigate('/login'); }}>← Back to login</a></p>
          </>
        )}
      </div>
    </div>
  );
}

// ─── App Router ────────────────────────────────────────────────────────────────
function App() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { visitor, isLoading: visitorLoading } = useVisitor();
  const path = usePath();

  // Admin and Auth Routes
  if (path === '/login') return <LoginPage />;
  if (path === '/register') return <RegisterPage />;
  if (path === '/auth/google/callback') return <GoogleCallbackPage />;

  // Initial session restoration loading state
  if (authLoading || visitorLoading) {
    return <div className="auth-loading"><span className="spinner" /></div>;
  }

  // If no user or visitor session, show the clean onboarding welcome screen
  const hasSession = isAuthenticated || Boolean(visitor);
  if (!hasSession) {
    return <WelcomeScreen />;
  }

  // Single unified ChatGPT Data Analytics interface!
  return <ChatGPTApp />;
}

export default App;
