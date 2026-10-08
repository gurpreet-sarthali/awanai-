import React, { useEffect, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, CheckCircle, Database, RefreshCw, Shield, Users } from 'lucide-react';
import { getAdminAnalytics, triggerLogCleanup } from '../services/monitoringApi';
import { AdminDashboardData } from '../types/monitoring';
import { getAutomationAdminOverview, getAutomationAdminRuns, type AutomationAdminOverview, type AutomationAdminRun } from '../services/automationApi';

interface AdminDashboardProps {
  token: string;
  onBack: () => void;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ token, onBack: _onBack }) => {
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [days, setDays] = useState<number>(30);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'datasets' | 'ai' | 'errors' | 'feedback' | 'automations'>('overview');
  const [cleaning, setCleaning] = useState<boolean>(false);
  const [cleanupMessage, setCleanupMessage] = useState<string | null>(null);
  const [automationOverview, setAutomationOverview] = useState<AutomationAdminOverview | null>(null);
  const [automationRuns, setAutomationRuns] = useState<AutomationAdminRun[]>([]);
  const [automationStatus, setAutomationStatus] = useState('');
  const [automationWorkspace, setAutomationWorkspace] = useState('');

  const fetchDashboard = async () => {
    setLoading(true);
    setError(null);
    try {
      const [res, automationSummary, runs] = await Promise.all([
        getAdminAnalytics(token, days),
        getAutomationAdminOverview(),
        getAutomationAdminRuns({
          since: new Date(Date.now() - days * 86400000).toISOString(),
          status: automationStatus || undefined,
          workspace_id: automationWorkspace || undefined,
          limit: 100,
        }),
      ]);
      setData(res);
      setAutomationOverview(automationSummary);
      setAutomationRuns(runs);
    } catch (err: any) {
      setError(err?.message || 'Failed to load admin dashboard telemetry.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [days, token, automationStatus, automationWorkspace]);

  const handleCleanup = async () => {
    setCleaning(true);
    setCleanupMessage(null);
    try {
      const res = await triggerLogCleanup(token, 90, 30);
      setCleanupMessage(
        `Cleanup complete: deleted ${res.deleted?.usage_events || 0} usage events and ${res.deleted?.error_logs || 0} old error logs.`
      );
      fetchDashboard();
    } catch (err: any) {
      setCleanupMessage(`Cleanup failed: ${err?.message}`);
    } finally {
      setCleaning(false);
    }
  };

  const overview = data?.overview;
  const series = data?.time_series ?? [];
  const maxAnalyses = Math.max(1, ...series.map(p => p.analyses || 0));
  const maxUploads = Math.max(1, ...series.map(p => p.dataset_uploads || 0));
  const maxUsers = Math.max(1, ...series.map(p => p.active_users || 0));

  return (
    <div className="admin-dashboard-container">
      {/* ── Header ── */}
      <div className="admin-header">
        <div className="admin-title">
          <Shield className="admin-icon" size={28} />
          <div>
            <h2>Platform Admin &amp; Monitoring Dashboard</h2>
            <p>Real-time telemetry, user activity, AI usage metrics, and error oversight</p>
          </div>
        </div>
        <div className="admin-actions">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="days-select">
            <option value={1}>Today</option>
            <option value={7}>Last 7 Days</option>
            <option value={30}>Last 30 Days</option>
            <option value={90}>Last 90 Days</option>
          </select>
          <button className="btn-secondary flex-btn" onClick={fetchDashboard} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {error && <div className="admin-error-alert"><AlertTriangle size={18} /> {error}</div>}
      {cleanupMessage && <div className="admin-info-alert"><CheckCircle size={18} /> {cleanupMessage}</div>}

      {/* ── KPI Cards ── */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Active Users (DAU / WAU / MAU)</span>
            <Users className="metric-icon users-color" size={20} />
          </div>
          <div className="metric-value">{overview ? `${overview.dau} / ${overview.wau} / ${overview.mau}` : '...'}</div>
          <div className="metric-subtext">Total Users: {overview?.total_users || 0}</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Total Datasets</span>
            <Database className="metric-icon datasets-color" size={20} />
          </div>
          <div className="metric-value">{overview?.total_datasets ?? '...'}</div>
          <div className="metric-subtext">{overview?.uploaded_datasets_in_period || 0} uploaded in selected period</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Analyses Completed</span>
            <BarChart3 className="metric-icon analytics-color" size={20} />
          </div>
          <div className="metric-value">{overview?.total_analyses ?? '...'}</div>
          <div className="metric-subtext">{overview?.failed_analyses || 0} failed analyses</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">AI Helpfulness &amp; Latency</span>
            <Activity className="metric-icon ai-color" size={20} />
          </div>
          <div className="metric-value">{overview ? `${overview.ai_helpfulness_rate}%` : '...'}</div>
          <div className="metric-subtext">Avg Response: {overview?.avg_ai_response_time_ms || 0} ms</div>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className="admin-tabs">
        {(['overview', 'users', 'datasets', 'ai', 'errors', 'feedback', 'automations'] as const).map((tab) => {
          const labels: Record<string, string> = {
            overview: 'Overview',
            users: 'Users & Trends',
            datasets: 'Datasets',
            ai: 'AI Usage',
            errors: `Error Logs (${data?.errors.length || 0})`,
            feedback: `User Feedback (${data?.feedback.length || 0})`,
            automations: 'Automations',
          };
          return (
            <button
              key={tab}
              className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {labels[tab]}
            </button>
          );
        })}
      </div>

      {/* ── Tab Panels ── */}
      {loading ? (
        <div className="admin-loading">Loading telemetry data…</div>
      ) : (
        <div className="tab-content-container">

          {/* Overview */}
          {activeTab === 'overview' && (
            <div className="overview-panel">
              <div className="panel-card">
                <h3>Activity Trends — Analyses per Day</h3>
                {!series.length ? (
                  <p className="empty-text">No time-series data recorded in this period yet.</p>
                ) : (
                  <div className="simple-bar-chart">
                    {series.map((point) => (
                      <div key={point.date} className="chart-column">
                        <div className="bar-wrapper">
                          <div
                            className="bar-fill analyses-bar"
                            style={{ height: `${Math.max(4, (point.analyses / maxAnalyses) * 100)}px` }}
                            title={`Analyses: ${point.analyses}`}
                          />
                        </div>
                        <span className="bar-label">{point.date.slice(5)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="panel-card">
                <div className="panel-header-actions">
                  <h3>Log Retention &amp; System Maintenance</h3>
                  <button className="btn-danger-sm" onClick={handleCleanup} disabled={cleaning}>
                    {cleaning ? 'Cleaning…' : 'Run Retention Cleanup'}
                  </button>
                </div>
                <p className="info-subtext">
                  Automated policies clean usage events older than 90 days and error logs older than 30 days.
                </p>
                <div className="retention-stats">
                  <div className="retention-stat"><span>Total Errors Logged</span><strong>{overview?.total_errors || 0}</strong></div>
                  <div className="retention-stat"><span>Total AI Requests</span><strong>{overview?.total_ai_requests || 0}</strong></div>
                  <div className="retention-stat">
                    <span>Avg User Rating</span>
                    <strong>{overview?.avg_user_rating ? overview.avg_user_rating.toFixed(1) : '—'} ★</strong>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Users & Trends */}
          {activeTab === 'users' && (
            <div className="panel-card">
              <h3>User Activity Trends</h3>
              <div className="stats-row">
                <div className="stat-box"><span>DAU</span><strong>{overview?.dau ?? '—'}</strong></div>
                <div className="stat-box"><span>WAU</span><strong>{overview?.wau ?? '—'}</strong></div>
                <div className="stat-box"><span>MAU</span><strong>{overview?.mau ?? '—'}</strong></div>
                <div className="stat-box"><span>Total Users</span><strong>{overview?.total_users ?? '—'}</strong></div>
              </div>
              {!series.length ? (
                <p className="empty-text">No daily user activity data recorded in this period.</p>
              ) : (
                <>
                  <h4 className="chart-subtitle">Daily Active Users</h4>
                  <div className="simple-bar-chart">
                    {series.map((point) => (
                      <div key={point.date} className="chart-column">
                        <div className="bar-wrapper">
                          <div
                            className="bar-fill users-bar"
                            style={{ height: `${Math.max(4, (point.active_users / maxUsers) * 100)}px` }}
                            title={`Active Users: ${point.active_users}`}
                          />
                        </div>
                        <span className="bar-label">{point.date.slice(5)}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Datasets */}
          {activeTab === 'datasets' && (
            <div className="panel-card">
              <h3>Dataset Upload Activity</h3>
              <div className="stats-row">
                <div className="stat-box"><span>Total Datasets</span><strong>{overview?.total_datasets ?? '—'}</strong></div>
                <div className="stat-box"><span>Uploads in Period</span><strong>{overview?.uploaded_datasets_in_period ?? '—'}</strong></div>
                <div className="stat-box"><span>Analyses Run</span><strong>{overview?.total_analyses ?? '—'}</strong></div>
                <div className="stat-box"><span>Failed Analyses</span><strong className="stat-danger">{overview?.failed_analyses ?? '—'}</strong></div>
              </div>
              {!series.length ? (
                <p className="empty-text">No dataset upload data recorded in this period.</p>
              ) : (
                <>
                  <h4 className="chart-subtitle">Daily Dataset Uploads</h4>
                  <div className="simple-bar-chart">
                    {series.map((point) => (
                      <div key={point.date} className="chart-column">
                        <div className="bar-wrapper">
                          <div
                            className="bar-fill datasets-bar"
                            style={{ height: `${Math.max(4, (point.dataset_uploads / maxUploads) * 100)}px` }}
                            title={`Uploads: ${point.dataset_uploads}`}
                          />
                        </div>
                        <span className="bar-label">{point.date.slice(5)}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* AI Usage */}
          {activeTab === 'ai' && (
            <div className="panel-card">
              <h3>Gemini AI Usage &amp; Performance</h3>
              <div className="stats-row">
                <div className="stat-box"><span>Total AI Requests</span><strong>{overview?.total_ai_requests ?? '—'}</strong></div>
                <div className="stat-box"><span>Successful</span><strong>{overview?.successful_ai_requests ?? '—'}</strong></div>
                <div className="stat-box"><span>Avg Latency</span><strong>{overview?.avg_ai_response_time_ms ?? '—'} ms</strong></div>
                <div className="stat-box"><span>Helpfulness Rate</span><strong>{overview?.ai_helpfulness_rate ?? '—'}%</strong></div>
              </div>
              {!data?.ai_feedback?.length ? (
                <p className="empty-text">No AI message feedback collected yet.</p>
              ) : (
                <>
                  <h4 className="chart-subtitle">Recent AI Message Ratings</h4>
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>User</th>
                        <th>Rating</th>
                        <th>Reason</th>
                        <th>Comment</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.ai_feedback.slice(0, 50).map((fb) => (
                        <tr key={fb.id}>
                          <td className="timestamp-cell">{new Date(fb.created_at).toLocaleString()}</td>
                          <td>{fb.user_email}</td>
                          <td>
                            <span className={`category-badge ${fb.rating === 'helpful' ? 'badge-helpful' : 'badge-not-helpful'}`}>
                              {fb.rating === 'helpful' ? '👍 Helpful' : '👎 Not Helpful'}
                            </span>
                          </td>
                          <td>{fb.reason || '—'}</td>
                          <td>{fb.comment || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          )}

          {/* Error Logs */}
          {activeTab === 'errors' && (
            <div className="errors-panel">
              <h3>Recent System Error Logs</h3>
              {!data?.errors.length ? (
                <p className="empty-text">No production errors recorded. All systems operational!</p>
              ) : (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Category</th>
                      <th>Endpoint</th>
                      <th>HTTP Status</th>
                      <th>Error Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.errors.map((err) => (
                      <tr key={err.id}>
                        <td className="timestamp-cell">{new Date(err.created_at).toLocaleString()}</td>
                        <td><span className={`category-badge badge-${err.error_category}`}>{err.error_category}</span></td>
                        <td className="code-cell">{err.endpoint}</td>
                        <td className={`status-cell status-${err.http_status}`}>{err.http_status}</td>
                        <td className="message-cell">{err.error_message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* User Feedback */}
          {activeTab === 'feedback' && (
            <div className="feedback-panel">
              <h3>User Feedback &amp; Ratings</h3>
              {!data?.feedback.length ? (
                <p className="empty-text">No user feedback submissions yet.</p>
              ) : (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>User</th>
                      <th>Type</th>
                      <th>Rating</th>
                      <th>Comment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.feedback.map((fb) => (
                      <tr key={fb.id}>
                        <td className="timestamp-cell">{new Date(fb.created_at).toLocaleString()}</td>
                        <td>{fb.user_email}</td>
                        <td><span className="type-badge">{fb.feedback_type}</span></td>
                        <td className="star-rating">{'★'.repeat(fb.rating)}</td>
                        <td>{fb.comment || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {activeTab === 'automations' && (
            <div className="panel-card">
              <h3>Scheduled Analytics &amp; Job Health</h3>
              <div className="stats-row">
                <div className="stat-box"><span>Active Automations</span><strong>{automationOverview?.active_automations ?? '—'}</strong></div>
                <div className="stat-box"><span>Successful Runs</span><strong>{automationOverview?.successful_runs ?? '—'}</strong></div>
                <div className="stat-box"><span>Failed Runs</span><strong>{automationOverview?.failed_runs ?? '—'}</strong></div>
                <div className="stat-box"><span>Average Run Latency</span><strong>{Math.round(automationOverview?.average_execution_time_ms ?? 0)} ms</strong></div>
              </div>
              <div className="admin-automation-filters">
                <label>Workspace ID<input value={automationWorkspace} onChange={event => setAutomationWorkspace(event.target.value)} placeholder="All workspaces" /></label>
                <label>Status<select value={automationStatus} onChange={event => setAutomationStatus(event.target.value)}><option value="">All statuses</option><option value="pending">Pending</option><option value="running">Running</option><option value="completed">Completed</option><option value="failed">Failed</option><option value="canceled">Canceled</option></select></label>
                <span>Scheduled analytics · {days}-day run filter</span>
              </div>
              {!automationRuns.length ? <p className="empty-text">No matching automation runs.</p> : (
                <table className="admin-table">
                  <thead><tr><th>Created</th><th>Automation</th><th>Workspace</th><th>Status</th><th>Attempt</th><th>Duration</th><th>Error</th></tr></thead>
                  <tbody>{automationRuns.map(run => <tr key={run.id}>
                    <td className="timestamp-cell">{new Date(run.created_at).toLocaleString()}</td>
                    <td>{run.automation_name}</td><td className="code-cell">{run.workspace_id}</td>
                    <td>{run.status}</td><td>{run.attempt}</td><td>{run.execution_time_ms ?? '—'} ms</td><td className="code-cell">{run.error_code ?? '—'}</td>
                  </tr>)}</tbody>
                </table>
              )}
            </div>
          )}

        </div>
      )}
    </div>
  );
};
