import { useCallback, useEffect, useRef, useState } from 'react';
import { BarChart3, CalendarClock, Clock, Code, Database, Download, FileText, Gauge, Home, LogOut, MessageSquare, MessageSquareText, Moon, Plus, RefreshCw, Send, Shield, Sun, ThumbsDown, ThumbsUp, Trash2, Upload } from 'lucide-react';
import { DatasetSelector } from './components/DatasetSelector';
import { UserFeedbackModal } from './components/UserFeedbackModal';
import { AdminDashboard } from './components/AdminDashboard';
import { DeveloperDashboard } from './components/DeveloperDashboard';
import { QueryHistory } from './components/QueryHistory';
import { submitAIMessageFeedback } from './services/monitoringApi';
import { useAuth } from './context/AuthContext';
import { useTheme } from './context/ThemeContext';
import { DEFAULT_DATASET_ID, useSelectedDataset } from './hooks/useSelectedDataset';
import { useApi } from './hooks/useApi';
import { getAnalytics, getAnalyticsSummary } from './services/analyticsApi';
import { apiUrl, assetUrl } from './services/api';
import { getBillingPlans, type BillingPlan } from './services/billingApi';
import {
  createAlert,
  createAutomation,
  createSavedQuery,
  downloadRunReport,
  deleteAlert,
  deleteAutomation,
  listAlerts,
  listAutomationRuns,
  listAutomations,
  listSavedQueries,
  runAutomation,
  updateAlert,
  updateAutomation,
  type AnalyticsAlert,
  type AnalyticsAutomation,
  type AutomationRun,
  type SavedAnalyticsQuery,
} from './services/automationApi';
import { apiFetch } from './services/api';
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
import { deleteDataset, getManagedDataset, getManagedPreview, getManagedSchema, uploadDataset } from './services/datasetsApi';
import { generateChart } from './services/visualizationApi';
import type { AnalyticsOperation, ChartMetadata } from './types/api';
import './styles.css';

const nav = [['/', 'Overview', Home], ['/dashboard', 'Dashboard', Gauge], ['/dataset', 'Dataset', Database], ['/analytics', 'Analytics', BarChart3], ['/ask', 'Ask your data', MessageSquareText], ['/history', 'Query History', Clock], ['/automations', 'Automations', CalendarClock], ['/billing', 'Billing', Shield], ['/developer', 'Developer', Code]] as const;
const placementOperations: [AnalyticsOperation, string][] = [
  ['placement_by_internship', 'Internship analysis'],
  ['placement_by_cgpa_group', 'CGPA analysis'],
  ['placement_by_project_group', 'Project analysis'],
  ['placement_by_communication', 'Communication analysis'],
  ['average_metrics_by_placement', 'Average metrics by placement'],
];
const genericOperations: [AnalyticsOperation, string][] = [
  ['overview', 'Dataset overview'],
  ['count', 'Row count'],
  ['average', 'Column average'],
  ['value_counts', 'Value counts'],
];

type PageProps = { datasetId: string; setDatasetId: (value: string) => void };

// ─── User Profile Section ──────────────────────────────────────────────────────
function UserProfileSection() {
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
      window.location.href = '/login';
    } catch {
      window.location.href = '/login';
    }
  };

  if (!user) return null;
  const initials = user.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2);

  return (
    <div className="user-profile">
      <div className="user-avatar">{user.profile_picture_url ? <img src={user.profile_picture_url} alt={user.name} /> : <span>{initials}</span>}</div>
      <div className="user-info">
        <span className="user-name">{user.name}</span>
        <span className="user-email">{user.email}</span>
      </div>
      <button id="logout-btn" className="logout-btn" onClick={handleLogout} disabled={loggingOut} title="Logout">
        <LogOut size={15} />
      </button>
    </div>
  );
}

// ─── Shell Layout ──────────────────────────────────────────────────────────────
function Shell({ children, active, datasetId, setDatasetId }: PageProps & { children: React.ReactNode; active: string }) {
  const { user, token } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">A</span><span>AskMyData</span></div>
        <p className="eyebrow">Multi-dataset analytics</p>
        <DatasetSelector datasetId={datasetId} onChange={setDatasetId} />
        <nav>
          {nav.map(([href, label, Icon]) => (
            <a className={active === href ? 'nav-link active' : 'nav-link'} href={href} key={href}>
              <Icon size={17} /><span>{label}</span>
            </a>
          ))}
          {user?.is_admin && (
            <a className={active === '/admin' ? 'nav-link active' : 'nav-link'} href="/admin" key="/admin">
              <Shield size={17} /><span>Admin Dashboard</span>
            </a>
          )}
        </nav>
        <div className="sidebar-note"><span className="status-dot" />Dataset-scoped requests</div>
        <UserProfileSection />
      </aside>
      <main className="main-content">
        <header className="topbar">
          <span>Workspace / {active === '/' ? 'overview' : active.slice(1)}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              id="theme-toggle-btn"
              className="btn-icon-subtle"
              onClick={toggleTheme}
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              aria-label="Toggle dark mode"
            >
              {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
            </button>
            <button className="btn-secondary" style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }} onClick={() => setFeedbackOpen(true)}>
              <MessageSquare size={14} style={{ marginRight: '0.35rem' }} /> Send Feedback
            </button>
            <span className="phase-tag">Phase 23 · Final Polish</span>
          </div>
        </header>
        {children}
      </main>
      <UserFeedbackModal isOpen={feedbackOpen} token={token} onClose={() => setFeedbackOpen(false)} />
    </div>
  );
}

// ─── Shared Helpers ────────────────────────────────────────────────────────────
function State({ loading, error, children }: { loading: boolean; error: string; children: React.ReactNode }) {
  if (loading) return <div className="state loading"><span className="spinner" />Loading live data…</div>;
  if (error) return <div className="state error"><strong>Could not load this view</strong><span>{error}</span></div>;
  return <>{children}</>;
}

function MetricCard({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return <article className="metric-card"><span className="metric-label">{label}</span><strong>{value}</strong>{hint && <small>{hint}</small>}</article>;
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return <div className="empty">No rows returned.</div>;
  const columns = Object.keys(rows[0]);
  const downloadCsv = () => {
    const cell = (value: unknown) => {
      let text = value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);
      if (/^[\s]*[=+\-@]/.test(text)) text = `'${text}`;
      return `"${text.replace(/"/g, '""')}"`;
    };
    const content = [columns, ...rows.map(row => columns.map(column => row[column]))]
      .map(record => record.map(cell).join(','))
      .join('\r\n');
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'askmydata-results.csv';
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <><div className="table-export-toolbar"><span>{rows.length} result rows</span><button type="button" className="button subtle" onClick={downloadCsv} title="Download results as CSV" aria-label="Download results as CSV"><Download size={15} /></button></div><div className="table-wrap"><table><thead><tr>{columns.map(column => <th key={column}>{column.split('_').join(' ')}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{columns.map(column => <td key={column}>{String(row[column] ?? '—')}</td>)}</tr>)}</tbody></table></div></>;
}

function ResultTable({ result }: { result: unknown }) {
  if (Array.isArray(result)) return <DataTable rows={result.filter(item => typeof item === 'object') as Record<string, unknown>[]} />;
  if (result && typeof result === 'object') return <DataTable rows={Object.entries(result as Record<string, unknown>).map(([metric, value]) => ({ metric, value: typeof value === 'object' ? JSON.stringify(value) : value }))} />;
  return <div className="big-result">{String(result)}</div>;
}

function ChartPanel({ operation, title, datasetId }: { operation: AnalyticsOperation; title: string; datasetId: string }) {
  const [chart, setChart] = useState<ChartMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');
  const makeChart = async () => {
    setLoading(true);
    setError('');
    try {
      setChart(await generateChart('bar', operation, datasetId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Chart generation failed.');
    } finally {
      setLoading(false);
    }
  };
  const downloadChart = async () => {
    if (!chart) return;
    setDownloading(true);
    setError('');
    try {
      const response = await fetch(assetUrl(chart.file_url));
      if (!response.ok) throw new Error('Chart download failed.');
      const blobUrl = URL.createObjectURL(await response.blob());
      const extension = new URL(chart.file_url, window.location.origin).pathname.match(/\.(png|jpe?g|webp|svg)$/i)?.[1] ?? 'png';
      const filename = chart.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'chart';
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = `${filename}.${extension}`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Chart download failed.');
    } finally {
      setDownloading(false);
    }
  };

  const exportPdf = () => {
    if (!chart) return;
    const win = window.open('', '_blank');
    if (!win) return;
    const imgSrc = assetUrl(chart.file_url);
    win.document.write(`<!DOCTYPE html><html><head><title>${chart.title} — AskMyData Report</title><style>body{font-family:sans-serif;margin:32px;color:#102a43}h1{font-size:22px;margin-bottom:4px}p{color:#6f7d86;font-size:13px;margin-bottom:24px}img{max-width:100%;border:1px solid #d9ddd9;border-radius:8px}footer{margin-top:32px;font-size:11px;color:#aaa;border-top:1px solid #eee;padding-top:12px}@media print{body{margin:0}}</style></head><body><h1>${chart.title}</h1><p>Generated by AskMyData · ${new Date().toLocaleString()}</p><img src="${imgSrc}" alt="${chart.title}" /><footer>AskMyData — AI-powered Natural Language Data Analytics Platform</footer><script>window.onload=()=>window.print();<\/script></body></html>`);
    win.document.close();
  };

  return (
    <article className="chart-card">
      <div className="card-heading"><div><span className="overline">Visualization</span><h3>{title}</h3></div><div className="chart-actions">{chart && (<><button type="button" className="button subtle" onClick={exportPdf} aria-label="Export as PDF" title="Export as PDF"><FileText size={15} /></button><button type="button" className="button subtle" onClick={downloadChart} disabled={downloading} aria-label="Download chart" title="Download chart image">{downloading ? <span className="spinner" /> : <Download size={15} />}</button></>)}<button className="button subtle" onClick={makeChart} disabled={loading}>{loading ? 'Generating…' : <><RefreshCw size={15} /> Generate chart</>}</button></div></div>
      {error && <div className="inline-error">{error}</div>}
      {chart ? <img className="chart-image" src={assetUrl(chart.file_url)} alt={chart.title} /> : <div className="chart-placeholder"><BarChart3 size={28} /><span>Generate a backend chart for the selected dataset.</span></div>}
    </article>
  );
}

// ─── Auth Pages ────────────────────────────────────────────────────────────────
function LoginPage() {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [googleUrl, setGoogleUrl] = useState<string | null>(null);

  useEffect(() => {
    // Fetch Google OAuth URL from backend — uses VITE_API_BASE_URL in production
    fetch(apiUrl('/api/v1/auth/google/status'))
      .then(res => res.json())
      .then(data => { if (data.configured && data.authorization_url) setGoogleUrl(data.authorization_url); })
      .catch(() => {});
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(email, password);
      window.location.href = '/dashboard';
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
        <div className="auth-brand"><span className="brand-mark">A</span><span className="auth-brand-name">AskMyData</span></div>
        <h1 className="auth-title">Welcome back</h1>
        <p className="auth-subtitle">Sign in to your workspace</p>
        {error && <div className="auth-error" role="alert">{error}</div>}
        {googleUrl && (
          <>
            <a
              id="google-login-btn"
              href={googleUrl}
              className="button auth-google-submit"
              onClick={() => {
                const state = new URL(googleUrl).searchParams.get('state');
                if (state) sessionStorage.setItem('google_oauth_state', state);
              }}
            >
              <svg width="18" height="18" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
              Continue with Google
            </a>
            <div className="auth-separator"><span>or sign in with email</span></div>
          </>
        )}
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
        <p className="auth-footer">No account yet? <a href="/register">Create one →</a></p>
        <div className="auth-demo-hint">
          <span className="overline">Demo credentials</span>
          <p>Email: <code>goru@rezzai.com</code> · Password: <code>goru5</code></p>
        </div>
      </div>
    </div>
  );
}

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
      window.location.href = '/dashboard';
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
        <div className="auth-brand"><span className="brand-mark">A</span><span className="auth-brand-name">AskMyData</span></div>
        <h1 className="auth-title">Create your account</h1>
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
        <p className="auth-footer">Already have an account? <a href="/login">Sign in →</a></p>
      </div>
    </div>
  );
}

// ─── Protected Route Guard ─────────────────────────────────────────────────────
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="auth-loading"><span className="spinner" /></div>;
  if (!isAuthenticated) {
    window.location.replace('/login');
    return null;
  }
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuth();
  if (isLoading) return <div className="auth-loading"><span className="spinner" /></div>;
  if (!isAuthenticated) { window.location.replace('/login'); return null; }
  if (!user?.is_admin) { window.location.replace('/'); return null; }
  return <>{children}</>;
}

// ─── Page Components ───────────────────────────────────────────────────────────
function PageIntro({ kicker, title, description }: { kicker: string; title: string; description: string }) {
  return <div className="page-intro"><span className="kicker">{kicker}</span><h1>{title}</h1><p>{description}</p></div>;
}

function HomePage(props: PageProps) {
  const { user } = useAuth();
  return (
    <Shell {...props} active="/">
      <section className="hero">
        <div className="hero-copy">
          <span className="kicker">Upload CSVs. Ask scoped questions.</span>
          <h1>Your data.<br /><em>One workspace.</em></h1>
          <p>Welcome back{user ? `, ${user.name.split(' ')[0]}` : ''}. AskMyData validates your CSV datasets, stores them securely under your account, and keeps analytics, charts, and NL-to-SQL scoped to the dataset you select.</p>
          <div className="hero-actions"><a className="button primary" href="/dataset">Upload a dataset <span>→</span></a><a className="button ghost" href="/ask">Ask your data</a></div>
        </div>
      </section>
    </Shell>
  );
}

function DashboardPage({ datasetId, setDatasetId }: PageProps) {
  const state = useApi(() => getAnalyticsSummary(datasetId), [datasetId]);
  const result = (state.data?.result || {}) as Record<string, unknown>;
  const isPlacement = typeof result.placement_rate === 'number';
  return (
    <Shell active="/dashboard" datasetId={datasetId} setDatasetId={setDatasetId}>
      <PageIntro kicker="Workspace overview" title="The signal at a glance" description="Metrics are loaded from the selected dataset only. All requests are scoped to your account." />
      <State {...state}>
        {isPlacement ? (
          <div className="metric-grid">
            {[['Total students', result.total_students], ['Placed students', result.placed_students], ['Not placed', result.not_placed_students], ['Placement rate', `${Number(result.placement_rate).toFixed(2)}%`], ['Average CGPA', Number(result.average_cgpa).toFixed(2)], ['Average IQ', Number(result.average_iq).toFixed(2)], ['Average projects', Number(result.average_projects).toFixed(2)]].map(([label, value]) => (
              <MetricCard key={String(label)} label={String(label)} value={value as string | number} />
            ))}
          </div>
        ) : (
          <div className="metric-grid">
            <MetricCard label="Rows" value={Number(result.row_count || 0)} />
            <MetricCard label="Columns" value={Number(result.column_count || 0)} />
            <MetricCard label="Numeric columns" value={Array.isArray(result.numeric_columns) ? result.numeric_columns.length : 0} />
            <MetricCard label="Categorical columns" value={Array.isArray(result.categorical_columns) ? result.categorical_columns.length : 0} />
          </div>
        )}
        {datasetId === DEFAULT_DATASET_ID && (
          <div className="dashboard-grid">
            <ChartPanel operation="placement_by_internship" title="Placement by internship" datasetId={datasetId} />
            <ChartPanel operation="placement_by_cgpa_group" title="Placement by CGPA group" datasetId={datasetId} />
          </div>
        )}
      </State>
    </Shell>
  );
}

function DatasetPage({ datasetId, setDatasetId }: PageProps) {
  const [uploadName, setUploadName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadWarnings, setUploadWarnings] = useState<string[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const detail = useApi(() => getManagedDataset(datasetId), [datasetId, refreshKey]);
  const schema = useApi(() => getManagedSchema(datasetId), [datasetId, refreshKey]);
  const preview = useApi(() => getManagedPreview(datasetId, 8), [datasetId, refreshKey]);

  const onUpload = async (file: File | null) => {
    if (!file) return;
    setUploading(true);
    setUploadError('');
    setUploadWarnings([]);
    try {
      const result = await uploadDataset(file, uploadName);
      setDatasetId(result.dataset_id);
      setUploadWarnings(result.warnings);
      setRefreshKey(value => value + 1);
    } catch (reason) {
      setUploadError(reason instanceof Error ? reason.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const onDelete = async () => {
    if (datasetId === DEFAULT_DATASET_ID) return;
    await deleteDataset(datasetId);
    setDatasetId(DEFAULT_DATASET_ID);
    setRefreshKey(value => value + 1);
  };

  return (
    <Shell active="/dataset" datasetId={datasetId} setDatasetId={setDatasetId}>
      <PageIntro kicker="My Datasets" title="Upload, inspect, and validate" description="CSV uploads are validated, cleaned, imported into isolated MySQL tables, and registered to your account." />
      <section className="panel ask-panel">
        <label htmlFor="dataset-upload">Upload CSV</label>
        <div className="ask-row">
          <input id="dataset-name" value={uploadName} onChange={event => setUploadName(event.target.value)} placeholder="Optional display name" />
          <input id="dataset-upload" type="file" accept=".csv,text/csv" onChange={event => onUpload(event.target.files?.[0] || null)} disabled={uploading} />
          <button className="button primary" disabled={uploading}><Upload size={15} /> {uploading ? 'Uploading…' : 'Choose file'}</button>
        </div>
        {uploadError && <div className="inline-error">{uploadError}</div>}
        {uploadWarnings.length > 0 && <ul>{uploadWarnings.map(warning => <li key={warning}>{warning}</li>)}</ul>}
      </section>
      <State {...detail}>
        {detail.data && (
          <div className="dataset-banner">
            <div><span className="overline">{detail.data.is_builtin ? 'Demo dataset' : 'Your dataset'}</span><h2>{detail.data.dataset_name}</h2><small>{detail.data.filename} · {detail.data.status}</small></div>
            <div className="dataset-stats"><span><b>{detail.data.rows.toLocaleString()}</b> rows</span><span><b>{detail.data.columns}</b> columns</span></div>
            {!detail.data.is_builtin && detail.data.status === 'READY' && <button className="button ghost" onClick={onDelete}><Trash2 size={15} /> Delete dataset</button>}
          </div>
        )}
      </State>
      <div className="content-grid">
        <section className="panel">
          <div className="card-heading"><div><span className="overline">Schema</span><h3>Column metadata</h3></div><a className="text-link" href="/analytics">Analyze dataset →</a></div>
          <State {...schema}>{schema.data && <DataTable rows={schema.data.columns.map(column => ({ Column: column.column_name, Original: column.original_column_name, Type: column.data_type, Nullable: column.nullable ? 'Yes' : 'No' }))} />}</State>
        </section>
        <section className="panel">
          <div className="card-heading"><div><span className="overline">Preview</span><h3>Limited row preview</h3></div></div>
          <State {...preview}>{preview.data && <DataTable rows={preview.data.rows} />}</State>
        </section>
      </div>
    </Shell>
  );
}

function AnalyticsPage({ datasetId, setDatasetId }: PageProps) {
  const operations = datasetId === DEFAULT_DATASET_ID ? placementOperations : genericOperations;
  return (
    <Shell active="/analytics" datasetId={datasetId} setDatasetId={setDatasetId}>
      <PageIntro kicker="Analytics" title="Dataset-scoped operations" description="Every request includes the selected dataset_id. The backend verifies ownership before executing." />
      <div className="analytics-stack">{operations.map(([operation, title]) => <AnalyticsBlock key={operation} operation={operation} title={title} datasetId={datasetId} />)}</div>
    </Shell>
  );
}

function AnalyticsBlock({ operation, title, datasetId }: { operation: AnalyticsOperation; title: string; datasetId: string }) {
  const column = operation === 'average' ? (datasetId === DEFAULT_DATASET_ID ? 'CGPA' : 'sales') : operation === 'value_counts' ? (datasetId === DEFAULT_DATASET_ID ? 'Placement' : 'region') : undefined;
  const state = useApi(() => getAnalytics(operation, datasetId, column), [operation, datasetId, column]);
  return <section className="panel analytics-block"><div className="card-heading"><div><span className="overline">{operation}</span><h2>{title}</h2></div></div><State {...state}>{state.data && <ResultTable result={state.data.result} />}</State></section>;
}

// ─── Chat Page (Phase 11) ──────────────────────────────────────────────────

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  const meta = msg.result_metadata;

  return (
    <div className={`chat-bubble-wrap ${isUser ? 'user' : 'assistant'}`}>
      <div className={`chat-bubble ${isUser ? 'user' : 'assistant'}`}>
        <p className="bubble-text">{msg.content}</p>
        {!isUser && meta && (
          <div className="bubble-meta">
            {meta.chart?.file_url && (
              <img className="bubble-chart" src={assetUrl(meta.chart.file_url)} alt={meta.chart.title ?? 'chart'} />
            )}
            {meta.metrics && Object.keys(meta.metrics).length > 0 && (
              <div className="bubble-metrics">
                {Object.entries(meta.metrics).map(([k, v]) => (
                  <div key={k} className="bubble-metric-item">
                    <span className="bubble-metric-label">{k.replace(/_/g, ' ')}</span>
                    <span className="bubble-metric-value">{typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v ?? '—')}</span>
                  </div>
                ))}
              </div>
            )}
            {Array.isArray(meta.insights) && meta.insights.length > 0 && (
              <details className="bubble-details">
                <summary>Insights ({meta.insights.length})</summary>
                <ul>{meta.insights.map((ins, i) => <li key={i}>{ins}</li>)}</ul>
              </details>
            )}
            {Array.isArray(meta.recommendations) && meta.recommendations.length > 0 && (
              <details className="bubble-details">
                <summary>Recommendations</summary>
                <ul>{meta.recommendations.map((r, i) => <li key={i}>{r}</li>)}</ul>
              </details>
            )}
            {meta.analysis && (
              <details className="bubble-details">
                <summary>Technical analysis</summary>
                <p className="bubble-analysis">{meta.analysis}</p>
              </details>
            )}
          </div>
        )}
      </div>
      <span className="bubble-time">{new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
    </div>
  );
}

function AskPage({ datasetId, setDatasetId }: PageProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConv, setActiveConv] = useState<ConversationDetail | null>(null);
  const [question, setQuestion] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingConvs, setLoadingConvs] = useState(true);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [sendError, setSendError] = useState('');
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameVal, setRenameVal] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(async () => {
    setLoadingConvs(true);
    try {
      const list = await listConversations();
      setConversations(list);
      // Auto-open conversation navigated from Query History page
      const pendingId = sessionStorage.getItem('askmydata.openConvId');
      if (pendingId) {
        sessionStorage.removeItem('askmydata.openConvId');
        const detail = await getConversation(pendingId).catch(() => null);
        if (detail) setActiveConv(detail);
      }
    } catch { /* ignore */ } finally {
      setLoadingConvs(false);
    }
  }, []);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConv?.messages]);

  const openConversation = async (id: string) => {
    setLoadingMsgs(true);
    setSendError('');
    try {
      const detail = await getConversation(id);
      setActiveConv(detail);
    } catch { setSendError('Could not load conversation.'); } finally {
      setLoadingMsgs(false);
    }
  };

  const handleNew = async () => {
    try {
      const conv = await createConversation(datasetId);
      setConversations(prev => [conv, ...prev]);
      setActiveConv({ ...conv, messages: [] });
      setSendError('');
    } catch { setSendError('Could not create conversation.'); }
  };

  const handleSend = async () => {
    const trimmed = question.trim();
    if (!trimmed || !activeConv || sending) return;
    setSending(true);
    setSendError('');
    setQuestion('');
    // Optimistic user bubble
    const tempUserMsg: ChatMessage = {
      id: `tmp-${Date.now()}`,
      conversation_id: activeConv.id,
      role: 'user',
      message_type: 'question',
      content: trimmed,
      dataset_id: datasetId,
      created_at: new Date().toISOString(),
      result_metadata: null,
    };
    setActiveConv(prev => prev ? { ...prev, messages: [...prev.messages, tempUserMsg] } : prev);
    try {
      const reply = await sendMessage(activeConv.id, trimmed, datasetId);
      // Reload full conversation to get updated title + both messages
      const updated = await getConversation(activeConv.id);
      setActiveConv(updated);
      setConversations(prev =>
        prev.map(c => c.id === updated.id ? { ...c, title: updated.title, updated_at: updated.updated_at } : c)
          .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      );
      void reply; // used via full reload
    } catch (err) {
      setSendError(err instanceof Error ? err.message : 'Failed to get a response.');
      // Remove optimistic bubble
      setActiveConv(prev => prev ? { ...prev, messages: prev.messages.filter(m => m.id !== tempUserMsg.id) } : prev);
    } finally {
      setSending(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteConversation(id);
      setConversations(prev => prev.filter(c => c.id !== id));
      if (activeConv?.id === id) setActiveConv(null);
    } catch { setSendError('Could not delete conversation.'); }
  };

  const startRename = (conv: ConversationSummary) => {
    setRenamingId(conv.id);
    setRenameVal(conv.title);
  };

  const commitRename = async (id: string) => {
    const title = renameVal.trim();
    setRenamingId(null);
    if (!title) return;
    try {
      const updated = await renameConversation(id, title);
      setConversations(prev => prev.map(c => c.id === id ? { ...c, title: updated.title } : c));
      if (activeConv?.id === id) setActiveConv(prev => prev ? { ...prev, title: updated.title } : prev);
    } catch { /* silent */ }
  };

  const examples = datasetId === DEFAULT_DATASET_ID
    ? ['What is the placement rate for students with internships?', 'What is the average CGPA of placed students?', 'Show me placement breakdown by communication score.']
    : ['What is the average value in this dataset?', 'How many rows are there?', 'What are the distinct values?'];

  return (
    <Shell active="/ask" datasetId={datasetId} setDatasetId={setDatasetId}>
      <div className="chat-shell">
        {/* Conversation Sidebar */}
        <aside className="conv-sidebar">
          <div className="conv-sidebar-header">
            <span className="conv-sidebar-title">Conversations</span>
            <button id="new-conversation-btn" className="conv-new-btn" onClick={handleNew} title="New conversation">
              <Plus size={14} /> New
            </button>
          </div>
          {loadingConvs ? (
            <div className="conv-loading"><span className="spinner" /></div>
          ) : conversations.length === 0 ? (
            <div className="conv-empty">No conversations yet.<br />Click &ldquo;New&rdquo; to start.</div>
          ) : (
            <ul className="conv-list">
              {conversations.map(conv => (
                <li
                  key={conv.id}
                  className={`conv-item ${activeConv?.id === conv.id ? 'active' : ''}`}
                  onClick={() => openConversation(conv.id)}
                >
                  {renamingId === conv.id ? (
                    <input
                      className="conv-rename-input"
                      value={renameVal}
                      onChange={e => setRenameVal(e.target.value)}
                      onBlur={() => commitRename(conv.id)}
                      onKeyDown={e => { if (e.key === 'Enter') commitRename(conv.id); if (e.key === 'Escape') setRenamingId(null); }}
                      autoFocus
                      onClick={e => e.stopPropagation()}
                    />
                  ) : (
                    <span className="conv-item-title" onDoubleClick={e => { e.stopPropagation(); startRename(conv); }}>
                      {conv.title}
                    </span>
                  )}
                  <button
                    className="conv-delete-btn"
                    title="Delete"
                    onClick={e => { e.stopPropagation(); handleDelete(conv.id); }}
                  >
                    <Trash2 size={11} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* Chat Area */}
        <div className="chat-area">
          {!activeConv ? (
            <div className="chat-welcome">
              <MessageSquareText size={40} className="chat-welcome-icon" />
              <h2>Start a conversation</h2>
              <p>Select a conversation from the sidebar or create a new one to begin asking questions about your dataset.</p>
              <button id="chat-new-btn" className="button primary" onClick={handleNew}>
                <Plus size={15} /> New conversation
              </button>
            </div>
          ) : (
            <>
              <div className="chat-thread-header">
                <h3 className="chat-thread-title">{activeConv.title}</h3>
                {activeConv.dataset_id && (
                  <span className="demo-badge">dataset: {activeConv.dataset_id.slice(0, 8)}…</span>
                )}
              </div>
              <div className="chat-thread">
                {loadingMsgs ? (
                  <div className="chat-loading"><span className="spinner" /> Loading messages…</div>
                ) : activeConv.messages.length === 0 ? (
                  <div className="chat-thread-empty">
                    <p>Ask a question below to get started.</p>
                    <div className="examples">
                      {examples.map(ex => (
                        <button key={ex} className="example" onClick={() => setQuestion(ex)}>{ex}</button>
                      ))}
                    </div>
                  </div>
                ) : (
                  activeConv.messages.map(msg => <ChatBubble key={msg.id} msg={msg} />)
                )}
                {sending && (
                  <div className="chat-bubble-wrap assistant">
                    <div className="chat-bubble assistant typing">
                      <span className="dot" /><span className="dot" /><span className="dot" />
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
              {sendError && <div className="chat-send-error">{sendError}</div>}
              <div className="chat-composer">
                <input
                  id="chat-input"
                  className="chat-input"
                  value={question}
                  onChange={e => setQuestion(e.target.value)}
                  placeholder="Ask about your dataset…"
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  disabled={sending}
                />
                <button
                  id="chat-send-btn"
                  className="button primary chat-send-btn"
                  onClick={handleSend}
                  disabled={!question.trim() || sending}
                >
                  {sending ? <span className="spinner" /> : <Send size={15} />}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </Shell>
  );
}

// ─── Admin Page ────────────────────────────────────────────────────────────────
function BillingPage(props: PageProps) {
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadPlans = async () => {
      try {
        const data = await getBillingPlans();
        setPlans(data);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : 'Unable to load billing plans.');
      } finally {
        setLoading(false);
      }
    };
    void loadPlans();
  }, []);

  return (
    <Shell {...props} active="/billing">
      <PageIntro kicker="Billing & Usage" title="Simple, usage-aware plans" description="The platform exposes mock billing metadata in development mode so plan limits and entitlements are visible without compromising the existing architecture." />
      {error && <div className="inline-error">{error}</div>}
      {loading ? (
        <div className="state loading"><span className="spinner" />Loading billing plans…</div>
      ) : (
        <div className="metric-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          {plans.map(plan => (
            <article key={plan.plan_id} className="metric-card" style={{ minHeight: '260px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <span className="kicker">{plan.name}</span>
                <h3 style={{ marginTop: '0.5rem', marginBottom: '0.5rem' }}>${plan.price.toFixed(2)} <small style={{ fontSize: '0.72rem' }}>/{plan.billing_interval}</small></h3>
                <p style={{ margin: '0 0 0.6rem', color: '#c7d2fe' }}>{plan.description ?? 'Included with your workspace.'}</p>
              </div>
              <div style={{ display: 'grid', gap: '0.4rem' }}>
                <small>AI requests: {plan.max_ai_requests ?? '—'}</small>
                <small>Analytics queries: {plan.max_analytics_queries ?? '—'}</small>
                <small>Reports: {plan.max_reports ?? '—'}</small>
                <small>Exports: {plan.max_exports ?? '—'}</small>
                <small>Conversations: {plan.max_conversations ?? '—'}</small>
              </div>
            </article>
          ))}
        </div>
      )}
    </Shell>
  );
}

function AutomationsPage(props: PageProps) {
  const [workspaces, setWorkspaces] = useState<Array<{ id: string; name: string }>>([]);
  const [workspaceId, setWorkspaceId] = useState(() => localStorage.getItem('askmydata.automationWorkspace') ?? '');
  const [queries, setQueries] = useState<SavedAnalyticsQuery[]>([]);
  const [automations, setAutomations] = useState<AnalyticsAutomation[]>([]);
  const [alerts, setAlerts] = useState<AnalyticsAlert[]>([]);
  const [runs, setRuns] = useState<Record<string, AutomationRun[]>>({});
  const [historyId, setHistoryId] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [queryTitle, setQueryTitle] = useState('');
  const [question, setQuestion] = useState('');
  const [operation, setOperation] = useState('count');
  const [column, setColumn] = useState('');
  const [scheduleName, setScheduleName] = useState('');
  const [queryId, setQueryId] = useState('');
  const [editingId, setEditingId] = useState('');
  const [frequency, setFrequency] = useState<'daily' | 'weekly' | 'monthly'>('weekly');
  const [runTime, setRunTime] = useState('09:00');
  const [timezoneName, setTimezoneName] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const [aiSummary, setAiSummary] = useState(false);
  const [alertName, setAlertName] = useState('');
  const [alertMetric, setAlertMetric] = useState('row_count');
  const [alertColumn, setAlertColumn] = useState('');
  const [alertThreshold, setAlertThreshold] = useState('100');

  const refresh = async (selectedWorkspace = workspaceId) => {
    if (!selectedWorkspace) return;
    const [queryItems, automationItems, alertItems] = await Promise.all([
      listSavedQueries(selectedWorkspace),
      listAutomations(selectedWorkspace),
      listAlerts(selectedWorkspace, props.datasetId),
    ]);
    setQueries(queryItems);
    setAutomations(automationItems);
    setAlerts(alertItems);
  };

  useEffect(() => {
    let cancelled = false;
    apiFetch<Array<{ id: string; name: string }>>('/api/v1/workspaces')
      .then(items => {
        if (cancelled) return;
        setWorkspaces(items);
        const preferred = items.some(item => item.id === workspaceId) ? workspaceId : items[0]?.id ?? '';
        setWorkspaceId(preferred);
        if (preferred) localStorage.setItem('askmydata.automationWorkspace', preferred);
      })
      .catch(reason => setError(reason instanceof Error ? reason.message : 'Could not load workspaces.'))
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!workspaceId) return;
    setLoading(true);
    refresh(workspaceId)
      .catch(reason => setError(reason instanceof Error ? reason.message : 'Could not load automations.'))
      .finally(() => setLoading(false));
    const timer = window.setInterval(() => {
      void refresh(workspaceId).catch(() => {});
    }, 20000);
    return () => window.clearInterval(timer);
  }, [workspaceId, props.datasetId]);

  const act = async (task: () => Promise<unknown>, success: string) => {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await task();
      await refresh();
      setMessage(success);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The automation action failed.');
    } finally {
      setBusy(false);
    }
  };

  const saveQuery = async (event: React.FormEvent) => {
    event.preventDefault();
    const config = { operation, ...(column.trim() ? { column: column.trim() } : {}) };
    await act(async () => {
      const saved = await createSavedQuery({ workspace_id: workspaceId, dataset_id: props.datasetId, title: queryTitle, question, config });
      setQueryId(saved.id);
      setQueryTitle('');
      setQuestion('');
    }, 'Saved analytics query.');
  };

  const saveAutomation = async (event: React.FormEvent) => {
    event.preventDefault();
    await act(async () => {
      const values = {
        saved_query_id: queryId, name: scheduleName, frequency,
        run_time: runTime, timezone: timezoneName, weekday: 0,
        day_of_month: 1, ai_summary: aiSummary,
      };
      if (editingId) await updateAutomation(editingId, workspaceId, values);
      else await createAutomation({ workspace_id: workspaceId, ...values });
      setScheduleName('');
      setEditingId('');
    }, 'Automation scheduled.');
  };

  const beginEdit = (automation: AnalyticsAutomation) => {
    setEditingId(automation.id);
    setScheduleName(automation.name);
    setQueryId(automation.saved_query_id);
    setFrequency(automation.frequency);
    setRunTime(automation.run_time);
    setTimezoneName(automation.timezone);
    setAiSummary(automation.ai_summary);
    document.getElementById('automation-schedule-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  const saveAlert = async (event: React.FormEvent) => {
    event.preventDefault();
    await act(async () => {
      await createAlert({
        workspace_id: workspaceId, dataset_id: props.datasetId, name: alertName,
        alert_type: alertMetric === 'outlier_rate' ? 'anomaly' : 'threshold',
        metric: alertMetric === 'outlier_rate' ? `outlier_rate:${alertColumn.trim()}` : alertMetric,
        operator: '>', threshold: Number(alertThreshold), cooldown_seconds: 3600,
      });
      setAlertName('');
      setAlertColumn('');
    }, 'Alert created.');
  };

  const toggleHistory = async (automationId: string) => {
    if (historyId === automationId) { setHistoryId(''); return; }
    setHistoryId(automationId);
    try {
      const items = await listAutomationRuns(automationId, workspaceId);
      setRuns(previous => ({ ...previous, [automationId]: items }));
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load run history.'); }
  };

  return (
    <Shell {...props} active="/automations">
      <PageIntro kicker="Scheduled analytics" title="Automations" description="Save safe analytics configurations, run them on a schedule, and review data-grounded reports and alerts." />
      <div className="automation-toolbar">
        <label className="automation-field"><span>Workspace</span><select value={workspaceId} onChange={event => { setWorkspaceId(event.target.value); localStorage.setItem('askmydata.automationWorkspace', event.target.value); }}>
          {workspaces.map(workspace => <option value={workspace.id} key={workspace.id}>{workspace.name}</option>)}
        </select></label>
        <span className="automation-context">Dataset: {props.datasetId} · Results delivered in-app</span>
      </div>
      <div className="automation-content">
        {error && <div className="inline-error" role="alert">{error}</div>}
        {message && <div className="automation-success" role="status">{message}</div>}
        {loading ? <div className="state loading"><span className="spinner" />Loading automations…</div> : !workspaceId ? (
          <div className="empty">Create or join a workspace before setting up automations.</div>
        ) : (
          <>
            <div className="automation-setup-grid">
              <form className="automation-panel" onSubmit={saveQuery}>
                <div className="automation-panel-heading"><span className="kicker">01 · Saved query</span><h2>Define deterministic analytics</h2></div>
                <label className="automation-field"><span>Query name</span><input value={queryTitle} onChange={event => setQueryTitle(event.target.value)} required maxLength={255} /></label>
                <label className="automation-field"><span>Question</span><input value={question} onChange={event => setQuestion(event.target.value)} required maxLength={1000} placeholder="Describe the result this workflow tracks" /></label>
                <div className="automation-form-row">
                  <label className="automation-field"><span>Operation</span><select value={operation} onChange={event => setOperation(event.target.value)}>
                    <option value="count">Row count</option><option value="overview">Dataset overview</option><option value="average">Average</option><option value="minimum">Minimum</option><option value="maximum">Maximum</option><option value="sum">Sum</option><option value="value_counts">Value counts</option>
                  </select></label>
                  {['average', 'minimum', 'maximum', 'sum', 'value_counts'].includes(operation) && <label className="automation-field"><span>Column</span><input value={column} onChange={event => setColumn(event.target.value)} required /></label>}
                </div>
                <button className="button primary" disabled={busy || !workspaceId}><Plus size={15} /> Save query</button>
              </form>

              <form id="automation-schedule-form" className="automation-panel" onSubmit={saveAutomation}>
                <div className="automation-panel-heading"><span className="kicker">02 · Schedule</span><h2>{editingId ? 'Edit automation' : 'Choose when it runs'}</h2></div>
                <label className="automation-field"><span>Automation name</span><input value={scheduleName} onChange={event => setScheduleName(event.target.value)} required maxLength={255} /></label>
                <label className="automation-field"><span>Saved query</span><select value={queryId} onChange={event => setQueryId(event.target.value)} required>
                  <option value="">Select a saved query</option>{queries.map(query => <option value={query.id} key={query.id}>{query.title}</option>)}
                </select></label>
                <div className="automation-form-row">
                  <label className="automation-field"><span>Frequency</span><select value={frequency} onChange={event => setFrequency(event.target.value as typeof frequency)}><option value="daily">Daily</option><option value="weekly">Weekly · Monday</option><option value="monthly">Monthly · day 1</option></select></label>
                  <label className="automation-field"><span>Local time</span><input type="time" value={runTime} onChange={event => setRunTime(event.target.value)} required /></label>
                </div>
                <label className="automation-check"><input type="checkbox" checked={aiSummary} onChange={event => setAiSummary(event.target.checked)} /><span>Include a Gemini summary of calculated results</span></label>
                <small className="automation-hint">Timezone: {timezoneName}. Gemini is optional and billed against workspace usage.</small>
                <div className="automation-actions"><button className="button primary" disabled={busy || !queryId}><CalendarClock size={15} /> {editingId ? 'Save changes' : 'Create schedule'}</button>{editingId && <button type="button" className="button subtle" onClick={() => { setEditingId(''); setScheduleName(''); }}>Cancel edit</button>}</div>
              </form>

              <form className="automation-panel" onSubmit={saveAlert}>
                <div className="automation-panel-heading"><span className="kicker">03 · Data monitoring</span><h2>Set a threshold alert</h2></div>
                <label className="automation-field"><span>Alert name</span><input value={alertName} onChange={event => setAlertName(event.target.value)} required maxLength={255} /></label>
                <div className="automation-form-row">
                  <label className="automation-field"><span>Metric</span><select value={alertMetric} onChange={event => setAlertMetric(event.target.value)}><option value="row_count">Row count</option><option value="missing_percent">Missing values (%)</option><option value="duplicate_rows">Duplicate rows</option><option value="outlier_rate">IQR outlier rate</option></select></label>
                  <label className="automation-field"><span>Triggers above</span><input type="number" value={alertThreshold} onChange={event => setAlertThreshold(event.target.value)} required /></label>
                </div>
                {alertMetric === 'outlier_rate' && <label className="automation-field"><span>Numeric column</span><input value={alertColumn} onChange={event => setAlertColumn(event.target.value)} required /></label>}
                <small className="automation-hint">Checked when a scheduled run creates a new dataset snapshot. Cooldown: one hour.</small>
                <button className="button primary" disabled={busy || !workspaceId}><Plus size={15} /> Create alert</button>
              </form>
            </div>

            <section className="automation-section">
              <div className="automation-section-heading"><div><span className="kicker">Workspace workflows</span><h2>Scheduled analytics</h2></div><button className="button subtle" onClick={() => void refresh()} disabled={busy}><RefreshCw size={15} /> Refresh</button></div>
              {automations.length === 0 ? <div className="empty">No schedules in this workspace yet.</div> : automations.map(automation => (
                <article className="automation-row" key={automation.id}>
                  <div className="automation-row-main"><strong>{automation.name}</strong><span>{queries.find(query => query.id === automation.saved_query_id)?.title ?? 'Saved query'} · {automation.frequency} at {automation.run_time} ({automation.timezone})</span><small>Next {new Date(automation.next_run_at).toLocaleString()} · Last status: {automation.last_status ?? 'not run'}</small></div>
                  <div className="automation-actions">
                    <button className="button subtle" disabled={busy} onClick={() => void act(() => runAutomation(automation.id, workspaceId), 'Run queued for the background worker.')}><RefreshCw size={14} /> Run now</button>
                    <button className="button subtle" disabled={busy} onClick={() => void act(() => updateAutomation(automation.id, workspaceId, { active: !automation.active }), automation.active ? 'Schedule paused.' : 'Schedule resumed.')}>{automation.active ? 'Pause' : 'Resume'}</button>
                    <button className="button subtle" disabled={busy} onClick={() => beginEdit(automation)}>Edit</button>
                    <button className="button subtle" disabled={busy} onClick={() => void toggleHistory(automation.id)}>History</button>
                    <button className="button subtle danger" disabled={busy} onClick={() => void act(() => deleteAutomation(automation.id, workspaceId), 'Automation deleted.')}><Trash2 size={14} /> Delete</button>
                  </div>
                  {historyId === automation.id && <div className="automation-history">{(runs[automation.id] ?? []).length === 0 ? <small>No runs recorded.</small> : (runs[automation.id] ?? []).map(run => <div className="automation-run" key={run.id}><span><strong>{run.status}</strong> · {new Date(run.created_at).toLocaleString()}</span>{run.error_code && <code>{run.error_code}</code>}{run.result && <span>Rows: {run.result.profile?.rows ?? '—'} · Metrics: {JSON.stringify(run.result.metrics)}</span>}{run.result?.ai_summary && <p>{run.result.ai_summary}</p>}{run.status === 'completed' && <button className="button subtle" onClick={() => void act(() => downloadRunReport(automation.id, workspaceId, run.id), 'CSV report downloaded.')}>Download CSV</button>}</div>)}</div>}
                </article>
              ))}
            </section>

            <section className="automation-section">
              <div className="automation-section-heading"><div><span className="kicker">Data monitoring</span><h2>Alerts</h2></div></div>
              {alerts.length === 0 ? <div className="empty">No alerts for this dataset.</div> : alerts.map(alert => <article className="automation-row" key={alert.id}>
                <div className="automation-row-main"><strong>{alert.name}</strong><span>{alert.metric} {alert.operator} {alert.threshold} · {alert.active ? 'Active' : 'Paused'}</span><small>Cooldown: {Math.round(alert.cooldown_seconds / 60)} minutes</small></div>
                <div className="automation-actions"><button className="button subtle" onClick={() => void act(() => updateAlert(alert.id, workspaceId, !alert.active), alert.active ? 'Alert paused.' : 'Alert resumed.')}>{alert.active ? 'Pause' : 'Resume'}</button><button className="button subtle danger" onClick={() => void act(() => deleteAlert(alert.id, workspaceId), 'Alert deleted.')}><Trash2 size={14} /> Delete</button></div>
              </article>)}
            </section>
          </>
        )}
      </div>
    </Shell>
  );
}

function AdminPage(props: PageProps) {
  const { token } = useAuth();
  return (
    <Shell {...props} active="/admin">
      <AdminDashboard token={token ?? ''} onBack={() => { window.location.href = '/'; }} />
    </Shell>
  );
}

function DeveloperPage(props: PageProps) {
  const [workspaces, setWorkspaces] = useState<Array<{ id: string; name: string }>>([]);
  const [workspaceId, setWorkspaceId] = useState(() => localStorage.getItem('askmydata.automationWorkspace') ?? '');
  const [loadingWs, setLoadingWs] = useState(true);

  useEffect(() => {
    apiFetch<{ workspaces: Array<{ id: string; name: string }> }>('/api/v1/workspaces')
      .then(data => {
        setWorkspaces(data.workspaces ?? []);
        if (!workspaceId && (data.workspaces ?? []).length > 0) {
          setWorkspaceId(data.workspaces[0].id);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingWs(false));
  }, [workspaceId]);

  const handleWorkspaceChange = (id: string) => {
    setWorkspaceId(id);
    localStorage.setItem('askmydata.automationWorkspace', id);
  };

  return (
    <Shell {...props} active="/developer">
      <div style={{ padding: '32px 52px 0', maxWidth: 960, margin: '0 auto' }}>
        {loadingWs ? null : workspaces.length > 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
            <label style={{ fontSize: 11, fontWeight: 700, fontFamily: "'DM Mono',monospace", textTransform: 'uppercase', letterSpacing: '.06em', color: '#6f7d86' }}>Workspace</label>
            <select
              value={workspaceId}
              onChange={e => handleWorkspaceChange(e.target.value)}
              style={{ border: '1.5px solid #d9ddd9', borderRadius: 7, padding: '6px 10px', fontSize: 13, fontFamily: 'inherit', background: '#fff', color: '#102a43', outline: 'none' }}
            >
              {workspaces.map(ws => <option key={ws.id} value={ws.id}>{ws.name}</option>)}
            </select>
          </div>
        ) : null}
      </div>
      {workspaceId ? (
        <DeveloperDashboard workspaceId={workspaceId} />
      ) : (
        <div style={{ maxWidth: 600, margin: '60px auto', padding: '0 24px', textAlign: 'center' }}>
          <h2 style={{ fontSize: 24, fontWeight: 800, marginBottom: 12 }}>No workspace selected</h2>
          <p style={{ color: '#6f7d86', fontSize: 14 }}>
            Please join or create a workspace first. The Developer API is scoped to a workspace.
          </p>
        </div>
      )}
    </Shell>
  );
}


// ─── Query History Page (Phase 23) ───────────────────────────────────────────
function HistoryPage(props: PageProps) {
  const openInChat = (id: string) => {
    // Navigate to /ask and we store the convId to auto-open
    sessionStorage.setItem('askmydata.openConvId', id);
    window.location.href = '/ask';
  };
  return (
    <Shell {...props} active="/history">
      <QueryHistory onOpen={openInChat} />
    </Shell>
  );
}

// ─── App Router ────────────────────────────────────────────────────────────────
function App() {
  const { datasetId, setDatasetId } = useSelectedDataset();
  const { isAuthenticated, isLoading } = useAuth();
  const path = window.location.pathname;
  const props = { datasetId, setDatasetId };

  // Public auth routes — accessible without login
  if (path === '/login') return <LoginPage />;
  if (path === '/register') return <RegisterPage />;

  // Show spinner while session is being restored on page load
  if (isLoading) return <div className="auth-loading"><span className="spinner" /></div>;

  // Redirect unauthenticated users away from protected routes
  if (!isAuthenticated && path !== '/') {
    window.location.replace('/login');
    return null;
  }

  // Protected routes — wrap in RequireAuth for extra safety
  if (path === '/dashboard') return <RequireAuth><DashboardPage {...props} /></RequireAuth>;
  if (path === '/dataset') return <RequireAuth><DatasetPage {...props} /></RequireAuth>;
  if (path === '/analytics') return <RequireAuth><AnalyticsPage {...props} /></RequireAuth>;
  if (path === '/ask') return <RequireAuth><AskPage {...props} /></RequireAuth>;
  if (path === '/history') return <RequireAuth><HistoryPage {...props} /></RequireAuth>;
  if (path === '/automations') return <RequireAuth><AutomationsPage {...props} /></RequireAuth>;
  if (path === '/billing') return <RequireAuth><BillingPage {...props} /></RequireAuth>;
  if (path === '/developer') return <RequireAuth><DeveloperPage {...props} /></RequireAuth>;
  if (path === '/admin') return <RequireAdmin><AdminPage {...props} /></RequireAdmin>;
  if (path === '/auth/google/callback') return <GoogleCallbackPage />;

  // Home page — accessible but redirects to login if not authenticated
  if (!isAuthenticated) return <LoginPage />;
  return <HomePage {...props} />;
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
        window.location.replace('/dashboard');
      })
      .catch(err => {
        setErrorMsg(err.message || 'Google login failed. Please try again.');
        setStatus('error');
      });
  }, [loginWithToken]);

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand"><span className="brand-mark">A</span><span className="auth-brand-name">AskMyData</span></div>
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
            <p className="auth-footer"><a href="/login">← Back to login</a></p>
          </>
        )}
      </div>
    </div>
  );
}

export default App;
